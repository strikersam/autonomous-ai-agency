"""Tests for agent/user_research_skill.py.

Covers all four capabilities (Plan, Synthesize, Qual, Quant) plus tool
registration via the agent capability registry.
"""
from __future__ import annotations

import pytest

from agent.user_research_skill import (
    QuantAnalysis,
    QualAnalysis,
    ResearchBrief,
    ResearchHypothesis,
    ResearchMethod,
    ResearchObjective,
    ResearchPlan,
    _classify_sentiment,
    _extract_keywords,
    _sample_size_for_proportion,
    analyze_qualitative,
    analyze_quantitative,
    auto_register,
    plan_research,
    register_user_research_tools,
    synthesize_research,
)


# ── Plan ───────────────────────────────────────────────────────────────────────


class TestPlanResearch:
    def test_minimal_plan(self) -> None:
        plan = plan_research(
            title="Why do users churn after onboarding?",
            primary_question="What causes week-1 churn?",
            audience="Product team",
            objectives=[
                {"statement": "Identify the top 3 friction points in onboarding"},
            ],
            methods=[
                {"method": "interview", "target_participants": 8, "rationale": "Deep dive into pain"},
            ],
        )
        assert isinstance(plan, ResearchPlan)
        assert plan.title.startswith("Why")
        assert plan.objectives[0].id == "OBJ-1"
        assert plan.methods[0].id  # auto-assigned
        assert plan.target_sample_size >= 8  # at least the method target

    def test_sample_size_grows_with_population(self) -> None:
        small = _sample_size_for_proportion(population_size=100, margin_of_error=0.05)
        large = _sample_size_for_proportion(population_size=1_000_000, margin_of_error=0.05)
        assert small > 0
        assert large > small  # finite correction means small N needs more

    def test_objective_ids_must_be_unique(self) -> None:
        with pytest.raises(Exception):  # ValidationError
            plan_research(
                title="T",
                primary_question="Q that is long enough",
                audience="A",
                objectives=[
                    {"id": "OBJ-1", "statement": "A first objective statement."},
                    {"id": "OBJ-1", "statement": "A second objective statement."},
                ],
                methods=[{"method": "survey", "target_participants": 5}],
            )

    def test_method_validation(self) -> None:
        with pytest.raises(Exception):
            ResearchMethod(method="not_a_method", target_participants=1)

    def test_hypothesis_default_null(self) -> None:
        plan = plan_research(
            title="T",
            primary_question="Q that is long enough",
            audience="A",
            objectives=[{"statement": "A first objective statement."}],
            methods=[{"method": "survey", "target_participants": 5}],
            hypotheses=[{"statement": "Users prefer the new flow over the old."}],
        )
        assert plan.hypotheses[0].null_alternative is True
        assert plan.hypotheses[0].id == "HYP-1"

    def test_scope_in_out_default_empty(self) -> None:
        plan = plan_research(
            title="T",
            primary_question="Q that is long enough",
            audience="A",
            objectives=[{"statement": "A first objective statement."}],
            methods=[{"method": "survey", "target_participants": 5}],
        )
        assert plan.scope_in == []
        assert plan.scope_out == []

    def test_extra_field_rejected(self) -> None:
        with pytest.raises(Exception):
            ResearchObjective.model_validate({
                "id": "OBJ-1",
                "statement": "A first objective statement.",
                "secret_field": "should be rejected",
            })

    def test_timeline_bounds(self) -> None:
        with pytest.raises(Exception):
            plan_research(
                title="T",
                primary_question="Q that is long enough",
                audience="A",
                objectives=[{"statement": "A first objective statement."}],
                methods=[{"method": "survey", "target_participants": 5}],
                timeline_days=0,
            )

    def test_horizon_creation(self) -> None:
        plan = plan_research(
            title="T",
            primary_question="Q that is long enough",
            audience="A",
            objectives=[{"statement": "A first objective statement."}],
            methods=[{"method": "survey", "target_participants": 5}],
        )
        assert plan.created_at.endswith("+00:00") or "T" in plan.created_at


# ── Qual ───────────────────────────────────────────────────────────────────────


