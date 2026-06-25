"""Tests for per-company trend scoping (Autonomy Charter G4).

Covers the stack-tag vocabulary, per-company relevance scoring, gate-lane
routing (🟢 research vs 🔴 code change), and the fan-out/dedup behaviour that
turns one platform trend into 0..N company-scoped tasks.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from agent.trend_scoping import (
    company_stack_tags,
    extract_stack_tags,
    fan_out_trend,
    fan_out_trends,
    is_code_change_trend,
    map_trend_to_company_task,
    score_trend_for_company,
    trend_source_id,
    trend_stack_tags,
)
from tasks.models import TaskPriority
from tasks.service import TaskWorkflowService
from tasks.store import TaskStore


# ── lightweight stand-ins for TrendAlert / CompanyGraph ──────────────────────


@dataclass
class _Alert:
    source: str = "github"
    title: str = ""
    summary: str = ""
    url: str = "https://example.com"
    relevance_score: float = 0.8
    tags: list[str] = field(default_factory=list)


@dataclass
class _Company:
    id: str
    name: str = "Acme"


def _graph(stack_tokens: list[str]) -> dict:
    """A minimal CompanyGraph-shaped dict whose website carries a stack."""
    return {
        "websites": [{"inferred_stack": {"frameworks": stack_tokens, "languages": []}}],
        "repos": [],
        "systems": [],
        "detected_systems": [],
    }


# ── stack vocabulary ─────────────────────────────────────────────────────────


def test_extract_stack_tags_matches_aliases():
    assert "react" in extract_stack_tags("A new React.js hook pattern")
    assert "stripe" in extract_stack_tags("Stripe announces new billing API")
    assert extract_stack_tags("a generic post about nothing") == set()


def test_company_stack_tags_from_graph():
    tags = company_stack_tags(_graph(["React", "PostgreSQL"]))
    assert "react" in tags and "postgres" in tags


def test_company_stack_tags_reads_systems_and_repos():
    graph = {
        "websites": [],
        "repos": [{"languages": ["Python"], "frameworks": ["Django"], "inferred_stack": None}],
        "systems": [{"name": "Shopify", "system_type": "CMS"}],
        "detected_systems": [{"name": "Stripe"}],
    }
    tags = company_stack_tags(graph)
    assert {"python", "shopify", "stripe"} <= tags


# ── relevance scoring ────────────────────────────────────────────────────────


def test_score_requires_overlap():
    # No overlap → 0; overlap → scales with confidence.
    assert score_trend_for_company({"react"}, {"vue"}, 0.9) == 0.0
    assert score_trend_for_company({"react"}, {"react"}, 0.8) > 0.5


def test_score_zero_for_tagless_trend():
    assert score_trend_for_company(set(), {"react"}, 1.0) == 0.0


def test_score_scales_with_coverage():
    full = score_trend_for_company({"react"}, {"react"}, 0.8)
    partial = score_trend_for_company({"react", "stripe"}, {"react"}, 0.8)
    assert full > partial > 0.0


# ── gate routing ─────────────────────────────────────────────────────────────


def test_is_code_change_trend_detects_markers():
    assert is_code_change_trend(_Alert(tags=["release", "action-required"])) is True
    assert is_code_change_trend(_Alert(title="Critical security vulnerability (CVE-2026-1)")) is True
    assert is_code_change_trend(_Alert(title="A survey of React patterns", tags=["research"])) is False


def test_map_trend_routes_code_change_to_telegram_gate():
    alert = _Alert(title="React 20 release", summary="upgrade required", tags=["release"])
    task = map_trend_to_company_task(alert, _Company(id="c1", name="Acme"), score=0.8)
    assert task.requires_approval is True
    assert "gate:telegram" in task.tags
    assert task.priority == TaskPriority.HIGH
    assert "untrusted" in task.prompt.lower()


def test_map_trend_routes_research_to_autonomous():
    alert = _Alert(title="React patterns explored", tags=["research"])
    task = map_trend_to_company_task(alert, _Company(id="c1"), score=0.7)
    assert task.requires_approval is False
    assert "gate:autonomous" in task.tags
    assert task.source == "trend"
    assert task.source_id == trend_source_id(alert, "c1")


# ── fan-out + dedup ──────────────────────────────────────────────────────────


@pytest.fixture
def stores():
    store = TaskStore(db=None)
    return store, TaskWorkflowService(store=store)


async def test_fan_out_scopes_to_matching_company_only(stores):
    store, service = stores
    alert = _Alert(title="New React.js concurrent rendering", relevance_score=0.9)
    react_co = (_Company(id="react1", name="ReactCo"), _graph(["React"]))
    vue_co = (_Company(id="vue1", name="VueCo"), _graph(["Vue"]))

    created = await fan_out_trend(alert, [react_co, vue_co], store=store, service=service)

    assert len(created) == 1
    assert created[0].tags.count("company:react1") == 1
    # only the React company got a task
    assert (await store.find_by_source_id(trend_source_id(alert, "react1"))) is not None
    assert (await store.find_by_source_id(trend_source_id(alert, "vue1"))) is None


async def test_fan_out_is_idempotent(stores):
    store, service = stores
    alert = _Alert(title="Stripe billing API changes", relevance_score=0.9)
    co = (_Company(id="c1"), _graph(["Stripe"]))

    first = await fan_out_trend(alert, [co], store=store, service=service)
    again = await fan_out_trend(alert, [co], store=store, service=service)

    assert len(first) == 1
    assert again == []
    assert len(await store.list_all(limit=100)) == 1


async def test_fan_out_skips_tagless_trend(stores):
    store, service = stores
    alert = _Alert(title="A generic announcement about nothing", relevance_score=0.95)
    co = (_Company(id="c1"), _graph(["React"]))
    assert await fan_out_trend(alert, [co], store=store, service=service) == []


async def test_fan_out_trends_across_multiple(stores):
    store, service = stores
    alerts = [
        _Alert(title="React 20 ships", relevance_score=0.9),
        _Alert(title="Postgres 18 performance", relevance_score=0.9),
    ]
    companies = [
        (_Company(id="react1"), _graph(["React"])),
        (_Company(id="db1"), _graph(["PostgreSQL"])),
    ]
    created = await fan_out_trends(alerts, companies, store=store, service=service)
    # React trend → react1; Postgres trend → db1
    assert len(created) == 2
    by_company = {t.tags[1] for t in created}  # "company:<id>" is second tag
    assert by_company == {"company:react1", "company:db1"}


def test_trend_stack_tags_reads_title_summary_tags():
    alert = _Alert(title="Big news", summary="now powered by Next.js", tags=["vercel"])
    tags = trend_stack_tags(alert)
    assert {"nextjs", "vercel"} <= tags
