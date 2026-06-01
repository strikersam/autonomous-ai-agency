"""Tests for agents.ai_insights — AI-Assisted Engineering metrics."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from agents.ai_insights import (
    AIToolMetrics,
    EngagementMetrics,
    PerformanceAnalytics,
    ToolKind,
    UsageEvent,
    build_report,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def sample_events() -> list[UsageEvent]:
    """A spread of events from 3 users across 3 tools over a week."""
    base = datetime(2026, 5, 25, 9, 0)
    return [
        UsageEvent("alice", "claude_code", ToolKind.AGENT, base, accepted=True,
                   latency_ms=200, tokens_in=100, tokens_out=300, pr_id="pr1"),
        UsageEvent("alice", "copilot", ToolKind.COMPLETION, base + timedelta(minutes=10),
                   accepted=True, latency_ms=80, tokens_in=20, tokens_out=15),
        UsageEvent("alice", "copilot", ToolKind.COMPLETION, base + timedelta(hours=2),
                   accepted=False, latency_ms=90, tokens_in=20, tokens_out=15),
        UsageEvent("bob", "cursor", ToolKind.AGENT, base + timedelta(days=1),
                   accepted=True, latency_ms=300, tokens_in=200, tokens_out=600,
                   pr_id="pr2"),
        UsageEvent("bob", "claude_code", ToolKind.CHAT, base + timedelta(days=1, hours=1),
                   accepted=True, latency_ms=250, tokens_in=150, tokens_out=400),
        UsageEvent("carol", "copilot", ToolKind.COMPLETION, base + timedelta(days=2),
                   accepted=False, latency_ms=70, tokens_in=15, tokens_out=10),
    ]


# ── EngagementMetrics ─────────────────────────────────────────────────────────


def test_engagement_record_appends():
    eng = EngagementMetrics()
    e = UsageEvent("u1", "tool", ToolKind.AGENT, datetime.now())
    eng.record(e)
    assert eng.events == [e]


def test_engagement_dau_counts_unique_users(sample_events):
    eng = EngagementMetrics(events=sample_events)
    target = datetime(2026, 5, 25, 12, 0)
    # base day has only alice
    assert eng.daily_active_users(target) == 1


def test_engagement_dau_zero_when_no_events():
    eng = EngagementMetrics()
    assert eng.daily_active_users(datetime(2026, 1, 1)) == 0


def test_engagement_wau_window(sample_events):
    eng = EngagementMetrics(events=sample_events)
    end = datetime(2026, 5, 28, 23, 59)
    # all 3 users in the past 7 days
    assert eng.weekly_active_users(end) == 3


def test_engagement_sessions_split_on_gap(sample_events):
    eng = EngagementMetrics(events=sample_events)
    sessions = eng.sessions_per_user(gap_minutes=30)
    # alice: events at 0min, 10min (same session), then 2hr later (new session) → 2
    assert sessions["alice"] == 2
    # bob: events 1hr apart on the same day → with 30min gap → 2 sessions
    assert sessions["bob"] == 2
    # carol: single event → 1 session
    assert sessions["carol"] == 1


def test_engagement_tool_diversity(sample_events):
    eng = EngagementMetrics(events=sample_events)
    diversity = eng.tool_diversity()
    assert diversity["alice"] == 2  # claude_code + copilot
    assert diversity["bob"] == 2    # cursor + claude_code
    assert diversity["carol"] == 1  # copilot only


# ── PerformanceAnalytics ──────────────────────────────────────────────────────


def test_performance_cycle_time_delta_negative_when_ai_faster():
    perf = PerformanceAnalytics()
    perf.record_pr("p1", 4.0, ai_assisted=True)
    perf.record_pr("p2", 5.0, ai_assisted=True)
    perf.record_pr("p3", 8.0, ai_assisted=False)
    perf.record_pr("p4", 10.0, ai_assisted=False)
    delta = perf.cycle_time_delta()
    assert delta is not None
    assert delta < 0  # AI is faster


def test_performance_cycle_time_delta_none_without_both_cohorts():
    perf = PerformanceAnalytics()
    perf.record_pr("p1", 4.0, ai_assisted=True)
    assert perf.cycle_time_delta() is None


def test_performance_defect_rate_filters_by_cohort():
    perf = PerformanceAnalytics()
    perf.record_pr("p1", 4.0, ai_assisted=True, had_defect=True)
    perf.record_pr("p2", 4.0, ai_assisted=True, had_defect=False)
    perf.record_pr("p3", 4.0, ai_assisted=False, had_defect=True)
    perf.record_pr("p4", 4.0, ai_assisted=False, had_defect=True)
    assert perf.defect_rate(ai_assisted=True) == 0.5
    assert perf.defect_rate(ai_assisted=False) == 1.0


def test_performance_summary_shape():
    perf = PerformanceAnalytics()
    perf.record_pr("p1", 4.0, ai_assisted=True)
    perf.record_pr("p2", 8.0, ai_assisted=False)
    s = perf.summary()
    assert s["total_prs"] == 2
    assert s["ai_prs"] == 1
    assert "cycle_time_delta_hours" in s
    assert "defect_rate_ai" in s


# ── AIToolMetrics ─────────────────────────────────────────────────────────────


def test_tool_metrics_acceptance_rate(sample_events):
    tools = AIToolMetrics()
    tools.add_events(sample_events)
    # copilot: 1 accepted out of 3 → ~0.333
    assert tools.acceptance_rate("copilot") == pytest.approx(1 / 3)
    # claude_code: 2/2 accepted
    assert tools.acceptance_rate("claude_code") == 1.0


def test_tool_metrics_acceptance_rate_unknown_tool():
    tools = AIToolMetrics()
    assert tools.acceptance_rate("nonexistent") == 0.0


def test_tool_metrics_average_latency(sample_events):
    tools = AIToolMetrics()
    tools.add_events(sample_events)
    # copilot latencies: 80, 90, 70 → mean 80
    assert tools.average_latency("copilot") == pytest.approx(80.0)


def test_tool_metrics_token_efficiency(sample_events):
    tools = AIToolMetrics()
    tools.add_events(sample_events)
    # claude_code: in=100+150=250, out=300+400=700 → 700/250 = 2.8
    assert tools.token_efficiency("claude_code") == pytest.approx(2.8)


def test_tool_metrics_ranking_sorted_descending(sample_events):
    tools = AIToolMetrics()
    tools.add_events(sample_events)
    ranking = tools.tool_ranking()
    rates = [r[1] for r in ranking]
    assert rates == sorted(rates, reverse=True)
    # claude_code and cursor both have 100% acceptance
    assert ranking[0][0] in {"claude_code", "cursor"}
    # copilot has the lowest acceptance and must be last
    assert ranking[-1][0] == "copilot"


def test_tool_metrics_kind_breakdown(sample_events):
    tools = AIToolMetrics()
    tools.add_events(sample_events)
    breakdown = tools.kind_breakdown()
    assert breakdown["agent"] == 2
    assert breakdown["completion"] == 3
    assert breakdown["chat"] == 1


# ── Integration: build_report ─────────────────────────────────────────────────


def test_build_report_assembles_all_sections(sample_events):
    eng = EngagementMetrics(events=sample_events)
    perf = PerformanceAnalytics()
    perf.record_pr("p1", 4.0, ai_assisted=True)
    perf.record_pr("p2", 8.0, ai_assisted=False)
    tools = AIToolMetrics()
    tools.add_events(sample_events)

    report = build_report(eng, perf, tools)
    assert "generated_at" in report
    assert "engagement" in report
    assert "performance" in report
    assert "tools" in report
    assert report["performance"]["total_prs"] == 2
    assert report["tools"]["kind_breakdown"]["agent"] == 2
