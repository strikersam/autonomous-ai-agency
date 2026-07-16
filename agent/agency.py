"""agent/agency.py — Autonomous Agent Agency (CEO-driven, LLM-powered)

Runs the repo as a self-managing agency where a CEO agent — backed by the
local LLM proxy itself — coordinates a swarm of specialist runtimes.

Agency architecture:
  CEO (LLM-powered) — calls the proxy's /v1/chat/completions with full state
                       context; issues structured directives to worker runtimes.
  Dev        → ClaudeCode / InternalAgent — code fixes, new features, tests
  Security   → ClaudeCode / InternalAgent — CVE remediation, secret cleanup
  Reviewer   → InternalAgent — council-review skill on recent commits
  Release    → InternalAgent — release-readiness, changelog, version bump
  Scout      → InternalAgent — trend evaluation, doc sync, repowise analysis
  Optimizer  → Goose / Aider — performance profiling, refactoring

Runtime routing:
  • ClaudeCode  → complex multi-file coding, security-sensitive, long tasks
  • Hermes      → autonomous long-running research / refactoring loops
  • Goose       → CLI automation, shell-heavy tasks
  • Aider       → focused file-level edits with context
  • OpenCode    → repo-aware editing, git operations
  • InternalAgent → quick analysis, simple fixes, fallback
"""
from __future__ import annotations

# nosec: B603,B607,B413,B301,B104,B608

import asyncio
import hashlib
import json
import logging
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

import re

import httpx

log = logging.getLogger("qwen-proxy")

# Cache the last GitHub API response for diagnostics
_last_gh_fetch_status: int | None = None
_last_gh_fetch_count: int = 0
_last_gh_fetch_error: str = ""


# ── GitHub helpers ─────────────────────────────────────────────────────────────

def _gh_token() -> str:
    return os.environ.get("GH_TOKEN") or os.environ.get("GH_PAT") or os.environ.get("GITHUB_TOKEN", "")


def _gh_repo() -> str:
    """Return the GitHub repo in 'owner/name' format.

    Priority:
    1. GITHUB_REPOSITORY env var (set on Render via render.yaml — but the
       dashboard may have a stale/empty value).
    2. Derive from SELF_REPO_URL (resolved by services.self_bootstrap to
       https://github.com/strikersam/autonomous-ai-agency).
    3. Empty string (quick-note fetch will be skipped).
    """
    raw = os.environ.get("GITHUB_REPOSITORY", "").strip()
    if raw:
        return raw
    # Fallback: derive from SELF_REPO_URL
    try:
        from services.self_bootstrap import SELF_REPO_URL
        # SELF_REPO_URL is like "https://github.com/strikersam/autonomous-ai-agency"
        if "github.com/" in SELF_REPO_URL:
            return SELF_REPO_URL.split("github.com/", 1)[1].rstrip("/")
    except Exception:
        pass
    return ""


async def _fetch_github_quick_notes() -> list[dict]:
    """Return ALL open GitHub issues for this repo (not just 'quick-note' labelled).

    The CEO processes every open issue — quick-notes, bugs, trend digests,
    feature requests — so the agency drives the full backlog, not just
    phone-captured quick notes. Issues with the 'quick-note:exhausted' label
    are still excluded (they've been retried too many times).
    """
    token, repo = _gh_token(), _gh_repo()
    if not token or not repo:
        log.warning(
            "Agency: issue fetch skipped — token=%s repo=%s",
            "set" if token else "MISSING",
            repo or "MISSING",
        )
        return []
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(
            f"https://api.github.com/repos/{repo}/issues",
            params={"state": "open", "per_page": "50", "sort": "created", "direction": "asc"},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )
    global _last_gh_fetch_status, _last_gh_fetch_count, _last_gh_fetch_error
    _last_gh_fetch_status = resp.status_code
    if resp.status_code != 200:
        _last_gh_fetch_error = resp.text[:200]
        log.warning(
            "Agency: GitHub issue fetch returned %d for %s — body: %s",
            resp.status_code, repo, resp.text[:200],
        )
        return []
    _last_gh_fetch_error = ""
    issues = [
        {
            "number": i["number"],
            "title": i["title"],
            "body": (i.get("body") or "")[:800],
            "labels": [lb["name"] for lb in i.get("labels", [])],
            "created_at": i.get("created_at", ""),
        }
        for i in resp.json()
        if "pull_request" not in i  # exclude PRs
    ]
    _last_gh_fetch_count = len(issues)
    log.info("Agency: fetched %d quick-note issues from %s", len(issues), repo)
    return issues


async def _close_github_issue(number: int, reason: str = "not_planned") -> None:
    token, repo = _gh_token(), _gh_repo()
    if not token or not repo:
        return
    async with httpx.AsyncClient(timeout=15) as client:
        await client.patch(
            f"https://api.github.com/repos/{repo}/issues/{number}",
            json={"state": "closed", "state_reason": reason},
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
            },
        )


