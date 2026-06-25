"""intent.py — Intent classification for direct chat (answer_only, execute_now, etc.)."""
from __future__ import annotations
import re
from typing import Any, Literal

# Intent categories
INTENT_EXECUTION = "execution"
INTENT_ANALYSIS = "analysis"
INTENT_CONVERSATION = "conversation"
INTENT_CLARIFY = "clarify"

_EXECUTION_KEYWORDS = re.compile(
    r"\b(fix|implement|create|add|generate|build|scaffold|refactor|migrate|"
    r"debug|commit|push|clone|branch|merge|pr|pull request|diff|patch|"
    r"edit|test|run|deploy|setup|install|update|change|resolve|address|correct|adjust|modify|replace|remove|delete)\b",
    re.IGNORECASE,
)

_ANALYSIS_KEYWORDS = re.compile(
    r"\b(analyze|analyse|inspect|check|explain|understand|review|audit|investigate|look at|what is|search|find|diagnose|troubleshoot|examine|scan|assess|evaluate)\b",
    re.IGNORECASE,
)

def _contains_keyword(content: str) -> bool:
    """Return True if content contains any execution or analysis keyword."""
    if not content or not isinstance(content, str):
        return False
    stripped = content.strip().lower()
    return bool(_EXECUTION_KEYWORDS.search(stripped) or _ANALYSIS_KEYWORDS.search(stripped))

def detect_intent(content: str) -> str:
    """Detect the user's intent from message content."""
    if not content or not isinstance(content, str):
        return INTENT_CONVERSATION

    stripped = content.strip().lower()

    # If the message contains execution or analysis keywords, it's not trivial
    if _contains_keyword(stripped):
        # We still need to distinguish between execution, analysis, and clarify
        # Execution has priority
        if _EXECUTION_KEYWORDS.search(stripped):
            # If it's too vague, we might need clarification
            words = stripped.split()
            if len(words) < 4 and any(w in stripped for w in ["fix", "edit", "change"]):
                return INTENT_CLARIFY
            return INTENT_EXECUTION

        # Analysis next
        if _ANALYSIS_KEYWORDS.search(stripped):
            return INTENT_ANALYSIS

        # If we have a keyword but it's not clearly execution or analysis, default to conversation?
        # This should not happen with our keyword lists, but just in case.
        return INTENT_CONVERSATION

    # Very short messages or vague requests should probably be clarified or treated as conversation
    words = stripped.split()
    if len(words) < 3:
        return INTENT_CONVERSATION

    # Check for clarification intent (e.g., vague requests that need more detail)
    # We'll treat short messages that are not trivial as needing clarification if they don't have clear intent
    # but we already handled trivial above. For now, we'll be conservative and treat short non-trivial as conversation.
    # Alternatively, we could use a set of clarification phrases.
    # Use whole-word / phrase matching so "how are you" doesn't trigger INTENT_CLARIFY.
    # Single-word markers ("how", "why", "what") must appear at the start of the sentence
    # or follow common question starters to avoid false positives on greetings.
    _CLARIFY_RE = re.compile(
        r"(?:^|\s)(?:how (?:do|does|would|should|can)|why |what (?:is|are|should|would|can)|"
        r"can you |could you |please |help me |i need |tell me |show me |guide me |walk me through )",
        re.IGNORECASE,
    )
    if _CLARIFY_RE.search(stripped):
        return INTENT_CLARIFY

    return INTENT_CONVERSATION


# New helper: classify into higher-level direct chat categories
def classify_direct_chat_intent(content: str) -> str:
    """Map lower-level intents into conversation-driven action categories.

    Returns one of: 'answer_only', 'clarify_needed', 'plan_only', 'execute_now', 'execute_after_approval'
    """
    base = detect_intent(content)

    # Quick map for clarity
    if base == INTENT_CLARIFY:
        return "clarify_needed"
    if base == INTENT_CONVERSATION:
        return "answer_only"
    if base == INTENT_ANALYSIS:
        # Analysis typically means the user wants an inspection and a plan
        return "plan_only"

    # Execution intent: check for sensitive targets or explicit approval cues
    if base == INTENT_EXECUTION:
        # Use specific module names / terms — avoid generic substrings like "auth"
        # that would match "authentication" in innocent prompts.
        sensitive_indicators = ["admin_auth", "key_store", "secrets", "password", "credential", "private key", "service_manager"]
        lowered = content.lower()
        if any(si in lowered for si in sensitive_indicators):
            return "execute_after_approval"
        # If user asked explicitly for a plan or proposal, only plan
        if any(phrase in lowered for phrase in ("plan", "proposal", "what would you do", "how would you")):
            return "plan_only"
        # Otherwise, proceed to execute now for concrete requests
        return "execute_now"

    # Default to answer only
    return "answer_only"
