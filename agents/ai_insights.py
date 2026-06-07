"""
AI-Assisted Engineering Insights — track AI tool usage, engagement, and performance.

Inspired by the DX Q1 AI-Assisted Engineering Impact Report:
https://getdx.com/report/ai-assisted-engineering-Q1-impact-report/

Provides metrics that engineering leaders care about:
- Engagement: how often AI tools are used, by whom, on what
- Performance: cycle-time delta, PR throughput, defect rate
- Tool quality: per-tool acceptance rate, time-to-value

Quick-Note Issue: #264
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Iterable, Optional


class ToolKind(str, Enum):
    """Categories of AI engineering tools tracked."""

    AGENT = "agent"            # autonomous coding agents (Claude Code, Cursor)
    COMPLETION = "completion"  # inline completions (Copilot, Codeium)
    CHAT = "chat"              # conversational assistants
    REVIEW = "review"          # PR/code review bots
    SEARCH = "search"          # semantic code search


@dataclass
class UsageEvent:
    """A single AI tool interaction."""

    user_id: str
    tool: str
    kind: ToolKind
    timestamp: datetime
    accepted: bool = False
    latency_ms: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    pr_id: Optional[str] = None


@dataclass
class EngagementMetrics:
    """
    Track adoption and engagement across the engineering org.

    DX report key signals:
    - Daily Active Users (DAU)
    - Weekly Active Users (WAU)
    - Sessions per user per week
    - Tool diversity (how many different tools each user touches)
    """

    events: list[UsageEvent] = field(default_factory=list)

    def record(self, event: UsageEvent) -> None:
        """Record a usage event."""
        self.events.append(event)

    def daily_active_users(self, day: Optional[datetime] = None) -> int:
        """Number of unique users with at least one event on the given day."""
        if day is None:
            day = datetime.now()
        target = day.date()
        return len({
            e.user_id for e in self.events
            if e.timestamp.date() == target
        })

    def weekly_active_users(self, end: Optional[datetime] = None) -> int:
        """Unique users in the 7 days ending at `end` (default: now)."""
        if end is None:
            end = datetime.now()
        start = end - timedelta(days=7)
        return len({
            e.user_id for e in self.events
            if start <= e.timestamp <= end
        })

    def sessions_per_user(self, gap_minutes: int = 30) -> dict[str, int]:
        """
        Count distinct sessions per user. A session ends when there's a gap
        of more than `gap_minutes` between consecutive events for that user.
        """
        gap = timedelta(minutes=gap_minutes)
        sessions: dict[str, int] = {}
        by_user: dict[str, list[UsageEvent]] = {}
        for e in self.events:
            by_user.setdefault(e.user_id, []).append(e)

        for user, evs in by_user.items():
            evs_sorted = sorted(evs, key=lambda x: x.timestamp)
            count = 1
            for prev, cur in zip(evs_sorted, evs_sorted[1:]):
                if cur.timestamp - prev.timestamp > gap:
                    count += 1
            sessions[user] = count
        return sessions

    def tool_diversity(self) -> dict[str, int]:
        """How many distinct tools each user has touched."""
        diversity: dict[str, set[str]] = {}
        for e in self.events:
            diversity.setdefault(e.user_id, set()).add(e.tool)
        return {user: len(tools) for user, tools in diversity.items()}


@dataclass
class PerformanceAnalytics:
    """
    Compare engineering performance with vs without AI tooling.

    DX report findings: AI-assisted PRs typically show 10-25% cycle-time
    reduction and ~5% lower defect rate when used correctly.
    """

    pr_records: list[dict] = field(default_factory=list)

    def record_pr(
        self,
        pr_id: str,
        cycle_time_hours: float,
        ai_assisted: bool,
        had_defect: bool = False,
        author: Optional[str] = None,
    ) -> None:
        """Record a PR completion."""
        self.pr_records.append({
            "pr_id": pr_id,
            "cycle_time_hours": cycle_time_hours,
            "ai_assisted": ai_assisted,
            "had_defect": had_defect,
            "author": author,
        })

    def cycle_time_delta(self) -> Optional[float]:
        """
        Difference in median cycle time: AI-assisted vs control.
        Returns negative numbers when AI is faster.
        """
        ai = [p["cycle_time_hours"] for p in self.pr_records if p["ai_assisted"]]
        ctrl = [p["cycle_time_hours"] for p in self.pr_records if not p["ai_assisted"]]
        if not ai or not ctrl:
            return None
        return statistics.median(ai) - statistics.median(ctrl)

    def defect_rate(self, ai_assisted: Optional[bool] = None) -> float:
        """Defect rate (0..1) for the requested cohort."""
        records = self.pr_records
        if ai_assisted is not None:
            records = [p for p in records if p["ai_assisted"] == ai_assisted]
        if not records:
            return 0.0
        return sum(1 for p in records if p["had_defect"]) / len(records)

    def throughput(self, days: int = 7) -> dict[str, int]:
        """PR throughput per cohort over the last `days` days."""
        cutoff = datetime.now() - timedelta(days=days)
        recent = [p for p in self.pr_records if p.get("ai_assisted") is not None]
        ai_count = sum(1 for p in recent if p["ai_assisted"])
        ctrl_count = sum(1 for p in recent if not p["ai_assisted"])
        return {"ai_assisted": ai_count, "control": ctrl_count}

    def summary(self) -> dict:
        """High-level performance summary for dashboards."""
        delta = self.cycle_time_delta()
        return {
            "total_prs": len(self.pr_records),
            "ai_prs": sum(1 for p in self.pr_records if p["ai_assisted"]),
            "cycle_time_delta_hours": delta,
            "defect_rate_ai": self.defect_rate(ai_assisted=True),
            "defect_rate_control": self.defect_rate(ai_assisted=False),
        }


@dataclass
class AIToolMetrics:
    """
    Per-tool quality metrics: which AI tools actually deliver value?

    Tracks acceptance rate (suggestions kept vs rejected), latency, and
    token efficiency. Engineering leaders use these to choose vendors.
    """

    events: list[UsageEvent] = field(default_factory=list)

    def add_events(self, events: Iterable[UsageEvent]) -> None:
        self.events.extend(events)

    def acceptance_rate(self, tool: str) -> float:
        """Fraction of suggestions accepted for the given tool."""
        tool_events = [e for e in self.events if e.tool == tool]
        if not tool_events:
            return 0.0
        return sum(1 for e in tool_events if e.accepted) / len(tool_events)

    def average_latency(self, tool: str) -> float:
        """Average response latency in ms for the given tool."""
        tool_events = [e for e in self.events if e.tool == tool]
        if not tool_events:
            return 0.0
        return statistics.mean(e.latency_ms for e in tool_events)

    def token_efficiency(self, tool: str) -> float:
        """
        Output tokens per input token (higher = more verbose responses).
        Useful for cost analysis.
        """
        tool_events = [e for e in self.events if e.tool == tool]
        total_in = sum(e.tokens_in for e in tool_events)
        total_out = sum(e.tokens_out for e in tool_events)
        if total_in == 0:
            return 0.0
        return total_out / total_in

    def tool_ranking(self) -> list[tuple[str, float]]:
        """Tools ranked by acceptance rate (highest first)."""
        tools = {e.tool for e in self.events}
        ranked = [(t, self.acceptance_rate(t)) for t in tools]
        return sorted(ranked, key=lambda x: x[1], reverse=True)

    def kind_breakdown(self) -> dict[str, int]:
        """Event counts grouped by ToolKind."""
        counts: dict[str, int] = {}
        for e in self.events:
            counts[e.kind.value] = counts.get(e.kind.value, 0) + 1
        return counts


def build_report(
    engagement: EngagementMetrics,
    performance: PerformanceAnalytics,
    tools: AIToolMetrics,
) -> dict:
    """Assemble the executive-summary report."""
    return {
        "generated_at": datetime.now().isoformat(),
        "engagement": {
            "dau": engagement.daily_active_users(),
            "wau": engagement.weekly_active_users(),
            "sessions": engagement.sessions_per_user(),
            "tool_diversity": engagement.tool_diversity(),
        },
        "performance": performance.summary(),
        "tools": {
            "ranking": tools.tool_ranking(),
            "kind_breakdown": tools.kind_breakdown(),
        },
    }