def _build_quick_note_instruction(issue: dict) -> str:
    body = issue.get("body", "")
    url_m  = re.search(r"https?://\S+", body)
    task_m = re.search(r"[Tt]ask:\s*(.+?)(?:\n|$)", body)
    url  = url_m.group(0)  if url_m  else ""
    task = task_m.group(1).strip() if task_m else body[:300]
    return (
        f"Implement GitHub issue #{issue['number']}: {issue['title']}\n\n"
        + (f"Source URL: {url}\n" if url else "")
        + f"Task: {task}\n\n"
        "Instructions:\n"
        "1. Implement the feature with minimal, correct code in the appropriate module.\n"
        "2. Add or update tests in tests/.\n"
        "3. Add an entry to docs/changelog.md under ## [Unreleased] ### Added.\n"
        "4. Run `pytest -x` and confirm all tests pass.\n"
        "5. Stage and commit with a descriptive message.\n"
    )

_REPO_ROOT = Path(__file__).parent.parent
TICK_INTERVAL_MINUTES = int(os.environ.get("AGENCY_TICK_MINUTES", "5"))
PROXY_BASE_URL = os.environ.get("AGENCY_PROXY_URL", "http://localhost:8000")
CEO_MODEL = os.environ.get("AGENCY_CEO_MODEL", "qwen3-coder:14b")


def _now_str() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# ── Role / Runtime mapping ─────────────────────────────────────────────────────

class AgentRole(str, Enum):
    CEO       = "ceo"
    DEV       = "dev"
    SECURITY  = "security"
    REVIEWER  = "reviewer"
    RELEASE   = "release"
    SCOUT     = "scout"
    OPTIMIZER = "optimizer"


# Fallback title used when a directive has no distinguishing title of its own
# (e.g. the CEO's LLM response omitted "title" from its JSON). Shared between
# `_parse_ceo_directives` and `Agency._dispatch_directive` so the latter can
# detect the generic case and disambiguate the schedule name — see the
# comment in `_dispatch_directive` for why this matters.
_GENERIC_DIRECTIVE_TITLE = "CEO directive"

# Preferred runtime per role (ordered: first available wins)
_ROLE_RUNTIME_PREFERENCE: dict[AgentRole, list[str]] = {
    AgentRole.DEV:       ["claude_code", "internal_agent"],
    AgentRole.SECURITY:  ["claude_code", "internal_agent"],
    AgentRole.REVIEWER:  ["internal_agent", "claude_code"],
    AgentRole.RELEASE:   ["internal_agent", "claude_code"],
    AgentRole.SCOUT:     ["internal_agent"],
    AgentRole.OPTIMIZER: ["goose", "aider", "internal_agent"],
}


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class AgentDirective:
    directive_id: str
    role: AgentRole
    title: str
    instruction: str
    priority: int = 5
    preferred_runtime: str = "internal_agent"
    issued_at: str = field(default_factory=_now_str)
    status: str = "pending"
    result: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "directive_id": self.directive_id,
            "role": self.role.value,
            "title": self.title,
            "priority": self.priority,
            "preferred_runtime": self.preferred_runtime,
            "issued_at": self.issued_at,
            "status": self.status,
            "result": self.result,
        }


@dataclass
class AgencyCycleResult:
    cycle_id: str
    started_at: str
    directives_issued: int
    directives: list[dict]
    improvement_issues_seen: int
    ceo_assessment: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "cycle_id": self.cycle_id,
            "started_at": self.started_at,
            "directives_issued": self.directives_issued,
            "directives": self.directives,
            "improvement_issues_seen": self.improvement_issues_seen,
            "ceo_assessment": self.ceo_assessment,
        }


# ── Agency ────────────────────────────────────────────────────────────────────

