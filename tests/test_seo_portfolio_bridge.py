"""tests/test_seo_portfolio_bridge.py - Tests for SEO → Portfolio/Agile bridge (issue #1356)."""
from __future__ import annotations

import pytest
from agents.seo_portfolio_bridge import (
    build_seo_roadmap,
    delegation_task_to_initiative,
    delegation_plan_to_initiatives,
    plan_seo_sprint,
    run_seo_to_agile_pipeline,
)
from agents.agile_sprints import AgileManager
from agents.portfolio import Initiative, RoadmapHorizon
from models.seo_audit import SeoDelegationTask, SeoIssuePriority


def _sample_delegation_tasks() -> list[SeoDelegationTask]:
    """Create sample delegation tasks for testing."""
    return [
        SeoDelegationTask(
            task_key="seo-fix-page-titles",
            title="Fix Page Titles findings: 3 finding type(s) across 15 URL hit(s)",
            priority="high",
            effort="M",
            pillar="technical",
            category="Page Titles",
            suggested_specialist="seo",
            check_codes=["title_missing", "title_too_short", "title_too_long"],
            urls_affected=15,
            auto_fixable=True,
            instructions="- Page Titles: Missing (5 URLs): Add unique, descriptive page titles\n- Page Titles: Too Short (5 URLs): Expand titles to 30-60 characters\n- Page Titles: Too Long (5 URLs): Truncate titles to under 60 characters",
            sample_urls=["https://example.com/page1", "https://example.com/page2"],
            estimated_monthly_value=5000.0,
            business_value=13,
            time_criticality=8,
            risk_reduction=5,
            job_size=5,
            wsjf_score=5.2,
        ),
        SeoDelegationTask(
            task_key="seo-fix-meta-descriptions",
            title="Fix Meta Descriptions findings: 2 finding type(s) across 10 URL hit(s)",
            priority="medium",
            effort="S",
            pillar="content",
            category="Meta Descriptions",
            suggested_specialist="seo",
            check_codes=["meta_description_missing", "meta_description_too_short"],
            urls_affected=10,
            auto_fixable=True,
            instructions="- Meta Descriptions: Missing (6 URLs): Add unique meta descriptions\n- Meta Descriptions: Too Short (4 URLs): Expand to 120-155 characters",
            sample_urls=["https://example.com/page3", "https://example.com/page4"],
            estimated_monthly_value=3000.0,
            business_value=8,
            time_criticality=5,
            risk_reduction=2,
            job_size=2,
            wsjf_score=7.5,
        ),
        SeoDelegationTask(
            task_key="seo-fix-security-headers",
            title="Fix Security Headers findings: 1 finding type(s) across 20 URL hit(s)",
            priority="high",
            effort="L",
            pillar="security",
            category="Security Headers",
            suggested_specialist="devops",
            check_codes=["security_headers_missing"],
            urls_affected=20,
            auto_fixable=False,
            instructions="- Security Headers: Missing (20 URLs): Add CSP, HSTS, X-Frame-Options headers",
            sample_urls=["https://example.com/"],
            estimated_monthly_value=8000.0,
            business_value=20,
            time_criticality=8,
            risk_reduction=8,
            job_size=8,
            wsjf_score=4.5,
        ),
    ]


class TestDelegationTaskToInitiative:
    def test_conversion_preserves_wsjf_components(self):
        tasks = _sample_delegation_tasks()
        task = tasks[0]

        initiative = delegation_task_to_initiative(
            task, audit_id="audit_123", website_url="https://example.com"
        )

        assert initiative.initiative_id == "seo-seo-fix-page-titles"
        assert initiative.title == "[SEO] Fix Page Titles findings: 3 finding type(s) across 15 URL hit(s)"
        assert initiative.business_value == task.business_value
        assert initiative.time_criticality == task.time_criticality
        assert initiative.risk_reduction == task.risk_reduction
        assert initiative.job_size == task.job_size
        assert initiative.wsjf == pytest.approx(task.wsjf_score, rel=0.01)
        assert initiative.source == "seo_audit"
        assert "audit_123" in initiative.rationale
        assert "https://example.com" in initiative.description

    def test_conversion_all_tasks(self):
        tasks = _sample_delegation_tasks()

        initiatives = delegation_plan_to_initiatives(
            tasks, audit_id="audit_123", website_url="https://example.com"
        )

        assert len(initiatives) == 3
        for init, task in zip(initiatives, tasks):
            assert init.initiative_id == f"seo-{task.task_key}"
            assert init.business_value == task.business_value
            assert init.time_criticality == task.time_criticality
            assert init.risk_reduction == task.risk_reduction
            assert init.job_size == task.job_size


