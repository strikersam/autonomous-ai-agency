"""
Quality checker inspired by stop-slop (https://github.com/hardikpandya/stop-slop).

Removes common AI writing tells:
- Throat-clearing phrases
- Emphasis crutches (weak adverbs)
- Business jargon
- Meta-commentary
- Structural issues (passive voice, Wh-starters, etc)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class AITellType(str, Enum):
    """Categories of AI tells"""

    THROAT_CLEARING = "throat_clearing"
    EMPHASIS_CRUTCH = "emphasis_crutch"
    JARGON = "jargon"
    META_COMMENTARY = "meta_commentary"
    ADVERB = "adverb"
    PASSIVE_VOICE = "passive_voice"
    WH_STARTER = "wh_starter"
    FALSE_AGENCY = "false_agency"


@dataclass
class AITellIssue:
    """Single AI tell issue"""

    tell_type: AITellType
    text: str
    suggestion: Optional[str] = None
    line_num: Optional[int] = None


class StopSlopChecker:
    """Detect and optionally remove AI tells from text"""

    # Throat-clearing phrases (case-insensitive)
    THROAT_CLEARING = [
        "it's important to note that",
        "it's worth noting that",
        "as you may know",
        "one should keep in mind",
        "it should be noted",
        "as mentioned above",
        "it's worth mentioning",
        "it goes without saying",
        "needless to say",
        "suffice it to say",
    ]

    # Emphasis crutches (weak adverbs to ban)
    EMPHASIS_CRUTCHES = [
        "truly",
        "really",
        "very",
        "literally",
        "actually",
        "certainly",
        "definitely",
        "absolutely",
        "simply",
        "merely",
    ]

    # Business jargon
    JARGON = [
        "leverage",
        "synergy",
        "paradigm shift",
        "ecosystem",
        "best practice",
        "best-in-class",
        "moving forward",
        "at the end of the day",
        "take it to the next level",
        "blue sky thinking",
        "circle back",
        "drill down",
    ]

    # Meta-commentary (referring to the text itself)
    META_COMMENTARY = [
        r"the following (code|example|snippet|section)",
        r"as mentioned (above|previously)",
        r"to elaborate on this",
        r"to summarize",
        r"in conclusion",
        r"this demonstrates",
        r"this shows that",
        r"it allows us to",
        r"this enables",
    ]

    # Wh-sentence starters (usually weak in prose)
    WH_STARTERS = [
        "^what does this",
        "^what is this",
        "^what are these",
        "^when should",
        "^where do",
        "^why do we",
        "^who would use",
        "^how do we",
    ]

    # Passive voice patterns (very basic detection)
    PASSIVE_PATTERNS = [
        r"\b\w+\s+is\s+\w+ed\b",  # "is configured"
        r"\b\w+\s+are\s+\w+ed\b",  # "are defined"
        r"\b\w+\s+was\s+\w+ed\b",  # "was created"
        r"\b\w+\s+were\s+\w+ed\b",  # "were written"
    ]

    def __init__(self, strict: bool = False):
        """
        Initialize checker.

        Args:
            strict: If True, also report adverbs even if not in emphasis list
        """
        self.strict = strict

    def check_text(self, text: str) -> list[AITellIssue]:
        """Find all AI tells in text"""
        issues = []

        issues.extend(self._check_throat_clearing(text))
        issues.extend(self._check_emphasis_crutches(text))
        issues.extend(self._check_jargon(text))
        issues.extend(self._check_meta_commentary(text))
        issues.extend(self._check_wh_starters(text))

        if self.strict:
            issues.extend(self._check_passive_voice(text))

        return issues

    def _check_throat_clearing(self, text: str) -> list[AITellIssue]:
        """Find throat-clearing phrases"""
        issues = []
        text_lower = text.lower()

        for phrase in self.THROAT_CLEARING:
            if phrase in text_lower:
                issues.append(
                    AITellIssue(
                        tell_type=AITellType.THROAT_CLEARING,
                        text=phrase,
                        suggestion=f"Remove '{phrase}'—just state your point",
                    )
                )

        return issues

    def _check_emphasis_crutches(self, text: str) -> list[AITellIssue]:
        """Find emphasis crutches (weak adverbs)"""
        issues = []
        words = text.lower().split()

        for crutch in self.EMPHASIS_CRUTCHES:
            if crutch in words:
                issues.append(
                    AITellIssue(
                        tell_type=AITellType.EMPHASIS_CRUTCH,
                        text=crutch,
                        suggestion=f"Remove '{crutch}'—weak adverb",
                    )
                )

        return issues

    def _check_jargon(self, text: str) -> list[AITellIssue]:
        """Find business jargon"""
        issues = []
        text_lower = text.lower()

        for jargon in self.JARGON:
            if jargon.lower() in text_lower:
                issues.append(
                    AITellIssue(
                        tell_type=AITellType.JARGON,
                        text=jargon,
                        suggestion=f"Replace '{jargon}' with plain language",
                    )
                )

        return issues

    def _check_meta_commentary(self, text: str) -> list[AITellIssue]:
        """Find meta-commentary (text referring to itself)"""
        issues = []

        for pattern in self.META_COMMENTARY:
            if re.search(pattern, text, re.IGNORECASE):
                issues.append(
                    AITellIssue(
                        tell_type=AITellType.META_COMMENTARY,
                        text=pattern,
                        suggestion="Remove meta-commentary—let the content speak",
                    )
                )

        return issues

    def _check_wh_starters(self, text: str) -> list[AITellIssue]:
        """Find Wh-sentence starters (weak prose starters)"""
        issues = []
        lines = text.split("\n")

        for line in lines:
            line_stripped = line.strip().lower()
            for pattern in self.WH_STARTERS:
                if re.search(pattern, line_stripped):
                    issues.append(
                        AITellIssue(
                            tell_type=AITellType.WH_STARTER,
                            text=line_stripped,
                            suggestion="Rewrite as a statement, not a question",
                        )
                    )
                    break

        return issues

    def _check_passive_voice(self, text: str) -> list[AITellIssue]:
        """Find basic passive voice patterns (strict mode only)"""
        issues = []

        for pattern in self.PASSIVE_PATTERNS:
            if re.search(pattern, text):
                issues.append(
                    AITellIssue(
                        tell_type=AITellType.PASSIVE_VOICE,
                        text=pattern,
                        suggestion="Convert to active voice",
                    )
                )

        return issues

    def clean_text(self, text: str) -> str:
        """Remove most obvious AI tells from text"""
        result = text

        # Remove throat-clearing
        for phrase in self.THROAT_CLEARING:
            result = re.sub(
                re.escape(phrase), "", result, flags=re.IGNORECASE | re.MULTILINE
            )

        # Remove emphasis crutches (word boundaries)
        for crutch in self.EMPHASIS_CRUTCHES:
            result = re.sub(
                r"\b" + re.escape(crutch) + r"\b",
                "",
                result,
                flags=re.IGNORECASE,
            )

        # Clean up double spaces from removals
        result = re.sub(r"\s+", " ", result)

        return result.strip()

    def report(self, issues: list[AITellIssue]) -> str:
        """Format issues as human-readable report"""
        if not issues:
            return "✓ No AI tells detected"

        lines = [f"⚠️  Found {len(issues)} AI tell(s):\n"]
        for issue in issues:
            lines.append(f"  [{issue.tell_type.value}] {issue.text}")
            if issue.suggestion:
                lines.append(f"    → {issue.suggestion}")

        return "\n".join(lines)
