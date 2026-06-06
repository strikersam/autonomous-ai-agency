from __future__ import annotations

"""Synthetic Training Data Generation Pipeline (B3 roadmap item).

Auto-generates fine-tuning data (instruction/response pairs) from successful
agent sessions, filtered by reward model scores, and exported in Alpaca and
ShareGPT formats.

The pipeline:
1. Reads successful agent step results from session stores
2. Generates instruction→response pairs from execution traces
3. Filters by reward model quality scores
4. Exports in Alpaca (instruction/input/output) and ShareGPT (conversations) JSONL
"""

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-proxy")

# ── Configuration ──────────────────────────────────────────────────────────────

_DEFAULT_OUTPUT_DIR = os.environ.get("SYNTHETIC_DATA_DIR", ".data/synthetic")
_MIN_REWARD_SCORE = float(os.environ.get("SYNTHETIC_DATA_MIN_SCORE", "0.7"))
_MAX_SAMPLES_PER_SESSION = int(os.environ.get("SYNTHETIC_DATA_MAX_PER_SESSION", "10"))


@dataclass
class TrainingSample:
    """A single instruction/response pair for fine-tuning."""

    instruction: str
    response: str
    input_context: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    reward_score: float = 0.0
    source_session: str = ""
    source_step: int = 0
    created_at: str = ""

    def to_alpaca(self) -> dict[str, str]:
        """Convert to Alpaca format: {instruction, input, output}."""
        return {
            "instruction": self.instruction,
            "input": self.input_context or "",
            "output": self.response,
        }

    def to_sharegpt(self) -> dict[str, Any]:
        """Convert to ShareGPT format: {conversations: [{from, value}]}."""
        conversations = []
        if self.input_context:
            conversations.append({"from": "system", "value": self.input_context})
        conversations.append({"from": "human", "value": self.instruction})
        conversations.append({"from": "gpt", "value": self.response})
        return {"conversations": conversations}

    def to_dict(self) -> dict[str, Any]:
        return {
            "instruction": self.instruction,
            "response": self.response,
            "input_context": self.input_context,
            "reward_score": self.reward_score,
            "source_session": self.source_session,
            "source_step": self.source_step,
        }