class Agency:
    """CEO-coordinated multi-agent agency for continuous codebase management.

    The CEO calls the local proxy LLM for strategic assessment.
    Worker agents are dispatched via AgentScheduler → runtime routing.
    """

    def __init__(self, tick_minutes: int = TICK_INTERVAL_MINUTES) -> None:
        self._tick = tick_minutes * 60
        self._running = False
        self._thread: threading.Thread | None = None
        self._history: list[AgencyCycleResult] = []
        self._directives: list[AgentDirective] = []
        self._cycle_count = 0
        self._last_quick_notes: dict = {}  # cached for CEO prompt
        # FastAPI main loop — captured by attach_main_loop() so the CEO
        # thread can dispatch run_cycle() onto it via run_coroutine_threadsafe.
        # Without this, asyncio.run(run_cycle()) creates a fresh loop that
        # can't see Motor/aiosqlite clients bound to the main loop.
        self._main_loop: Any = None
        # Company Graph integration
        try:
            from services.specialist import get_specialist_service
            self._specialist_service = get_specialist_service()
            log.info("Company Graph Specialist Service initialized")
        except ImportError as e:
            log.warning(f"Specialist Service not available: {e}")
            self._specialist_service = None

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="agency-tick", daemon=True)
        self._thread.start()
        log.info(
            "Agency started (tick=%dm, CEO model=%s, roles=%s)",
            self._tick // 60, CEO_MODEL, [r.value for r in AgentRole],
        )

    def stop(self) -> None:
        self._running = False

    def attach_main_loop(self, loop: Any) -> None:
        """Capture the FastAPI main event loop so the CEO thread can dispatch
        run_cycle() onto it via run_coroutine_threadsafe.

        Without this, asyncio.run(run_cycle()) creates a fresh loop that
        can't see Motor/aiosqlite clients bound to the main loop — the
        self-bootstrap and quick-note fetch crash silently.
        """
        self._main_loop = loop
        log.info("CEO agency main loop attached (loop=%r)", loop)

    def get_status(self) -> dict[str, Any]:
        return {
            "running": self._running,
            "tick_minutes": self._tick // 60,
            "cycle_count": self._cycle_count,
            "ceo_model": CEO_MODEL,
            "pending_directives": sum(1 for d in self._directives if d.status == "pending"),
            "recent_cycles": [c.as_dict() for c in self._history[-5:]],
            "roles": [r.value for r in AgentRole],
            "runtime_routing": {k.value: v for k, v in _ROLE_RUNTIME_PREFERENCE.items()},
        }

    # ── Main cycle ────────────────────────────────────────────────────────────

    async def run_cycle(self) -> AgencyCycleResult:
        # The CEO 24x7 cycle is a *sanctioned internal caller*. It does not execute
        # agent work inline — it assesses state (an LLM chat call, not AgentRunner)
        # and issues directives that flow through the scheduler → task dispatcher →
        # InternalAgentAdapter (the golden-path EXECUTE leaf, which sets its own
        # bypass in its own asyncio context). We therefore permit the cycle under the
        # default AGENCY_WORKFLOW_MODE=orchestrator instead of forcing the global
        # flag to "legacy". No bypass is needed at the cycle level since all inline
        # execution happens in InternalAgentAdapter which sets its own localized bypass.
        import services.workflow_orchestrator as _wo

        if not _wo.is_legacy_mode():
            _wo.emit_deprecation("Agency.run_cycle() [sanctioned 24x7 internal cycle]")

        cycle_id = "cycle_" + secrets.token_hex(4)
        started_at = _now_str()
        self._cycle_count += 1
        log.info("Agency cycle %s starting (count=%d)", cycle_id, self._cycle_count)

        # Quick-note maintenance: close exhausted issues, dispatch pending ones to Dev
        qn_directives = await self._handle_quick_notes()

        # Self-bootstrap retry: if the platform hasn't onboarded itself as a
        # company yet (e.g. the startup background task was cancelled by a
        # Render free-tier cold-start spin-down), retry it here on every CEO
        # cycle. This is idempotent — ensure_self_company() no-ops if the
        # company already exists with specialists.
        # Skip in tests (SELF_BOOTSTRAP_ENABLED=false) to avoid interfering
        # with E2E tests that create their own companies.
        if os.environ.get("SELF_BOOTSTRAP_ENABLED", "true").strip().lower() in ("true", "1", "yes"):
            try:
                from services.self_bootstrap import ensure_self_company
                await ensure_self_company()
            except Exception as exc:
                log.debug("Agency: self-bootstrap retry skipped: %s", exc)

        state_context = self._build_state_context()
        state_context["quick_notes"] = self._last_quick_notes

        # ── Company-aware CEO assessment ────────────────────────────
        # The CEO now considers ALL onboarded companies (not just the
        # single GITHUB_REPOSITORY). For each company it issues
        # company-scoped directives that route through the company's
        # own specialists via company:{id} tags.
        company_directives = await self._company_directives(state_context)
        qn_directives.extend(company_directives)

        # CEO assessment — try LLM first, fall back to rule-based
        assessment, ceo_directives = await self._ceo_assess_llm(state_context)

        # De-duplicate: skip directives whose title is already in a recent
        # "running" or "pending" directive to prevent the CEO from re-issuing
        # the same work repeatedly before the previous run finishes.
        recent_titles: set[str] = {
            d.title for d in self._directives[-50:]
            if d.status in {"pending", "running"}
        }
        deduped: list[AgentDirective] = []
        for directive in (qn_directives + ceo_directives):
            if directive.title in recent_titles:
                log.debug(
                    "Agency: skipping duplicate directive '%s' (already pending/running)",
                    directive.title,
                )
            else:
                deduped.append(directive)
                recent_titles.add(directive.title)

        directives = deduped
        for directive in directives:
            self._directives.append(directive)
            self._dispatch_directive(directive)

        if len(self._directives) > 200:
            self._directives = self._directives[-200:]

        result = AgencyCycleResult(
            cycle_id=cycle_id,
            started_at=started_at,
            directives_issued=len(directives),
            directives=[d.as_dict() for d in directives],
            improvement_issues_seen=self._issue_count(),
            ceo_assessment=assessment,
        )
        self._history.append(result)
        if len(self._history) > 50:
            self._history = self._history[-50:]

        log.info("Agency cycle %s done — %d directive(s)", cycle_id, len(directives))
        return result

    # ── Company-aware directive generation ───────────────────────────

    async def _company_directives(
        self, state: dict[str, Any],
    ) -> list[AgentDirective]:
        """Generate directives for each onboarded company.

        The CEO examines each company's health, recent schedule runs, and
        specialist activity. It issues company-scoped directives tagged
        with ``company:{company_id}`` so the task dispatcher routes them
        to the correct company specialists.
        """
        directives: list[AgentDirective] = []
        try:
            from services.company_graph_store import get_company_graph_store
            store = get_company_graph_store()
            companies = await store.list_companies(limit=100)
        except Exception as exc:
            log.debug("Agency: could not list companies: %s", exc)
            return directives

        if not companies:
            return directives

        for company in companies:
            cid = company.id
            # Ensure specialists are bridged to AgentStore (idempotent).
            # On first cycle after deploy the bridge may not have run yet
            # if activate_company was never called (e.g. a restart cleared
            # in-memory state).
            try:
                from services.company_agency import get_company_agency_service
                agency_svc = get_company_agency_service()
                # On the very first cycle, pass start_runtimes=True and
                # create_schedules=True so the company is fully activated,
                # not just bridged.  On subsequent cycles the bridge-only
                # call is sufficient (schedules already exist).
                is_first_cycle = self._cycle_count <= 1
                await agency_svc.activate_company(
                    cid,
                    start_runtimes=is_first_cycle,
                    create_schedules=is_first_cycle,
                )
            except Exception as exc:
                log.debug("Agency: company re-bridge skipped for %s: %s", cid, exc)

            # On the first cycle, just ensure the bridge is in place.
            # Removed: previously this skipped ALL work generation on cycle 1,
            # meaning no directives were dispatched until cycle 2 (30 min after
            # startup at the default 15-min tick).  Now we allow health-check
            # and CEO-assessment directives to run immediately, only skipping
            # the per-company periodic directives (which need the bridge to
            # be settled first — but that's already done above).
            if self._cycle_count <= 1:
                log.info("Agency: ensured specialist bridge for company %s", cid)
                # Don't skip — let CEO assessment and quick-notes run on
                # cycle 1 so the agency starts producing work immediately.

            # Every 3rd cycle, issue a health-check directive
            if self._cycle_count % 3 == 0:
                directives.append(self._make_directive(
                    role=AgentRole.SCOUT,
                    priority=5,
                    title=f"Health: {company.name or cid[:8]}",
                    instruction=(
                        f"Company: {company.name} (ID: {cid})\n"
                        f"Domain: {company.domain}\n\n"
                        "Check the health of this company:\n"
                        "1. GET /api/company/{cid} — verify the record exists.\n"
                        "2. Check each specialist has recent activity (< 2x schedule interval).\n"
                        "3. If any specialist is stalled, create a GitHub issue with the findings.\n"
                        "4. Review recent task results and flag any recurring failures.\n\n"
                        "Only create a GitHub issue if something actionable is wrong."
                    ),
                ))
                directives[-1].tags = [f"company:{cid}"]

            # Every 6th cycle, issue a code-quality or improvement directive
            if self._cycle_count % 6 == 0:
                directives.append(self._make_directive(
                    role=AgentRole.DEV,
                    priority=3,
                    title=f"Improve: {company.name or cid[:8]}",
                    instruction=(
                        f"Company: {company.name} (ID: {cid})\n"
                        f"Domain: {company.domain}\n"
                        f"Repo: {company.repos[0].url if company.repos else 'N/A'}\n\n"
                        "Look at this company's connected repository. Identify the single\n"
                        "highest-value improvement: a bug fix, a test gap, a doc inconsistency,\n"
                        "or a code quality issue. Implement the fix and open a pull request.\n"
                        "Do NOT merge — just open the PR for review."
                    ),
                ))
                directives[-1].tags = [f"company:{cid}"]

        return directives

    # ── Quick-note GitHub issue maintenance ──────────────────────────────────

    async def _handle_quick_notes(self) -> list[AgentDirective]:
        """Close exhausted quick-note issues; dispatch Dev directives for open ones."""
        directives: list[AgentDirective] = []
        try:
            issues = await _fetch_github_quick_notes()
        except Exception as exc:
            log.debug("Agency: quick-note fetch failed: %s", exc)
            return directives

        exhausted = [i for i in issues if "quick-note:exhausted" in i["labels"]]
        # Issues with no exhausted label and not on their last retry are fair game for Dev
        actionable = [
            i for i in issues
            if "quick-note:exhausted" not in i["labels"]
        ]

        closed = 0
        for issue in exhausted:
            log.info("Agency: auto-closing exhausted quick-note #%d", issue["number"])
            try:
                await _close_github_issue(issue["number"])
                closed += 1
            except Exception as exc:
                log.warning("Agency: could not close issue #%d: %s", issue["number"], exc)

        # Dispatch at most one Dev directive per cycle to avoid flooding the queue
        if actionable:
            issue = actionable[0]
            # Use a generic title for all issue types (not just quick-notes)
            is_quick_note = "quick-note" in issue.get("labels", [])
            prefix = "quick-note" if is_quick_note else "issue"
            directives.append(self._make_directive(
                role=AgentRole.DEV,
                priority=3,
                title=f"{prefix} #{issue['number']}: {issue['title'][:50]}",
                instruction=_build_quick_note_instruction(issue),
            ))
            log.info(
                "Agency: dispatched Dev for %s #%d (%d actionable issues total)",
                prefix, issue["number"], len(actionable),
            )

        self._last_quick_notes = {"actionable": actionable, "exhausted_closed": closed}
        return directives

    # ── State snapshot ────────────────────────────────────────────────────────

    def _build_state_context(self) -> dict[str, Any]:
        ctx: dict[str, Any] = {
            "cycle_count": self._cycle_count,
            "timestamp": _now_str(),
        }
        try:
            from agent.improvement_loop import get_improvement_loop
            loop = get_improvement_loop()
            if loop:
                status = loop.get_status()
                ctx["improvement_loop"] = {
                    "active_issues": status.get("active_issues", [])[:10],
                    "failing_tests": status.get("failing_tests", [])[:10],
                    "scan_count": status.get("scan_count", 0),
                    "issues_detected": status.get("issues_detected", 0),
                    "issues_resolved": status.get("issues_resolved", 0),
                }
        except Exception:
            pass
        try:
            from agent.log_monitor import get_log_monitor
            monitor = get_log_monitor()
            if monitor:
                ctx["log_monitor"] = monitor.get_stats()
        except Exception:
            pass
        try:
            from agent.trend_watcher import get_trend_watcher
            watcher = get_trend_watcher()
            if watcher:
                ctx["trends"] = watcher.get_stats()
                ctx["top_trends"] = watcher.get_alerts(limit=3)
        except Exception:
            pass
        try:
            from agent.self_healing import get_self_healing_agent
            healer = get_self_healing_agent()
            if healer:
                ctx["self_healing"] = {"recent_events": healer.get_events()[-5:]}
        except Exception:
            pass
        return ctx

    # ── CEO: LLM-powered assessment ───────────────────────────────────────────

    async def _ceo_assess_llm(
        self, state: dict[str, Any]
    ) -> tuple[str, list[AgentDirective]]:
        """Call the configured provider stack to perform CEO strategic assessment."""
        try:
            from backend.server import call_llm

            prompt = _build_ceo_prompt(state, self._cycle_count)
            requested_model = (os.environ.get("AGENCY_CEO_MODEL") or "").strip() or None
            text = await call_llm(
                [
                    {"role": "system", "content": _CEO_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt},
                ],
                model=requested_model,
                temperature=0.3,
            )
            directives = _parse_ceo_directives(text, self._cycle_count)
            return text[:500], directives
        except Exception as exc:
            log.debug("Agency CEO LLM call failed, using rule-based: %s", exc)
        return self._ceo_assess_rules(state)

    # ── CEO: Rule-based fallback ──────────────────────────────────────────────

    def _ceo_assess_rules(
        self, state: dict[str, Any]
    ) -> tuple[str, list[AgentDirective]]:
        directives: list[AgentDirective] = []
        parts: list[str] = []
        loop_state = state.get("improvement_loop", {})
        failing = loop_state.get("failing_tests", [])
        active  = loop_state.get("active_issues", [])

        if failing:
            directives.append(self._make_directive(
                role=AgentRole.DEV, priority=1,
                title=f"Fix {len(failing)} failing test(s)",
                instruction=(
                    f"Tests failing:\n" + "\n".join(f"- `{t}`" for t in failing[:10])
                    + "\n\nRun `pytest -x`, fix each failure with minimum correct change. "
                    "Update docs/changelog.md under `### Fixed`. Never mock to hide failures."
                ),
            ))
            parts.append(f"{len(failing)} failing test(s) → Dev dispatched")

        security_issues = [i for i in active if i.get("category") == "security"]
        if security_issues:
            top = security_issues[0]
            directives.append(self._make_directive(
                role=AgentRole.SECURITY, priority=2,
                title=f"Security: {top.get('title', '')[:60]}",
                instruction=top.get("description", "Remediate the security finding."),
            ))
            parts.append(f"{len(security_issues)} security issue(s) → Security dispatched")

        trend_issues = [i for i in active if "[Trend]" in i.get("title", "")]
        if trend_issues and self._cycle_count % 3 == 0:
            top = trend_issues[0]
            directives.append(self._make_directive(
                role=AgentRole.SCOUT, priority=5,
                title=f"Evaluate trend: {top.get('title', '')[:60]}",
                instruction=(
                    top.get("description", "Evaluate if this AI trend is applicable.") +
                    "\n\nIf actionable (e.g. new Ollama model), update router/registry.py "
                    "and docs/changelog.md. Otherwise create a GitHub issue for tracking."
                ),
            ))
            parts.append("Trend evaluation → Scout dispatched")

        if self._cycle_count % 4 == 0:
            directives.append(self._make_directive(
                role=AgentRole.REVIEWER, priority=6,
                title="Periodic council review",
                instruction=(
                    "Run the council-review skill on changes since the last git tag. "
                    "Flag correctness, security, or maintainability issues. "
                    "Create GitHub issues for significant findings."
                ),
            ))
            parts.append("Council review → Reviewer dispatched")

        if self._cycle_count % 8 == 0:
            directives.append(self._make_directive(
                role=AgentRole.OPTIMIZER, priority=7,
                title="Performance & code quality pass",
                instruction=(
                    "Profile the proxy for hot paths (model routing, chat streaming). "
                    "Identify any O(n²) loops, unnecessary DB queries, or blocking I/O. "
                    "Apply targeted optimizations. Update changelog under `### Changed`."
                ),
            ))
            parts.append("Performance pass → Optimizer dispatched")

        if self._cycle_count % 48 == 0:
            directives.append(self._make_directive(
                role=AgentRole.RELEASE, priority=8,
                title="Release readiness check",
                instruction=(
                    "Run the release-readiness skill. If checks pass: bump version in "
                    "docs/changelog.md (move [Unreleased] to a dated version), run pytest, "
                    "commit `release: vX.Y.Z`. If checks fail, create a GitHub issue."
                ),
            ))
            parts.append("Release check → Release dispatched")

        if not parts:
            parts.append("All systems nominal")

        return " | ".join(parts), directives

    # ── Dispatch ──────────────────────────────────────────────────────────────

    def _dispatch_directive(self, directive: AgentDirective) -> None:
        from packages.scheduler.scheduler import get_scheduler
        try:
            scheduler = get_scheduler()
            # Derive a DETERMINISTIC schedule name from the directive title.
            # NEVER use directive_id (which contains secrets.token_hex) — it
            # makes every schedule name unique and defeats dedup-by-name,
            # causing the 2,873-row schedule pile that OOM'd the 512MB
            # Render instance on 2026-07-03.
            # Use the title (truncated) which is deterministic for the same
            # recurring directive.
            #
            # BUT: a generic/missing title (blank, or the CEO-parser's
            # "CEO directive" fallback when the LLM's JSON omits "title")
            # would collapse EVERY such directive onto the same schedule
            # name. scheduler.create() dedups by name and returns the
            # existing job unchanged — so the second and every later
            # generic-titled directive would be silently dropped (never
            # scheduled) while still being marked "running" below. Detect
            # the generic case and disambiguate with a deterministic hash of
            # the instruction instead: identical retries of the same
            # instruction still dedup to one row, but distinct directives
            # that merely share a generic title no longer collide.
            _title = directive.title[:80].strip()
            if _title and _title != _GENERIC_DIRECTIVE_TITLE:
                _name = _title
            else:
                _digest = hashlib.sha256(directive.instruction.encode("utf-8")).hexdigest()[:10]
                _name = f"agency-directive-{_digest}"
            # Build job tags for routing to correct company specialists.
            job_tags = [
                "agency", directive.role.value,
                f"priority-{directive.priority}",
                f"runtime-{directive.preferred_runtime}",
            ]
            # Forward company tags so the task dispatcher routes to
            # the correct company specialists.
            for tag in (directive.tags or []):
                if tag.startswith("company:"):
                    job_tags.append(tag)
            job = scheduler.create(
                name=f"agency: {_name}",
                cron="* * * * *",
                instruction=directive.instruction,
                description=f"[{directive.role.value}] {directive.title}",
                run_once=True,   # execute once and self-delete — prevents schedule spam
                tags=job_tags,
            )
            directive.status = "running"
            log.info(
                "Agency dispatched %s → role=%s runtime=%s job=%s",
                directive.directive_id, directive.role.value,
                directive.preferred_runtime, job.job_id,
            )
            # Langfuse trace: CEO directive dispatched
            try:
                from langfuse_obs import emit_agency_observation
                emit_agency_observation(
                    operation="ceo_directive",
                    actor="ceo",
                    task_id=job.job_id,
                    task_title=directive.title,
                    task_type=directive.role.value,
                    status="dispatched",
                    input_text=directive.instruction[:2000],
                    metadata={"directive_id": directive.directive_id, "priority": directive.priority},
                )
            except Exception:
                pass
        except Exception as exc:
            directive.status = "failed"
            directive.result = str(exc)
            log.warning("Agency: dispatch failed for %s: %s", directive.directive_id, exc)
            # Langfuse trace: CEO directive dispatch failed
            try:
                from langfuse_obs import emit_agency_observation
                emit_agency_observation(
                    operation="ceo_directive",
                    actor="ceo",
                    task_title=directive.title,
                    task_type=directive.role.value,
                    status="failed",
                    error=str(exc)[:500],
                )
            except Exception:
                pass

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _make_directive(
        self, *, role: AgentRole, title: str, instruction: str, priority: int,
    ) -> AgentDirective:
        prefs = _ROLE_RUNTIME_PREFERENCE.get(role, ["internal_agent"])
        return AgentDirective(
            directive_id="dir_" + secrets.token_hex(4),
            role=role,
            title=title,
            instruction=instruction,
            priority=priority,
            preferred_runtime=prefs[0],
        )

    def _issue_count(self) -> int:
        try:
            from agent.improvement_loop import get_improvement_loop
            loop = get_improvement_loop()
            return len(loop.get_status().get("active_issues", [])) if loop else 0
        except Exception:
            return 0

    def _loop(self) -> None:
        # Fire immediately on startup so the first cycle runs before the
        # instance spins down (Render free tier: 15 min inactivity timeout).
        # Subsequent cycles sleep for self._tick (default 5 min).
        while self._running:
            try:
                if self._main_loop is not None:
                    # Dispatch onto the FastAPI main loop so coroutines can
                    # safely touch Motor/aiosqlite clients bound to it.
                    future = asyncio.run_coroutine_threadsafe(
                        self.run_cycle(), self._main_loop
                    )
                    future.result(timeout=300)  # 5-min cap per cycle
                else:
                    # Fallback: fresh loop (only used before attach_main_loop)
                    asyncio.run(self.run_cycle())
            except Exception as exc:
                log.error("Agency tick error: %s", exc)
            time.sleep(self._tick)


