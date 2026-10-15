"""agent/verification_runtime.py — the agent loop's end-of-run verification step.

Called once per ``AgentRunner`` run, after the judge: builds the evidence report
from what the run actually executed (agent/verification_evidence.py), binds it
to the workspace's git revision, persists it next to the contract on the plan's
spec (services/spec_store.py), and logs a ``verification_failed`` session event
so recurring failures reach the session retrospective (services/session_retro.py).

Persistence failure never fails the run, but it is recorded on the report
(``persisted``) and logged at WARNING, so a missing record is visible rather
than silently assumed to exist.
"""

from __future__ import annotations

import asyncio
import logging
import subprocess  # nosec B404 - constant git argv, list form
from pathlib import Path
from typing import Any

from agent.verification_contract import VerificationContract
from agent.verification_evidence import EvidenceReport, build_report

log = logging.getLogger("qwen-proxy")


def _git_head(root: Path) -> str | None:
    try:
        proc = subprocess.run(  # nosec B603 B607 - constant git argv, list form (no shell)
            ["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True, timeout=10,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    head = proc.stdout.strip()
    return head if proc.returncode == 0 and head else None


def _ui_gap(steps: list[dict[str, Any]], ui_evidence: list[dict[str, Any]]) -> str | None:
    from tasks.verification import _ui_proof_gap

    try:
        return _ui_proof_gap({"steps": steps, "ui_evidence": ui_evidence})
    except Exception:  # noqa: BLE001 - an unreadable UI check is a gap, not a pass
        log.warning("UI evidence gap check failed", exc_info=True)
        return "the UI evidence check itself failed"


async def finalize_verification(
    *, root: Path, contract: VerificationContract, spec_id: str | None, steps: list[dict[str, Any]],
    judge: dict[str, Any], ui_evidence: list[dict[str, Any]], commits: list[str],
    time_budget_exceeded: bool, log_event: Any = None, session_id: str | None = None,
) -> dict[str, Any]:
    """Build, persist and return the run's evidence report as a dict.

    Never raises: if the report cannot be built, the run keeps its results and
    gets an unreadable-on-purpose record, which the task gate treats as
    INCONCLUSIVE (fail closed), never as a pass.
    """
    revision = await asyncio.to_thread(_git_head, root)
    try:
        report = build_report(
            contract, steps=steps, judge=judge, commits=commits,
            time_budget_exceeded=time_budget_exceeded, ui_gap=_ui_gap(steps, ui_evidence),
            source_revision=revision,
        )
    except Exception as exc:  # noqa: BLE001 - verification infrastructure failure, fail closed
        log.exception("Evidence report could not be built")
        return {"verdict": "INCONCLUSIVE", "persisted": False,
                "reasons": [f"evidence report could not be built: {type(exc).__name__}"]}
    data = report.model_dump()
    data["persisted"] = await _persist(spec_id, report)
    log.info("Verification %s for contract %s (%d checks, risk %s)",
             report.verdict, report.contract_fingerprint, len(report.checks), report.risk_tier)
    if report.verdict != "VERIFIED" and log_event is not None:
        log_event(session_id, "verification_failed", {
            "verdict": report.verdict,
            "failure_phase": (report.findings[0].kind if report.findings else "incomplete"),
            "issues": report.defects()[:5],
        })
    return data


async def _persist(spec_id: str | None, report: EvidenceReport) -> bool:
    if not spec_id:
        return False
    try:
        from services.spec_store import record_evidence

        return await record_evidence(spec_id, report.model_dump())
    except Exception:  # noqa: BLE001 - storage is best-effort; the report still travels with the run
        log.warning("Could not persist evidence report %s", report.report_id, exc_info=True)
        return False


def pr_blockers(report: dict[str, Any] | None) -> list[str]:
    """Auto-PR blockers from the report: never open a PR for work the evidence shows is broken."""
    if not isinstance(report, dict) or report.get("verdict") != "FAILED":
        return []
    reasons = "; ".join(str(r)[:200] for r in (report.get("reasons") or [])[:3])
    return [f"Verification FAILED: {reasons or 'see the evidence report'}"]