class TestAnalyzeQualitative:
    TRANSCRIPTS = [
        "The new dashboard is great, I love the new layout. But login is broken and confusing.",
        "Wish I could export data faster. The export is slow and the UI is hard to navigate.",
        "I love the new feature, it's very fast. But I hate the broken search functionality.",
        "Login works fine for me. Wish there was a dark mode. Otherwise good.",
        "The whole experience is frustrating. Login is broken, search is broken, export is slow.",
    ]

    def test_participant_count(self) -> None:
        result = analyze_qualitative(source="5 customer interviews", transcripts=self.TRANSCRIPTS)
        assert isinstance(result, QualAnalysis)
        assert result.participant_count == 5
        assert len(result.quotes) == 5

    def test_pain_points_extracted(self) -> None:
        result = analyze_qualitative(source="5 customer interviews", transcripts=self.TRANSCRIPTS)
        # 'broken' appears in 3 transcripts
        names = {p.name for p in result.pain_points}
        assert "broken" in names
        broken = next(p for p in result.pain_points if p.name == "broken")
        assert broken.frequency >= 3

    def test_desires_extracted(self) -> None:
        result = analyze_qualitative(source="5 customer interviews", transcripts=self.TRANSCRIPTS)
        names = {d.name for d in result.desires}
        assert "love" in names or "wish" in names

    def test_auto_participant_ids(self) -> None:
        result = analyze_qualitative(source="t", transcripts=["hi", "hello"])
        assert result.quotes[0].participant_id == "P1"
        assert result.quotes[1].participant_id == "P2"

    def test_custom_participant_ids(self) -> None:
        result = analyze_qualitative(
            source="t",
            transcripts=["a", "b"],
            participant_ids=["alice", "bob"],
        )
        assert result.quotes[0].participant_id == "alice"

    def test_mismatched_ids_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_qualitative(
                source="t",
                transcripts=["a", "b"],
                participant_ids=["alice"],
            )

    def test_empty_transcripts_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_qualitative(source="t", transcripts=[])

    def test_sentiment_assignment(self) -> None:
        result = analyze_qualitative(
            source="t",
            transcripts=[
                "I love this, it's amazing and great",
                "I hate this, it's terrible and broken",
                "I went to the store",
            ],
        )
        sentiments = [q.sentiment for q in result.quotes]
        assert sentiments[0] == "positive"
        assert sentiments[1] == "negative"
        assert sentiments[2] == "neutral"

    def test_min_theme_frequency_filter(self) -> None:
        # With min_theme_frequency=10, no theme should qualify
        result = analyze_qualitative(
            source="t",
            transcripts=self.TRANSCRIPTS,
            min_theme_frequency=10,
        )
        assert result.pain_points == []
        assert result.desires == []

    def test_custom_pain_keywords(self) -> None:
        result = analyze_qualitative(
            source="t",
            transcripts=["the cat is awesome", "the dog is awesome"],
            pain_point_keywords=["cat"],
        )
        cat_theme = [p for p in result.pain_points if p.name == "cat"]
        assert len(cat_theme) == 1
        assert cat_theme[0].frequency == 1

    def test_horizon_creation(self) -> None:
        result = analyze_qualitative(source="t", transcripts=["a", "b"])
        assert "T" in result.created_at


# ── Quant ──────────────────────────────────────────────────────────────────────


