from __future__ import annotations

"""Nemotron Reward Model Scoring (B1 roadmap item).

Scores agent step outputs using the NVIDIA Nemotron-4-340B-Reward model via
the NVIDIA NIM API — a cheaper, more consistent alternative to the LLM-based
Verifier for quality scoring.  Falls back to the LLM verifier when NIM is
unavailable.

Reference: NVIDIA-NeMo/Nemotron reward model — instruction-following quality
scoring on a 0.0–1.0 scale.
"""

import json
import logging
import os
import time
from typing import Any

import httpx
from pydantic import BaseModel, Field

log = logging.getLogger("qwen-proxy")

# ── Configuration ──────────────────────────────────────────────────────────────

# Nemotron-4-340B-Reward model ID on NVIDIA NIM.
# Override via NEMOTRON_REWARD_MODEL env var for custom deployments.
_DEFAULT_REWARD_MODEL = os.environ.get(
    "NEMOTRON_REWARD_MODEL",
    "nvidia/nemotron-4-340b-reward",
)

# NVIDIA NIM base URL for the reward endpoint.
# Defaults to the standard NIM integration endpoint; override via NEMOTRON_REWARD_BASE.
_DEFAULT_REWARD_BASE = os.environ.get(
    "NEMOTRON_REWARD_BASE",
    "https://integrate.api.nvidia.com/v1",
)

# Minimum score threshold for considering a step "passed" via reward scoring.
# Scores below this threshold trigger fallback to the LLM verifier.
_REWARD_PASS_THRESHOLD = float(
    os.environ.get("NEMOTRON_REWARD_PASS_THRESHOLD", "0.7")
)

# Timeout in seconds for reward model HTTP requests.
_REWARD_TIMEOUT = float(os.environ.get("NEMOTRON_REWARD_TIMEOUT", "15.0"))


def _nvidia_api_key() -> str | None:
    return os.environ.get("NVIDIA_API_KEY") or os.environ.get("NVidiaApiKey")


class RewardScore(BaseModel):
    """Result of a single reward model scoring operation."""

    score: float = Field(default=0.0, ge=0.0, le=1.0)
    model: str = Field(default="")
    model_used: bool = Field(default=True)
    latency_ms: float = Field(default=0.0)
    error: str = Field(default="")


class RewardScorer:
    """Scores agent step outputs using the Nemotron-4-340B-Reward model.

    The reward model evaluates instruction-following quality: given a prompt
    (the step goal + description) and a response (the model's output), it
    returns a 0.0–1.0 score.  Scores >= ``REWARD_PASS_THRESHOLD`` (default 0.7)
    are treated as passing.

    Usage::

        scorer = RewardScorer()
        result = await scorer.score(
            prompt="Fix the off-by-one error in loop.py",
            response="Changed range(n) to range(n+1) on line 42",
        )
        if result.score >= 0.7:
            print("Step passes reward check")
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.model = model or _DEFAULT_REWARD_MODEL
        self.base_url = (base_url or _DEFAULT_REWARD_BASE).rstrip("/")
        self._api_key: str | None = _nvidia_api_key()
        self._available: bool | None = None  # cached availability check

    @property
    def is_available(self) -> bool:
        """True when the reward model is configured and reachable."""
        if self._available is not None:
            return self._available
        self._available = bool(self._api_key) and bool(self.model)
        return self._available

    async def score(
        self,
        *,
        prompt: str,
        response: str,
    ) -> RewardScore:
        """Score a response against a prompt using the Nemotron reward model.

        Returns a ``RewardScore`` with the 0.0–1.0 score.  On any error
        (network, auth, model unavailable), returns ``score=0.0`` with
        ``model_used=False`` and ``error`` set — the caller should fall back
        to the LLM verifier.
        """
        if not self.is_available:
            return RewardScore(
                score=0.0,
                model=self.model,
                model_used=False,
                error="Reward model not configured (missing NVIDIA_API_KEY or NEMOTRON_REWARD_MODEL)",
            )

        start = time.perf_counter()
        try:
            result = await self._call_reward_api(prompt, response)
        except Exception as exc:
            latency_ms = (time.perf_counter() - start) * 1000
            log.debug("Nemotron reward scoring failed: %s", exc)
            return RewardScore(
                score=0.0,
                model=self.model,
                model_used=False,
                latency_ms=latency_ms,
                error=str(exc)[:500],
            )

        latency_ms = (time.perf_counter() - start) * 1000
        return RewardScore(
            score=result,
            model=self.model,
            model_used=True,
            latency_ms=latency_ms,
        )

    async def _call_reward_api(self, prompt: str, response: str) -> float:
        """Call the NVIDIA NIM reward endpoint and return the score.

        The Nemotron reward model expects a chat-format request with the
        instruction as the user message and returns a score in the response.
        """
        url = f"{self.base_url}/chat/completions"
        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._api_key}",
        }

        # The reward model evaluates the response against the instruction.
        # Format: system prompt sets up the scoring task, user message contains
        # both the instruction and the response to evaluate.
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a reward model that scores responses on a 0.0 to 1.0 scale. "
                    "Output ONLY a single JSON object with key 'score' (float 0.0-1.0). "
                    "Score 1.0 for perfect responses, 0.0 for completely incorrect ones."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Instruction: {prompt}\n\n"
                    f"Response to evaluate: {response}\n\n"
                    "Score this response on how well it follows the instruction (0.0-1.0). "
                    "Return ONLY: {\"score\": <float>}"
                ),
            },
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": 32,
            "temperature": 0.0,
            "stream": False,
        }

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(_REWARD_TIMEOUT, connect=5.0),
        ) as client:
            resp = await client.post(url, json=payload, headers=headers)

        resp.raise_for_status()
        data = resp.json()

        # Extract score from response
        content = data["choices"][0]["message"]["content"]
        return self._parse_score(content)

    def _parse_score(self, content: str) -> float:
        """Parse the reward score from the model's JSON response."""
        import re as _re

        # Try direct JSON parse
        try:
            parsed = json.loads(content.strip())
            if isinstance(parsed, dict) and "score" in parsed:
                score = float(parsed["score"])
                return max(0.0, min(1.0, score))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        # Try regex extract (match positive numbers only, ignore leading minus)
        match = _re.search(r"(?<![-.\d])(\d+\.?\d*)", content)
        if match:
            score = float(match.group(1))
            return max(0.0, min(1.0, score))

        log.debug("Could not parse reward score from: %s", content[:200])
        return 0.0


# ── Module-level singleton ─────────────────────────────────────────────────────

_reward_scorer: RewardScorer | None = None


def get_reward_scorer() -> RewardScorer:
    """Return the module-level RewardScorer singleton."""
    global _reward_scorer
    if _reward_scorer is None:
        _reward_scorer = RewardScorer()
    return _reward_scorer