class TestSeoRoadmap:
    def test_build_roadmap_basic(self):
        tasks = _sample_delegation_tasks()

        roadmap = build_seo_roadmap(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            capacity_per_horizon=20,
        )

        assert roadmap.total_initiatives == 3
        assert roadmap.capacity_per_horizon == 20
        assert roadmap.portfolio.initiative_count == 3

        # All three should fit in NOW (total job_size = 5+2+8=15 <= 20)
        now_items = roadmap.roadmap[RoadmapHorizon.NOW.value]
        assert len(now_items) == 3
        assert roadmap.scheduled_initiatives == 3
        assert roadmap.unscheduled_initiatives == 0

    def test_build_roadmap_capacity_constraint(self):
        tasks = _sample_delegation_tasks()

        # Capacity 10 - only the two smallest (job_size 2 and 5) fit in NOW
        roadmap = build_seo_roadmap(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            capacity_per_horizon=10,
        )

        now_items = roadmap.roadmap[RoadmapHorizon.NOW.value]
        next_items = roadmap.roadmap[RoadmapHorizon.NEXT.value]
        later_items = roadmap.roadmap[RoadmapHorizon.LATER.value]
        unscheduled = roadmap.roadmap[RoadmapHorizon.UNSCHEDULED.value]

        # Should fit job_size 2 + 5 = 7 in NOW, leaving 3 capacity
        # Job size 8 goes to NEXT
        assert len(now_items) == 2
        assert len(next_items) == 1
        assert len(later_items) == 0
        assert len(unscheduled) == 0

    def test_roadmap_markdown_render(self):
        tasks = _sample_delegation_tasks()

        roadmap = build_seo_roadmap(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            capacity_per_horizon=20,
        )

        md = roadmap.to_markdown()
        assert "NOW" in md
        assert "NEXT" in md
        assert "LATER" in md
        assert "SEO" in md
        assert "WSJF" in md


class TestSeoSprint:
    def test_plan_sprint_basic(self):
        tasks = _sample_delegation_tasks()

        sprint = plan_seo_sprint(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            sprint_name="Sprint 1 - SEO",
            capacity=20,
        )

        assert sprint.sprint.name == "Sprint 1 - SEO"
        assert sprint.sprint.status.value == "planning"
        assert sprint.capacity_total == 20
        # All three fit (15 total job_size)
        assert sprint.capacity_used == 15
        assert len(sprint.plan.committed) == 3
        assert len(sprint.plan.deferred) == 0

        # Check stories created
        assert len(sprint.sprint._stories) == 3
        for story in sprint.sprint._stories.values():
            assert story.story_points > 0

    def test_plan_sprint_capacity_constraint(self):
        tasks = _sample_delegation_tasks()

        sprint = plan_seo_sprint(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            sprint_name="Sprint 1 - SEO",
            capacity=10,
        )

        # Only 2+5=7 fits, 8 is deferred
        assert sprint.capacity_used == 7
        assert len(sprint.plan.committed) == 2
        assert len(sprint.plan.deferred) == 1

    def test_sprint_links_initiatives(self):
        tasks = _sample_delegation_tasks()

        sprint = plan_seo_sprint(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            sprint_name="Sprint 1 - SEO",
            capacity=20,
        )

        # Each committed initiative should have the sprint linked
        for init in sprint.plan.committed:
            assert sprint.sprint.sprint_id in init.sprint_ids

    def test_sprint_markdown_render(self):
        tasks = _sample_delegation_tasks()

        sprint = plan_seo_sprint(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            sprint_name="Sprint 1 - SEO",
            capacity=20,
        )

        md = sprint.to_markdown()
        assert "Sprint 1 - SEO" in md
        assert "Committed" in md
        assert "WSJF" in md


class TestFullPipeline:
    def test_pipeline_basic(self):
        tasks = _sample_delegation_tasks()

        result = run_seo_to_agile_pipeline(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            capacity_per_horizon=20,
            sprint_capacity=20,
            sprint_name="Sprint 1 - SEO",
        )

        assert result.audit_id == "audit_123"
        assert result.website_url == "https://example.com"
        assert len(result.initiatives) == 3
        assert result.roadmap.total_initiatives == 3
        assert result.sprint is not None
        assert result.sprint.sprint.name == "Sprint 1 - SEO"

    def test_pipeline_without_sprint(self):
        tasks = _sample_delegation_tasks()

        result = run_seo_to_agile_pipeline(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            capacity_per_horizon=20,
            sprint_capacity=20,
            create_sprint=False,
        )

        assert result.sprint is None
        assert result.roadmap.total_initiatives == 3

    def test_pipeline_markdown_render(self):
        tasks = _sample_delegation_tasks()

        result = run_seo_to_agile_pipeline(
            tasks,
            audit_id="audit_123",
            website_url="https://example.com",
            capacity_per_horizon=20,
            sprint_capacity=20,
            sprint_name="Sprint 1 - SEO",
        )

        md = result.to_markdown()
        assert "SEO → Agile Pipeline" in md
        assert "Roadmap" in md
        assert "Sprint Plan" in md


class TestIntegrationWithAgileManager:
    def test_sprint_uses_shared_agile_manager(self):
        tasks = _sample_delegation_tasks()
        agile_mgr = AgileManager()

        sprint1 = plan_seo_sprint(
            tasks,
            audit_id="audit_1",
            website_url="https://example.com",
            sprint_name="Sprint 1",
            capacity=20,
            agile_manager=agile_mgr,
        )

        sprint2 = plan_seo_sprint(
            tasks,
            audit_id="audit_2",
            website_url="https://example.com",
            sprint_name="Sprint 2",
            capacity=20,
            agile_manager=agile_mgr,
        )

        # Both sprints should be in the same manager
        assert agile_mgr.sprint_count == 2
        assert sprint1.sprint.sprint_id in agile_mgr._sprints
        assert sprint2.sprint.sprint_id in agile_mgr._sprints