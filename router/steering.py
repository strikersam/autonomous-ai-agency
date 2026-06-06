from __future__ import annotations

"""SteerLM / RLHF-Style Steering for Local Models (B2 roadmap item).

Implements runtime steering of model outputs based on reward labels such as
helpfulness, correctness, complexity, and verbosity.  Injects steering tokens
into the system prompt to bias generation toward higher-quality outputs.

Reference: NVIDIA NeMo SteerLM — attribute-conditioned generation via
steering tokens injected before the user prompt.

Usage::

    steering = SteeringInjector()

    # Inject steering tokens into a message list
    messages = steering.inject(
        messages=[{"role": "user", "content": "Explain quantum computing"}],
        labels={"helpfulness": 4, "correctness": 4, "complexity": 3},
    )

    # Or use a preset:
    messages = steering.inject(messages=[...], preset="high_quality")
"""

import logging
import os
from typing import Any

log = logging.getLogger("qwen-proxy")


# ── Steering label definitions ────────────────────────────────────────────────

# Default steering labels and their value ranges.
# Each label maps to a 0-4 scale (0=low, 4=high).
_DEFAULT_LABELS: dict[str, str] = {
    "helpfulness": "How helpful the response should be",
    "correctness": "How factually correct the response should be",
    "complexity": "How detailed/complex the response should be",
    "verbosity": "How verbose the response should be",
    "creativity": "How creative the response should be",
    "concise": "Whether to prefer concise over verbose",
}

# Steering token format for models that support it (Nemotron, Llama, Qwen).
# These are injected into the system prompt as structured instructions.
_STEERING_TOKEN_FORMAT = os.environ.get(
    "STEERLM_TOKEN_FORMAT",
    "quality",
).strip().lower()

# Whether steering is enabled globally.
_STEERING_ENABLED = os.environ.get("STEERLM_ENABLED", "false").strip().lower() in (
    "true", "1", "yes", "on",
)


