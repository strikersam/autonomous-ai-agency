"""Tests for the intelligent C-suite advisory layer (agent/executive_advisory.py).

Hermetic: the LLM, research, and memory are all injected — no network, no DB.
The routing/synthesis tests disable grounding/memory so call counts are exact;
dedicated tests exercise the grounding and memory paths with fakes.
"""
from __future__ import annotations

import pytest

import agent.executive_advisory as ea
from agent.executive_advisory import (
    AdviceResult,
    AdvisoryMemory,
    ExecutiveAdvisory,
    Grounding,
    _compose_context,
    _format_company_context,
    _keywords,
    _mem_key,
    default_executives,
    get_executive_advisory,
    reset_executive_advisory,
)


def _recording_llm(replies: list[str]):
    """Return an async llm that yields queued replies and records calls."""
    calls: list[list[dict[str, str]]] = []
    seq = iter(replies)

    async def llm(messages):
        calls.append(messages)
        try:
            return next(seq)
        except StopIteration:
            return "default reply"

    llm.calls = calls  # type: ignore[attr-defined]
    return llm


# ── Routing ───────────────────────────────────────────────────────────────


def test_select_routes_by_domain_keyword():
    adv = ExecutiveAdvisory()
    assert "cfo" in adv.select("What pricing and runway do we need?")
    assert "gc" in adv.select("Review this vendor contract for IP risk")
    assert "cmo" in adv.select("Plan our go-to-market launch campaign")


def test_select_falls_back_when_nothing_matches():
    adv = ExecutiveAdvisory()
    assert adv.select("xyzzy plugh") == ["cso", "cfo", "cpo"]


# ── advise (routing + synthesis, grounding/memory off) ──────────────────────


@pytest.mark.asyncio
async def test_advise_consults_selected_execs_and_synthesizes():
    llm = _recording_llm(["CFO view", "CSO view", "SYNTHESIS"])
    adv = ExecutiveAdvisory(llm=llm)
    result = await adv.advise("What is our pricing strategy vs competitors?",
                              ground=False, remember=False)
    assert isinstance(result, AdviceResult)
    assert set(result.consulted) >= {"cfo", "cso"}
    assert result.answer == "SYNTHESIS"
    assert len(llm.calls) == len(result.consulted) + 1  # execs + synthesis


@pytest.mark.asyncio
async def test_advise_single_exec_needs_no_synthesis():
    llm = _recording_llm(["only-gc"])
    adv = ExecutiveAdvisory(llm=llm)
    result = await adv.advise("anything", roles=["gc"], synthesize=False,
                              ground=False, remember=False)
    assert result.consulted == ["gc"]
    assert result.answer == "only-gc"
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_advise_is_fail_soft_when_a_voice_errors():
    async def flaky_llm(messages):
        raise RuntimeError("provider down")

    adv = ExecutiveAdvisory(llm=flaky_llm)
    result = await adv.advise("legal contract question", roles=["gc"],
                              ground=False, remember=False)
    assert result.opinions[0].error
    assert result.opinions[0].text == ""
    assert result.answer == ""  # nothing usable, but no exception


@pytest.mark.asyncio
async def test_advise_unknown_role_is_dropped():
    llm = _recording_llm(["x"])
    adv = ExecutiveAdvisory(llm=llm)
    result = await adv.advise("q", roles=["not-a-real-exec"],
                              ground=False, remember=False)
    assert result.consulted == []
    assert len(llm.calls) == 0


# ── Grounding (facts) ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_grounding_evidence_is_injected_and_recorded():
    llm = _recording_llm(["gc opinion"])

    async def research(question):
        return Grounding(text="ACME raised $5M seed", sources=["https://x.test"])

    adv = ExecutiveAdvisory(llm=llm, research=research)
    result = await adv.advise("legal risk?", roles=["gc"], remember=False)
    # evidence reached the executive's prompt, fenced as untrusted
    user_msg = llm.calls[0][1]["content"]
    assert "ACME raised $5M seed" in user_msg
    assert "UNTRUSTED" in user_msg
    # and is surfaced on the result for traceability
    assert result.grounding.text == "ACME raised $5M seed"
    assert result.grounding.sources == ["https://x.test"]


@pytest.mark.asyncio
async def test_grounding_failure_degrades_to_empty():
    llm = _recording_llm(["gc opinion"])

    async def research(question):
        raise RuntimeError("search down")

    adv = ExecutiveAdvisory(llm=llm, research=research)
    result = await adv.advise("legal risk?", roles=["gc"], remember=False)
    assert result.grounding.text == ""
    assert result.answer == "gc opinion"  # still answers without evidence


@pytest.mark.asyncio
async def test_default_research_parses_web_reach(monkeypatch):
    class _FakeReach:
        def search_web(self, query, limit=8):
            return {"ok": True, "results": [
                {"title": "Result A", "url": "https://a.test"},
                {"title": "Result B", "url": "https://b.test"},
            ]}

    monkeypatch.setattr("agent.web_reach.get_web_reach", lambda: _FakeReach())
    adv = ExecutiveAdvisory()
    g = await adv._default_research("market size")
    assert "Result A (https://a.test)" in g.text
    assert g.sources == ["https://a.test", "https://b.test"]


