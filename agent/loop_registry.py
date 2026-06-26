"""agent/loop_registry.py — Loop Engineering governance layer.

This module turns the repo's *sprawl* of autonomous workflows and in-process
daemons into a single, legible, machine-readable catalogue — the missing
"durable spine" that Loop Engineering (https://github.com/cobusgreyling/loop-engineering)
identifies as the difference between a pile of automations and an operable fleet.

It provides the three things that framework ships as CLI tools, expressed here
as typed, testable code that an operator "running the agency" can rely on:

* **catalogue**   — :class:`LoopRegistry` loaded from ``loops/registry.yaml``.
* **loop-audit**  — :func:`loop_readiness` scores fleet maturity 0..100.
* **loop-cost**   — :meth:`LoopSpec.estimate_monthly_tokens` models token spend.
* **self-heal**   — :func:`audit_drift` detects registry/​workflow drift so the
  catalogue can never silently rot as workflows are added or removed.

Design rules (see ``CLAUDE.md``): type annotations on every public function,
Pydantic models for all I/O shapes, ``logging`` not ``print``, async for file
I/O. The module is import-safe with no side effects and ships a small CLI
(``python -m agent.loop_registry audit``) used by the ``loop-audit`` workflow.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, field_validator

log = logging.getLogger("qwen-loops")

# ---------------------------------------------------------------------------
# Vocabulary — Loop Engineering's maturity ladder, patterns and cost tiers
# ---------------------------------------------------------------------------

# L1 report-only → L2 assisted/​gated fixes → L3 unattended autonomy.
MaturityLevel = Literal["L1", "L2", "L3"]

# Loop Engineering's seven production patterns, plus repo-native ones.
LoopPattern = Literal[
    "daily-triage",
    "pr-babysitter",
    "ci-sweeper",
    "dependency-sweeper",
    "changelog-drafter",
    "post-merge-cleanup",
    "issue-triage",
    # repo-native patterns
    "autonomy-tick",
    "learn-scan",
    "self-heal",
    "infra-heartbeat",
    "security-scan",
]

CostTier = Literal["low", "medium", "high", "very_high"]
TriggerKind = Literal["schedule", "event", "daemon"]

# Approximate token budget a single run of each tier consumes. Used by the
# loop-cost estimator; rough by design (Loop Engineering treats cost as a
# monitored signal, not a precise meter).
_TIER_TOKENS_PER_RUN: dict[CostTier, int] = {
    "low": 2_000,
    "medium": 20_000,
    "high": 120_000,
    "very_high": 400_000,
}

# Default registry location, relative to the repo root (parent of this package).
DEFAULT_REGISTRY_PATH = Path(__file__).resolve().parent.parent / "loops" / "registry.yaml"
DEFAULT_WORKFLOWS_DIR = Path(__file__).resolve().parent.parent / ".github" / "workflows"


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class LoopSpec(BaseModel):
    """A single autonomous loop in the fleet.

    A *loop* is a recurring, self-iterating process — a scheduled workflow or
    an in-process daemon — not a one-shot CI gate. Each loop declares what it
    does, how often, how much it costs, how mature it is, and whether a human
    gate guards its risky actions.
    """

    id: str = Field(..., description="Stable kebab-case identifier.")
    name: str = Field(..., description="Human-readable name.")
    pattern: LoopPattern
    level: MaturityLevel
    trigger: TriggerKind
    cadence: str = Field(..., description="Human-readable cadence, e.g. 'every 2 min'.")
    runs_per_day: float = Field(
        ..., ge=0, description="Approximate runs/day; 0 for event-driven loops."
    )
    cost: CostTier
    source: str = Field(
        ..., description="Backing file/module, e.g. '.github/workflows/x.yml' or 'agent/x.py'."
    )
    self_heal: bool = Field(
        default=False, description="True if the loop detects and repairs failures/​drift."
    )
    gate: Literal["none", "telegram", "human"] = Field(
        default="none", description="Human-approval gate guarding risky/​outward actions."
    )
    purpose: str = Field(default="", description="One-line description of intent.")

    @field_validator("id")
    @classmethod
    def _kebab(cls, v: str) -> str:
        if not v or v != v.strip().lower() or " " in v:
            raise ValueError(f"loop id must be lowercase/​kebab-case without spaces: {v!r}")
        return v

    def estimate_monthly_tokens(self) -> int:
        """loop-cost: approximate tokens this loop spends over 30 days."""
        return int(_TIER_TOKENS_PER_RUN[self.cost] * self.runs_per_day * 30)


class LoopRegistry(BaseModel):
    """The full fleet catalogue."""

    version: int = 1
    loops: list[LoopSpec] = Field(default_factory=list)

    @field_validator("loops")
    @classmethod
    def _unique_ids(cls, loops: list[LoopSpec]) -> list[LoopSpec]:
        ids = [l.id for l in loops]
        dupes = {i for i in ids if ids.count(i) > 1}
        if dupes:
            raise ValueError(f"duplicate loop ids: {sorted(dupes)}")
        return loops

    def by_id(self, loop_id: str) -> LoopSpec | None:
        return next((l for l in self.loops if l.id == loop_id), None)

    def estimate_monthly_tokens(self) -> int:
        """loop-cost: total fleet token spend over 30 days."""
        return sum(l.estimate_monthly_tokens() for l in self.loops)


class ReadinessReport(BaseModel):
    """loop-audit result — fleet maturity scored 0..100 with a breakdown."""

    score: int = Field(..., ge=0, le=100)
    grade: Literal["A", "B", "C", "D", "F"]
    total_loops: int
    by_level: dict[str, int]
    self_heal_coverage: float = Field(..., ge=0, le=1)
    gated_risky_coverage: float = Field(..., ge=0, le=1)
    dimensions: dict[str, int]
    notes: list[str] = Field(default_factory=list)


class DriftReport(BaseModel):
    """self-heal result — divergence between the registry and reality on disk."""

    ok: bool
    missing_from_registry: list[str] = Field(
        default_factory=list, description="Scheduled workflows with no registry entry."
    )
    stale_sources: list[str] = Field(
        default_factory=list, description="Registry entries whose source file is gone."
    )


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def load_registry_sync(path: Path | str = DEFAULT_REGISTRY_PATH) -> LoopRegistry:
    """Load and validate the registry from YAML (synchronous; for CLI/tests)."""
    p = Path(path)
    raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    return LoopRegistry.model_validate(raw)


async def load_registry(path: Path | str = DEFAULT_REGISTRY_PATH) -> LoopRegistry:
    """Async loader — file read runs off the event loop (async-I/O rule)."""
    return await asyncio.to_thread(load_registry_sync, path)


# ---------------------------------------------------------------------------
# loop-audit — fleet readiness scoring
# ---------------------------------------------------------------------------


def _grade(score: int) -> Literal["A", "B", "C", "D", "F"]:
    if score >= 90:
        return "A"
    if score >= 75:
        return "B"
    if score >= 60:
        return "C"
    if score >= 45:
        return "D"
    return "F"


def loop_readiness(registry: LoopRegistry) -> ReadinessReport:
    """Score how mature, self-healing and well-governed the loop fleet is.

    Four weighted dimensions (each 0..100), composited into one score:

    * **maturity** (40%)   — share of loops operating unattended/​assisted (L2+),
      weighted so L3 counts double L2. A fleet stuck at L1 reports but never
      acts is not yet running itself.
    * **self-heal** (25%)  — share of loops that repair failures/​drift.
    * **governance** (20%) — every loop carries a purpose and a real source.
    * **safety** (15%)     — risky high-cost loops sit behind a human gate.
    """
    loops = registry.loops
    n = len(loops)
    by_level = {lvl: sum(1 for l in loops if l.level == lvl) for lvl in ("L1", "L2", "L3")}

    if n == 0:
        return ReadinessReport(
            score=0, grade="F", total_loops=0, by_level=by_level,
            self_heal_coverage=0.0, gated_risky_coverage=0.0,
            dimensions={"maturity": 0, "self_heal": 0, "governance": 0, "safety": 0},
            notes=["registry is empty — no loops catalogued"],
        )

    # maturity: L2 = 0.6 credit, L3 = 1.0 credit, L1 = 0.
    maturity = round(100 * sum(1.0 if l.level == "L3" else 0.6 if l.level == "L2" else 0.0
                               for l in loops) / n)

    self_heal_n = sum(1 for l in loops if l.self_heal)
    self_heal = round(100 * self_heal_n / n)

    governed_n = sum(1 for l in loops if l.purpose.strip() and l.source.strip())
    governance = round(100 * governed_n / n)

    # safety: among risky loops (high/​very_high cost AND able to act, L2+),
    # what fraction carries a human gate? No risky loops → fully safe.
    risky = [l for l in loops if l.cost in ("high", "very_high") and l.level in ("L2", "L3")]
    gated_risky = sum(1 for l in risky if l.gate != "none")
    safety = 100 if not risky else round(100 * gated_risky / len(risky))

    score = round(0.40 * maturity + 0.25 * self_heal + 0.20 * governance + 0.15 * safety)
    score = max(0, min(100, score))

    notes: list[str] = []
    if by_level["L3"] == 0:
        notes.append("no fully-unattended (L3) loops — fleet still needs a human in the cadence")
    if self_heal < 50:
        notes.append("under half of loops self-heal — failures may need manual recovery")
    if risky and gated_risky < len(risky):
        notes.append(f"{len(risky) - gated_risky} risky high-cost loop(s) run without a human gate")

    return ReadinessReport(
        score=score,
        grade=_grade(score),
        total_loops=n,
        by_level=by_level,
        self_heal_coverage=round(self_heal_n / n, 3),
        gated_risky_coverage=round((gated_risky / len(risky)) if risky else 1.0, 3),
        dimensions={"maturity": maturity, "self_heal": self_heal,
                    "governance": governance, "safety": safety},
        notes=notes,
    )


# ---------------------------------------------------------------------------
# self-heal — drift detection between registry and workflows on disk
# ---------------------------------------------------------------------------


def _scheduled_workflow_files(workflows_dir: Path) -> list[str]:
    """Return repo-relative paths of workflows that run on a cron schedule."""
    out: list[str] = []
    if not workflows_dir.is_dir():
        return out
    for wf in sorted(workflows_dir.glob("*.yml")):
        text = wf.read_text(encoding="utf-8", errors="ignore")
        if "schedule:" in text and "cron:" in text:
            out.append(f".github/workflows/{wf.name}")
    return out


def audit_drift(
    registry: LoopRegistry,
    workflows_dir: Path | str = DEFAULT_WORKFLOWS_DIR,
    repo_root: Path | str | None = None,
) -> DriftReport:
    """Detect catalogue rot.

    * **missing_from_registry** — every cron-scheduled workflow must be
      catalogued, so a newly-added autonomous loop can't slip in ungoverned.
    * **stale_sources** — every registry entry's ``source`` file must still
      exist, so deleted loops can't linger as phantom catalogue entries.
    """
    wf_dir = Path(workflows_dir)
    root = Path(repo_root) if repo_root else wf_dir.resolve().parent.parent

    scheduled = set(_scheduled_workflow_files(wf_dir))
    registered_sources = {l.source for l in registry.loops}
    missing = sorted(scheduled - registered_sources)

    stale: list[str] = []
    for loop in registry.loops:
        # Daemons may point at modules; only flag sources that look like repo paths.
        src = loop.source
        if not (root / src).exists():
            stale.append(src)

    return DriftReport(
        ok=not missing and not stale,
        missing_from_registry=missing,
        stale_sources=sorted(stale),
    )


# ---------------------------------------------------------------------------
# CLI — used by the loop-audit workflow and by operators locally
# ---------------------------------------------------------------------------


def _cmd_audit(args: argparse.Namespace) -> int:
    registry = load_registry_sync(args.registry)
    report = loop_readiness(registry)
    drift = audit_drift(registry, args.workflows)

    print(f"Loop Readiness: {report.score}/100 (grade {report.grade})")
    print(f"  loops={report.total_loops}  by_level={report.by_level}")
    print(f"  dimensions={report.dimensions}")
    print(f"  self_heal_coverage={report.self_heal_coverage}  "
          f"gated_risky_coverage={report.gated_risky_coverage}")
    for note in report.notes:
        print(f"  • {note}")
    print(f"Est. fleet spend: ~{registry.estimate_monthly_tokens():,} tokens/30d")
    if drift.ok:
        print("Drift: none — registry matches scheduled workflows on disk")
    else:
        print("Drift DETECTED:")
        for m in drift.missing_from_registry:
            print(f"  - missing from registry: {m}")
        for s in drift.stale_sources:
            print(f"  - stale source (file gone): {s}")

    if args.check and not drift.ok:
        return 1
    if args.min_score is not None and report.score < args.min_score:
        print(f"FAIL: readiness {report.score} < required {args.min_score}", file=sys.stderr)
        return 2
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="loop_registry", description="Loop Engineering audit CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_audit = sub.add_parser("audit", help="Score fleet readiness and detect drift")
    p_audit.add_argument("--registry", default=str(DEFAULT_REGISTRY_PATH))
    p_audit.add_argument("--workflows", default=str(DEFAULT_WORKFLOWS_DIR))
    p_audit.add_argument("--check", action="store_true",
                         help="Exit non-zero if registry/​workflow drift is detected")
    p_audit.add_argument("--min-score", type=int, default=None,
                         help="Exit non-zero if readiness score falls below this")
    p_audit.set_defaults(func=_cmd_audit)

    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    raise SystemExit(main())
