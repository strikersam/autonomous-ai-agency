"""packages/bounty/ledger.py — per-agent profit and loss, and who gets to keep working.

Every hunter agent pays for itself or stops being scheduled. Costs are the LLM
spend recorded on each attempt plus a fixed charge for every attempt that
reached human review — the reviewer's time is the scarcest input, so an agent
that keeps producing rejected PRs is the most expensive kind. Revenue is the
bounty amount once a payout is observed.

Allocation is "survival of the profitable": agents still on probation get an
equal share, proven earners get slots in proportion to their return, and an
agent that has used up its probation without earning is retired (0 slots).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from packages.bounty.models import BountyState, HuntRecord


@dataclass(frozen=True)
class AgentProfile:
    """One hunter agent: the niche it competes in."""

    agent_id: str
    languages: frozenset[str]
    description: str


ROSTER: tuple[AgentProfile, ...] = (
    AgentProfile("hunter-python", frozenset({"python"}), "Python libraries and services."),
    AgentProfile("hunter-web", frozenset({"javascript", "typescript"}), "JS/TS packages and apps."),
    AgentProfile("hunter-systems", frozenset({"go", "rust"}), "Go and Rust projects."),
)


def agent_for_language(roster: tuple[AgentProfile, ...], language: str) -> AgentProfile | None:
    """The first agent whose niche covers *language*, if any."""
    wanted = language.strip().lower()
    for profile in roster:
        if wanted in profile.languages:
            return profile
    return None


@dataclass
class AgentPnL:
    """Running totals for one agent."""

    agent_id: str
    attempts: int = 0
    reviews: int = 0
    submitted: int = 0
    merged: int = 0
    paid: int = 0
    revenue_usd: float = 0.0
    cost_usd: float = 0.0
    states: dict[str, int] = field(default_factory=dict)

    @property
    def net_usd(self) -> float:
        """Revenue minus cost."""
        return round(self.revenue_usd - self.cost_usd, 2)


_SUBMITTED = {BountyState.SUBMITTED, BountyState.MERGED, BountyState.PAID, BountyState.LOST}


def compute_pnl(
    records: list[HuntRecord], roster: tuple[AgentProfile, ...], review_cost_usd: int,
) -> dict[str, AgentPnL]:
    """Aggregate hunt records into one P&L per roster agent."""
    pnl = {p.agent_id: AgentPnL(p.agent_id) for p in roster}
    for record in records:
        row = pnl.setdefault(record.agent_id, AgentPnL(record.agent_id))
        row.attempts += 1
        row.states[record.state.value] = row.states.get(record.state.value, 0) + 1
        row.cost_usd += record.llm_cost_usd
        if record.reached_review():
            row.reviews += 1
            row.cost_usd += review_cost_usd
        if record.state in _SUBMITTED:
            row.submitted += 1
        if record.state in {BountyState.MERGED, BountyState.PAID}:
            row.merged += 1
        if record.state is BountyState.PAID:
            row.paid += 1
            row.revenue_usd += record.revenue_usd
    for row in pnl.values():
        row.cost_usd = round(row.cost_usd, 2)
    return pnl


def fitness(row: AgentPnL, retire_after: int) -> float:
    """Scheduling weight: 1.0 on probation, return ratio once proven, 0 when retired."""
    if row.revenue_usd > 0:
        return max(0.5, (row.revenue_usd + 1) / (row.cost_usd + 1))
    if row.attempts >= retire_after:
        return 0.0
    return 1.0


def allocate(pnl: dict[str, AgentPnL], slots: int, retire_after: int) -> dict[str, int]:
    """Split *slots* attempts across agents by fitness (largest-remainder rounding)."""
    weights = {aid: fitness(row, retire_after) for aid, row in pnl.items()}
    total = sum(weights.values())
    if slots <= 0 or total <= 0:
        return {aid: 0 for aid in pnl}
    exact = {aid: slots * w / total for aid, w in weights.items()}
    share = {aid: int(v) for aid, v in exact.items()}
    leftover = slots - sum(share.values())
    for aid in sorted(exact, key=lambda a: exact[a] - share[a], reverse=True)[:leftover]:
        share[aid] += 1
    return share


def render_ledger(pnl: dict[str, AgentPnL], allocation: dict[str, int], retire_after: int) -> str:
    """Markdown table for the ledger issue and the job summary."""
    lines = [
        "| Agent | Attempts | Reviews | Submitted | Merged | Paid | Revenue | Cost | Net | Status | Slots |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for aid, row in sorted(pnl.items()):
        status = "retired" if fitness(row, retire_after) == 0 else (
            "earning" if row.revenue_usd > 0 else "probation")
        lines.append(
            f"| {aid} | {row.attempts} | {row.reviews} | {row.submitted} | {row.merged} | "
            f"{row.paid} | ${row.revenue_usd:.2f} | ${row.cost_usd:.2f} | ${row.net_usd:.2f} | "
            f"{status} | {allocation.get(aid, 0)} |"
        )
    total_rev = sum(r.revenue_usd for r in pnl.values())
    total_cost = sum(r.cost_usd for r in pnl.values())
    lines.append(f"\n**Agency total:** revenue ${total_rev:.2f}, cost ${total_cost:.2f}, "
                 f"net ${total_rev - total_cost:.2f}")
    return "\n".join(lines)
