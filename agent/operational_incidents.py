"""agent/operational_incidents.py — recurring operational failures, auto-diagnosed.

Closes the last hop of the self-heal chain: the one an operator was walking by
hand.

``agent/log_monitor.py`` turns application ERROR logs into fix tasks, but it
deliberately drops everything matching ``_OPERATIONAL_PATTERNS`` — timeouts,
"blocked after N dispatch attempts", "all runtimes failed", rate limits. That
filter is correct as far as it goes: an LLM editing source files cannot fix a
saturated free tier, and filing one fix task per timeout is the documented
"timeout → fix task → slow run → timeout" amplification loop.

But dropping them entirely left no path at all. A failure mode that recurred
every few minutes for hours produced exactly zero signal inside the platform —
the only way anyone learned about it was a human reading the dashboard and
pasting logs into a chat. That is the gap this module fills.

The distinction it draws is *one occurrence* versus *a pattern*:

  * a single timeout is noise — a slow provider, a cold model, one bad minute,
  * the same failure ``INCIDENT_THRESHOLD`` times inside ``WINDOW_SECONDS`` is
    an incident, and an incident deserves a diagnosis.

On crossing that line the tracker gathers the evidence a human would have
gathered — the Render logs around the event, including the ``phase_start`` /
``phase_end`` markers that name which agent phase stalled — and files **one**
issue through ``ImprovementLoop.register_external_issue``, the same intake
``services/render_ops.py`` already uses. No second pipeline, no fix task per
occurrence, and the anti-storm properties are kept as hard bounds: a recurrence
threshold, a per-signature cooldown, and an hourly cap.

Signature normalisation is what makes the threshold reachable at all. The
log monitor keys on ``message[:120]`` verbatim, so ``Task task_c7022c0b… timed
out`` and ``Task task_e2d70c78… timed out`` hash differently and each looks
like a first occurrence forever. Here the volatile parts — task ids, job ids,
hex digests, bare numbers — are collapsed first, so repetitions of one failure
mode actually accumulate.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from packages.config import settings

log = logging.getLogger("qwen-agent")

# The tuning bounds live on the settings surface (CLAUDE.md §3 forbids reading
# environment variables outside a config module). They are mirrored here as
# module globals so the hot path does no attribute lookups through settings on
# every log line, and so tests can override one bound without rebuilding the
# whole settings object.
#
# Occurrences of one normalised signature inside WINDOW_SECONDS before the
# pattern is treated as an incident. Below this it is indistinguishable from a
# transient blip, and filing would recreate the storm the log-monitor filter
# exists to prevent.
INCIDENT_THRESHOLD: int = settings.ops_incident_threshold

# Rolling window the threshold is counted over.
WINDOW_SECONDS: int = settings.ops_incident_window_seconds

# Don't re-file the same signature within this window, however often it recurs.
COOLDOWN_SECONDS: int = settings.ops_incident_cooldown_seconds

# Hard ceiling on incidents filed per rolling hour, across all signatures.
MAX_INCIDENTS_PER_HOUR: int = settings.ops_incident_max_per_hour

# How far back to pull Render logs when building the evidence bundle.
EVIDENCE_LOOKBACK_MINUTES: int = settings.ops_incident_lookback_minutes

# Max Render log lines fetched per incident. Bounds both API cost and the size
# of the issue body.
EVIDENCE_LOG_LIMIT: int = 200

# Log lines quoted into the filed issue. The fetch is wider than the quote so
# the phase-marker analysis below sees more than the excerpt does.
EVIDENCE_QUOTE_LINES: int = 25

# Volatile substrings replaced before hashing, so repetitions of one failure
# mode collapse onto a single signature instead of scattering across ids.
_NORMALISERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\btask_[0-9a-f]{6,}\b", re.I), "task_<id>"),
    (re.compile(r"\bjob_[0-9a-f]{6,}\b", re.I), "job_<id>"),
    (re.compile(r"\bdir_[0-9a-f]{6,}\b", re.I), "dir_<id>"),
    (re.compile(r"\bcycle_[0-9a-f]{6,}\b", re.I), "cycle_<id>"),
    (
        re.compile(
            r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I
        ),
        "<uuid>",
    ),
    (re.compile(r"\b[0-9a-f]{12,}\b", re.I), "<hex>"),
    (re.compile(r"\d+"), "<n>"),
)


def _now() -> float:
    """Monotonic clock, behind an indirection so tests can freeze it.

    Patching ``time.monotonic`` itself would mutate the standard-library module
    for every thread in the process for the duration of a test.
    """
    return time.monotonic()


# ── in-process phase tracking ────────────────────────────────────────────────
#
# `agent/loop.py::_timed_phase` logs a phase_start/phase_end pair around every
# LLM call and tool dispatch, and those markers name the call that never
# returned. Reading them back out of Render's log API would mean round-tripping
# our *own* log lines through an external service — and on a single-service
# deployment (no `agency-render-mcp` sidecar) that service is unreachable, so
# the answer would never arrive at all.
#
# Tracking the phases here instead makes the answer exact rather than inferred:
# a phase still open when the incident fires *is* the stall, with its real
# duration, no marker-counting required.

# Bounded so a long-lived process cannot accumulate phases if an end marker is
# ever missed. Oldest entries are dropped first.
_MAX_OPEN_PHASES: int = 64

_phase_lock = threading.Lock()
# (phase, context) → monotonic start time, insertion-ordered so the most
# recently opened — the innermost of a nested pair — is last.
_open_phases: "dict[tuple[str, str], float]" = {}


def note_phase_start(phase: str, context: str = "") -> None:
    """Record that *phase* began. Called from ``_timed_phase``; never raises."""
    try:
        with _phase_lock:
            if len(_open_phases) >= _MAX_OPEN_PHASES:
                _open_phases.pop(next(iter(_open_phases)), None)
            _open_phases[(phase, context)] = _now()
    except Exception:  # noqa: BLE001 - instrumentation must never break the loop
        log.debug("OperationalIncidents: could not record phase start for %s", phase)


def note_phase_end(phase: str, context: str = "") -> None:
    """Record that *phase* finished. Called from ``_timed_phase``; never raises."""
    try:
        with _phase_lock:
            _open_phases.pop((phase, context), None)
    except Exception:  # noqa: BLE001 - instrumentation must never break the loop
        log.debug("OperationalIncidents: could not record phase end for %s", phase)


def open_phase_report() -> dict[str, Any]:
    """Describe the phases currently in flight, innermost (newest) first.

    A phase that has been open far longer than any LLM call should take is the
    stalled one. Because these are tracked as they happen rather than inferred
    from log text, the elapsed time is real — the caller does not have to guess
    from an unbalanced marker count.
    """
    now = _now()
    with _phase_lock:
        raw = list(_open_phases.items())
    # Newest first: with nested phases (`execute_step` wrapping `tool_dispatch`)
    # the inner call is the cause and the wrapper is only the symptom. Sorted on
    # the raw start time, not the rounded elapsed — two phases opening inside
    # one clock tick both round to 0.0s, tie, and fall back to insertion order,
    # which names the outer wrapper.
    raw.sort(key=lambda item: item[1], reverse=True)
    entries = [
        {"phase": phase, "context": context, "open_for_s": round(now - started, 1)}
        for (phase, context), started in raw
    ]
    return {
        "open": entries,
        "likely_stuck_phase": entries[0]["phase"] if entries else None,
        "stuck_for_s": entries[0]["open_for_s"] if entries else None,
    }


def reset_phase_tracking() -> None:
    """Drop all open-phase state. Used by tests."""
    with _phase_lock:
        _open_phases.clear()


def scrub(text: str) -> str:
    """Strip credentials from text before it is written into an issue body.

    Failure samples and Render log excerpts are copied verbatim into the filed
    issue, and this repository has already had a live MongoDB password reach a
    log line that way (2026-08-01). Everything derived from a failure passes
    through here first.

    Both shared helpers are applied because they cover different shapes:
    ``redact_connection_url`` strips a URI's ``user:pass@host`` segment and
    secret query parameters, while ``mask_secret`` catches loose API keys and
    bearer tokens that are not part of a URI. A log excerpt can contain either.

    Fails closed: if a helper is unavailable the value is withheld entirely
    rather than passed through unmasked.
    """
    if not text:
        return ""
    try:
        from packages.auth.rbac import mask_secret
        from packages.security.redact import redact_connection_url

        return mask_secret(redact_connection_url(text))
    except Exception:  # noqa: BLE001 - never let redaction failure leak the raw text
        log.debug("OperationalIncidents: redaction helpers unavailable — withholding value")
        return "<redaction unavailable — value withheld>"


def normalise(message: str) -> str:
    """Collapse the volatile parts of *message* so recurrences group together.

    ``Task task_c7022c0bd20258b3 Execution timed out after 600s`` and
    ``Task task_e2d70c78bf8c35b2 Execution timed out after 600s`` both become
    ``Task task_<id> Execution timed out after <n>s`` — one signature, two
    occurrences, which is the whole point.
    """
    text = (message or "").strip()
    for pattern, replacement in _NORMALISERS:
        text = pattern.sub(replacement, text)
    return text[:200]


def signature_for(logger_name: str, message: str) -> str:
    """Stable dedup key over the *normalised* message."""
    raw = f"{logger_name}:{normalise(message)}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


@dataclass
class OperationalIncident:
    """One failure mode that recurred often enough to warrant diagnosis."""

    signature: str
    logger_name: str
    normalised: str
    sample: str
    count: int
    window_seconds: int
    first_seen: str
    last_seen: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def title(self) -> str:
        """Issue title: the failure mode plus how hard it is recurring."""
        return (
            f"Recurring operational failure ({self.count}x in "
            f"{self.window_seconds // 60}m): {self.normalised[:90]}"
        )


class OperationalIncidentTracker:
    """Count operational failures; diagnose and file the ones that persist.

    Every method is safe to call from a logging handler on any thread: nothing
    here raises, and nothing blocks on I/O. The evidence gathering that does
    touch the network is handed to the event loop as a background task.
    """

    def __init__(self) -> None:
        """Start with no tracked signatures and no filing history."""
        self._lock = threading.Lock()
        self._occurrences: dict[str, list[float]] = {}
        self._samples: dict[str, tuple[str, str]] = {}  # sig → (logger, sample)
        self._first_seen: dict[str, float] = {}
        self._filed: dict[str, float] = {}  # sig → last filed (monotonic)
        self._filed_times: list[float] = []  # rolling hour of filings
        # Attempted and filed are tracked separately: admission is granted
        # synchronously but the filing itself happens later and can fail, so
        # conflating them would let the metrics report incidents that never
        # reached the intake.
        self._incidents_attempted = 0
        self._incidents_filed = 0
        self._cap_warned = False

    # ── public API ────────────────────────────────────────────────────────────

    def record(self, logger_name: str, message: str) -> bool:
        """Note one operational failure. Returns True when it filed an incident.

        Called synchronously from the log-monitor's operational branch, which
        runs inside a ``logging.Handler`` — so this must never raise and never
        block.
        """
        try:
            return self._record(logger_name, message)
        except Exception as exc:  # noqa: BLE001 - never break the logging path
            log.debug("OperationalIncidents: record failed: %s", exc)
            return False

    def note_filing_result(self, sig: str, filed: bool) -> None:
        """Reconcile the admission granted in ``_may_file`` with what happened.

        Admission is granted synchronously — cooldown set, hourly-cap slot
        taken — but the filing itself runs later and can fail: the
        ``ImprovementLoop`` may be idle during startup, the import may fail, or
        the intake may dedup. Without this, one failed attempt would suppress
        the signature for the whole cooldown and the metrics would report an
        incident that never reached the intake. On failure the reservation is
        released so the next recurrence can try again.
        """
        with self._lock:
            if filed:
                self._incidents_filed += 1
                return
            self._filed.pop(sig, None)
            if self._filed_times:
                self._filed_times.pop()

    def get_stats(self) -> dict[str, Any]:
        """Live counters, for the diagnostics endpoint and tests."""
        with self._lock:
            return {
                "tracked_signatures": len(self._occurrences),
                "incidents_attempted": self._incidents_attempted,
                "incidents_filed": self._incidents_filed,
                "threshold": INCIDENT_THRESHOLD,
                "window_seconds": WINDOW_SECONDS,
                "active_cooldowns": len(self._filed),
            }

    def reset(self) -> None:
        """Drop all state. Used by tests."""
        with self._lock:
            self._occurrences.clear()
            self._samples.clear()
            self._first_seen.clear()
            self._filed.clear()
            self._filed_times.clear()
            self._incidents_attempted = 0
            self._incidents_filed = 0
            self._cap_warned = False

    # ── internals ─────────────────────────────────────────────────────────────

    def _record(self, logger_name: str, message: str) -> bool:
        """Count one failure; return True when this crossed into an incident."""
        sig = signature_for(logger_name, message)
        now = _now()

        with self._lock:
            hits = [t for t in self._occurrences.get(sig, []) if t > now - WINDOW_SECONDS]
            hits.append(now)
            self._occurrences[sig] = hits
            self._samples[sig] = (logger_name, (message or "")[:1000])
            self._first_seen.setdefault(sig, now)
            # The process is long-lived and every matching ERROR line adds a
            # signature, so without this the maps only ever grow.
            self._evict_stale(now, keep=sig)

            if len(hits) < INCIDENT_THRESHOLD:
                return False
            if not self._may_file(sig, now):
                return False

            # Scrubbed at construction, not at render time: `normalised` also
            # feeds the issue *title*, so redacting only in the body would leak
            # a credential into the one field that is always displayed.
            incident = OperationalIncident(
                signature=sig,
                logger_name=logger_name,
                normalised=scrub(normalise(message)),
                sample=scrub((message or "")[:1000]),
                count=len(hits),
                window_seconds=WINDOW_SECONDS,
                first_seen=_iso_from_monotonic(self._first_seen[sig], now),
                last_seen=_utcnow_iso(),
            )

        log.warning(
            "OperationalIncidents: %r recurred %dx in %dm — diagnosing and filing",
            incident.normalised[:80], incident.count, WINDOW_SECONDS // 60,
        )
        _schedule(_diagnose_and_file(incident))
        return True

    def _evict_stale(self, now: float, *, keep: str) -> None:
        """Forget signatures that have gone quiet. Caller must hold the lock.

        A signature is droppable once its occurrence bucket has aged out of the
        window *and* its filing cooldown has expired — dropping it earlier would
        release the cooldown and let the same failure re-file.
        """
        cutoff = now - WINDOW_SECONDS
        stale = [
            sig for sig, hits in self._occurrences.items()
            if sig != keep
            and (not hits or hits[-1] <= cutoff)
            and now - self._filed.get(sig, float("-inf")) >= COOLDOWN_SECONDS
        ]
        for sig in stale:
            self._occurrences.pop(sig, None)
            self._samples.pop(sig, None)
            self._first_seen.pop(sig, None)
            self._filed.pop(sig, None)

    def _may_file(self, sig: str, now: float) -> bool:
        """Cooldown + hourly cap. Caller must hold the lock.

        Reserves the slot on success. ``note_filing_result`` releases it again
        if the filing that follows does not reach the intake.
        """
        last = self._filed.get(sig)
        if last is not None and now - last < COOLDOWN_SECONDS:
            return False

        cutoff = now - 3600.0
        self._filed_times = [t for t in self._filed_times if t >= cutoff]
        if MAX_INCIDENTS_PER_HOUR > 0 and len(self._filed_times) >= MAX_INCIDENTS_PER_HOUR:
            if not self._cap_warned:
                log.warning(
                    "OperationalIncidents: hourly cap (%d) reached — "
                    "further incidents suppressed this hour.",
                    MAX_INCIDENTS_PER_HOUR,
                )
                self._cap_warned = True
            return False

        self._filed_times.append(now)
        self._filed[sig] = now
        self._incidents_attempted += 1
        self._cap_warned = False
        return True


# ── evidence gathering ────────────────────────────────────────────────────────


async def gather_render_evidence() -> dict[str, Any]:
    """Pull recent Render logs and summarise them for the issue body.

    This is the manual step being automated: instead of an operator opening the
    Render dashboard and copying a log window, the incident carries its own.

    Degrades rather than fails. Without ``RENDER_API_KEY`` the Render MCP client
    is unavailable, and the incident is still filed — with a note saying the
    platform view was unreachable, which is itself useful.
    """
    try:
        from packages.config import settings
        from packages.integrations.render_mcp import get_render_mcp
    except Exception as exc:  # noqa: BLE001 - optional dependency
        return {"available": False, "reason": f"render integration unavailable: {exc}"}

    if not settings.is_render_mcp_configured:
        return {
            "available": False,
            "reason": "RENDER_API_KEY / RENDER_MCP_URL not configured",
        }

    now = datetime.now(timezone.utc)
    try:
        client = get_render_mcp()
        # Honours the RENDER_SERVICE_IDS allow-list, falling back to workspace
        # discovery — the same resolution the Render ops loop uses.
        service_ids = await client.resolve_service_ids()
        if not service_ids:
            return {"available": False, "reason": "no Render services resolved"}
        logs = await client.list_logs(
            service_ids,
            start_time=(now - timedelta(minutes=EVIDENCE_LOOKBACK_MINUTES)).isoformat(),
            end_time=now.isoformat(),
            limit=EVIDENCE_LOG_LIMIT,
        )
    except Exception as exc:  # noqa: BLE001 - diagnosis must not raise
        return {"available": False, "reason": f"log fetch failed: {exc}"}

    messages = [str(entry.get("message", "")) for entry in (logs or [])]
    return {
        "available": True,
        "line_count": len(messages),
        "window_minutes": EVIDENCE_LOOKBACK_MINUTES,
        "phases": summarise_phases(messages),
        "excerpt": "\n".join(m[:220] for m in messages[-EVIDENCE_QUOTE_LINES:]),
    }


def summarise_phases(messages: list[str]) -> dict[str, Any]:
    """Find agent phases that started but never finished.

    ``agent/loop.py::_timed_phase`` brackets every LLM call and tool dispatch
    with ``phase_start <phase> …`` / ``phase_end <phase> … elapsed_s=…``. A
    phase with more starts than ends in the same window is one that never
    returned — which names the stuck call outright instead of leaving only the
    outer "Execution timed out after 600s".
    """
    starts: dict[str, int] = {}
    ends: dict[str, int] = {}
    last_start_at: dict[str, int] = {}
    for position, message in enumerate(messages):
        for marker, bucket in (("phase_start ", starts), ("phase_end ", ends)):
            idx = message.find(marker)
            if idx == -1:
                continue
            rest = message[idx + len(marker):].strip()
            phase = rest.split(" ", 1)[0] if rest else "?"
            bucket[phase] = bucket.get(phase, 0) + 1
            if bucket is starts:
                last_start_at[phase] = position

    unfinished = {
        phase: count - ends.get(phase, 0)
        for phase, count in starts.items()
        if count - ends.get(phase, 0) > 0
    }
    # The phases nest: `execute_step` wraps `tool_dispatch`, so an inner call
    # that never returns leaves *both* unfinished. The innermost one is the
    # actual stall, and it is the one whose `phase_start` came last — ranking
    # by count instead would tie and pick the outer wrapper, naming the
    # symptom rather than the cause.
    stuck = max(unfinished, key=lambda p: last_start_at.get(p, -1)) if unfinished else None
    return {
        "started": starts,
        "finished": ends,
        "unfinished": unfinished,
        "likely_stuck_phase": stuck,
    }


async def _diagnose_and_file(incident: OperationalIncident) -> None:
    """Attach evidence to *incident*, then hand it to the existing intake.

    The filing outcome is reported back to the tracker so a failed attempt
    releases its cooldown and hourly-cap slot instead of suppressing the
    signature for hours over an intake that was merely not running yet.
    """
    # The in-process view first: it needs no network, no API key, and no
    # sidecar, so it is the one source that is always present. Render is
    # enrichment on top — valuable for what the process could not log because
    # it was killed (OOM, restart), useless if the MCP sidecar is not deployed.
    evidence: dict[str, Any] = {"phases_in_process": open_phase_report()}
    try:
        evidence.update(await gather_render_evidence())
    except Exception as exc:  # noqa: BLE001 - file it even without evidence
        evidence.update({"available": False, "reason": str(exc)})
    incident.evidence = evidence

    filed = _file_incident(incident)
    if filed:
        log.info("OperationalIncidents: filed %s", incident.title)
    else:
        log.warning(
            "OperationalIncidents: could not file %r — releasing its cooldown so "
            "the next recurrence can retry", incident.normalised[:80],
        )
    get_operational_incident_tracker().note_filing_result(incident.signature, filed)


def _file_incident(incident: OperationalIncident) -> bool:
    """Register the incident through ``ImprovementLoop.register_external_issue``.

    Deliberately the same intake ``services/render_ops.py`` uses: one issue
    pipeline, one dedup path, one set of persistence rules.
    """
    try:
        from agent.improvement_loop import (
            DetectedIssue, IssueCategory, IssueSeverity, get_improvement_loop,
        )
    except Exception as exc:  # noqa: BLE001 - intake is optional
        log.debug("OperationalIncidents: ImprovementLoop unavailable (%s)", exc)
        return False

    loop = get_improvement_loop()
    if loop is None:
        log.info(
            "OperationalIncidents: %s (not filed, ImprovementLoop idle)", incident.title
        )
        return False

    issue = DetectedIssue(
        issue_id=f"ops-{incident.signature}",
        category=IssueCategory.PERFORMANCE,
        severity=IssueSeverity.HIGH,
        title=incident.title,
        description=_format_incident(incident),
    )
    try:
        return bool(loop.register_external_issue(issue))
    except Exception as exc:  # noqa: BLE001 - never break the tracker
        log.warning("OperationalIncidents: could not register issue: %s", exc)
        return False


def _format_incident(incident: OperationalIncident) -> str:
    """Build the issue body: what recurred, plus the gathered evidence."""
    evidence = incident.evidence or {}
    parts = [
        f"An operational failure recurred **{incident.count} times** in the last "
        f"{incident.window_seconds // 60} minutes.",
        "",
        f"**Logger:** `{incident.logger_name}`",
        f"**Normalised signature:** `{incident.normalised}`",
        f"**First seen:** {incident.first_seen}  ",
        f"**Last seen:** {incident.last_seen}",
        "",
        "**Sample message:**",
        f"```\n{scrub(incident.sample[:800])}\n```",
    ]

    # In-process phases are authoritative: tracked as they happen rather than
    # inferred from log text, so the phase and its real duration are exact.
    in_process = evidence.get("phases_in_process") or {}
    stuck_now = in_process.get("likely_stuck_phase")
    if stuck_now:
        parts += [
            "",
            f"**Stuck phase: `{stuck_now}`** — open for "
            f"{in_process.get('stuck_for_s')}s and still not returned "
            "(`agent/loop.py::_timed_phase`, tracked in-process).",
            f"All phases currently open: `{in_process.get('open')}`",
        ]
    elif in_process:
        parts += [
            "",
            "No agent phase was open when this fired — the stall is outside the "
            "loop's instrumented phases (or the run had already been abandoned).",
        ]

    # The Render-log view is a cross-check, and covers windows the process
    # itself could not log (an OOM kill leaves no in-process trace).
    phases = evidence.get("phases") or {}
    stuck = phases.get("likely_stuck_phase")
    if stuck and stuck != stuck_now:
        unfinished = phases.get("unfinished", {})
        parts += [
            "",
            f"Render logs additionally show `{stuck}` with "
            f"{unfinished.get(stuck)} more `phase_start` than `phase_end` in the "
            f"window. Unfinished: `{unfinished}`",
        ]

    if evidence.get("available"):
        parts += [
            "",
            f"**Render logs** (last {evidence.get('window_minutes')}m, "
            f"{evidence.get('line_count')} lines):",
            f"```\n{scrub(evidence.get('excerpt', ''))[:2500]}\n```",
        ]
    else:
        parts += [
            "",
            f"_Render platform logs unavailable: {evidence.get('reason', 'unknown')}._ "
            "This is enrichment only — the in-process phase view above does not "
            "depend on it. If the reason is a connection failure, the "
            "`agency-render-mcp` sidecar declared in `render.yaml` is probably "
            "not deployed, which also means `services/render_ops.py` "
            "(deploy/OOM/memory monitoring) is silently doing nothing.",
        ]

    parts += [
        "",
        "**Source:** operational-incident tracker (`agent/operational_incidents.py`). "
        "This is an infrastructure/behaviour failure, not necessarily a code defect — "
        "diagnose before editing, and prefer a configuration or bound change over a "
        "source edit when the cause is capacity or latency.",
    ]
    return "\n".join(parts)


# ── helpers ───────────────────────────────────────────────────────────────────


def _utcnow_iso() -> str:
    """Current UTC wall-clock as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()


