"""
Agentic CFO — autonomous financial analyst for AI infrastructure spend.

Inspired by emerging "agentic CFO" patterns:
https://www.coindesk.com/ — agentic financial decision-making

Provides:
- FinancialMetrics: revenue, costs, burn rate, runway, gross margin
- BudgetOptimizer: re-allocates budget across line items by ROI
- FinancialAgent: makes recommendations (cut/scale/hold) per cost center

Quick-Note Issue: #236
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Optional


class Recommendation(str, Enum):
    """Budget recommendations a financial agent can issue."""

    CUT = "cut"
    HOLD = "hold"
    SCALE = "scale"
    INVESTIGATE = "investigate"


@dataclass
class CostLine:
    """A single budget line item (e.g. 'GPU compute', 'API credits')."""

    name: str
    monthly_cost: float
    revenue_attributed: float = 0.0   # revenue this line directly enables
    category: str = "operations"       # operations / R&D / G&A / sales

    @property
    def roi(self) -> float:
        """Revenue per dollar spent. Higher is better."""
        if self.monthly_cost <= 0:
            return 0.0
        return self.revenue_attributed / self.monthly_cost


@dataclass
class FinancialMetrics:
    """
    Core financial metrics tracked monthly.

    All inputs are dollars/month. Methods compute the standard CFO metrics
    every board deck needs: burn, runway, gross margin, CAC payback.
    """

    monthly_revenue: float = 0.0
    monthly_costs: float = 0.0
    cash_on_hand: float = 0.0
    cost_lines: list[CostLine] = field(default_factory=list)
    period: Optional[date] = None

    @property
    def burn_rate(self) -> float:
        """Net monthly burn (cost minus revenue). Positive = losing money."""
        return self.monthly_costs - self.monthly_revenue

    def runway_months(self) -> float:
        """How many months of cash remain at current burn."""
        burn = self.burn_rate
        if burn <= 0:
            return float("inf")  # profitable
        if self.cash_on_hand <= 0:
            return 0.0
        return self.cash_on_hand / burn

    def gross_margin(self) -> float:
        """
        Gross margin = (revenue - COGS) / revenue.
        COGS is the sum of cost lines categorized 'operations' or 'cogs'.
        Returns 0.0 if no revenue.
        """
        if self.monthly_revenue <= 0:
            return 0.0
        cogs = sum(c.monthly_cost for c in self.cost_lines
                   if c.category in {"operations", "cogs"})
        return (self.monthly_revenue - cogs) / self.monthly_revenue

    def total_costs(self) -> float:
        """Sum of all cost lines (sanity check vs monthly_costs)."""
        return sum(c.monthly_cost for c in self.cost_lines)

    def roi_by_line(self) -> dict[str, float]:
        return {c.name: c.roi for c in self.cost_lines}

    def summary(self) -> dict:
        return {
            "period": self.period.isoformat() if self.period else None,
            "revenue": self.monthly_revenue,
            "costs": self.monthly_costs,
            "burn_rate": self.burn_rate,
            "runway_months": self.runway_months(),
            "gross_margin": self.gross_margin(),
            "cash_on_hand": self.cash_on_hand,
        }


@dataclass
class BudgetOptimizer:
    """
    Reallocate budget across cost lines to maximize total ROI under
    a fixed budget cap. Uses a simple greedy ROI-weighted distribution.
    """

    cost_lines: list[CostLine]

    def total_budget(self) -> float:
        return sum(c.monthly_cost for c in self.cost_lines)

    def reallocate(self, new_budget: float) -> list[CostLine]:
        """
        Return a new list of CostLine objects redistributed to fit `new_budget`.

        Strategy: each line's share is proportional to its ROI. Lines with
        zero ROI get a 5% floor so they aren't fully starved.
        """
        if new_budget <= 0:
            return [CostLine(c.name, 0.0, c.revenue_attributed, c.category)
                    for c in self.cost_lines]

        rois = [max(c.roi, 0.0) for c in self.cost_lines]
        floor_share = 0.05 / max(len(self.cost_lines), 1)
        total_roi = sum(rois)

        out: list[CostLine] = []
        for c, roi in zip(self.cost_lines, rois):
            if total_roi > 0:
                share = (roi / total_roi) * 0.95 + floor_share
            else:
                share = 1.0 / len(self.cost_lines)
            new_cost = round(new_budget * share, 2)
            out.append(CostLine(
                name=c.name,
                monthly_cost=new_cost,
                revenue_attributed=c.revenue_attributed,
                category=c.category,
            ))
        return out

    def savings(self, target_budget: float) -> float:
        """Dollar savings if reallocated to `target_budget`."""
        return self.total_budget() - target_budget

    def lowest_roi_lines(self, n: int = 3) -> list[CostLine]:
        """Return the bottom-n cost lines by ROI (candidates to cut)."""
        return sorted(self.cost_lines, key=lambda c: c.roi)[:n]


@dataclass
class FinancialAgent:
    """
    The agentic CFO: ingests metrics + cost lines and emits recommendations.

    Decision rules (intentionally simple and auditable — a human CFO must
    sign off before action is taken):
        - runway < 6 months                         → CUT lowest-ROI line
        - gross_margin < 0.40                       → INVESTIGATE COGS lines
        - line.roi > 5.0 and category in {sales,RD} → SCALE that line
        - line.roi < 0.5 and not strategic          → CUT that line
        - otherwise                                 → HOLD
    """

    name: str = "agentic_cfo"
    runway_threshold_months: float = 6.0
    margin_threshold: float = 0.40
    scale_roi_threshold: float = 5.0
    cut_roi_threshold: float = 0.5
    strategic_lines: set[str] = field(default_factory=set)

    def assess(self, metrics: FinancialMetrics) -> dict[str, Recommendation]:
        """Per-line recommendation map."""
        recs: dict[str, Recommendation] = {}

        runway = metrics.runway_months()
        margin = metrics.gross_margin()

        # Crisis mode: low runway → cut the worst performer aggressively
        if runway < self.runway_threshold_months and metrics.cost_lines:
            worst = min(metrics.cost_lines, key=lambda c: c.roi)
            recs[worst.name] = Recommendation.CUT

        # Margin investigation: flag COGS lines
        if margin < self.margin_threshold and metrics.monthly_revenue > 0:
            for c in metrics.cost_lines:
                if c.category in {"operations", "cogs"}:
                    recs.setdefault(c.name, Recommendation.INVESTIGATE)

        # Per-line ROI rules
        for c in metrics.cost_lines:
            if c.name in recs:
                continue
            if c.roi >= self.scale_roi_threshold and c.category in {"sales", "R&D"}:
                recs[c.name] = Recommendation.SCALE
            elif c.roi < self.cut_roi_threshold and c.name not in self.strategic_lines:
                recs[c.name] = Recommendation.CUT
            else:
                recs[c.name] = Recommendation.HOLD

        return recs

    def explain(self, metrics: FinancialMetrics) -> list[str]:
        """Human-readable narrative of the recommendations."""
        recs = self.assess(metrics)
        lines = [
            f"Runway: {metrics.runway_months():.1f} months",
            f"Gross margin: {metrics.gross_margin() * 100:.1f}%",
            f"Burn rate: ${metrics.burn_rate:,.0f}/month",
            "",
            "Recommendations:",
        ]
        for line in metrics.cost_lines:
            rec = recs.get(line.name, Recommendation.HOLD)
            lines.append(
                f"  {line.name:25s} ROI={line.roi:.2f}  → {rec.value.upper()}"
            )
        return lines