@pytest.mark.asyncio
async def test_default_research_handles_search_failure(monkeypatch):
    class _FakeReach:
        def search_web(self, query, limit=8):
            return {"ok": False, "error": "no results"}

    monkeypatch.setattr("agent.web_reach.get_web_reach", lambda: _FakeReach())
    adv = ExecutiveAdvisory()
    g = await adv._default_research("anything")
    assert g.text == "" and g.sources == []


# ── Memory ──────────────────────────────────────────────────────────────────


class _FakeMemory:
    def __init__(self, recall_text=""):
        self._recall = recall_text
        self.remembered: list[tuple[str, str]] = []

    def recall_sync(self, question, *, limit=3):
        return self._recall

    def remember_sync(self, question, answer):
        self.remembered.append((question, answer))


@pytest.mark.asyncio
async def test_prior_advice_is_recalled_into_context():
    llm = _recording_llm(["opinion"])
    mem = _FakeMemory(recall_text="- last quarter we advised raising prices")
    adv = ExecutiveAdvisory(llm=llm, memory=mem)
    await adv.advise("pricing?", roles=["cfo"], ground=False)
    user_msg = llm.calls[0][1]["content"]
    assert "Prior advice on record" in user_msg
    assert "raising prices" in user_msg


@pytest.mark.asyncio
async def test_answer_is_persisted_to_memory():
    llm = _recording_llm(["cfo opinion"])
    mem = _FakeMemory()
    adv = ExecutiveAdvisory(llm=llm, memory=mem)
    await adv.advise("pricing?", roles=["cfo"], ground=False, remember=True)
    assert mem.remembered == [("pricing?", "cfo opinion")]


@pytest.mark.asyncio
async def test_memory_off_skips_recall_and_store():
    llm = _recording_llm(["cfo opinion"])
    mem = _FakeMemory(recall_text="should not appear")
    adv = ExecutiveAdvisory(llm=llm, memory=mem)
    await adv.advise("pricing?", roles=["cfo"], ground=False, remember=False)
    assert mem.remembered == []
    assert "should not appear" not in llm.calls[0][1]["content"]


def test_advisory_memory_roundtrips_via_store(tmp_path):
    from agent.persistent_memory import PersistentMemoryStore

    store = PersistentMemoryStore(db_path=str(tmp_path / "mem.db"))
    mem = AdvisoryMemory(store=store)
    mem.remember_sync("How should we price the widget tier?", "Raise to $49")
    recalled = mem.recall_sync("widget pricing decision")
    assert "Raise to $49" in recalled


def test_advisory_memory_is_fail_soft_on_broken_store():
    class _Broken:
        def search_memories(self, *a, **k):
            raise RuntimeError("db gone")

        def save(self, *a, **k):
            raise RuntimeError("db gone")

    mem = AdvisoryMemory(store=_Broken())
    assert mem.recall_sync("q") == ""
    mem.remember_sync("q", "a")  # must not raise


# ── Helpers ─────────────────────────────────────────────────────────────────


def test_compose_context_orders_and_fences_sections():
    ctx = _compose_context(
        {"name": "Acme"},
        Grounding(text="a fact", sources=["u"]),
        "prior line",
    )
    assert ctx.index("## Company") < ctx.index("## Prior advice on record")
    assert ctx.index("## Prior advice on record") < ctx.index("## Web research")
    assert "UNTRUSTED" in ctx


def test_keywords_and_mem_key_are_stable():
    assert _keywords("Pricing strategy for pricing") == ["pricing", "strategy"]
    assert _mem_key("Same Question") == _mem_key("  same question  ")
    assert _mem_key("a").startswith("advice:")


def test_format_company_context_variants():
    assert _format_company_context(None) == ""
    assert _format_company_context("  hi  ") == "hi"
    out = _format_company_context({"name": "Acme", "stage": "seed", "empty": ""})
    assert "name: Acme" in out and "stage: seed" in out and "empty" not in out


def test_default_executives_have_unique_roles():
    roles = [e.role for e in default_executives()]
    assert len(roles) == len(set(roles))
    assert {"cso", "cfo", "coo", "cmo", "cpo", "gc"} == set(roles)


def test_singleton_reset():
    reset_executive_advisory()
    a = get_executive_advisory()
    assert get_executive_advisory() is a
    reset_executive_advisory()
    assert get_executive_advisory() is not a


def test_result_as_dict_shape():
    d = AdviceResult(question="q", consulted=["cfo"]).as_dict()
    assert d["question"] == "q" and d["consulted"] == ["cfo"]
    assert d["opinions"] == [] and d["answer"] == ""
    assert d["grounding"] == {"text": "", "sources": []}