def _iso_from_monotonic(then: float, now: float) -> str:
    """Best-effort wall-clock for a monotonic timestamp taken earlier."""
    delta = max(0.0, now - then)
    return (datetime.now(timezone.utc) - timedelta(seconds=delta)).isoformat()


# Strong references to in-flight diagnosis tasks. The event loop holds only a
# weak one, so without this the garbage collector can reclaim a task mid-flight
# and the diagnosis disappears silently.
_pending: set[asyncio.Task[None]] = set()


def _schedule(coro: Any) -> None:
    """Run *coro* without blocking the caller, from any thread.

    The caller is a logging handler, which may be on the event loop thread, a
    worker thread, or a process with no loop at all.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        threading.Thread(target=asyncio.run, args=(coro,), daemon=True).start()
        return
    task = loop.create_task(coro)
    _pending.add(task)
    task.add_done_callback(_pending.discard)


# ── singleton ─────────────────────────────────────────────────────────────────

_tracker: OperationalIncidentTracker | None = None


def get_operational_incident_tracker() -> OperationalIncidentTracker:
    """Return the shared tracker, creating it on first use."""
    global _tracker
    if _tracker is None:
        _tracker = OperationalIncidentTracker()
    return _tracker


def reset_operational_incident_tracker() -> None:
    """Drop the cached tracker. Used by tests."""
    global _tracker
    _tracker = None


def record_operational_error(logger_name: str, message: str) -> bool:
    """Module-level entry point used by ``agent/log_monitor.py``."""
    return get_operational_incident_tracker().record(logger_name, message)
