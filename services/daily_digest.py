from __future__ import annotations

"""services/daily_digest.py

Daily review digest — the user-review surface for the autonomous agency.

Two halves:
  1. aggregate_last_24h(...) -> DigestSummary    (pure data assembly)
  2. format_digest_markdown(...) -> str           (Markdown-v1 escape)

build_daily_digest(...) combines them and applies the big-message policy:
  if the rendered markdown exceeds 4096 chars, the full version is written
  to ~/.agency/workspace/pastes/digest-<date>.md and the returned markdown
  body is replaced with a short pointer + counts. The dispatcher still sends
  the short body to Telegram via `send_daily_digest_async()`.

User-locked decisions:
  - Single-operator scope (chat_id 8661289550 / TELEGRAM_CHAT_ID env)
  - No decision TTL (decisions live until resolved)
  - Big-message policy: truncate + auto-upload to AGENCY_WORKSPACE_ROOT/pastes/

Public API:
  - build_daily_digest(decisions_store, workflow_orchestrator, cutoff_utc=None, workspace_root=None) -> DigestPayload
  - aggregate_last_24h(...) -> DigestSummary
  - format_digest_markdown(summary, generated_utc=None) -> str
  - compute_cutoff(hours=24) -> datetime

The aggregator takes workflow_orchestrator either as the singleton callable
or as a get_workflow_orchestrator() reference — both shapes work because
backend's admin endpoint passes the callable.
"""
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Callable, Optional, Union

log = logging.getLogger(__name__)

_TELEGRAM_MAX_CHARS = 4096
_TRUNCATE_THRESHOLD = 4000  # leave headroom for ellipsis + footer text

_REVIEW_STATUSES = frozenset({"awaiting_approval", "pending_review", "needs_user"})
_WIN_STATUSES = frozenset({"completed", "succeeded"})


@dataclass
class DigestSummary:
    awaiting_review: list[dict[str, Any]] = field(default_factory=list)
    recent_wins: list[dict[str, Any]] = field(default_factory=list)
    pending_decisions: list[dict[str, Any]] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


@dataclass
class DigestPayload:
    cutoff_utc: str
    generated_utc: str
    summary: DigestSummary
    markdown_body: str
    truncated_path: Optional[str] = None  # set when markdown exceeds TELEGRAM_MAX


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def compute_cutoff(hours: int = 24) -> datetime:
    return _now_utc() - timedelta(hours=hours)


def _md_escape(s: str) -> str:
    """Light-weight Markdown-v1 escape for Telegram. Defensive: never trust
    user-supplied data in digest body."""
    if not s:
        return ""
    return (
        s.replace("\\", "\\\\")
        .replace("*", "\\*")
        .replace("_", "\\_")
        .replace("`", "\\`")
        .replace("[", "\\[")
    )


def _try_parse_json(s: str) -> dict[str, Any]:
    try:
        v = json.loads(s)
        return v if isinstance(v, dict) else {"raw": v}
    except Exception:
        return {"raw": s}


def _run_attr(run: Any, key: str, default: Any = None) -> Any:
    if isinstance(run, dict):
        return run.get(key, default)
    return getattr(run, key, default)


def _resolve_orchestrator(
    workflow_orchestrator: Union[Any, Callable[[], Any]],
) -> Optional[Any]:
    if callable(workflow_orchestrator):
        try:
            return workflow_orchestrator()
        except Exception as exc:
            log.warning("daily_digest.orchestrator_call_failed exc=%s", exc)
            return None
    return workflow_orchestrator


def aggregate_last_24h(
    *,
    decisions_store: Any,
    workflow_orchestrator: Union[Any, Callable[[], Any]],
    cutoff_utc: Optional[datetime] = None,
) -> DigestSummary:
    """Pure aggregator: no I/O, no formatting. All callers pass stores in."""
    cutoff = cutoff_utc or compute_cutoff(24)
    cutoff_iso = cutoff.isoformat()

    pending_decisions: list[dict[str, Any]] = []
    try:
        for d in (decisions_store.list_pending() or []):
            pending_decisions.append(
                {
                    "decision_id": d.get("decision_id"),
                    "decision_type": d.get("decision_type"),
                    "context": _try_parse_json(d.get("context_json", "{}")),
                    "created_utc": d.get("created_utc"),
                }
            )
    except Exception as exc:
        # Graceful degradation: SQLite OperationalError (lock contention,
        # permission denied, WAL pressure) must not block the digest — the
        # operator still benefits from workflow-orchestrator counts even if
        # the decision store is briefly unreachable.
        log.warning("daily_digest.aggregator.decisions_store_failed exc=%s", exc)

    awaiting_review: list[dict[str, Any]] = []
    recent_wins: list[dict[str, Any]] = []
    orch = _resolve_orchestrator(workflow_orchestrator)
    if orch is not None and hasattr(orch, "list_runs"):
        try:
            runs = orch.list_runs() or []
        except Exception as exc:
            log.warning("daily_digest.list_runs_failed exc=%s", exc)
            runs = []
        for run in runs:
            status = _run_attr(run, "status")
            if status in _REVIEW_STATUSES:
                awaiting_review.append(
                    {
                        "run_id": _run_attr(run, "run_id"),
                        "goal": _run_attr(run, "goal", ""),
                        "status": status,
                        "created_utc": _run_attr(run, "created_at") or _run_attr(run, "created_utc"),
                    }
                )
            elif status in _WIN_STATUSES:
                finished = _run_attr(run, "finished_at") or _run_attr(run, "finished_utc")
                if finished and finished >= cutoff_iso:
                    recent_wins.append(
                        {
                            "run_id": _run_attr(run, "run_id"),
                            "goal": _run_attr(run, "goal", ""),
                            "finished_utc": finished,
                        }
                    )
        recent_wins = recent_wins[:5]

    counts = {
        "awaiting_review": len(awaiting_review),
        "pending_decisions": len(pending_decisions),
        "recent_wins_24h": len(recent_wins),
    }
    return DigestSummary(
        awaiting_review=awaiting_review,
        recent_wins=recent_wins,
        pending_decisions=pending_decisions,
        counts=counts,
    )


