"""
Hybrid AI — combine deterministic rule engines with LLM reasoning.

Implements a dual-path architecture where a DeterministicEngine handles
well-defined logic and an LLMReasoner handles ambiguous/fuzzy cases,
coordinated by a HybridSystem that routes each query to the right path.

Quick-Note Issue: #237
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional


class ReasoningMode(str, Enum):
    """Which reasoning path is active for a given query."""

    DETERMINISTIC = "deterministic"
    LLM = "llm"
    FALLBACK = "fallback"


class ConfidenceLevel(str, Enum):
    """Confidence label for a reasoning result."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNKNOWN = "unknown"


@dataclass
class Rule:
    """A single deterministic rule with a condition and action."""

    name: str
    condition: Callable[[dict[str, Any]], bool]
    action: Callable[[dict[str, Any]], Any]
    priority: int = 0
    description: str = ""


@dataclass
class ReasoningResult:
    """Output from either the deterministic engine or LLM reasoner."""

    answer: Any
    mode: ReasoningMode
    confidence: ConfidenceLevel = ConfidenceLevel.MEDIUM
    reasoning_trace: str = ""
    latency_ms: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)

    @property
    def is_confident(self) -> bool:
        return self.confidence in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)


@dataclass
class DeterministicEngine:
    """
    Rule-based reasoning engine for well-defined problems.

    Rules are evaluated in priority order (highest first). The first
    matching rule's action is executed and its result returned.
    If no rule matches, returns None.
    """

    rules: list[Rule] = field(default_factory=list)

    def add_rule(self, rule: Rule) -> None:
        self.rules.append(rule)
        self.rules.sort(key=lambda r: -r.priority)

    def remove_rule(self, name: str) -> bool:
        before = len(self.rules)
        self.rules = [r for r in self.rules if r.name != name]
        return len(self.rules) < before

    def evaluate(self, inputs: dict[str, Any]) -> Optional[ReasoningResult]:
        """Run rules against inputs. Returns first match, or None."""
        import time
        t0 = time.time()
        for rule in self.rules:
            try:
                if rule.condition(inputs):
                    answer = rule.action(inputs)
                    return ReasoningResult(
                        answer=answer,
                        mode=ReasoningMode.DETERMINISTIC,
                        confidence=ConfidenceLevel.HIGH,
                        reasoning_trace=f"Rule matched: {rule.name}",
                        latency_ms=(time.time() - t0) * 1000,
                    )
            except Exception:
                continue
        return None

    @property
    def rule_count(self) -> int:
        return len(self.rules)

    def rule_names(self) -> list[str]:
        return [r.name for r in self.rules]


@dataclass
class LLMReasoner:
    """LLM-based reasoning for ambiguous or open-ended problems."""

    model_name: str = "default"
    fallback_handler: Optional[Callable[[dict[str, Any]], ReasoningResult]] = None

    def reason(self, inputs: dict[str, Any]) -> ReasoningResult:
        """Attempt to reason via the fallback_handler."""
        import time
        t0 = time.time()
        if self.fallback_handler:
            result = self.fallback_handler(inputs)
            result.latency_ms = (time.time() - t0) * 1000
            return result
        return ReasoningResult(
            answer=None,
            mode=ReasoningMode.FALLBACK,
            confidence=ConfidenceLevel.UNKNOWN,
            reasoning_trace="No LLM handler configured.",
            latency_ms=(time.time() - t0) * 1000,
        )


@dataclass
class HybridSystem:
    """
    Orchestrates the deterministic engine and LLM reasoner.

    Strategy:
      1. Try DeterministicEngine first.
      2. If no rule matches, delegate to LLMReasoner.
      3. Tag the result with the mode that produced it.
    """

    engine: DeterministicEngine = field(default_factory=DeterministicEngine)
    reasoner: LLMReasoner = field(default_factory=LLMReasoner)
    decisions: list[ReasoningResult] = field(default_factory=list)

    def query(self, inputs: dict[str, Any]) -> ReasoningResult:
        """Route a query through the hybrid pipeline and record the result."""
        result = self.engine.evaluate(inputs)
        if result is not None:
            self.decisions.append(result)
            return result
        result = self.reasoner.reason(inputs)
        self.decisions.append(result)
        return result

    def set_deterministic_rules(self, rules: list[Rule]) -> None:
        self.engine.rules = sorted(rules, key=lambda r: -r.priority)

    @property
    def total_decisions(self) -> int:
        return len(self.decisions)

    def decisions_by_mode(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for d in self.decisions:
            counts[d.mode.value] = counts.get(d.mode.value, 0) + 1
        return counts

    def deterministic_hit_rate(self) -> float:
        """Fraction of queries handled deterministically."""
        if not self.decisions:
            return 0.0
        det = self.decisions_by_mode().get("deterministic", 0)
        return det / len(self.decisions)

    def average_latency_ms(self) -> float:
        if not self.decisions:
            return 0.0
        return sum(d.latency_ms for d in self.decisions) / len(self.decisions)

    def summary(self) -> dict:
        return {
            "total_decisions": self.total_decisions,
            "deterministic_hit_rate": round(self.deterministic_hit_rate(), 3),
            "decisions_by_mode": self.decisions_by_mode(),
            "average_latency_ms": round(self.average_latency_ms(), 1),
            "rules_configured": self.engine.rule_count,
        }