class TestAnalyzeQuantitative:
    def test_basic_stats(self) -> None:
        result = analyze_quantitative(
            source="NPS survey",
            values=[1, 2, 3, 4, 5],
            metric_name="NPS",
            metric_type="rating",
        )
        assert isinstance(result, QuantAnalysis)
        assert result.sample_size == 5
        assert result.mean == 3.0
        assert result.median == 3.0
        assert result.stdev == pytest.approx(1.581, rel=0.01)
        assert result.min_value == 1.0
        assert result.max_value == 5.0

    def test_distribution_buckets(self) -> None:
        result = analyze_quantitative(
            source="t",
            values=[1, 2, 3, 4, 5],
            metric_name="NPS",
            metric_type="rating",
            bins=5,
        )
        assert sum(result.distribution.values()) == 5

    def test_categorical_distribution(self) -> None:
        result = analyze_quantitative(
            source="t",
            values=[1, 1, 2, 2, 2, 3],
            metric_name="answer_choice",
            metric_type="count",
        )
        assert result.distribution == {"1": 2, "2": 3, "3": 1}

    def test_segments_validation(self) -> None:
        result = analyze_quantitative(
            source="t",
            values=[1, 2, 3, 4, 5],
            metric_name="NPS",
            metric_type="rating",
            segments=[
                {"name": "enterprise", "count": 3, "mean": 4.0, "median": 4.0, "stdev": 0.5},
                {"name": "smb", "count": 2, "mean": 2.5, "median": 2.5, "stdev": 0.5},
            ],
        )
        assert len(result.segments) == 2
        assert result.segments[0].name == "enterprise"

    def test_empty_values_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_quantitative(source="t", values=[], metric_name="x")

    def test_invalid_bins_raises(self) -> None:
        with pytest.raises(ValueError):
            analyze_quantitative(source="t", values=[1, 2], metric_name="x", bins=1)
        with pytest.raises(ValueError):
            analyze_quantitative(source="t", values=[1, 2], metric_name="x", bins=100)

    def test_single_value(self) -> None:
        result = analyze_quantitative(source="t", values=[5.0], metric_name="x")
        assert result.mean == 5.0
        assert result.median == 5.0
        assert result.stdev == 0.0  # pstdev of single value

    def test_invalid_metric_type(self) -> None:
        with pytest.raises(Exception):
            analyze_quantitative(source="t", values=[1, 2], metric_name="x", metric_type="bogus")  # type: ignore[arg-type]


# ── Synthesize ─────────────────────────────────────────────────────────────────


class TestSynthesizeResearch:
    def test_quant_only(self) -> None:
        quant = analyze_quantitative(
            source="NPS",
            values=[9, 9, 8, 10, 9, 8, 9],
            metric_name="NPS",
            metric_type="rating",
        )
        brief = synthesize_research(title="Q4 NPS results", quant=quant)
        assert isinstance(brief, ResearchBrief)
        assert "NPS" in brief.executive_summary
        assert any("NPS" in f for f in brief.key_findings)
        assert brief.confidence == "medium"

    def test_qual_only(self) -> None:
        qual = analyze_qualitative(
            source="5 interviews",
            transcripts=[
                "I love the new design, but login is broken",
                "Login is broken and slow",
                "Login is broken, otherwise good",
            ],
        )
        brief = synthesize_research(title="Onboarding pain", qual=qual)
        assert "broken" in {p.name for p in qual.pain_points} or any(
            "broken" in f for f in brief.key_findings
        )
        assert any("broken" in r for r in brief.recommendations) or len(brief.recommendations) >= 1

    def test_combined_qual_quant(self) -> None:
        quant = analyze_quantitative(
            source="t", values=[3, 4, 5], metric_name="rating", metric_type="rating"
        )
        qual = analyze_qualitative(
            source="t", transcripts=["love it, very easy", "love it, very easy", "hate login, broken"],
        )
        brief = synthesize_research(title="Combined", quant=quant, qual=qual)
        assert "n=3" in brief.executive_summary
        assert "3 participants" in brief.executive_summary
        assert len(brief.key_findings) >= 2

    def test_user_supplied_findings_override(self) -> None:
        brief = synthesize_research(
            title="t",
            key_findings=["Custom finding 1", "Custom finding 2"],
            recommendations=["Custom rec 1"],
        )
        assert brief.key_findings == ["Custom finding 1", "Custom finding 2"]
        assert brief.recommendations == ["Custom rec 1"]

    def test_segment_gap_in_findings(self) -> None:
        quant = analyze_quantitative(
            source="t", values=[3, 3, 3, 3, 3], metric_name="rating",
            segments=[
                {"name": "enterprise", "count": 3, "mean": 5.0, "median": 5.0, "stdev": 0.0},
                {"name": "smb", "count": 2, "mean": 2.0, "median": 2.0, "stdev": 0.0},
            ],
        )
        brief = synthesize_research(title="t", quant=quant)
        assert any("enterprise" in f and "smb" in f for f in brief.key_findings)

    def test_no_data_still_produces_brief(self) -> None:
        brief = synthesize_research(title="Empty")
        assert "Empty" in brief.executive_summary
        assert len(brief.key_findings) >= 1
        assert len(brief.recommendations) >= 1

    def test_confidence_levels(self) -> None:
        for level in ("high", "medium", "low"):
            brief = synthesize_research(title="t", confidence=level)  # type: ignore[arg-type]
            assert brief.confidence == level