# ── CEO LLM prompt helpers ─────────────────────────────────────────────────────

_CEO_SYSTEM_PROMPT = """You are the CEO of an autonomous AI engineering agency operating 24/7.
You manage a self-hosted AI platform (local-llm-server) that must continuously improve itself.

## Your mandate
You do NOT just react to problems — you proactively drive product quality, security,
and value delivery. You reason about WHAT to fix, WHY it matters now, and HOW to prioritize.

## Output format
Respond ONLY with a valid JSON array. Each directive:
{
  "role": "dev|security|reviewer|release|scout|optimizer",
  "priority": 1-10,
  "title": "short title under 60 chars",
  "instruction": "detailed step-by-step instruction for the agent — include file paths, commands to run, acceptance criteria"
}

## Priority framework
1 = Test suite broken (blocks all other work)
2 = Security CVE or auth vulnerability
3 = User-requested feature (quick-note issues)
4 = Bug causing user-visible failures
5 = Performance degradation or reliability gap
6 = Code quality or tech debt that's growing
7 = Trend/opportunity evaluation worth a spike
8 = Periodic review or release prep
9–10 = Optimization when everything else is green

## Strategic context
- This is a product used by real users — reliability > features
- Every agent instruction MUST include: what files to read first, commands to run, how to verify success
- Never create a directive for something already in-progress or recently resolved
- If the system is healthy and no quick-note tasks exist, return [] — do not invent work
- Quick-note GitHub issues (not exhausted) = high-priority user requests; always address before trend work
- After any failing test cycle: first directive must be the test fix, nothing else until green
- Recent git commits in the state show what changed — use them to spot regressions or opportunities

## Instruction quality bar
A good instruction tells the agent:
1. WHY this matters right now
2. WHICH files to start with (include full paths)
3. WHAT commands to run
4. HOW to verify success (what should pass/change)
5. WHAT to update in docs/changelog.md
"""


