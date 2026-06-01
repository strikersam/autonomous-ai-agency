"""Tests for agents.financial_analyst — Agentic CFO."""

from __future__ import annotations

import importlib.util
import sys

import pytest

# Load the module directly to bypass agents/__init__.py dependency chain
_FIN_SPEC = importlib.util.spec_from_file_location(
    "financial_analyst", "agents/financial_analyst.py"
)
_fin = importlib.util.module_from_spec(_FIN_SPEC)
sys.modules["financial_analyst"] = _fin
_FIN_SPEC.loader.exec_module(_fin)

BudgetOptimizer = _fin.BudgetOptimizer
CostLine = _fin.CostLine
FinancialAgent = _fin.FinancialAgent
FinancialMetrics = _fin.FinancialMetrics
Recommendation = _fin.Recommendation


# ── CostLine ──────────────────────────────────────────────────────────────────


def test_costline_roi_basic():
    c = CostLine("gpu", monthly_cost=1000.0, revenue_attributed=3000.0)
    assert c.roi == 3.0


def test_costline_roi_zero_when_no_cost():
    c = CostLine("free_tier", monthly_cost=0.0, revenue_attributed=100.0)
    assert c.roi == 0.0


# ── FinancialMetrics ──────────────────────────────────────────────────────────


def test_metrics_burn_rate():
    m = FinancialMetrics(monthly_revenue=10_000, monthly_costs=15_000)
    assert m.burn_rate == 5_000


def test_metrics_burn_rate_negative_when_profitable():
    m = FinancialMetrics(monthly_revenue=20_000, monthly_costs=15_000)
    assert m.burn_rate == -5_000


def test_metrics_runway_months():
    m = FinancialMetrics(
        monthly_revenue=10_000, monthly_costs=15_000, cash_on_hand=50_000
    )
    assert m.runway_months() == 10.0  # 50k / 5k burn


def test_metrics_runway_infinite_when_profitable():
    m = FinancialMetrics(monthly_revenue=20_000, monthly_costs=10_000, cash_on_hand=50_000)
    assert m.runway_months() == float("inf")


def test_metrics_runway_zero_when_no_cash():
    m = FinancialMetrics(monthly_revenue=0, monthly_costs=10_000, cash_on_hand=0)
    assert m.runway_months() == 0.0


def test_metrics_gross_margin():
    m = FinancialMetrics(
        monthly_revenue=100_000,
        monthly_costs=80_000,
        cost_lines=[
            CostLine("gpu", 30_000, category="cogs"),
            CostLine("api", 10_000, category="operations"),
            CostLine("salaries", 40_000, category="G&A"),
        ],
    )
    # COGS = 30k + 10k = 40k, margin = (100k - 40k)/100k = 0.6
    assert m.gross_margin() == 0.6


def test_metrics_gross_margin_normalizes_category_case():
    m = FinancialMetrics(
        monthly_revenue=100_000,
        monthly_costs=80_000,
        cost_lines=[
            CostLine("gpu", 70_000, category="COGS"),
        ],
    )

    assert m.gross_margin() == 0.3


def test_metrics_gross_margin_zero_when_no_revenue():
    m = FinancialMetrics(monthly_revenue=0, monthly_costs=10_000)
    assert m.gross_margin() == 0.0


def test_metrics_summary_shape():
    m = FinancialMetrics(monthly_revenue=10_000, monthly_costs=8_000, cash_on_hand=100_000)
    s = m.summary()
    for key in ("revenue", "costs", "burn_rate", "runway_months", "gross_margin", "cash_on_hand"):
        assert key in s


# ── BudgetOptimizer ───────────────────────────────────────────────────────────


def test_optimizer_total_budget_sums_lines():
    opt = BudgetOptimizer(cost_lines=[
        CostLine("a", 1000), CostLine("b", 500),
    ])
    assert opt.total_budget() == 1500


def test_optimizer_reallocate_respects_total_budget():
    opt = BudgetOptimizer(cost_lines=[
        CostLine("high_roi", 500, revenue_attributed=2500),
        CostLine("low_roi",  500, revenue_attributed=250),
    ])
    new_lines = opt.reallocate(new_budget=1000)
    total = sum(c.monthly_cost for c in new_lines)
    assert abs(total - 1000) < 1.0  # allow small rounding


