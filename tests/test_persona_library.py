"""Specialist personas from agency-agents (quick note #1570).

Every auto-provisioned company specialist was registered in AgentStore with an
empty system_prompt, so it worked tasks with no role method at all. These tests
pin the vendored persona catalogue, the distillation, and the wiring into
services/company_agency.activate_company.
"""
from __future__ import annotations

from typing import get_args

import pytest

from agents import persona_library as pl
from models.company_graph import Company, Specialist, SpecialistFamily


class TestCatalogue:
    def test_every_mapped_family_is_a_real_family(self) -> None:
        assert set(pl.FAMILY_PERSONAS) <= set(get_args(SpecialistFamily))

    @pytest.mark.parametrize("family,stem", sorted(pl.FAMILY_PERSONAS.items()))
    def test_every_persona_file_is_vendored_and_non_trivial(self, family, stem) -> None:
        assert (pl.PERSONA_DIR / f"{stem}.md").is_file()
        assert len(pl.persona_for_family(family)) > 800, family

    def test_the_mit_license_travels_with_the_files(self) -> None:
        text = (pl.PERSONA_DIR / "LICENSE").read_text(encoding="utf-8")
        assert text.startswith("MIT License")
        assert (pl.PERSONA_DIR / "README.md").is_file()

    def test_unmatched_families_get_no_persona_rather_than_a_wrong_one(self) -> None:
        for family in ("merchandising", "pim", "oms", "dam", "trading", "ecommerce"):
            assert pl.persona_for_family(family) == ""
        assert pl.persona_for_family("not-a-family") == ""


class TestDistill:
    SOURCE = (
        "---\nname: X\n---\n\n# X Agent\n\nIntro line.\n\n"
        "## 🧠 Your Identity & Memory\n- Role: tester\n\n"
        "## 📋 Your Technical Deliverables\n```python\nprint('long example')\n```\n\n"
        "## 🚨 Critical Rules You Must Follow\n- Never skip tests\n\n"
        "## 💭 Your Communication Style\n- chatty\n\n"
        "## 🔄 Your Workflow Process\n1. read\n```bash\nrm -rf /\n```\n2. test\n"
    )

    def test_keeps_role_defining_sections_only(self) -> None:
        out = pl.distill(self.SOURCE)
        assert out.startswith("# X Agent")
        assert "Never skip tests" in out and "1. read" in out and "Role: tester" in out
        assert "Communication Style" not in out
        assert "Technical Deliverables" not in out

    def test_drops_frontmatter_and_code(self) -> None:
        out = pl.distill(self.SOURCE)
        assert "name: X" not in out
        assert "```" not in out and "rm -rf" not in out

    def test_cap_falls_on_a_section_boundary(self) -> None:
        out = pl.distill(self.SOURCE, max_chars=len("# X Agent\n\nIntro line.") + 60)
        assert out.endswith(("tester", "Intro line."))

    def test_every_real_persona_respects_the_cap(self) -> None:
        for stem in set(pl.FAMILY_PERSONAS.values()):
            text = (pl.PERSONA_DIR / f"{stem}.md").read_text(encoding="utf-8")
            assert len(pl.distill(text)) <= pl.MAX_PERSONA_CHARS, stem

    def test_the_agencys_rules_take_precedence(self) -> None:
        prompt = pl.persona_for_family("security", "Acme")
        assert "You work for Acme" in prompt
        assert "take precedence over it" in prompt
        assert pl.SOURCE_REPO in prompt


class _FakeAgentStore:
    def __init__(self) -> None:
        self.agents: dict[str, object] = {}

    async def get(self, agent_id, owner_id=None):
        return self.agents.get(agent_id)

    async def create(self, agent):
        self.agents[agent.agent_id] = agent

    async def update(self, agent):
        self.agents[agent.agent_id] = agent


@pytest.fixture()
def activation(monkeypatch):
    company = Company(id="co_p", name="Persona Co", domain="p.test",
                      owner_id="t", onboarding_status="complete")
    specialists = [
        Specialist(id="s_sec", name="Sec", family="security", company_id="co_p", is_provisioned=True),
        Specialist(id="s_pim", name="Pim", family="pim", company_id="co_p", is_provisioned=True),
    ]

    class _Store:
        async def get_company(self, cid):
            return company

        async def list_specialists(self, cid):
            return specialists

        async def update_specialist(self, s):
            return s

    import agents.store as store_mod
    import services.company_graph_store as cgs_mod
    from services.company_agency import CompanyAgencyService

    agent_store = _FakeAgentStore()
    monkeypatch.setattr(cgs_mod, "get_company_graph_store", lambda: _Store())
    monkeypatch.setattr(store_mod, "get_agent_store", lambda: agent_store)
    return CompanyAgencyService(), agent_store


@pytest.mark.asyncio
async def test_activation_gives_each_specialist_its_persona(activation) -> None:
    svc, agent_store = activation
    await svc.activate_company(company_id="co_p", start_runtimes=False, create_schedules=False)
    sec = agent_store.agents["specialist:s_sec"]
    assert "Application Security Engineer" in sec.system_prompt
    assert "Persona Co" in sec.system_prompt
    assert agent_store.agents["specialist:s_pim"].system_prompt == ""


@pytest.mark.asyncio
async def test_existing_empty_prompts_are_backfilled_but_custom_ones_kept(activation) -> None:
    from agents.store import AgentDefinition

    svc, agent_store = activation
    agent_store.agents["specialist:s_sec"] = AgentDefinition(
        agent_id="specialist:s_sec", owner_id="co_p", name="Sec", system_prompt="")
    agent_store.agents["specialist:s_pim"] = AgentDefinition(
        agent_id="specialist:s_pim", owner_id="co_p", name="Pim", system_prompt="custom")
    await svc.activate_company(company_id="co_p", start_runtimes=False, create_schedules=False)
    assert "Application Security Engineer" in agent_store.agents["specialist:s_sec"].system_prompt
    assert agent_store.agents["specialist:s_pim"].system_prompt == "custom"