def _collect_recent_git_context() -> str:
    """Return recent commits and changed files for CEO situational awareness."""
    import subprocess
    try:
        log = subprocess.run(  # nosec B603 B607 -- fixed git argv, no user input
            ["git", "log", "--oneline", "--no-merges", "-10"],
            capture_output=True, text=True, timeout=5,
        )
        diff_stat = subprocess.run(  # nosec B603 B607 -- fixed git argv, no user input
            ["git", "diff", "--stat", "HEAD~5", "HEAD"],
            capture_output=True, text=True, timeout=5,
        )
        if log.returncode == 0 and log.stdout.strip():
            out = f"Recent commits:\n{log.stdout.strip()}"
            if diff_stat.returncode == 0 and diff_stat.stdout.strip():
                changed = [l for l in diff_stat.stdout.splitlines() if "|" in l][:8]
                out += "\nFiles changed recently:\n" + "\n".join(changed)
            return out
    except Exception:
        pass
    return ""


def _build_ceo_prompt(state: dict[str, Any], cycle: int) -> str:
    lines = [f"# Agency state — cycle {cycle} at {_now_str()}\n"]

    # ── Recent git activity ────────────────────────────────────────────────
    git_ctx = _collect_recent_git_context()
    if git_ctx:
        lines.append(f"## Recent Changes\n{git_ctx}\n")

    # ── Test health ────────────────────────────────────────────────────────
    loop = state.get("improvement_loop", {})
    if loop.get("failing_tests"):
        lines.append(f"## FAILING TESTS ({len(loop['failing_tests'])}) ← FIX FIRST")
        for t in loop["failing_tests"][:8]:
            lines.append(f"  - `{t}`")
    else:
        lines.append("## Tests: ✅ All passing")

    # ── Active issues by priority ──────────────────────────────────────────
    active = loop.get("active_issues", [])
    if active:
        lines.append(f"\n## Active Issues ({len(active)})")
        for i in sorted(active, key=lambda x: x.get("priority", 5))[:6]:
            lines.append(f"  [{i.get('category','?')}] {i.get('title','')[:80]}")

    # ── Self-healing events ────────────────────────────────────────────────
    healing = state.get("self_healing", {}).get("recent_events", [])
    if healing:
        lines.append(f"\n## Self-Healing Events (last {len(healing)})")
        for ev in healing[-3:]:
            lines.append(f"  {ev.get('type','?')}: {str(ev.get('detail',''))[:60]}")

    # ── Log monitor ────────────────────────────────────────────────────────
    monitor = state.get("log_monitor", {})
    if monitor.get("tasks_created", 0) > 0:
        lines.append(f"\n## Runtime Errors: {monitor['tasks_created']} error tasks captured")

    # ── Trends ────────────────────────────────────────────────────────────
    trends = state.get("top_trends", [])
    if trends:
        lines.append(f"\n## AI/Tech Trends (top {min(3, len(trends))})")
        for t in trends[:3]:
            lines.append(f"  [{t['source']}] {t['title'][:80]} (relevance={t['relevance_score']:.2f})")

    # ── Scan totals ────────────────────────────────────────────────────────
    lines.append(
        f"\n## Cumulative — detected: {loop.get('issues_detected', 0)}, "
        f"resolved: {loop.get('issues_resolved', 0)}, "
        f"cycles: {loop.get('scan_count', 0)}"
    )

    # ── Quick-note tasks (owner-requested features) ───────────────────────
    qn = state.get("quick_notes", {})
    if qn.get("actionable"):
        lines.append(f"\n## Owner-Requested Features — PRIORITY 3 ({len(qn['actionable'])} open)")
        for i in qn["actionable"][:5]:
            labels = ", ".join(i.get("labels", []))
            lines.append(f"  #{i['number']} [{labels}] {i['title'][:80]}")
    if qn.get("exhausted_closed"):
        lines.append(f"\nAuto-closed {qn['exhausted_closed']} completed quick-note issue(s).")

    lines.append(
        "\n## Instructions\n"
        "Issue directives where there is concrete work to do. "
        "Include exact file paths and commands in every instruction. "
        "Return [] if all checks pass and no owner tasks exist."
    )
    return "\n".join(lines)


