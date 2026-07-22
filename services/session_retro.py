"""services/session_retro.py — session retrospective mining.

Closes the gap between the improvement loop (which keys off concrete signals:
failing tests, FIXMEs, missing coverage) and true self-improvement from lived
experience: nothing today looks back over *completed agent sessions* to find
recurring friction. This module reads the durable event log every
``AgentRunner`` session already writes (`AgentSessionStore.append_event`,
queried via `get_events`), clusters recurring failure signatures, and — once
a cluster crosses a frequency threshold — registers it as an issue through
the same `ImprovementLoop.register_external_issue` path used by inbound
issue triage, so the existing fix-dispatch machinery picks it up.

No live LLM call is required for clustering (frequency + failure_phase
grouping is enough signal on its own and keeps this module deterministically
testable); ``judge_cluster`` accepts an optional callable for teams that want
to layer an LLM-as-judge pass on top of a cluster's raw evidence.

Disabled by default (Golden Rule): set SESSION_RETRO_ENABLED=true to opt in.

Env vars (read here only):
    SESSION_RETRO_ENABLED         default "false"
    SESSION_RETRO_LOOKBACK        default "50"  — most recent sessions scanned
    SESSION_RETRO_MIN_CLUSTER     default "3"   — occurrences before filing
"""
from __future__ import annotations

import logging
import os
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable

log = logging.getLogger("qwen-proxy")

_FRICTION_EVENT_TYPES = frozenset(
    {"empirical_verify_failed", "spec_awaiting_approval"}
)


def retro_enabled() -> bool:
    return os.environ.get("SESSION_RETRO_ENABLED", "false").strip().lower() in ("true", "1", "yes", "on")


@dataclass
class FrictionEvent:
    session_id: str
    event_type: str
    signature: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class FrictionCluster:
    signature: str
    event_type: str
    count: int
    sessions: list[str]
    sample_payload: dict[str, Any] = field(default_factory=dict)


def _signature(event_type: str, payload: dict[str, Any]) -> str:
    """A coarse dedup key: failure phase (or first issue text) is enough
    to group repeat friction without needing exact-string matches."""
    if event_type == "empirical_verify_failed":
        issues = payload.get("issues") or []
        first = str(issues[0])[:80] if issues else "unknown"
        return f"empirical_verify_failed:{first}"
    if event_type == "spec_awaiting_approval":
        return "spec_awaiting_approval"
    return f"{event_type}:{str(payload)[:80]}"


def collect_friction_events(store: Any, *, lookback: int) -> list[FrictionEvent]:
    """Scan the most recent *lookback* sessions for friction-signal events."""
    sessions = store.list_all()
    sessions = sorted(sessions, key=lambda s: getattr(s, "updated_at", ""), reverse=True)[:lookback]

    events: list[FrictionEvent] = []
    for session in sessions:
        session_id = session.session_id
        for raw_event in store.get_events(session_id, from_position=0, limit=500):
            if raw_event.event_type not in _FRICTION_EVENT_TYPES:
                continue
            events.append(
                FrictionEvent(
                    session_id=session_id,
                    event_type=raw_event.event_type,
                    signature=_signature(raw_event.event_type, raw_event.payload),
                    payload=raw_event.payload,
                )
            )
    return events


def cluster_friction(events: list[FrictionEvent]) -> list[FrictionCluster]:
    """Group friction events by signature, most frequent first."""
    grouped: dict[str, list[FrictionEvent]] = defaultdict(list)
    for event in events:
        grouped[event.signature].append(event)

    clusters = [
        FrictionCluster(
            signature=sig,
            event_type=evts[0].event_type,
            count=len(evts),
            sessions=sorted({e.session_id for e in evts}),
            sample_payload=evts[0].payload,
        )
        for sig, evts in grouped.items()
    ]
    clusters.sort(key=lambda c: c.count, reverse=True)
    return clusters


def judge_cluster(cluster: FrictionCluster, judge_fn: Callable[[FrictionCluster], str] | None = None) -> str:
    """Return a human-readable description of the cluster.

    Uses *judge_fn* (an LLM-as-judge callable) when provided; otherwise a
    deterministic summary of the raw evidence.
    """
    if judge_fn is not None:
        try:
            return judge_fn(cluster)
        except Exception as exc:  # nosec B110 -- judging is best-effort
            log.debug("session_retro: judge_fn failed, using fallback summary: %s", exc)
    return (
        f"Friction pattern '{cluster.signature}' occurred {cluster.count} times "
        f"across {len(cluster.sessions)} session(s)."
    )


def clusters_to_issues(clusters: list[FrictionCluster], *, min_count: int) -> list[Any]:
    """Convert clusters meeting the frequency threshold into DetectedIssues."""
    from agent.improvement_loop import DetectedIssue, IssueCategory, IssueSeverity

    issues = []
    for cluster in clusters:
        if cluster.count < min_count:
            continue
        severity = IssueSeverity.HIGH if cluster.count >= min_count * 2 else IssueSeverity.MEDIUM
        issues.append(
            DetectedIssue(
                issue_id=f"retro-{abs(hash(cluster.signature)) % 10**8}",
                category=IssueCategory.PERFORMANCE if "verify" in cluster.event_type else IssueCategory.FEATURE_REQUEST,
                severity=severity,
                title=f"Recurring agent friction: {cluster.signature[:80]}",
                description=judge_cluster(cluster),
            )
        )
    return issues


async def run_retro_cycle() -> dict[str, Any]:
    """Mine recent sessions for friction and route qualifying clusters.

    Returns {"scanned": int, "clusters": int, "routed": int} or a disabled
    marker. Best-effort — never raises.
    """
    if not retro_enabled():
        return {"scanned": 0, "clusters": 0, "routed": 0, "reason": "disabled"}

    lookback = int(os.environ.get("SESSION_RETRO_LOOKBACK", "50"))
    min_cluster = int(os.environ.get("SESSION_RETRO_MIN_CLUSTER", "3"))

    try:
        from agent.state import AgentSessionStore
        store = AgentSessionStore()
    except Exception as exc:
        log.warning("session_retro: could not open session store: %s", exc)
        return {"scanned": 0, "clusters": 0, "routed": 0, "reason": str(exc)}

    events = collect_friction_events(store, lookback=lookback)
    clusters = cluster_friction(events)
    issues = clusters_to_issues(clusters, min_count=min_cluster)

    from agent.improvement_loop import get_improvement_loop
    loop = get_improvement_loop()
    routed = 0
    if loop is not None:
        for issue in issues:
            if loop.register_external_issue(issue):
                routed += 1

    return {"scanned": len(events), "clusters": len(clusters), "routed": routed}
