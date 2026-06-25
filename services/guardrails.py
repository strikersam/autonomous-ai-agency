from __future__ import annotations

"""Safety Guardrails (B4 roadmap item).

Implements configurable safety rails for LLM inputs and outputs:
- Topic filtering: block or warn on prohibited topics
- Jailbreak detection: regex + keyword patterns for prompt injection
  (Note: regex-based detection is a first-pass filter; it does not replace
  comprehensive input sanitization or a dedicated moderation API.)
- Output validation: check for PII, harmful content, compliance
- YAML/JSON rule engine for declarative safety policies

Usage::

    guard = GuardrailEngine()

    # Check user input
    result = guard.check_input("How do I hack into a server?")
    if result.blocked:
        return "I cannot help with that."

    # Check model output
    result = guard.check_output("Here is the password: admin123")
    if result.has_issues:
        log.warning("Output flagged: %s", result.issues)
"""

import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-proxy")

# ── Configuration ──────────────────────────────────────────────────────────────

_GUARDRAILS_ENABLED = os.environ.get("GUARDRAILS_ENABLED", "true").strip().lower() in ("true", "1", "yes")
_GUARDRAILS_CONFIG = os.environ.get("GUARDRAILS_CONFIG", "guardrails.yaml")

# Whether to block or warn on violations
_DEFAULT_ACTION: str = os.environ.get("GUARDRAILS_DEFAULT_ACTION", "warn").strip().lower()


@dataclass
class GuardResult:
    """Result of a guardrail check."""

    blocked: bool = False
    warned: bool = False
    issues: list[str] = field(default_factory=list)
    categories: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def has_issues(self) -> bool:
        return len(self.issues) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "warned": self.warned,
            "issues": self.issues,
            "categories": self.categories,
            "details": self.details,
        }


# ── Default safety rules ───────────────────────────────────────────────────────

_DEFAULT_RULES: dict[str, Any] = {
    "version": "1.0",
    "rules": {
        "input_rules": {
            "prohibited_topics": {
                "description": "Block clearly malicious or harmful requests",
                "action": "block",
                "patterns": [
                    r"how\s+(to|can\s+(i|you))\s+hack",
                    r"generate\s+(malware|ransomware|phishing)",
                    r"how\s+to\s+(make|create|build)\s+(a\s+)?bomb",
                    r"(self[\s-]?harm|suicide)\s+(instructions|method)",
                    r"(exploit|breach)\s+(the\s+)?(vulnerability|security)",
                ],
            },
            "jailbreak_detection": {
                "description": "Detect prompt injection and jailbreak attempts",
                "action": "block",
                "patterns": [
                    r"ignore\s+(all\s+)?(previous|prior|above|system)\s+(instructions?|prompts?)",
                    r"you\s+are\s+now\s+(DAN|STAN|jailbreak)",
                    r"pretend\s+(you\s+are|to\s+be)\s+(an?\s+)?(unfiltered|unrestricted)",
                    r"do\s+not\s+follow\s+(any\s+)?(ethical|safety)\s+guidelines",
                    r"(developer|system)\s+mode\s+(activated|enabled|on)",
                    r"forget\s+(everything|all)\s+(you\s+)?(know|learned)",
                ],
            },
        },
        "output_rules": {
            "pii_detection": {
                "description": "Flag potential PII in model outputs",
                "action": "warn",
                "patterns": [
                    r"\b\d{3}-\d{2}-\d{4}\b",           # SSN
                    r"\b\d{16}\b",                        # Credit card (simple)
                    r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # email
                    r"\b(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",  # phone
                ],
            },
            "harmful_content": {
                "description": "Detect harmful or inappropriate content",
                "action": "block",
                "patterns": [
                    r"(password|secret|api[_\s]?key|token)\s*[:=]\s*[\"'\\w]",
                    r"<script[^>]*>.*?</script>",
                    r"(DROP\s+TABLE|DELETE\s+FROM|INSERT\s+INTO)\s",
                ],
            },
        },
    },
}


