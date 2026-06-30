"""packages/intelligence/__init__.py — Intelligence Layer.

Shared brain for all agents: planning, reflection, verification,
context optimization, self-improvement.
"""
from packages.intelligence.planner import Planner, ExecutionPlan, PlanStep
from packages.intelligence.reflector import Reflector, Reflection
from packages.intelligence.verifier import Verifier, VerificationResult
from packages.intelligence.context import ContextOptimizer, ContextWindow
from packages.intelligence.self_improve import SelfImprover, ImprovementSuggestion, get_self_improver

__all__ = [
    "Planner", "ExecutionPlan", "PlanStep",
    "Reflector", "Reflection",
    "Verifier", "VerificationResult",
    "ContextOptimizer", "ContextWindow",
    "SelfImprover", "ImprovementSuggestion", "get_self_improver",
]