def _parse_ceo_directives(
    text: str, cycle: int
) -> list[AgentDirective]:
    directives: list[AgentDirective] = []
    try:
        start = text.find("[")
        end   = text.rfind("]") + 1
        if start < 0 or end <= start:
            return directives
        items = json.loads(text[start:end])
        for item in items[:4]:
            role_str = item.get("role", "dev")
            try:
                role = AgentRole(role_str)
            except ValueError:
                role = AgentRole.DEV
            prefs = _ROLE_RUNTIME_PREFERENCE.get(role, ["internal_agent"])
            directives.append(AgentDirective(
                directive_id="dir_" + secrets.token_hex(4),
                role=role,
                title=str(item.get("title", _GENERIC_DIRECTIVE_TITLE))[:80],
                instruction=str(item.get("instruction", "")),
                priority=int(item.get("priority", 5)),
                preferred_runtime=prefs[0],
            ))
    except Exception as exc:
        log.debug("Agency: failed to parse CEO JSON response: %s", exc)
    return directives


def _get_api_key() -> str:
    return (
        os.environ.get("PROXY_API_KEY")
        or os.environ.get("ADMIN_TOKEN")
        or "agency-internal"
    )


# ── Singleton ──────────────────────────────────────────────────────────────────

_agency_instance: Agency | None = None


def set_agency(instance: Agency) -> None:
    global _agency_instance
    _agency_instance = instance


def get_agency() -> Agency | None:
    return _agency_instance
