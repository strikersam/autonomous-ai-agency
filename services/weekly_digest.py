"""services/weekly_digest.py — Weekly readiness digest for Telegram.

Compiles loop readiness score, drift status, estimated monthly token cost,
and open auto-PR count into a Markdown digest sent via NotificationDispatcher.

Usage (standalone)::

    python -m services.weekly_digest          # one-shot: build + send
    python -m services.weekly_digest --dry    # preview without sending

Usage (in-process, e.g. from a cron loop)::

    from services.weekly_digest import build_digest, send_digest
    text = build_digest()
    send_digest(text)
"""
from __future__ import annotations

import logging
import os
import subprocess  # nosec
import time
from pathlib import Path
from typing import Any

log = logging.getLogger("weekly-digest")

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_readiness() -> dict[str, Any]:
    """Load loop readiness report from the registry."""
    try:
        from agent.loop_registry import load_registry_sync, loop_readiness, audit_drift
        registry = load_registry_sync(_REPO_ROOT / "loops" / "registry.yaml")
        report = loop_readiness(registry)
        drift = audit_drift(registry)
        return {
            "score": report.score,
            "grade": report.grade,
            "total_loops": report.total_loops,
            "by_level": report.by_level,
            "self_heal_coverage": report.self_heal_coverage,
            "dimensions": report.dimensions,
            "drift_ok": drift.ok,
            "missing_from_registry": drift.missing_from_registry,
            "stale_sources": drift.stale_sources,
            "monthly_tokens": registry.estimate_monthly_tokens(),
        }
    except Exception as exc:
        log.warning("weekly-digest: failed to load readiness: %s", exc)
        return {"error": str(exc)}


def _count_open_auto_prs() -> int:
    """Count open PRs with the 'automated' or 'auto-pr' label via git log heuristic."""
    try:
        result = subprocess.run(  # nosec
            ["git", "branch", "-r", "--list", "origin/agent/*"],
            capture_output=True, text=True, timeout=10,
            cwd=str(_REPO_ROOT),
        )
        if result.returncode == 0:
            branches = [b.strip() for b in result.stdout.strip().splitlines() if b.strip()]
            return len(branches)
    except Exception as exc:
        log.debug("weekly-digest: auto-PR branch count failed: %s", exc)
    return 0


def build_digest() -> str:
    """Build the weekly readiness digest as Markdown text."""
    r = _load_readiness()

    lines: list[str] = []
    lines.append("📊 *Weekly Readiness Digest*")
    lines.append(f"_{time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime())}_")
    lines.append("")

    if "error" in r:
        lines.append(f"⚠️ Could not load readiness data: {r['error']}")
        return "\n".join(lines)

    lines.append(f"*Readiness:* {r['score']}/100 (Grade {r['grade']})")
    by_level = r.get("by_level", {})
    lines.append(
        f"*Fleet:* {r['total_loops']} loops — "
        f"L3: {by_level.get('L3', 0)}, "
        f"L2: {by_level.get('L2', 0)}, "
        f"L1: {by_level.get('L1', 0)}"
    )
    lines.append(f"*Self-heal coverage:* {r['self_heal_coverage']:.0%}")
    lines.append("")

    dims = r.get("dimensions", {})
    if dims:
        lines.append("*Dimensions:*")
        for k, v in dims.items():
            lines.append(f"  • {k}: {v}/100")
        lines.append("")

    if r.get("drift_ok"):
        lines.append("✅ No registry drift detected")
    else:
        missing = r.get("missing_from_registry", [])
        stale = r.get("stale_sources", [])
        lines.append("⚠️ *Registry drift detected:*")
        if missing:
            lines.append(f"  Missing entries: {', '.join(missing)}")
        if stale:
            lines.append(f"  Stale sources: {', '.join(stale)}")
    lines.append("")

    monthly_tokens = r.get("monthly_tokens", 0)
    if monthly_tokens > 0:
        lines.append(f"*Est. monthly tokens:* {monthly_tokens:,}")

    auto_pr_count = _count_open_auto_prs()
    lines.append(f"*Open auto-PR branches:* {auto_pr_count}")

    return "\n".join(lines)


def send_digest(text: str) -> None:
    """Send the digest text via NotificationDispatcher (Telegram)."""
    try:
        from telegram_service import NotificationDispatcher
        dispatcher = NotificationDispatcher()
        dispatcher.send_manual_notification(text)
        log.info("weekly-digest: sent successfully")
    except Exception as exc:
        log.error("weekly-digest: send failed: %s", exc)


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    digest = build_digest()
    if "--dry" in sys.argv:
        print(digest)
    else:
        print(digest)
        send_digest(digest)