class GuardrailEngine:
    """Configurable safety rail engine for LLM inputs and outputs.

    Supports:
    - Pattern-based topic filtering (regex rules)
    - Jailbreak / prompt injection detection (first-pass regex filter)
    - Output content validation (PII, harmful content)
    - YAML/JSON rule configuration
    """

    def __init__(
        self,
        *,
        enabled: bool = _GUARDRAILS_ENABLED,
        config_path: str | None = None,
        default_action: str = _DEFAULT_ACTION,
    ) -> None:
        self.enabled = enabled
        self.default_action = default_action
        self.rules: dict[str, Any] = dict(_DEFAULT_RULES)

        # Load YAML config if available
        config_file = config_path or _GUARDRAILS_CONFIG
        if config_file:
            self._load_config(config_file)

        # Pre-compile regex patterns for performance
        self._input_patterns: list[tuple[re.Pattern, str, str]] = []  # (regex, category, action)
        self._output_patterns: list[tuple[re.Pattern, str, str]] = []
        self._compile_rules()

        self._checks_run = 0
        self._checks_blocked = 0

    # ── Public API ──────────────────────────────────────────────────────────

    def check_input(self, text: str) -> GuardResult:
        """Check user input against input safety rules.

        Returns a GuardResult with blocked/warned flags and any issues found.
        """
        if not self.enabled or not text:
            return GuardResult()

        self._checks_run += 1
        result = GuardResult()

        for pattern, category, action in self._input_patterns:
            match = pattern.search(text.lower())
            if match:
                issue = f"[{category}] {action.upper()}: matched pattern near '{match.group()[:60]}'"
                result.issues.append(issue)
                result.categories.append(category)
                if action == "block":
                    result.blocked = True
                elif action == "warn":
                    result.warned = True

        if result.blocked:
            self._checks_blocked += 1
            log.warning("Input blocked by guardrails: %s", result.issues)

        result.details = {
            "input_length": len(text),
            "patterns_checked": len(self._input_patterns),
        }
        return result

    def check_output(self, text: str) -> GuardResult:
        """Check model output against output safety rules.

        Returns a GuardResult with blocked/warned flags and any issues found.
        """
        if not self.enabled or not text:
            return GuardResult()

        self._checks_run += 1
        result = GuardResult()

        for pattern, category, action in self._output_patterns:
            match = pattern.search(text)
            if match:
                issue = f"[{category}] {action.upper()}: matched pattern '{match.group()[:60]}'"
                result.issues.append(issue)
                result.categories.append(category)
                if action == "block":
                    result.blocked = True
                elif action == "warn":
                    result.warned = True

        if result.blocked:
            self._checks_blocked += 1
            log.warning("Output blocked by guardrails: %s", result.issues)
        elif result.warned:
            log.info("Output flagged by guardrails (warn): %s", result.issues)

        result.details = {
            "output_length": len(text),
            "patterns_checked": len(self._output_patterns),
        }
        return result

    def check(self, text: str, *, direction: str = "input") -> GuardResult:
        """Unified check method. direction = 'input' or 'output'."""
        if direction == "output":
            return self.check_output(text)
        return self.check_input(text)

    def stats(self) -> dict[str, Any]:
        """Return guardrail statistics."""
        return {
            "enabled": self.enabled,
            "checks_run": self._checks_run,
            "checks_blocked": self._checks_blocked,
            "block_rate": round(self._checks_blocked / max(1, self._checks_run) * 100, 1),
            "input_patterns": len(self._input_patterns),
            "output_patterns": len(self._output_patterns),
            "default_action": self.default_action,
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    def _load_config(self, config_path: str) -> None:
        """Load guardrail rules from a YAML or JSON config file."""
        path = Path(config_path)
        if not path.exists():
            log.debug("Guardrail config not found: %s (using defaults)", config_path)
            return

        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            log.warning("Could not read guardrail config %s: %s", config_path, exc)
            return

        # Try YAML first, fall back to JSON
        try:
            import yaml
            config = yaml.safe_load(content)
        except ImportError:
            try:
                config = json.loads(content)
            except json.JSONDecodeError:
                log.warning("Could not parse guardrail config %s", config_path)
                return
        except Exception:
            try:
                config = json.loads(content)
            except json.JSONDecodeError:
                log.warning("Could not parse guardrail config %s", config_path)
                return

        if isinstance(config, dict):
            # Merge with defaults (user config takes precedence)
            self.rules = _deep_merge(_DEFAULT_RULES, config)
            log.info("Loaded guardrail config from %s (%d input rules, %d output rules)",
                     config_path,
                     len(self.rules.get("rules", {}).get("input_rules", {})),
                     len(self.rules.get("rules", {}).get("output_rules", {})))

    def _compile_rules(self) -> None:
        """Compile regex patterns from the rules configuration."""
        rules = self.rules.get("rules", {})

        # Input rules
        input_rules = rules.get("input_rules", {})
        for _rule_name, rule_config in input_rules.items():
            action = rule_config.get("action", self.default_action)
            for pattern_str in rule_config.get("patterns", []):
                try:
                    compiled = re.compile(pattern_str, re.IGNORECASE | re.DOTALL)
                    self._input_patterns.append((compiled, _rule_name, action))
                except re.error as exc:
                    log.warning("Invalid guardrail regex '%s': %s", pattern_str[:60], exc)

        # Output rules
        output_rules = rules.get("output_rules", {})
        for _rule_name, rule_config in output_rules.items():
            action = rule_config.get("action", self.default_action)
            for pattern_str in rule_config.get("patterns", []):
                try:
                    compiled = re.compile(pattern_str, re.IGNORECASE | re.DOTALL)
                    self._output_patterns.append((compiled, _rule_name, action))
                except re.error as exc:
                    log.warning("Invalid guardrail regex '%s': %s", pattern_str[:60], exc)


def _deep_merge(base: dict, override: dict) -> dict:
    """Deep merge two dicts. Override values take precedence."""
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


# ── Module-level singleton ─────────────────────────────────────────────────────

_guardrails: GuardrailEngine | None = None


def get_guardrails() -> GuardrailEngine:
    """Return the module-level GuardrailEngine singleton."""
    global _guardrails
    if _guardrails is None:
        _guardrails = GuardrailEngine()
    return _guardrails