def format_digest_markdown(summary: DigestSummary, *, generated_utc: Optional[str] = None) -> str:
    gen = generated_utc or _now_utc().isoformat()
    counts = summary.counts

    lines: list[str] = [
        f"*Daily Review Digest* — {gen}",
        "",
        (
            f"_Counts:_ awaiting\\_review={counts.get('awaiting_review', 0)} "
            f"pending\\_decisions={counts.get('pending_decisions', 0)} "
            f"recent\\_wins\\_24h={counts.get('recent_wins_24h', 0)}"
        ),
    ]

    if summary.recent_wins:
        lines += ["", "*Recent wins (last 24h):*"]
        for win in summary.recent_wins[:5]:
            run_id = _md_escape(str(win.get("run_id") or "?"))
            goal = _md_escape(str(win.get("goal") or "")[:120])
            lines.append(f"• `{run_id}` — {goal}")

    if summary.awaiting_review:
        lines += ["", "*Awaiting your review (workflow runs):*"]
        for r in summary.awaiting_review[:8]:
            run_id = _md_escape(str(r.get("run_id") or "?"))
            goal = _md_escape(str(r.get("goal") or "")[:120])
            lines.append(f"• `{run_id}` — {goal}")

    if summary.pending_decisions:
        lines += ["", "*Pending decisions:*"]
        for d in summary.pending_decisions[:8]:
            did = _md_escape(str(d.get("decision_id") or "?"))
            dtype = _md_escape(str(d.get("decision_type") or "?"))
            ctx = d.get("context") or {}
            one_liner = ctx.get("one_liner") or ctx.get("question") or ""
            one_liner = _md_escape(str(one_liner)[:120])
            lines.append(f"• `{did}` ({dtype}) — {one_liner}")

    lines += [
        "",
        "_Reply `/approve dec\\_xxxx` to clear, or `/redirect dec\\_xxxx <text>` to amend._",
    ]
    return "\n".join(lines)


def build_daily_digest(
    *,
    decisions_store: Any,
    workflow_orchestrator: Union[Any, Callable[[], Any]],
    cutoff_utc: Optional[datetime] = None,
    workspace_root: Optional[str] = None,
    now_utc: Optional[datetime] = None,
) -> DigestPayload:
    """Top-level entry. Returns DigestPayload ready for Telegram dispatch."""
    gen_now = now_utc or _now_utc()
    cutoff = cutoff_utc or (gen_now - timedelta(hours=24))

    summary = aggregate_last_24h(
        decisions_store=decisions_store,
        workflow_orchestrator=workflow_orchestrator,
        cutoff_utc=cutoff,
    )
    md = format_digest_markdown(summary, generated_utc=gen_now.isoformat())

    truncated_path: Optional[str] = None
    if len(md) > _TRUNCATE_THRESHOLD:
        root = workspace_root or os.environ.get("AGENCY_WORKSPACE_ROOT", "~/.agency/workspace")
        if root.startswith("~"):
            root = str(Path(root).expanduser())
        date_str = gen_now.strftime("%Y-%m-%d")
        out_path = Path(root) / "pastes" / f"digest-{date_str}.md"
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(md, encoding="utf-8")
            truncated_path = str(out_path)
        except OSError as exc:
            log.warning("daily_digest.workspace_write_failed path=%s exc=%s", out_path, exc)
            truncated_path = None
        md = _short_digest(summary, gen_now, truncated_path)

    return DigestPayload(
        cutoff_utc=cutoff.isoformat(),
        generated_utc=gen_now.isoformat(),
        summary=summary,
        markdown_body=md,
        truncated_path=truncated_path,
    )


def _short_digest(summary: DigestSummary, gen_now: datetime, truncated_path: Optional[str]) -> str:
    counts = summary.counts
    return (
        f"*Daily Review Digest* — {gen_now.isoformat()}\n"
        f"\nAwaiting={counts.get('awaiting_review', 0)} | "
        f"Pending={counts.get('pending_decisions', 0)} | "
        f"Wins(24h)={counts.get('recent_wins_24h', 0)}."
        + (f"\nFull digest: `{truncated_path}`" if truncated_path else "")
        + "\n_Reply `/approve dec\\_xxxx` or `/redirect dec\\_xxxx <text>`._"
    )
