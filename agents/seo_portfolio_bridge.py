"""
SEO-to-Portfolio Bridge — Convert SEO audit findings into portfolio initiatives,
roadmap plans, and agile sprints.

This module connects the SEO/GEO/AIO audit engine (which produces SeoDelegationTask
objects with WSJF scores) to the agentic portfolio/agile system, enabling SEO
remediation work to compete for capacity and be planned on the same roadmap as
product initiatives.

Key conversions:
- SeoDelegationTask → Initiative (portfolio epic)
- Delegation plan → Now/Next/Later roadmap
- Delegation plan → Sprint plan with UserStory per task

Design aligns with SAFe WSJF prioritisation used in both systems.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from agents.agile_sprints import AgileManager, AgileSprint, UserStory
from agents.portfolio import (
    CapacityAllocation,
    Initiative,
    InitiativeStatus,
    PortfolioManager,
    RoadmapHorizon,
)
from models.seo_audit import SeoDelegationTask


# =============================================================================
# CONVERSION: SeoDelegationTask → Initiative
# =============================================================================

def delegation_task_to_initiative(
    task: SeoDelegationTask,
    *,
    audit_id: str,
    website_url: str,
    source: str = "seo_audit",
) -> Initiative:
    """Convert a SeoDelegationTask into a portfolio Initiative.

    The WSJF components (business_value, time_criticality, risk_reduction, job_size)
    are already computed in SeoDelegationTask using the same modified-Fibonacci
    scale as agents/portfolio.py, so the conversion is lossless.

    Args:
        task: The SEO delegation work package.
        audit_id: ID of the originating SEO audit (for traceability).
        website_url: The audited website URL (for context in description).
        source: Provenance tag, defaults to "seo_audit".

    Returns:
        A portfolio Initiative ready to be registered in PortfolioManager.
    """
    description = (
        f"SEO remediation from audit `{audit_id}` of {website_url}.\n\n"
        f"**Category:** {task.category}\n"
        f"**Pillar:** {task.pillar}\n"
        f"**URLs affected:** {task.urls_affected}\n"
        f"**Effort:** {task.effort}\n"
        f"**Suggested specialist:** {task.suggested_specialist}\n"
        f"**Auto-fixable:** {'Yes' if task.auto_fixable else 'No'}\n\n"
        f"### Instructions\n{task.instructions}\n\n"
        f"### Sample URLs\n" + "\n".join(f"- {u}" for u in task.sample_urls)
    )

    return Initiative(
        initiative_id=f"seo-{task.task_key}",
        title=f"[SEO] {task.title}",
        description=description,
        business_value=task.business_value,
        time_criticality=task.time_criticality,
        risk_reduction=task.risk_reduction,
        job_size=task.job_size,
        status=InitiativeStatus.PROPOSED,
        horizon=RoadmapHorizon.UNSCHEDULED,
        source=source,
        estimated_monthly_value=task.estimated_monthly_value,
        rationale=(
            f"Auto-generated from SEO audit {audit_id}. "
            f"WSJF={task.wsjf_score:.2f} (CoD={task.business_value + task.time_criticality + task.risk_reduction}, "
            f"JobSize={task.job_size}). "
            f"Estimated monthly value: ${task.estimated_monthly_value:,.0f}"
        ),
    )


def delegation_plan_to_initiatives(
    tasks: List[SeoDelegationTask],
    *,
    audit_id: str,
    website_url: str,
) -> List[Initiative]:
    """Convert a full delegation plan (list of SeoDelegationTask) to Initiatives.

    Args:
        tasks: List of delegation tasks from an audit report.
        audit_id: ID of the originating SEO audit.
        website_url: The audited website URL.

    Returns:
        List of Initiatives, one per delegation task.
    """
    return [
        delegation_task_to_initiative(
            task, audit_id=audit_id, website_url=website_url
        )
        for task in tasks
    ]


# =============================================================================
# ROADMAP FROM SEO FINDINGS
# =============================================================================

@dataclass
class SeoRoadmapPlan:
    """Result of laying SEO initiatives onto a Now/Next/Later roadmap."""

    roadmap: dict[str, List[Initiative]]  # horizon -> initiatives
    portfolio: PortfolioManager
    total_initiatives: int
    scheduled_initiatives: int
    unscheduled_initiatives: int
    capacity_per_horizon: int

    def to_markdown(self) -> str:
        """Render the SEO roadmap as markdown."""
        lines = [
            "# SEO Remediation Roadmap (Now/Next/Later)",
            "",
            f"**Capacity per horizon:** {self.capacity_per_horizon} job-size units",
            f"**Total initiatives:** {self.total_initiatives} | "
            f"**Scheduled:** {self.scheduled_initiatives} | "
            f"**Unscheduled:** {self.unscheduled_initiatives}",
            "",
        ]

        for horizon in [RoadmapHorizon.NOW, RoadmapHorizon.NEXT, RoadmapHorizon.LATER]:
            items = self.roadmap.get(horizon.value, [])
            lines.append(f"## {horizon.value.upper()}")
            if items:
                lines.append("| Initiative | WSJF | Job Size | Monthly Value |")
                lines.append("|------------|------|----------|---------------|")
                for init in items:
                    mv = init.estimated_monthly_value
                    lines.append(
                        f"| {init.title} | {init.wsjf:.2f} | {init.job_size} | ${mv:,.0f} |"
                    )
            else:
                lines.append("_No initiatives scheduled in this horizon_")
            lines.append("")

        unscheduled = self.roadmap.get(RoadmapHorizon.UNSCHEDULED.value, [])
        if unscheduled:
            lines.append("## UNSCHEDULED (Backlog)")
            lines.append("| Initiative | WSJF | Job Size | Monthly Value |")
            lines.append("|------------|------|----------|---------------|")
            for init in unscheduled:
                mv = init.estimated_monthly_value
                lines.append(
                    f"| {init.title} | {init.wsjf:.2f} | {init.job_size} | ${mv:,.0f} |"
                )
            lines.append("")

        return "\n".join(lines)


def build_seo_roadmap(
    tasks: List[SeoDelegationTask],
    *,
    audit_id: str,
    website_url: str,
    capacity_per_horizon: int = 20,
) -> SeoRoadmapPlan:
    """Convert SEO delegation plan to a portfolio and lay it onto a Now/Next/Later roadmap.

    This is the primary entry point for "turn SEO backlog into roadmap" — it takes
    the raw audit findings, converts them to portfolio initiatives, and applies
    WSJF-based capacity allocation across three horizons.

    Args:
        tasks: List of SeoDelegationTask from an audit's delegation_plan.
        audit_id: ID of the originating SEO audit.
        website_url: The audited website URL.
        capacity_per_horizon: Job-size capacity for each of Now/Next/Later (default 20).

    Returns:
        SeoRoadmapPlan containing the populated PortfolioManager and roadmap layout.
    """
    portfolio = PortfolioManager()
    initiatives = delegation_plan_to_initiatives(
        tasks, audit_id=audit_id, website_url=website_url
    )

    for init in initiatives:
        portfolio.register(init)

    roadmap = portfolio.plan_roadmap(capacity_per_horizon=capacity_per_horizon)

    scheduled = sum(len(v) for k, v in roadmap.items() if k != RoadmapHorizon.UNSCHEDULED.value)
    unscheduled = len(roadmap.get(RoadmapHorizon.UNSCHEDULED.value, []))

    return SeoRoadmapPlan(
        roadmap=roadmap,
        portfolio=portfolio,
        total_initiatives=len(initiatives),
        scheduled_initiatives=scheduled,
        unscheduled_initiatives=unscheduled,
        capacity_per_horizon=capacity_per_horizon,
    )


# =============================================================================
# SPRINT PLANNING FROM SEO FINDINGS
# =============================================================================

@dataclass
class SeoSprintPlan:
    """Result of planning an agile sprint from SEO initiatives."""

    sprint: AgileSprint
    plan: 'SprintPlan'  # from agents.agile_ceremonies
    portfolio: PortfolioManager
    capacity_used: int
    capacity_total: int

    def to_markdown(self) -> str:
        """Render the sprint plan as markdown."""
        return self.plan.to_markdown()


def plan_seo_sprint(
    tasks: List[SeoDelegationTask],
    *,
    audit_id: str,
    website_url: str,
    sprint_name: str,
    sprint_goal: str = "",
    capacity: int = 20,
    agile_manager: Optional[AgileManager] = None,
) -> SeoSprintPlan:
    """Convert SEO delegation plan to a portfolio and allocate capacity into a sprint.

    Creates a new AgileSprint with one UserStory per committed initiative,
    links each initiative to the sprint, and leaves the sprint in PLANNING state.

    Args:
        tasks: List of SeoDelegationTask from an audit's delegation_plan.
        audit_id: ID of the originating SEO audit.
        website_url: The audited website URL.
        sprint_name: Name for the new sprint (e.g., "Sprint 42 - SEO Fixes").
        sprint_goal: Optional sprint goal description.
        capacity: Total job-size capacity for this sprint (default 20).
        agile_manager: Optional existing AgileManager; creates new if not provided.

    Returns:
        SeoSprintPlan with the sprint, allocation plan, and portfolio.
    """
    from agents.agile_ceremonies import plan_next_sprint, SprintPlan

    portfolio = PortfolioManager()
    initiatives = delegation_plan_to_initiatives(
        tasks, audit_id=audit_id, website_url=website_url
    )

    for init in initiatives:
        portfolio.register(init)

    if agile_manager is None:
        agile_manager = AgileManager()

    plan = plan_next_sprint(
        portfolio_mgr=portfolio,
        agile_mgr=agile_manager,
        name=sprint_name,
        goal=sprint_goal or f"SEO remediation from audit {audit_id}",
        capacity=capacity,
    )

    committed_job_size = sum(i.job_size for i in plan.committed)

    return SeoSprintPlan(
        sprint=plan.sprint,
        plan=plan,
        portfolio=portfolio,
        capacity_used=committed_job_size,
        capacity_total=capacity,
    )


# =============================================================================
# FULL PIPELINE: AUDIT → ROADMAP → SPRINT
# =============================================================================

@dataclass
class SeoToAgilePipelineResult:
    """Complete result of converting an SEO audit to portfolio + roadmap + sprint."""

    audit_id: str
    website_url: str
    initiatives: List[Initiative]
    roadmap: SeoRoadmapPlan
    sprint: Optional[SeoSprintPlan] = None

    def to_markdown(self) -> str:
        """Render the full pipeline result as markdown."""
        lines = [
            f"# SEO → Agile Pipeline for Audit `{self.audit_id}`",
            "",
            f"**Website:** {self.website_url}",
            f"**Initiatives created:** {len(self.initiatives)}",
            "",
            "## Roadmap",
            self.roadmap.to_markdown(),
        ]

        if self.sprint:
            lines.append("## Sprint Plan")
            lines.append(self.sprint.to_markdown())

        return "\n".join(lines)


def run_seo_to_agile_pipeline(
    tasks: List[SeoDelegationTask],
    *,
    audit_id: str,
    website_url: str,
    capacity_per_horizon: int = 20,
    sprint_capacity: int = 20,
    sprint_name: Optional[str] = None,
    sprint_goal: str = "",
    agile_manager: Optional[AgileManager] = None,
    create_sprint: bool = True,
) -> SeoToAgilePipelineResult:
    """Run the full pipeline: SEO delegation plan → Portfolio → Roadmap → (optional) Sprint.

    This is the "one call does it all" function for turning an SEO audit into
    actionable agile delivery artifacts.

    Args:
        tasks: List of SeoDelegationTask from an audit's delegation_plan.
        audit_id: ID of the originating SEO audit.
        website_url: The audited website URL.
        capacity_per_horizon: Job-size capacity for each roadmap horizon (default 20).
        sprint_capacity: Job-size capacity for the sprint (default 20).
        sprint_name: Name for the sprint; auto-generated if not provided.
        sprint_goal: Optional sprint goal description.
        agile_manager: Optional existing AgileManager.
        create_sprint: Whether to create a sprint plan (default True).

    Returns:
        SeoToAgilePipelineResult with portfolio, roadmap, and optional sprint.
    """
    portfolio = PortfolioManager()
    initiatives = delegation_plan_to_initiatives(
        tasks, audit_id=audit_id, website_url=website_url
    )

    for init in initiatives:
        portfolio.register(init)

    roadmap = portfolio.plan_roadmap(capacity_per_horizon=capacity_per_horizon)

    sprint = None
    if create_sprint:
        if agile_manager is None:
            agile_manager = AgileManager()
        sprint_name = sprint_name or f"SEO Sprint - {audit_id[:8]}"
        sprint = plan_seo_sprint(
            tasks,
            audit_id=audit_id,
            website_url=website_url,
            sprint_name=sprint_name,
            sprint_goal=sprint_goal or f"SEO remediation from audit {audit_id}",
            capacity=sprint_capacity,
            agile_manager=agile_manager,
        )

    # Reconstruct roadmap plan object with the same portfolio
    scheduled = sum(
        len(v) for k, v in roadmap.items() if k != RoadmapHorizon.UNSCHEDULED.value
    )
    unscheduled = len(roadmap.get(RoadmapHorizon.UNSCHEDULED.value, []))

    roadmap_plan = SeoRoadmapPlan(
        roadmap=roadmap,
        portfolio=portfolio,
        total_initiatives=len(initiatives),
        scheduled_initiatives=scheduled,
        unscheduled_initiatives=unscheduled,
        capacity_per_horizon=capacity_per_horizon,
    )

    return SeoToAgilePipelineResult(
        audit_id=audit_id,
        website_url=website_url,
        initiatives=initiatives,
        roadmap=roadmap_plan,
        sprint=sprint,
    )