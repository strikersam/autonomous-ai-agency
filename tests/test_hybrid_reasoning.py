"""Tests for agents.hybrid_reasoning — Hybrid AI."""

from __future__ import annotations

import pytest

from agents.hybrid_reasoning import (
    ConfidenceLevel,
    DeterministicEngine,
    HybridSystem,
    LLMReasoner,
    ReasoningMode,
    ReasoningResult,
    Rule,
)


def _make_rule(name: str = "test", priority: int = 0) -> Rule:
    return Rule(
        name=name,
        condition=lambda inputs: inputs.get("trigger") == name,
        action=lambda inputs: f"handled_{name}",
        priority=priority,
    )


class TestRule:
    def test_rule_executes_when_condition_true(self):
        r = Rule("greet", lambda i: i.get("say") == "hello", lambda i: "world")
        assert r.condition({"say": "hello"}) is True
        assert r.action({"say": "hello"}) == "world"

    def test_rule_skips_when_condition_false(self):
        r = Rule("greet", lambda i: i.get("say") == "hello", lambda i: "world")
        assert r.condition({"say": "bye"}) is False


class TestReasoningResult:
    def test_is_confident_for_high(self):
        r = ReasoningResult(answer="x", mode=ReasoningMode.DETERMINISTIC, confidence=ConfidenceLevel.HIGH)
        assert r.is_confident is True

    def test_is_confident_for_low(self):
        r = ReasoningResult(answer="x", mode=ReasoningMode.LLM, confidence=ConfidenceLevel.LOW)
        assert r.is_confident is False


class TestDeterministicEngine:
    def test_evaluate_matches_first_rule(self):
        engine = DeterministicEngine(rules=[_make_rule("alpha"), _make_rule("beta")])
        result = engine.evaluate({"trigger": "alpha"})
        assert result is not None
        assert result.answer == "handled_alpha"
        assert result.mode == ReasoningMode.DETERMINISTIC

    def test_evaluate_respects_priority(self):
        engine = DeterministicEngine(rules=[
            Rule("low", lambda i: True, lambda i: "low", priority=0),
            Rule("high", lambda i: True, lambda i: "high", priority=10),
        ])
        result = engine.evaluate({})
        assert result.answer == "high"

    def test_evaluate_returns_none_when_no_match(self):
        engine = DeterministicEngine(rules=[_make_rule("alpha")])
        assert engine.evaluate({"trigger": "nope"}) is None

    def test_evaluate_skips_errors(self):
        engine = DeterministicEngine(rules=[
            Rule("broken", lambda i: 1 / 0, lambda i: "nope"),  # type: ignore[arg-type]
            _make_rule("good"),
        ])
        result = engine.evaluate({"trigger": "good"})
        assert result.answer == "handled_good"

    def test_add_rule_sorts_by_priority(self):
        engine = DeterministicEngine()
        engine.add_rule(Rule("low", lambda i: True, lambda i: "low", priority=1))
        engine.add_rule(Rule("high", lambda i: True, lambda i: "high", priority=10))
        assert engine.rules[0].name == "high"

    def test_remove_rule(self):
        engine = DeterministicEngine(rules=[_make_rule("a")])
        assert engine.remove_rule("a") is True
        assert engine.remove_rule("a") is False
        assert engine.rule_count == 0

    def test_rule_names(self):
        engine = DeterministicEngine(rules=[_make_rule("a"), _make_rule("b")])
        assert set(engine.rule_names()) == {"a", "b"}


class TestLLMReasoner:
    def test_reason_with_handler(self):
        def handler(inputs: dict) -> ReasoningResult:
            return ReasoningResult(
                answer=f"llm_says_{inputs.get('q')}",
                mode=ReasoningMode.LLM,
                confidence=ConfidenceLevel.MEDIUM,
            )
        reasoner = LLMReasoner(fallback_handler=handler)
        result = reasoner.reason({"q": "hello"})
        assert result.answer == "llm_says_hello"
        assert result.mode == ReasoningMode.LLM

    def test_reason_without_handler(self):
        reasoner = LLMReasoner()
        result = reasoner.reason({"q": "hello"})
        assert result.mode == ReasoningMode.FALLBACK
        assert result.confidence == ConfidenceLevel.UNKNOWN


class TestHybridSystem:
    def test_query_routes_to_deterministic_first(self):
        system = HybridSystem()
        system.set_deterministic_rules([_make_rule("math")])
        result = system.query({"trigger": "math"})
        assert result.mode == ReasoningMode.DETERMINISTIC
        assert result.answer == "handled_math"

    def test_query_falls_back_to_llm(self):
        def handler(inputs: dict) -> ReasoningResult:
            return ReasoningResult(answer="llm_answer", mode=ReasoningMode.LLM, confidence=ConfidenceLevel.LOW)
        system = HybridSystem(engine=DeterministicEngine(rules=[]), reasoner=LLMReasoner(fallback_handler=handler))
        result = system.query({"q": "ambiguous"})
        assert result.mode == ReasoningMode.LLM

    def test_decisions_tracked(self):
        system = HybridSystem()
        system.set_deterministic_rules([_make_rule("a")])
        system.query({"trigger": "a"})
        system.query({"trigger": "b"})
        assert system.total_decisions == 2

    def test_decisions_by_mode(self):
        system = HybridSystem()
        system.set_deterministic_rules([_make_rule("a")])
        system.query({"trigger": "a"})
        system.query({"trigger": "b"})
        counts = system.decisions_by_mode()
        assert counts.get("deterministic", 0) == 1

    def test_deterministic_hit_rate(self):
        system = HybridSystem()
        system.set_deterministic_rules([_make_rule("known")])
        system.query({"trigger": "known"})
        system.query({"trigger": "unknown"})
        assert system.deterministic_hit_rate() == 0.5

    def test_deterministic_hit_rate_zero_when_no_decisions(self):
        system = HybridSystem()
        assert system.deterministic_hit_rate() == 0.0

    def test_average_latency(self):
        system = HybridSystem()
        system.set_deterministic_rules([_make_rule("fast")])
        system.query({"trigger": "fast"})
        assert system.average_latency_ms() >= 0

    def test_summary_shape(self):
        system = HybridSystem()
        system.set_deterministic_rules([_make_rule("a")])
        system.query({"trigger": "a"})
        s = system.summary()
        assert s["total_decisions"] == 1
        assert "deterministic_hit_rate" in s
        assert "rules_configured" in s
