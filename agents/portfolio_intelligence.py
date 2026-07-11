"""Portfolio intelligence — derive portfolio initiatives from real signals.

Instead of hardcoded demo data, the portfolio board is assembled autonomously
from live signals and scored with WSJF heuristics:

  • Roadmap backlog  — `.claude/state/active-tasks.md` (Roadmap Items + Sprint Tasks)
                       and `docs/roadmap-killer-todos.md` (P0/P1 priorities).
  • Bugs             — the active-tasks.md Bug Log (open rows) + GitHub issues
                       labelled `bug`.
  • Open PRs         — in-flight pull requests on the connected repo become
                       IN_PROGRESS initiatives.
  • Research / trends — `agent/trend_watcher.py` surfaces emerging-capability
                       initiatives (best-effort; skipped if offline).

Each initiative carries `source` + `rationale` provenance. GitHub and trend
access are lazy and fail soft, so the board always renders from local backlog
even with no network/token. A scheduled GitHub Action (`portfolio-refresh.yml`)
drives the regular cadence.

Pure parsing/scoring functions are kept dependency-free and injectable so the
module is unit-testable in isolation.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import Callable, Dict, List, Optional

from agents.portfolio import Initiative, InitiativeStatus, PortfolioManager
from uuid import uuid4

log = logging.getLogger("qwen-proxy")


def _default_repo() -> str:
    """Resolve the connected repo from the canonical config module.

    Was a hardcoded stale constant (``strikersam/local-llm-server`` — the
    repo's old name, before the ``autonomous-ai-agency`` rename). Every
    GitHub API call made with the stale name 404s, and
    ``fetch_github_signals`` doesn't check the response status before
    treating the JSON body as a list, so the 404 error object (a dict)
    crashed with ``TypeError: unhashable type: 'slice'`` — silently
    dropping all GitHub-sourced portfolio initiatives (bugs, PRs) on
    every refresh.
    """
    try:
        from packages.config import settings
        return settings.github_repository
    except Exception:
        return "strikersam/autonomous-ai-agency"


DEFAULT_REPO = _default_repo()
_REPO_ROOT = Path(__file__).resolve().parent.parent


# ── WSJF scoring weights per signal kind ─────────────────────────────────────
# (business_value, time_criticality, risk_reduction, job_size)
def _bug_scores() -> tuple:
    return (5, 8, 8, 3)            # WSJF ≈ 7.0 — urgent, low effort, de-risking


def _pr_scores(job_size: int = 5) -> tuple:
    return (8, 5, 3, max(1, job_size))  # in-flight value, already underway


def _roadmap_scores(priority: str, job_size: int) -> tuple:
    if priority.upper() == "P0":
        return (13, 8, 3, max(1, job_size))
    if priority.upper() == "P1":
        return (8, 3, 2, max(1, job_size))
    return (5, 2, 2, max(1, job_size))


def _research_scores(relevance: float, job_size: int = 8) -> tuple:
    # relevance is 0..1 → scale into a business-value band
    bv = max(2, min(13, round(relevance * 13)))
    return (bv, 5, 2, max(1, job_size))


# Effort heuristic: bigger, architectural items cost more.
_BIG_EFFORT_HINTS = (
    "pipeline", "middleware", "framework", "orchestrat", "architecture",
    "migration", "refactor", "overhaul", "platform", "infrastructure",
    "distributed", "guardrails", "registry", "compliance",
)


def estimate_job_size(text: str, *, base: int = 5) -> int:
    """Rough effort estimate (story-point-like) from the title text."""
    lowered = text.lower()
    size = base
    if any(h in lowered for h in _BIG_EFFORT_HINTS):
        size = 13
    elif len(text) > 60:
        size = 8
    return size


# ── Markdown table parsing ───────────────────────────────────────────────────
def _table_rows(markdown: str, section_heading: str) -> List[List[str]]:
    """Return the data rows (as cell lists) of the markdown table under a heading."""
    lines = markdown.splitlines()
    rows: List[List[str]] = []
    in_section = False
    seen_header = False
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("#"):
            in_section = section_heading.lower() in stripped.lower()
            seen_header = False
            continue
        if not in_section:
            continue
        if not stripped.startswith("|"):
            if seen_header and not stripped:
                # blank line after the table ends the section's table
                if rows:
                    break
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if not seen_header:
            seen_header = True
            continue
        if set("".join(cells)) <= set("-: "):  # separator row
            continue
        rows.append(cells)
    return rows


def _clean(cell: str) -> str:
    """Strip markdown emphasis/backticks/links from a table cell."""
    cell = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", cell)  # [text](url) → text
    return cell.replace("`", "").replace("*", "").strip()


def _is_open(status: str) -> bool:
    s = _clean(status).upper()
    return s in {"TODO", "IN_PROGRESS", "BLOCKED", "BUG_FOUND"}


def _status_for(raw: str) -> InitiativeStatus:
    s = _clean(raw).upper()
    if s == "IN_PROGRESS":
        return InitiativeStatus.IN_PROGRESS
    if s in {"BLOCKED", "BUG_FOUND"}:
        return InitiativeStatus.APPROVED
    return InitiativeStatus.PROPOSED


# ── Signal → Initiative builders ─────────────────────────────────────────────
def _mk(title: str, scores: tuple, *, source: str, rationale: str,
        status: InitiativeStatus = InitiativeStatus.PROPOSED) -> Initiative:
    bv, tc, rr, js = scores
    return Initiative(
        initiative_id=uuid4().hex[:12],
        title=title.strip()[:140],
        business_value=bv, time_criticality=tc, risk_reduction=rr, job_size=js,
        status=status, source=source, rationale=rationale,
    )


def initiatives_from_roadmap(markdown: str) -> List[Initiative]:
    """Build initiatives from the Roadmap Items + Current Sprint Tasks tables."""
    out: List[Initiative] = []
    # Roadmap Items: | # | Item | Priority | Status | PR |
    for cells in _table_rows(markdown, "Roadmap Items"):
        if len(cells) < 4:
            continue
        item, priority, status = _clean(cells[1]), _clean(cells[2]), cells[3]
        if not item or not _is_open(status):
            continue
        js = estimate_job_size(item)
        out.append(_mk(
            item, _roadmap_scores(priority, js),
            source="roadmap",
            rationale=f"Backlog {priority} from roadmap-killer-todos",
            status=_status_for(status),
        ))
    # Current Sprint Tasks: | # | Task | Status | PR/Branch | Notes | Updated |
    for cells in _table_rows(markdown, "Current Sprint Tasks"):
        if len(cells) < 3:
            continue
        task, status = _clean(cells[1]), cells[2]
        if not task or not _is_open(status):
            continue
        js = estimate_job_size(task)
        out.append(_mk(
            task, _roadmap_scores("P1", js),
            source="sprint",
            rationale="Open sprint task",
            status=_status_for(status),
        ))
    return out


def initiatives_from_bug_log(markdown: str) -> List[Initiative]:
    """Build urgent initiatives from open Bug Log rows."""
    out: List[Initiative] = []
    # Bug Log: | # | Bug Description | Found | Fixed | PR | Status |
    for cells in _table_rows(markdown, "Bug Log"):
        if len(cells) < 6:
            continue
        desc, status = _clean(cells[1]), _clean(cells[5]).upper()
        if not desc or status not in {"BUG_FOUND", "OPEN", "TODO"}:
            continue
        out.append(_mk(
            f"Fix: {desc}", _bug_scores(),
            source="bug", rationale="Open bug from the tracker",
            status=InitiativeStatus.APPROVED,
        ))
    return out


def initiatives_from_github(payload: Dict) -> List[Initiative]:
    """Build initiatives from a GitHub signals payload (pulls + bug issues)."""
    out: List[Initiative] = []
    for pr in payload.get("pulls", []):
        title = (pr.get("title") or "").strip()
        if not title:
            continue
        out.append(_mk(
            title, _pr_scores(estimate_job_size(title)),
            source="pr",
            rationale=f"Open PR #{pr.get('number')} — work in flight",
            status=InitiativeStatus.IN_PROGRESS,
        ))
    for issue in payload.get("bug_issues", []):
        title = (issue.get("title") or "").strip()
        if not title:
            continue
        out.append(_mk(
            f"Fix: {title}", _bug_scores(),
            source="bug",
            rationale=f"Open bug issue #{issue.get('number')}",
            status=InitiativeStatus.APPROVED,
        ))
    return out


def initiatives_from_research(alerts: List[Dict]) -> List[Initiative]:
    """Build strategic initiatives from research/trend alerts."""
    out: List[Initiative] = []
    for a in alerts:
        title = (a.get("title") or "").strip()
        if not title:
            continue
        relevance = float(a.get("relevance_score", 0.0) or 0.0)
        out.append(_mk(
            f"Evaluate: {title}", _research_scores(relevance, estimate_job_size(title, base=8)),
            source="research",
            rationale=f"{a.get('source', 'trend')} signal (relevance {relevance:.2f})",
            status=InitiativeStatus.PROPOSED,
        ))
    return out


# ── Live fetchers (lazy, fail-soft) ──────────────────────────────────────────
def fetch_github_signals(
    repo: str,
    token: Optional[str],
    *,
    http_get: Optional[Callable[[str, dict], object]] = None,
    max_items: int = 20,
) -> Dict:
    """Fetch open PRs and bug-labelled issues. Returns {} on any failure/no token."""
    if not token:
        log.info("portfolio: no GitHub token — skipping PR/issue signals")
        return {}

    def _default_get(url: str, headers: dict):
        import httpx
        return httpx.get(url, headers=headers, timeout=8.0)

    getter = http_get or _default_get
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"}
    base = f"https://api.github.com/repos/{repo}"
    payload: Dict = {"pulls": [], "bug_issues": []}

    def _items(resp: object, label: str) -> list:
        # A non-2xx GitHub response is a JSON *object* (e.g. 404's
        # {"message": "Not Found", ...}), not a list — slicing that with
        # [:max_items] raises "unhashable type: 'slice'" (dict.__getitem__
        # rejects the unhashable slice key). Check status + type first so
        # a wrong repo / bad token / outage logs a clear message instead
        # of a cryptic TypeError that looks unrelated to the real cause.
        status = getattr(resp, "status_code", None)
        if status is not None and status != 200:
            log.warning(
                "portfolio: GitHub %s fetch got HTTP %s for repo=%s — %s",
                label, status, repo, str(getattr(resp, "text", ""))[:200],
            )
            return []
        data = resp.json()
        if not isinstance(data, list):
            log.warning(
                "portfolio: GitHub %s fetch returned non-list JSON for repo=%s: %r",
                label, repo, data if not isinstance(data, dict) else data.get("message", data),
            )
            return []
        return data[:max_items]

    try:
        pr_resp = getter(f"{base}/pulls?state=open&per_page={max_items}", headers)
        for pr in _items(pr_resp, "pulls"):
            payload["pulls"].append({"title": pr.get("title"), "number": pr.get("number")})
        issue_resp = getter(f"{base}/issues?state=open&labels=bug&per_page={max_items}", headers)
        for issue in _items(issue_resp, "bug_issues"):
            if issue.get("pull_request"):
                continue  # the issues API also returns PRs
            payload["bug_issues"].append({"title": issue.get("title"), "number": issue.get("number")})
    except Exception as exc:  # network restricted, rate limited, bad token …
        log.warning("portfolio: GitHub signal fetch failed: %s", exc)
    return payload


def _run_coro_sync(coro):
    """Run an async coroutine from sync code, safe even inside a running loop.

    ``PortfolioIntelligence.build()`` is sync but is always invoked from
    inside FastAPI's async request handling (``refresh_board()`` /
    ``materialize_portfolio()``), so ``asyncio.run(coro)`` here always
    raised "cannot be called from a running event loop" — every refresh,
    in every environment, silently dropped all trend/research-sourced
    initiatives (caught by the caller's best-effort try/except). When a
    loop is already running, offload to a fresh thread with its own loop
    instead.
    """
    import asyncio

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)  # no loop running — the fast path
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(asyncio.run, coro).result(timeout=15)


def fetch_research_alerts(*, limit: int = 6, min_relevance: float = 0.35) -> List[Dict]:
    """Best-effort fetch of trend alerts. Returns [] if offline or unavailable."""
    try:
        from agent.trend_watcher import TrendWatcher
    except Exception as exc:
        log.info("portfolio: trend watcher unavailable: %s", exc)
        return []
    try:
        alerts = _run_coro_sync(TrendWatcher().fetch())
    except Exception as exc:
        log.warning("portfolio: trend fetch failed: %s", exc)
        return []
    out: List[Dict] = []
    for a in alerts:
        score = float(getattr(a, "relevance_score", 0.0) or 0.0)
        if score < min_relevance:
            continue
        out.append({
            "title": getattr(a, "title", ""),
            "source": getattr(a, "source", "trend"),
            "relevance_score": score,
        })
    return out[:limit]


# ── Orchestrator ─────────────────────────────────────────────────────────────
class PortfolioIntelligence:
    """Assembles a PortfolioManager from live signals with WSJF scoring."""

    def __init__(
        self,
        *,
        repo: str = DEFAULT_REPO,
        root: Optional[Path] = None,
        github_token: Optional[str] = None,
    ) -> None:
        self.repo = repo
        self.root = root or _REPO_ROOT
        self.github_token = github_token or _env_github_token()
        self.last_build: Dict[str, int] = {}

    def _read(self, rel: str) -> str:
        try:
            return (self.root / rel).read_text(encoding="utf-8")
        except Exception:
            return ""

    def build(
        self,
        *,
        include_github: bool = True,
        include_research: bool = True,
        github_payload: Optional[Dict] = None,
        research_alerts: Optional[List[Dict]] = None,
    ) -> PortfolioManager:
        """Sweep all signals and return a populated, de-duplicated PortfolioManager."""
        tasks_md = self._read(".claude/state/active-tasks.md")
        roadmap_md = self._read("docs/roadmap-killer-todos.md")

        collected: List[Initiative] = []
        collected += initiatives_from_roadmap(tasks_md)
        collected += initiatives_from_bug_log(tasks_md)
        if roadmap_md:
            collected += initiatives_from_roadmap(roadmap_md)

        if include_github:
            payload = github_payload if github_payload is not None else \
                fetch_github_signals(self.repo, self.github_token)
            collected += initiatives_from_github(payload)

        if include_research:
            alerts = research_alerts if research_alerts is not None else fetch_research_alerts()
            collected += initiatives_from_research(alerts)

        mgr = PortfolioManager()
        counts: Dict[str, int] = {}
        seen: Dict[str, Initiative] = {}
        for init in collected:
            key = _norm_title(init.title)
            existing = seen.get(key)
            if existing is not None:
                # keep the higher-WSJF / more-progressed signal
                if init.wsjf > existing.wsjf:
                    seen[key] = init
                continue
            seen[key] = init
        for init in seen.values():
            mgr.register(init)
            counts[init.source] = counts.get(init.source, 0) + 1
        self.last_build = counts
        return mgr


def _env_github_token() -> Optional[str]:
    return (
        os.environ.get("GITHUB_TOKEN")
        or os.environ.get("GH_PAT")
        or os.environ.get("GITHUB_ACCESS_TOKEN")
    )


def _norm_title(title: str) -> str:
    base = re.sub(r"^(fix|evaluate|implement|add)\s*:?\s*", "", title.lower()).strip()
    return re.sub(r"[^a-z0-9]+", " ", base).strip()
