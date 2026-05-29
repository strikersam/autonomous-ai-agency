"""Quality filters for agent-generated content.

Inspired by stop-slop (https://github.com/hardikpandya/stop-slop):
Removes AI tells, vague declaratives, meta-commentary, and improves authenticity.
"""
from __future__ import annotations

import re
from dataclasses import dataclass


# Common AI-generated phrases and patterns to flag/remove
BANNED_PHRASES = {
    # Throat-clearing / meta-commentary
    "let me", "i can", "i will", "i'd be happy to",
    "as an ai", "as a language model",
    "here's the thing", "the thing is",
    "let's dive in", "let's explore",
    
    # Unnecessary emphasis / business jargon
    "truly", "really", "actually", "basically",
    "clearly", "obviously", "essentially",
    "in essence", "at the end of the day",
    "push the envelope", "think outside the box",
    "synergy", "leverage", "optimize",
    
    # Vague declaratives / vibe statements
    "it goes without saying", "needless to say",
    "as mentioned", "as noted",
    "in other words", "that is to say",
    
    # False urgency / drama
    "it's critical", "it's crucial", "it's vital",
    "without delay", "immediately",
}

# Structural patterns (regex) to flag
STRUCTURAL_PATTERNS = [
    # All caps for emphasis (except acronyms in code)
    (r"\b[A-Z]{3,}\b(?![A-Z_])", "ALL_CAPS"),
    
    # Multiple exclamation marks
    (r"!{2,}", "MULTIPLE_EXCLAMATION"),
    
    # Staccato fragmentation (period followed by short fragment)
    (r"\. [A-Z][a-z]{0,3}\.", "FRAGMENTATION"),
    
    # Wh- question starters in middle of text (not conversational)
    (r"\n[Wh][a-z]+ (is|are|can|does|did|would)\b", "WH_STARTER"),
    
    # Unnecessary em-dashes
    (r" — [a-z]", "EMDASH_EMPHASIS"),
]


@dataclass
class QualityIssue:
    """A single quality issue in text."""
    type: str
    severity: str  # "warn" or "error"
    text: str
    suggestion: str | None = None
    line_num: int | None = None


class StopSlopFilter:
    """Filter to remove AI tells and improve authenticity of generated text."""
    
    def __init__(self, strict: bool = False) -> None:
        """
        Initialize the filter.
        
        Args:
            strict: If True, flag more aggressive patterns. If False, only flag egregious violations.
        """
        self.strict = strict
        
    def check_text(self, text: str) -> list[QualityIssue]:
        """Analyze text and return list of quality issues."""
        issues: list[QualityIssue] = []
        
        # Check for banned phrases
        words = text.lower().split()
        for phrase in BANNED_PHRASES:
            phrase_words = phrase.split()
            for i in range(len(words) - len(phrase_words) + 1):
                if words[i:i+len(phrase_words)] == phrase_words:
                    # Found phrase
                    severity = "error" if phrase in {"as an ai", "as a language model"} else "warn"
                    issues.append(QualityIssue(
                        type="BANNED_PHRASE",
                        severity=severity,
                        text=phrase,
                        suggestion=f"Consider removing or rewording '{phrase}'",
                    ))
        
        # Check structural patterns
        lines = text.split('\n')
        for line_idx, line in enumerate(lines, 1):
            for pattern, pattern_type in STRUCTURAL_PATTERNS:
                if re.search(pattern, line):
                    issues.append(QualityIssue(
                        type=pattern_type,
                        severity="warn",
                        text=line.strip()[:50],
                        line_num=line_idx,
                    ))
        
        # Check for passive voice (simple heuristic)
        passive_pattern = r"\b(is|are|was|were|be|been|being)\s+\w+ed\b"
        for line_idx, line in enumerate(lines, 1):
            if re.search(passive_pattern, line):
                if self.strict:
                    issues.append(QualityIssue(
                        type="PASSIVE_VOICE",
                        severity="warn",
                        text=line.strip()[:50],
                        suggestion="Consider using active voice",
                        line_num=line_idx,
                    ))
        
        return issues
    
    def clean_text(self, text: str, remove_phrases: bool = True) -> str:
        """
        Clean text by removing common AI tells.
        
        Args:
            text: Text to clean
            remove_phrases: If True, remove banned phrases. If False, just flag them.
        
        Returns:
            Cleaned text
        """
        cleaned = text
        
        if remove_phrases:
            for phrase in BANNED_PHRASES:
                # Case-insensitive removal with word boundaries
                pattern = r"\b" + re.escape(phrase) + r"\b"
                cleaned = re.sub(pattern, "", cleaned, flags=re.IGNORECASE)
            
            # Clean up extra whitespace
            cleaned = re.sub(r"\s+", " ", cleaned).strip()
        
        return cleaned
    
    def score_text(self, text: str) -> dict:
        """
        Score text on authenticity dimensions (1-10 each).
        
        Based on stop-slop scoring system:
        - Directness: Are statements direct or throat-clearing?
        - Rhythm: Is the text varied or metronomic?
        - Trust: Does it respect reader intelligence?
        - Authenticity: Sounds human?
        - Density: Is anything cuttable?
        
        Returns:
            Dict with scores and total (max 50)
        """
        issues = self.check_text(text)
        
        # Simple scoring based on issue counts
        directness = 10 - min(5, len([i for i in issues if i.type == "BANNED_PHRASE"]))
        
        fragmentation_count = len([i for i in issues if i.type == "FRAGMENTATION"])
        rhythm = 10 - min(5, fragmentation_count)
        
        emphasis_count = len([i for i in issues if i.type in {"ALL_CAPS", "EMDASH_EMPHASIS"}])
        trust = 10 - min(5, emphasis_count)
        
        ai_tells = len([i for i in issues if "AI" in i.text.upper() or "LANGUAGE MODEL" in i.text.upper()])
        authenticity = 10 - min(5, ai_tells)
        
        # Density: look for redundant words
        words = text.lower().split()
        unique_ratio = len(set(words)) / len(words) if words else 1.0
        density = max(5, min(10, int(unique_ratio * 10)))
        
        total = directness + rhythm + trust + authenticity + density
        
        return {
            "directness": directness,
            "rhythm": rhythm,
            "trust": trust,
            "authenticity": authenticity,
            "density": density,
            "total": total,
            "max": 50,
            "issues_found": len(issues),
        }


def apply_stop_slop_filter(text: str, action: str = "score", strict: bool = False) -> dict | str:
    """
    Convenience function to apply stop-slop filter to text.
    
    Args:
        text: Text to filter
        action: "score", "clean", or "check"
        strict: Enable strict mode
    
    Returns:
        Score dict, cleaned text, or issues list depending on action
    """
    filter_obj = StopSlopFilter(strict=strict)
    
    if action == "score":
        return filter_obj.score_text(text)
    elif action == "clean":
        return filter_obj.clean_text(text)
    elif action == "check":
        return filter_obj.check_text(text)
    else:
        raise ValueError(f"Unknown action: {action}")
