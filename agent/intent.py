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
    clarification_phrases = {
        "what", "how", "why", "can you", "could you", "please", "help me", "i need",
        "explain", "tell me", "show me", "guide me", "walk me through"
    }
    if any(phrase in stripped for phrase in clarification_phrases):
        return INTENT_CLARIFY

    return INTENT_CONVERSATION
