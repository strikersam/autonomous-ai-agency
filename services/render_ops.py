"""services/render_ops.py — autonomous Render debugging + environment monitoring.

Closes the blind spot in the self-heal chain. Today that chain starts at
``agent/log_monitor.py``, which attaches a handler to the root logger — so it
can only ever see failures that a *running* Python process logged. Everything
the platform does around the process is invisible to it:

  * a build that failed, so no container ever started,
  * an OOM kill or a restart loop,
  * memory or CPU pinned at the plan ceiling,
  * a deploy stuck in ``build_in_progress``,
  * 5xx served by the edge before a handler ran.

This module polls that view through the Render MCP server and feeds what it
finds into the *existing* intake — ``ImprovementLoop.register_external_issue``
— rather than starting a second issue pipeline. From there the normal
plan→execute→verify machinery picks the work up unchanged.

Signals detected per tick:

  ``deploy_failed``   latest deploy for a watched service is in a failed state
  ``deploy_stalled``  a deploy has been in progress past ``STALLED_DEPLOY_SECONDS``
  ``error_logs``      platform error logs in the window exceed ``ERROR_LOG_THRESHOLD``
  ``memory_pressure`` memory usage is above ``MEMORY_PRESSURE_RATIO`` of the limit

The loop is read-only. It never triggers a deploy or edits an environment
variable, regardless of ``RENDER_MCP_ALLOW_WRITES`` — diagnosing production and
changing production are different privileges, and only the first one belongs on
a timer.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from agent.mcp_client import MCPUnavailableError
from packages.config import settings
from packages.integrations.render_mcp import RenderDeploy, get_render_mcp

log = logging.getLogger("qwen-agent")

# A deploy still building after this long is treated as stalled.
STALLED_DEPLOY_SECONDS: int = 1800  # 30 minutes

# Number of platform ERROR log lines in the lookback window that constitutes a
# spike worth filing. Below this, normal noise (a scanner 404, a cold-start
# retry) would create an issue every tick.
ERROR_LOG_THRESHOLD: int = 10

# Memory usage above this fraction of the plan limit is reported. Render's free
# tier is 512MB and this service runs close to it, so the bar is set where a
# restart becomes likely rather than at the first sign of growth.
MEMORY_PRESSURE_RATIO: float = 0.90

# How far back each tick looks for error logs.
LOG_LOOKBACK_MINUTES: int = 30

# Max log lines fetched per service per tick — bounds both the Render API cost
# and the size of anything quoted into an issue body.
LOG_FETCH_LIMIT: int = 100

# Don't re-file the same finding within this window. Signature is
# sha256(kind + service_id + discriminator), so a deploy that fails twice for
# the same commit is one issue, not two.
COOLDOWN_SECONDS: int = 6 * 3600

# Deploy statuses that mean "still working on it".
_IN_PROGRESS_STATUSES: frozenset[str] = frozenset(
    {"created", "queued", "build_in_progress", "update_in_progress", "pre_deploy_in_progress"}
)

_SEVERITY_BY_KIND: dict[str, str] = {
    "deploy_failed": "critical",
    "deploy_stalled": "high",
    "error_logs": "high",
    "memory_pressure": "medium",
}


@dataclass
class RenderFinding:
    """One actionable problem observed on the Render platform."""

    kind: str
    service_id: str
    service_name: str
    severity: str
    title: str
    detail: str
    evidence: dict[str, Any] = field(default_factory=dict)

    @property
    def signature(self) -> str:
        """Stable dedup key: same problem on same service → same signature.

        Only ``deploy_id`` discriminates, because a *different* failed deploy is
        genuinely a different problem. Nothing time-derived may appear here: an
        earlier version also fell back to the hourly ``bucket``, which made the
        signature change every hour and so could never be blocked by the
        six-hour cooldown — a sustained error spike filed twelve issues a day
        instead of four, and ``_cooldowns`` grew an entry per hour forever.
        ``bucket`` stays in ``evidence`` for display.
        """
        discriminator = str(self.evidence.get("deploy_id") or "")
        raw = f"{self.kind}:{self.service_id}:{discriminator}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def as_dict(self) -> dict[str, Any]:
        return {**asdict(self), "signature": self.signature}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _rfc3339(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_timestamp(value: str) -> datetime | None:
    """Parse an RFC3339 timestamp from Render, tolerating a trailing ``Z``."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_metric_value(payload: Any) -> float | None:
    """Pull the most recent numeric sample out of a ``get_metrics`` payload.

    Render nests samples differently per metric type and the shape is not
    guaranteed, so this walks the structure looking for the last ``value``
    rather than indexing a fixed path — a shape change degrades to "no
    reading" instead of raising inside the monitoring loop.
    """
    if isinstance(payload, dict):
        for key in ("values", "samples", "points", "data"):
            found = _latest_metric_value(payload.get(key))
            if found is not None:
                return found
        if "value" in payload:
            try:
                return float(payload["value"])
            except (TypeError, ValueError):
                return None
        for value in payload.values():
            found = _latest_metric_value(value)
            if found is not None:
                return found
        return None
    if isinstance(payload, list):
        for item in reversed(payload):
            found = _latest_metric_value(item)
            if found is not None:
                return found
    return None