class SteeringInjector:
    """Inject steering tokens into prompts for quality-biased generation.

    Supports multiple steering formats:
    - ``quality``: Inject quality labels as system-prompt instructions
    - ``chatml``: Inject as ``<|im_start|>`` ChatML steering tokens
    - ``nemotron``: NVIDIA Nemotron-specific steering tag format
    """

    # Preset configurations for common use cases
    PRESETS: dict[str, dict[str, int]] = {
        "high_quality": {
            "helpfulness": 4,
            "correctness": 4,
            "complexity": 3,
            "verbosity": 2,
        },
        "fast_response": {
            "helpfulness": 3,
            "correctness": 3,
            "complexity": 1,
            "verbosity": 1,
        },
        "creative": {
            "helpfulness": 3,
            "correctness": 2,
            "complexity": 3,
            "creativity": 4,
            "verbosity": 3,
        },
        "code_review": {
            "helpfulness": 4,
            "correctness": 4,
            "complexity": 4,
            "verbosity": 3,
        },
        "concise_answer": {
            "helpfulness": 4,
            "correctness": 4,
            "complexity": 2,
            "concise": 4,
            "verbosity": 1,
        },
    }

    def __init__(self, *, format: str | None = None) -> None:
        self.format = format or _STEERING_TOKEN_FORMAT
        self.enabled = _STEERING_ENABLED
        self.labels = dict(_DEFAULT_LABELS)

    def inject(
        self,
        *,
        messages: list[dict[str, Any]],
        labels: dict[str, int] | None = None,
        preset: str | None = None,
    ) -> list[dict[str, Any]]:
        """Inject steering instructions into the message list.

        Args:
            messages: The existing message list (modified in place).
            labels: Dict of label_name → value (0-4). Overrides preset.
            preset: Named preset from ``SteeringInjector.PRESETS``.

        Returns the modified message list.
        """
        if not self.enabled:
            return messages

        resolved_labels = self._resolve_labels(labels, preset)
        if not resolved_labels:
            return messages

        steering_text = self._build_steering_text(resolved_labels)
        if not steering_text:
            return messages

        # Inject into the system message or prepend a new one
        copied = list(messages)
        if copied and copied[0].get("role") == "system":
            existing = str(copied[0].get("content", ""))
            copied[0] = {"role": "system", "content": f"{steering_text}\n\n{existing}"}
        else:
            copied.insert(0, {"role": "system", "content": steering_text})

        return copied

    def inject_payload(
        self,
        payload: dict[str, Any],
        labels: dict[str, int] | None = None,
        preset: str | None = None,
    ) -> dict[str, Any]:
        """Inject steering into an OpenAI chat payload dict.

        Modifies and returns the payload.
        """
        if not self.enabled:
            return payload
        msgs = payload.get("messages", [])
        if not msgs:
            return payload
        payload["messages"] = self.inject(messages=msgs, labels=labels, preset=preset)
        return payload

    def _resolve_labels(
        self,
        labels: dict[str, int] | None,
        preset: str | None,
    ) -> dict[str, int] | None:
        if labels:
            return {k: max(0, min(4, v)) for k, v in labels.items()}
        if preset and preset in self.PRESETS:
            return dict(self.PRESETS[preset])
        if preset:
            log.debug("Unknown steering preset: %s (available: %s)", preset, list(self.PRESETS))
        return None

    def _build_steering_text(self, labels: dict[str, int]) -> str:
        """Build the steering instruction text based on format."""
        if self.format == "nemotron":
            return self._build_nemotron_steering(labels)
        if self.format == "chatml":
            return self._build_chatml_steering(labels)
        # Default: quality-based system prompt instruction
        return self._build_quality_steering(labels)

    def _build_quality_steering(self, labels: dict[str, int]) -> str:
        """Build steering as natural-language quality instructions."""
        parts = []
        label_descriptions = {
            "helpfulness": "Be helpful and provide useful information",
            "correctness": "Ensure factual accuracy and correctness",
            "complexity": "Provide detailed and comprehensive explanations",
            "verbosity": "Use detailed and thorough responses",
            "creativity": "Be creative and think outside the box",
            "concise": "Be concise and to the point",
        }

        for label, value in sorted(labels.items()):
            if value >= 4:
                desc = label_descriptions.get(label, f"Prioritize {label}")
                parts.append(f"- {desc} (priority: maximum)")
            elif value >= 3:
                desc = label_descriptions.get(label, f"Consider {label}")
                parts.append(f"- {desc}")
            elif value >= 2:
                desc = label_descriptions.get(label, f"Balance {label}")
                parts.append(f"- {desc} (balanced)")

        if not parts:
            return ""

        return (
            "Quality directives for this response:\n"
            + "\n".join(parts)
            + "\n\nAdhere to these directives when generating your response."
        )

    def _build_chatml_steering(self, labels: dict[str, int]) -> str:
        """Build steering as ChatML-formatted tokens."""
        label_str = ", ".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"<|im_start|>steering\n{label_str}<|im_end|>"

    def _build_nemotron_steering(self, labels: dict[str, int]) -> str:
        """Build steering as Nemotron-specific steering tags."""
        quality = labels.get("helpfulness", 3)
        tox = 0  # Always steer away from toxicity
        tags = []
        for label, value in sorted(labels.items()):
            short = label[:4]
            tags.append(f"<extra_id_{short}>{value}")
        return f"<|begin_of_text|>{' '.join(tags)}\n"


# ── Helper: compute default steering labels from task type ─────────────────────

def steering_for_task(task_category: str) -> dict[str, int]:
    """Return recommended steering labels for a given task category.

    Used by the model router to auto-inject appropriate steering.
    """
    category_map: dict[str, dict[str, int]] = {
        "code_generation": SteeringInjector.PRESETS["code_review"],
        "code_review": SteeringInjector.PRESETS["code_review"],
        "code_debugging": {"helpfulness": 4, "correctness": 4, "complexity": 3},
        "reasoning": {"helpfulness": 4, "correctness": 4, "complexity": 4},
        "planning": {"helpfulness": 4, "correctness": 3, "complexity": 4},
        "fast_response": SteeringInjector.PRESETS["fast_response"],
        "conversation": SteeringInjector.PRESETS["high_quality"],
        "creative": SteeringInjector.PRESETS["creative"],
    }
    return category_map.get(task_category, {"helpfulness": 3, "correctness": 3})


# ── Module-level singleton ─────────────────────────────────────────────────────

_steering_injector: SteeringInjector | None = None


def get_steering_injector() -> SteeringInjector:
    """Return the module-level SteeringInjector singleton."""
    global _steering_injector
    if _steering_injector is None:
        _steering_injector = SteeringInjector()
    return _steering_injector