# ── Helpers ────────────────────────────────────────────────────────────────────


class TestHelpers:
    def test_sample_size_increases_with_stricter_margin(self) -> None:
        loose = _sample_size_for_proportion(margin_of_error=0.10)
        tight = _sample_size_for_proportion(margin_of_error=0.01)
        assert tight > loose

    def test_extract_keywords_stops_words(self) -> None:
        kws = _extract_keywords("the quick brown fox jumps over the lazy dog", top_n=5)
        words = [w for w, _ in kws]
        assert "the" not in words
        assert "fox" in words or "quick" in words

    def test_extract_keywords_handles_empty(self) -> None:
        assert _extract_keywords("") == []

    def test_classify_sentiment(self) -> None:
        assert _classify_sentiment("I love this") == "positive"
        assert _classify_sentiment("This is terrible") == "negative"
        assert _classify_sentiment("The sky is blue") == "neutral"


# ── Tool registration ─────────────────────────────────────────────────────────


class TestRegistration:
    def test_register_user_research_tools(self) -> None:
        from agent.capability_registry import ToolRegistry
        registry = ToolRegistry()
        count = register_user_research_tools(registry)
        assert count == 4
        names = {t.name for t in registry.list_all()}
        assert names == {
            "user_research_plan",
            "user_research_qual",
            "user_research_quant",
            "user_research_synthesize",
        }

    def test_capability_discovery(self) -> None:
        from agent.capability_registry import ToolRegistry
        registry = ToolRegistry()
        register_user_research_tools(registry)
        qual_tools = registry.find_by_capability("qualitative")
        quant_tools = registry.find_by_capability("quantitative")
        plan_tools = registry.find_by_capability("plan")
        synth_tools = registry.find_by_capability("synthesis")
        assert len(qual_tools) == 1
        assert len(quant_tools) == 1
        assert len(plan_tools) == 1
        assert len(synth_tools) == 1

    def test_all_have_user_research_capability(self) -> None:
        from agent.capability_registry import ToolRegistry
        registry = ToolRegistry()
        register_user_research_tools(registry)
        ur_tools = registry.find_by_capability("user_research")
        assert len(ur_tools) == 4

    def test_openai_export(self) -> None:
        from agent.capability_registry import ToolRegistry
        registry = ToolRegistry()
        register_user_research_tools(registry)
        oa = registry.to_openai_tools(capabilities=["user_research"])
        assert len(oa) == 4
        assert all(t["type"] == "function" for t in oa)
        assert all("parameters" in t["function"] for t in oa)

    def test_auto_register_idempotent(self) -> None:
        # First call registers, second call is a no-op
        first = auto_register()
        second = auto_register()
        # first could be 4 or 0 depending on global state from other tests,
        # but the *delta* between consecutive calls should never register twice.
        if first > 0:
            assert second == 0
        # Either way, exactly 4 user_research tools exist
        from agent.capability_registry import get_tool_registry
        registry = get_tool_registry()
        ur_tools = registry.find_by_capability("user_research")
        assert len(ur_tools) == 4


class TestEndToEnd:
    def test_plan_then_qual_then_synthesize(self) -> None:
        plan = plan_research(
            title="Onboarding friction",
            primary_question="What blocks first-week activation?",
            audience="Product",
            objectives=[{"statement": "Identify the top 3 first-week blockers."}],
            methods=[{"method": "interview", "target_participants": 6}],
        )
        qual = analyze_qualitative(
            source=f"{plan.target_sample_size} customer interviews",
            transcripts=[
                "Login is broken and slow. Hate it.",
                "Login is broken, otherwise good.",
                "Love the new dashboard, but login is broken.",
            ],
        )
        brief = synthesize_research(title="First-Week Friction", qual=qual)
        assert "broken" in {p.name for p in qual.pain_points}
        assert len(brief.key_findings) >= 1
        assert brief.qual_snapshot == qual