class RenderOpsMonitor:
    """Polls Render for platform-level failures and files them as issues."""

    def __init__(self, client: Any = None) -> None:
        self._client = client or get_render_mcp()
        self._cooldowns: dict[str, float] = {}
        self._ticks = 0
        self._findings_filed = 0
        self._findings_dropped = 0
        self._last_error: str = ""
        self._last_tick_at: str = ""

    # ── public API ───────────────────────────────────────────────────────────

    def get_status(self) -> dict[str, Any]:
        """Snapshot for ``/api/render/ops/status`` and the dashboard.

        ``self_heal_ready`` is the difference between *detecting* platform
        failures and *fixing* them. Findings are handed to the ImprovementLoop,
        which schedules the actual repair task; when that loop is not running the
        finding is logged and dropped, and the monitor looks healthy while
        nothing heals. Reporting it here means the dashboard can say which of
        the two is happening instead of showing a green tick either way.
        """
        return {
            "enabled": settings.is_render_ops_enabled,
            "configured": self._client.is_configured,
            "write_allowed": settings.is_render_mcp_write_allowed,
            "interval_seconds": settings.render_ops_interval_seconds,
            "ticks": self._ticks,
            "findings_filed": self._findings_filed,
            "findings_dropped": self._findings_dropped,
            "self_heal_ready": _self_heal_ready(),
            "active_cooldowns": len(self._cooldowns),
            "last_tick_at": self._last_tick_at,
            "last_error": self._last_error,
        }

    async def scan(self) -> list[RenderFinding]:
        """Run one full scan and return every finding, filed or not.

        Never raises: a monitoring loop that dies on an unreachable dependency
        stops monitoring exactly when it matters most. Transport failures are
        recorded in ``last_error`` and surfaced through ``get_status()``.
        """
        self._ticks += 1
        self._last_tick_at = _rfc3339(_utcnow())
        findings: list[RenderFinding] = []
        try:
            service_ids = await self._client.resolve_service_ids()
        except (MCPUnavailableError, RuntimeError) as exc:
            self._last_error = f"service discovery failed: {exc}"
            log.warning("RenderOps: %s", self._last_error)
            return []

        names = await self._service_names(service_ids)
        failed = False
        for service_id in service_ids:
            name = names.get(service_id, service_id)
            for check in (self._check_deploys, self._check_error_logs, self._check_memory):
                try:
                    findings.extend(await check(service_id, name))
                except (MCPUnavailableError, RuntimeError) as exc:
                    failed = True
                    self._last_error = f"{check.__name__} failed for {name}: {exc}"
                    log.warning("RenderOps: %s", self._last_error)
        # Only a scan where every check succeeded clears the error. Clearing it
        # because *some* finding came back would hide a check that is failing
        # every tick behind another check that happens to be working.
        if not failed:
            self._last_error = ""
        return findings

    async def tick(self) -> list[RenderFinding]:
        """Scan, then file everything that is past its cooldown.

        The cooldown is claimed only after a finding is actually filed. Claiming
        on the attempt would burn six hours of silence when the ImprovementLoop
        happened not to be up yet — which is exactly the window right after a
        restart, when platform findings matter most.
        """
        findings = await self.scan()

        # Every observation is reported to the healer, including ones inside
        # their cooldown: that is how it learns a fix did not hold.
        for finding in findings:
            _note_recurrence(finding)

        filed: list[RenderFinding] = []
        dropped = 0
        for finding in findings:
            if not self._is_cool(finding):
                continue
            if not _file_issue(finding):
                # Detected but nothing will fix it — almost always the
                # ImprovementLoop being down. Counted so the dashboard can show
                # "finding things, healing nothing" rather than a silent zero.
                dropped += 1
                continue
            if self._claim(finding):
                filed.append(finding)

        # Newly filed findings also open a verified heal, so the fix is checked
        # rather than merely scheduled.
        for finding in filed:
            await _report_to_healer(finding)

        self._findings_filed += len(filed)
        self._findings_dropped += dropped
        if filed:
            log.warning(
                "RenderOps: filed %d platform issue(s): %s",
                len(filed), ", ".join(f"{f.kind}/{f.service_name}" for f in filed),
            )
        if dropped:
            log.warning(
                "RenderOps: %d finding(s) detected but not filed — no fix will be "
                "scheduled for them. Check that the ImprovementLoop is running "
                "(AGENCY_IMPROVEMENT_ENABLED, RUN_BACKGROUND_IN_WEB).",
                dropped,
            )
        return filed

    # ── checks ───────────────────────────────────────────────────────────────

    async def _service_names(self, service_ids: list[str]) -> dict[str, str]:
        """Map service ID → human name, degrading to the ID when unavailable."""
        try:
            services = await self._client.list_services()
        except (MCPUnavailableError, RuntimeError):
            return {}
        return {
            s["id"]: str(s.get("name") or s["id"])
            for s in services
            if isinstance(s.get("id"), str) and s["id"] in set(service_ids)
        }

    async def _check_deploys(self, service_id: str, name: str) -> list[RenderFinding]:
        """Flag a failed latest deploy, or one that has been building too long."""
        deploy: RenderDeploy | None = await self._client.latest_deploy(service_id)
        if deploy is None:
            return []

        if deploy.failed:
            return [
                RenderFinding(
                    kind="deploy_failed",
                    service_id=service_id,
                    service_name=name,
                    severity=_SEVERITY_BY_KIND["deploy_failed"],
                    title=f"Render deploy failed for {name} ({deploy.status})",
                    detail=(
                        f"The most recent deploy of `{name}` finished with status "
                        f"`{deploy.status}`, so the running code is not the code on "
                        f"master. Commit `{deploy.commit[:8] or 'unknown'}`, created "
                        f"{deploy.created_at or 'unknown'}."
                    ),
                    evidence=deploy.as_dict(),
                )
            ]

        if deploy.status in _IN_PROGRESS_STATUSES:
            started = _parse_timestamp(deploy.created_at)
            if started and _utcnow() - started > timedelta(seconds=STALLED_DEPLOY_SECONDS):
                age_min = int((_utcnow() - started).total_seconds() // 60)
                return [
                    RenderFinding(
                        kind="deploy_stalled",
                        service_id=service_id,
                        service_name=name,
                        severity=_SEVERITY_BY_KIND["deploy_stalled"],
                        title=f"Render deploy stalled for {name} ({age_min}m in {deploy.status})",
                        detail=(
                            f"Deploy `{deploy.deploy_id}` of `{name}` has been in "
                            f"`{deploy.status}` for {age_min} minutes, past the "
                            f"{STALLED_DEPLOY_SECONDS // 60}-minute threshold. Check the "
                            "build log for a hung install or a dependency fetch that "
                            "never returns."
                        ),
                        evidence=deploy.as_dict(),
                    )
                ]
        return []

    async def _check_error_logs(self, service_id: str, name: str) -> list[RenderFinding]:
        """Flag an error-log spike in the lookback window."""
        now = _utcnow()
        logs = await self._client.list_logs(
            [service_id],
            level=["error"],
            start_time=_rfc3339(now - timedelta(minutes=LOG_LOOKBACK_MINUTES)),
            end_time=_rfc3339(now),
            limit=LOG_FETCH_LIMIT,
        )
        if len(logs) < ERROR_LOG_THRESHOLD:
            return []

        sample = "\n".join(str(entry.get("message", ""))[:200] for entry in logs[:10])
        # The fetch is capped, so at the cap the true count is unknown — say
        # "at least" rather than reporting the cap as if it were the total.
        capped = len(logs) >= LOG_FETCH_LIMIT
        count_text = f"{'at least ' if capped else ''}{len(logs)}"
        # Bucket by the hour so a sustained spike files once, not every tick.
        bucket = now.strftime("%Y-%m-%dT%H")
        return [
            RenderFinding(
                kind="error_logs",
                service_id=service_id,
                service_name=name,
                severity=_SEVERITY_BY_KIND["error_logs"],
                title=f"Render error-log spike on {name} ({count_text} in {LOG_LOOKBACK_MINUTES}m)",
                detail=(
                    f"`{name}` emitted {count_text} platform ERROR log lines in the last "
                    f"{LOG_LOOKBACK_MINUTES} minutes (threshold {ERROR_LOG_THRESHOLD}).\n\n"
                    f"First lines:\n```\n{sample}\n```"
                ),
                evidence={
                    "count": len(logs),
                    "count_is_capped": capped,
                    "bucket": bucket,
                    "window_minutes": LOG_LOOKBACK_MINUTES,
                },
            )
        ]

    async def _check_memory(self, service_id: str, name: str) -> list[RenderFinding]:
        """Flag memory usage sitting near the plan's limit."""
        payload = await self._client.get_metrics(
            service_id, ["memory_usage", "memory_limit"]
        )
        usage, limit = _split_memory(payload)
        if usage is None or not limit:
            return []
        ratio = usage / limit
        if ratio < MEMORY_PRESSURE_RATIO:
            return []

        bucket = _utcnow().strftime("%Y-%m-%dT%H")
        return [
            RenderFinding(
                kind="memory_pressure",
                service_id=service_id,
                service_name=name,
                severity=_SEVERITY_BY_KIND["memory_pressure"],
                title=f"Render memory pressure on {name} ({ratio:.0%} of limit)",
                detail=(
                    f"`{name}` is using {usage:,.0f} of {limit:,.0f} bytes "
                    f"({ratio:.0%}), above the {MEMORY_PRESSURE_RATIO:.0%} threshold. "
                    "At this level Render restarts the instance on the next spike, "
                    "which shows up as an unexplained cold start."
                ),
                evidence={"usage": usage, "limit": limit, "ratio": ratio, "bucket": bucket},
            )
        ]

    # ── dedup ────────────────────────────────────────────────────────────────

    def _is_cool(self, finding: RenderFinding) -> bool:
        """Return True when this finding is outside its cooldown. Does not claim."""
        last = self._cooldowns.get(finding.signature)
        return last is None or time.monotonic() - last >= COOLDOWN_SECONDS

    def _claim(self, finding: RenderFinding) -> bool:
        """Start this finding's cooldown. Always returns True so it can chain."""
        self._cooldowns[finding.signature] = time.monotonic()
        return True


def _split_memory(payload: Any) -> tuple[float | None, float | None]:
    """Extract (usage, limit) from a two-metric ``get_metrics`` payload.

    Render returns the requested metrics keyed by type when it can; when the
    shape is unrecognised both values come back ``None`` and the check is
    skipped rather than guessing.
    """
    if not isinstance(payload, dict):
        return None, None
    usage = _latest_metric_value(payload.get("memory_usage") or payload.get("memoryUsage"))
    limit = _latest_metric_value(payload.get("memory_limit") or payload.get("memoryLimit"))
    return usage, limit


def _self_heal_ready() -> bool:
    """True when a filed finding will actually be scheduled as a fix.

    Detection and repair are separate halves. ``_file_issue`` hands findings to
    the ImprovementLoop, and the loop only schedules a repair task when it was
    constructed with an ``on_task`` callback (``scheduler.create`` in
    ``services/background.py``). Without either, findings are recorded and
    nothing acts on them — a state that otherwise looks identical to "nothing
    is wrong". Never raises: this is a status probe, not a control path.
    """
    try:
        from agent.improvement_loop import get_improvement_loop

        loop = get_improvement_loop()
        return bool(loop is not None and getattr(loop, "_on_task", None))
    except Exception:  # noqa: BLE001 — a status probe must never break a scan
        return False


def _note_recurrence(finding: RenderFinding) -> None:
    """Tell the healer this platform failure is still happening.

    The healer verifies its own fixes: after dispatching one it watches for the
    same signature to come back, and regresses or escalates if it does. Without
    this call a "fixed" deploy failure that recurs every tick would look healed
    forever, because the six-hour cooldown suppresses re-filing. Reported on
    every observation, not only when a new issue is filed — that is the whole
    point of recurrence tracking. Best-effort and synchronous-safe.
    """
    try:
        from agent.self_healing import get_self_healing_agent
        healer = get_self_healing_agent()
        if healer:
            healer.note_recurrence(finding.signature)
    except Exception as exc:  # noqa: BLE001 - never break the monitor
        log.debug("RenderOps: recurrence note failed (ignored): %s", exc)


async def _report_to_healer(finding: RenderFinding) -> None:
    """Open a verified heal for this finding via SelfHealingAgent.

    ImprovementLoop alone schedules a fix and forgets it. The healer adds what
    a platform failure actually needs: dedup by signature, verification that
    the fix worked, regression when it did not, and escalation when retries are
    exhausted. LogMonitor already routes application errors here; platform
    failures deserve the same treatment, since "the build is broken" is
    precisely the case where an unverified fix is worthless.
    """
    try:
        from agent.self_healing import get_self_healing_agent
        healer = get_self_healing_agent()
        if healer is None:
            return
        await healer.on_manual_report(
            title=finding.title,
            description=(
                f"{finding.detail}\n\n"
                f"**Source:** Render MCP ({finding.kind})\n"
                f"**Service:** `{finding.service_name}` (`{finding.service_id}`)\n"
                f"**Evidence:** `{finding.evidence}`\n\n"
                "Observed on the Render platform, not in application logs — the "
                "process may have had no chance to log anything."
            ),
            severity=finding.severity,
            signature=finding.signature,
        )
    except Exception as exc:  # noqa: BLE001 - never break the monitor
        log.warning("RenderOps: could not open a heal for %s: %s", finding.kind, exc)


def _file_issue(finding: RenderFinding) -> bool:
    """Hand a finding to the existing ImprovementLoop intake.

    Returns True when the issue was registered. Best-effort by design: when the
    ImprovementLoop is not running (tests, RUN_BACKGROUND_IN_WEB=false) the
    finding is logged and dropped rather than blocking the monitor.
    """
    try:
        from agent.improvement_loop import (
            DetectedIssue, IssueCategory, IssueSeverity, get_improvement_loop,
        )
    except Exception as exc:  # noqa: BLE001 - intake is optional
        log.debug("RenderOps: ImprovementLoop unavailable (%s)", exc)
        return False

    loop = get_improvement_loop()
    if loop is None:
        log.info("RenderOps finding (not filed, ImprovementLoop idle): %s", finding.title)
        return False

    try:
        severity = IssueSeverity(finding.severity)
    except ValueError:
        severity = IssueSeverity.HIGH

    issue = DetectedIssue(
        issue_id=f"render-{finding.signature}",
        category=IssueCategory.PERFORMANCE,
        severity=severity,
        title=finding.title,
        description=(
            f"{finding.detail}\n\n"
            f"**Source:** Render MCP ({finding.kind})\n"
            f"**Service:** `{finding.service_name}` (`{finding.service_id}`)\n"
            f"**Evidence:** `{finding.evidence}`\n\n"
            "This was observed on the Render platform, not in application logs — "
            "the process itself may have had no chance to log anything."
        ),
    )
    try:
        return bool(loop.register_external_issue(issue))
    except Exception as exc:  # noqa: BLE001 - never break the monitor
        log.warning("RenderOps: could not register issue: %s", exc)
        return False


# ── singleton + background loop ──────────────────────────────────────────────

_monitor: RenderOpsMonitor | None = None


def get_render_ops_monitor() -> RenderOpsMonitor:
    """Return the shared monitor."""
    global _monitor
    if _monitor is None:
        _monitor = RenderOpsMonitor()
    return _monitor


def reset_render_ops_monitor() -> None:
    """Drop the cached monitor. Used by tests."""
    global _monitor
    _monitor = None


def render_ops_enabled() -> bool:
    """True when the loop should run: flag on *and* credentials present."""
    return settings.is_render_ops_enabled


async def render_ops_loop() -> None:
    """Poll Render forever at ``RENDER_OPS_INTERVAL_SECONDS``.

    Sleeps first so a restart storm doesn't hammer the Render API on every
    boot, and swallows per-tick failures so one bad response never ends the
    loop.
    """
    interval = max(60, settings.render_ops_interval_seconds)
    monitor = get_render_ops_monitor()
    log.info("Render ops loop started — platform monitoring every %ds", interval)
    while True:
        try:
            await asyncio.sleep(interval)
            await monitor.tick()
        except asyncio.CancelledError:
            log.info("Render ops loop stopped")
            raise
        except Exception as exc:  # noqa: BLE001 - the loop must outlive its errors
            log.warning("Render ops tick failed: %s", exc)