def test_optimizer_reallocate_favors_high_roi():
    opt = BudgetOptimizer(cost_lines=[
        CostLine("high_roi", 500, revenue_attributed=5000),  # ROI 10
        CostLine("low_roi",  500, revenue_attributed=500),   # ROI 1
    ])
    new_lines = opt.reallocate(new_budget=1000)
    high = next(c for c in new_lines if c.name == "high_roi")
    low  = next(c for c in new_lines if c.name == "low_roi")
    assert high.monthly_cost > low.monthly_cost


def test_optimizer_reallocate_zero_budget_zeros_all():
    opt = BudgetOptimizer(cost_lines=[CostLine("a", 100), CostLine("b", 200)])
    new_lines = opt.reallocate(new_budget=0)
    assert all(c.monthly_cost == 0 for c in new_lines)


def test_optimizer_lowest_roi_lines():
    opt = BudgetOptimizer(cost_lines=[
        CostLine("good",  100, revenue_attributed=1000),
        CostLine("bad",   100, revenue_attributed=10),
        CostLine("ugly",  100, revenue_attributed=5),
    ])
    bottom2 = opt.lowest_roi_lines(n=2)
    names = [c.name for c in bottom2]
    assert names == ["ugly", "bad"]


# ── FinancialAgent ────────────────────────────────────────────────────────────


def test_agent_recommends_cut_on_low_runway():
    metrics = FinancialMetrics(
        monthly_revenue=1000, monthly_costs=20_000, cash_on_hand=10_000,  # 0.5 months
        cost_lines=[
            CostLine("waste", 5000, revenue_attributed=10),
            CostLine("growth", 5000, revenue_attributed=25_000, category="sales"),
        ],
    )
    agent = FinancialAgent()
    recs = agent.assess(metrics)
    # The lowest-ROI line should be cut
    assert recs["waste"] == Recommendation.CUT


def test_agent_recommends_scale_for_high_roi_sales():
    metrics = FinancialMetrics(
        monthly_revenue=200_000, monthly_costs=50_000, cash_on_hand=500_000,
        cost_lines=[
            CostLine("ads", 10_000, revenue_attributed=100_000, category="sales"),
        ],
    )
    agent = FinancialAgent()
    recs = agent.assess(metrics)
    assert recs["ads"] == Recommendation.SCALE


def test_agent_recommends_investigate_low_margin():
    metrics = FinancialMetrics(
        monthly_revenue=100_000, monthly_costs=80_000, cash_on_hand=500_000,
        cost_lines=[
            CostLine("gpu", 70_000, revenue_attributed=50_000, category="cogs"),
        ],
    )
    agent = FinancialAgent()
    recs = agent.assess(metrics)
    # Margin = (100k - 70k)/100k = 0.30 < 0.40 threshold
    assert recs["gpu"] == Recommendation.INVESTIGATE


def test_agent_investigates_uppercase_cogs_categories():
    metrics = FinancialMetrics(
        monthly_revenue=100_000,
        monthly_costs=80_000,
        cash_on_hand=500_000,
        cost_lines=[
            CostLine("gpu", 70_000, revenue_attributed=50_000, category="COGS"),
        ],
    )

    agent = FinancialAgent()
    recs = agent.assess(metrics)

    assert recs["gpu"] == Recommendation.INVESTIGATE


def test_agent_holds_strategic_low_roi_lines():
    metrics = FinancialMetrics(
        monthly_revenue=100_000, monthly_costs=50_000, cash_on_hand=1_000_000,
        cost_lines=[
            CostLine("brand_research", 5000, revenue_attributed=100, category="R&D"),
        ],
    )
    agent = FinancialAgent(strategic_lines={"brand_research"})
    recs = agent.assess(metrics)
    # Without strategic flag this would be CUT; with flag it must HOLD
    assert recs["brand_research"] == Recommendation.HOLD


def test_agent_explain_returns_human_readable():
    metrics = FinancialMetrics(
        monthly_revenue=10_000, monthly_costs=8000, cash_on_hand=100_000,
        cost_lines=[CostLine("api", 1000, revenue_attributed=5000, category="operations")],
    )
    agent = FinancialAgent()
    lines = agent.explain(metrics)
    assert any("Runway" in line for line in lines)
    assert any("api" in line for line in lines)