class SyntheticDataPipeline:
    """Pipeline to generate synthetic training data from agent sessions.

    Usage::

        pipeline = SyntheticDataPipeline()
        pipeline.add_step_result(
            instruction="Fix the off-by-one bug in loop.py",
            response="Changed range(n) to range(n+1) on line 42",
            reward_score=0.95,
            session_id="sess-abc",
        )
        pipeline.export_alpaca("training_data.jsonl")
    """

    def __init__(
        self,
        *,
        output_dir: str = _DEFAULT_OUTPUT_DIR,
        min_score: float = _MIN_REWARD_SCORE,
        max_per_session: int = _MAX_SAMPLES_PER_SESSION,
    ) -> None:
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.min_score = min_score
        self.max_per_session = max_per_session
        self._samples: list[TrainingSample] = []
        self._session_counts: dict[str, int] = {}
        self._total_generated = 0
        self._total_filtered = 0

    # ── Ingestion ────────────────────────────────────────────────────────────

    def add_step_result(
        self,
        *,
        instruction: str,
        response: str,
        input_context: str = "",
        reward_score: float = 0.0,
        session_id: str = "",
        step_id: int = 0,
        metadata: dict[str, Any] | None = None,
    ) -> TrainingSample | None:
        """Add a step result. Returns the sample if accepted, None if filtered out."""
        self._total_generated += 1

        # Filter by reward score
        if reward_score < self.min_score:
            self._total_filtered += 1
            return None

        # Cap per-session samples
        count = self._session_counts.get(session_id, 0)
        if count >= self.max_per_session:
            self._total_filtered += 1
            return None

        sample = TrainingSample(
            instruction=instruction,
            response=response,
            input_context=input_context,
            metadata=metadata or {},
            reward_score=reward_score,
            source_session=session_id,
            source_step=step_id,
            created_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        )
        self._samples.append(sample)
        self._session_counts[session_id] = count + 1
        log.debug("Added training sample: session=%s step=%d score=%.2f", session_id, step_id, reward_score)
        return sample

    def add_from_session_results(
        self,
        session_id: str,
        step_results: list[dict[str, Any]],
        goal: str = "",
    ) -> int:
        """Bulk-add samples from an agent session's step results.

        Each step result with status='applied' and changed_files becomes a sample.
        Returns the number of accepted samples.
        """
        accepted = 0
        for step in step_results:
            if step.get("status") != "applied":
                continue
            changed = step.get("changed_files", [])
            if not changed:
                continue
            instruction = f"{goal}\nStep: {step.get('description', '')}\nFiles: {', '.join(changed)}"
            # Build response from observations
            observations = step.get("observations", [])
            response_parts = []
            for obs in observations[-5:]:  # last 5 observations
                tool = obs.get("tool", "")
                result = str(obs.get("result", ""))[:500]
                if tool:
                    response_parts.append(f"[{tool}] {result}")
            response = "\n".join(response_parts) or f"Applied changes to: {', '.join(changed)}"

            confidence = step.get("_confidence_scores", [0.0])
            score = confidence[0] if confidence else 0.5

            if self.add_step_result(
                instruction=instruction,
                response=response,
                input_context=goal,
                reward_score=score,
                session_id=session_id,
                step_id=step.get("step_id", accepted),
            ):
                accepted += 1
        return accepted

    # ── Export ────────────────────────────────────────────────────────────────

    def list_samples(self, min_score: float = 0.0) -> list[TrainingSample]:
        """Return samples filtered by minimum reward score."""
        if min_score <= 0:
            return list(self._samples)
        return [s for s in self._samples if s.reward_score >= min_score]

    def export_alpaca(
        self,
        filename: str = "alpaca_train.jsonl",
        min_score: float = 0.0,
    ) -> str:
        """Export samples in Alpaca JSONL format.

        Returns the path to the exported file.
        """
        path = self.output_dir / filename
        samples = self.list_samples(min_score)
        with open(path, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample.to_alpaca(), ensure_ascii=False) + "\n")
        log.info("Exported %d Alpaca samples to %s", len(samples), path)
        return str(path)

    def export_sharegpt(
        self,
        filename: str = "sharegpt_train.jsonl",
        min_score: float = 0.0,
    ) -> str:
        """Export samples in ShareGPT JSONL format.

        Returns the path to the exported file.
        """
        path = self.output_dir / filename
        samples = self.list_samples(min_score)
        with open(path, "w", encoding="utf-8") as f:
            for sample in samples:
                f.write(json.dumps(sample.to_sharegpt(), ensure_ascii=False) + "\n")
        log.info("Exported %d ShareGPT samples to %s", len(samples), path)
        return str(path)

    def export_json(
        self,
        filename: str = "training_data.json",
        min_score: float = 0.0,
    ) -> str:
        """Export all samples as a structured JSON array.

        Returns the path to the exported file.
        """
        path = self.output_dir / filename
        samples = self.list_samples(min_score)
        with open(path, "w", encoding="utf-8") as f:
            json.dump([s.to_dict() for s in samples], f, ensure_ascii=False, indent=2)
        log.info("Exported %d JSON samples to %s", len(samples), path)
        return str(path)

    # ── Stats ────────────────────────────────────────────────────────────────

    def stats(self) -> dict[str, Any]:
        """Return pipeline statistics."""
        scores = [s.reward_score for s in self._samples]
        return {
            "total_samples": len(self._samples),
            "total_generated": self._total_generated,
            "total_filtered": self._total_filtered,
            "acceptance_rate": round(len(self._samples) / max(1, self._total_generated) * 100, 1),
            "avg_reward_score": round(sum(scores) / max(1, len(scores)), 3) if scores else 0.0,
            "min_score_threshold": self.min_score,
            "sessions": len(self._session_counts),
            "output_dir": str(self.output_dir),
        }

    def clear(self) -> None:
        """Clear all accumulated samples."""
        self._samples.clear()
        self._session_counts.clear()
        self._total_generated = 0
        self._total_filtered = 0


# ── Module-level singleton ─────────────────────────────────────────────────────

_pipeline: SyntheticDataPipeline | None = None


def get_synthetic_pipeline() -> SyntheticDataPipeline:
    """Return the module-level SyntheticDataPipeline singleton."""
    global _pipeline
    if _pipeline is None:
        _pipeline = SyntheticDataPipeline()
    return _pipeline
