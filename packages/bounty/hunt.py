"""packages/bounty/hunt.py — one bounty-hunter run, end to end.

    discover → triage → allocate slots by agent P&L → solve → guard → push to
    fork → tracking issue (human review) → [approved] upstream PR with claim →
    sweep: merged / paid / lost → ledger

Nothing reaches a third-party repository until the operator adds the
``bounty:approved`` label. There is deliberately no switch that skips this:
an upstream PR is published under the operator's name.
"""
from __future__ import annotations

import logging
import re
import tempfile
from pathlib import Path
from typing import Any

import httpx

from packages.ai.agent_budget import agent_scope
from packages.bounty import sandbox, tracker
from packages.bounty.discovery import candidate_from_item, repo_from_item
from packages.bounty.github_client import GitHubClient, GitHubError
from packages.bounty.ledger import ROSTER, allocate, compute_pnl, render_ledger
from packages.bounty.models import BountyState, HuntRecord, Verdict, valid_repo
from packages.bounty.platforms import PLATFORMS, enabled_platforms
from packages.bounty.solver import ChatFn, solve
from packages.bounty.triage import TriageInput, already_paid, triage
from packages.bounty.workspace import clone, commit_and_push, inspect_patch
from packages.config.bounty_settings import BountySettings

log = logging.getLogger("qwen-proxy")

MAX_CANDIDATES = 40
TrackedRecord = tuple[int, HuntRecord, str]  # (issue number, record, issue body)


def _is_bot(comment: dict[str, Any]) -> bool:
    user = comment.get("user") or {}
    return str(user.get("type")) == "Bot" or str(user.get("login", "")).endswith("[bot]")


RepoCache = dict[str, tuple[dict[str, Any] | None, str]]


async def _expand(gh: GitHubClient, item: dict[str, Any], platform_id: str,
                  repo_cache: RepoCache) -> TriageInput | None:
    """Fetch comments, repo metadata and policy for one search hit."""
    repo = repo_from_item(item)
    if not valid_repo(repo):
        return None
    comments = await gh.issue_comments(repo, int(item.get("number", 0)))
    bounty = candidate_from_item(
        item, [str(c.get("body") or "") for c in comments if _is_bot(c)], platform_id)
    if bounty is None:
        return None
    if repo not in repo_cache:
        repo_cache[repo] = (await gh.get_repo(repo), await gh.policy_text(repo))
    info, policy = repo_cache[repo]
    return TriageInput(bounty, info or {"archived": True}, comments, policy)


async def discover(gh: GitHubClient, settings: BountySettings, known: set[str]) -> list[TriageInput]:
    """Search every enabled platform and fetch what triage needs for each new hit."""
    out: list[TriageInput] = []
    repo_cache: RepoCache = {}
    for platform in enabled_platforms(settings.platforms):
        try:
            items = await gh.search_issues(platform.search_query)
        except (GitHubError, httpx.HTTPError) as exc:
            log.warning("bounty: %s search failed: %s", platform.platform_id, exc)
            continue
        for item in items:
            if len(out) >= MAX_CANDIDATES:
                return out
            key = f"{repo_from_item(item)}#{item.get('number')}".lower()
            if key in known:
                continue
            known.add(key)
            try:
                expanded = await _expand(gh, item, platform.platform_id, repo_cache)
            except (GitHubError, httpx.HTTPError) as exc:
                log.warning("bounty: skipping %s: %s", key, exc)
                continue
            if expanded is not None:
                out.append(expanded)
    return out


async def load_records(gh: GitHubClient, settings: BountySettings) -> list[TrackedRecord]:
    """Every hunt record stored in the tracking repository."""
    issues = await gh.list_tracking_issues(settings.tracking_repo, tracker.TRACK_LABEL)
    out: list[TrackedRecord] = []
    for issue in issues:
        record = tracker.parse_record(str(issue.get("body") or ""))
        if record is not None:
            out.append((int(issue["number"]), record, str(issue.get("body") or "")))
    return out


async def save(gh: GitHubClient, settings: BountySettings, record: HuntRecord,
               *, number: int = 0, body: str = "", diff: str = "", test_log: str = "") -> int:
    """Create or update the tracking issue for *record*; return its number."""
    labels = tracker.labels_for(record)
    state = "closed" if record.state.terminal else "open"
    if number:
        new_body = tracker.rerender(body, record, settings.github_login)
        await gh.update_issue(settings.tracking_repo, number, body=new_body, labels=labels, state=state)
        return number
    text = tracker.render_body(record, settings.github_login, diff, test_log)
    issue = await gh.create_issue(settings.tracking_repo, tracker.issue_title(record), text, labels)
    number = int(issue.get("number", 0))
    if state == "closed" and number:
        await gh.update_issue(settings.tracking_repo, number, state="closed")
    return number


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:40] or "fix"


async def _solve_in(workdir: Path, gh: GitHubClient, item: TriageInput, settings: BountySettings,
                    chat: ChatFn, agent_id: str) -> tuple[Any, Any, str]:
    """Clone, prepare the sandbox and run the solver; returns (result, patch, base)."""
    bounty = item.bounty
    base = await clone(bounty.repo, workdir)
    plan = sandbox.plan_for(workdir) if sandbox.docker_available() else None
    if plan is not None:
        await sandbox.install(workdir, plan)
    issue = await gh.get_issue(bounty.repo, bounty.issue_number) or {}
    comments = [str(c.get("body") or "") for c in item.comments if not _is_bot(c)]
    with agent_scope(agent_id):
        result = await solve(bounty, str(issue.get("body") or ""), comments, workdir, chat,
                             max_steps=settings.solver_max_steps, plan=plan)
    if plan is not None and result.finished and result.tests == "unverified":
        outcome = await sandbox.run_tests(workdir, plan)  # the agent skipped its own check
        result.tests, result.test_log = outcome.status, outcome.log
    patch = await inspect_patch(workdir, settings.max_diff_lines, settings.github_token)
    return result, patch, base


async def attempt(gh: GitHubClient, settings: BountySettings, item: TriageInput,
                  verdict: Verdict, chat: ChatFn) -> HuntRecord:
    """Solve one bounty and park the result for review (or record the failure)."""
    bounty = item.bounty
    record = HuntRecord(bounty=bounty, agent_id=verdict.agent_id, state=BountyState.FAILED,
                        score=verdict.score, reasons=list(verdict.reasons))
    diff = test_log = ""
    with tempfile.TemporaryDirectory(prefix="bounty-") as tmp:
        workdir = Path(tmp) / "repo"
        try:
            result, patch, base = await _solve_in(workdir, gh, item, settings, chat, verdict.agent_id)
        except Exception:  # one bad repo or provider outage must not end the run
            log.exception("bounty: %s failed before a patch existed", bounty.key)
            record.summary = "could not prepare the workspace"
            await save(gh, settings, record)
            return record
        record.tokens_used, record.tests, test_log = result.tokens, result.tests, result.test_log
        record.summary, diff, record.base_branch = result.summary, patch.diff, base
        problems = list(patch.problems)
        if not result.finished:
            problems.append("solver did not finish")
        if result.tests == "failed":
            problems.append("tests fail after the change")
        if problems:
            record.reasons += problems
        else:
            record = await _publish(gh, settings, record, workdir)
    await save(gh, settings, record, diff=diff, test_log=test_log)
    return record


async def _publish(gh: GitHubClient, settings: BountySettings, record: HuntRecord,
                   workdir: Path) -> HuntRecord:
    """Push the patch to a branch on the operator's fork."""
    bounty = record.bounty
    try:
        fork = await gh.ensure_fork(bounty.repo, settings.github_login)
        branch = f"bounty/{bounty.issue_number}-{_slug(bounty.title)}"
        message = f"Fix #{bounty.issue_number}: {bounty.title}"[:72]
        await commit_and_push(workdir, branch=branch, fork=fork, message=message,
                              login=settings.github_login, token=settings.github_token)
    except (RuntimeError, GitHubError) as exc:
        log.warning("bounty: publishing %s failed: %s", bounty.key, exc)
        record.reasons.append("could not push to fork")
        return record
    return record.model_copy(update={"state": BountyState.AWAITING_REVIEW,
                                     "fork_repo": fork, "branch": branch})


def pr_body(record: HuntRecord) -> str:
    """Upstream PR description, including the platform's claim text."""
    bounty = record.bounty
    platform = PLATFORMS.get(bounty.platform, PLATFORMS["generic"])
    tests = {"passed": "The project's test suite passes with this change.",
             "unverified": "I could not run the project's test suite automatically."}
    return "\n\n".join([
        platform.claim_text(bounty.issue_number),
        record.summary or "Fix for the linked issue.",
        tests.get(record.tests, f"Tests: {record.tests}."),
        "This change was prepared with AI assistance and reviewed before submission.",
    ])


async def submit(gh: GitHubClient, settings: BountySettings, number: int, body: str,
                 record: HuntRecord) -> HuntRecord:
    """Open the upstream PR for an approved record, after re-checking the bounty."""
    bounty = record.bounty
    if record.state is not BountyState.AWAITING_REVIEW:
        return record
    issue = await gh.get_issue(bounty.repo, bounty.issue_number) or {}
    comments = await gh.issue_comments(bounty.repo, bounty.issue_number)
    if issue.get("state") != "open" or already_paid(comments):
        record = record.model_copy(update={"state": BountyState.LOST,
                                           "reasons": [*record.reasons, "bounty closed before submission"]})
        await save(gh, settings, record, number=number, body=body)
        return record
    head = f"{settings.github_login}:{record.branch}"
    pull = await gh.create_pull(bounty.repo, head=head, base=record.base_branch,
                                title=f"Fix #{bounty.issue_number}: {bounty.title}"[:120],
                                body=pr_body(record))
    record = record.model_copy(update={"state": BountyState.SUBMITTED,
                                       "upstream_pr": int(pull.get("number", 0))})
    await save(gh, settings, record, number=number, body=body)
    return record


async def decline(gh: GitHubClient, settings: BountySettings, number: int, body: str,
                  record: HuntRecord) -> HuntRecord:
    """Record the operator's decision not to submit."""
    if record.state is not BountyState.AWAITING_REVIEW:
        return record
    record = record.model_copy(update={"state": BountyState.DECLINED})
    await save(gh, settings, record, number=number, body=body)
    return record


def _payout_seen(comments: list[dict[str, Any]], login: str) -> bool:
    return any(login.lower() in str(c.get("body") or "").lower() for c in comments
               if _is_bot(c) and already_paid([c]))


async def _bounty_gone(gh: GitHubClient, record: HuntRecord) -> bool:
    """True when the upstream issue closed or was paid to someone while we waited."""
    bounty = record.bounty
    issue = await gh.get_issue(bounty.repo, bounty.issue_number) or {}
    if issue.get("state") != "open":
        return True
    return already_paid(await gh.issue_comments(bounty.repo, bounty.issue_number))


async def advance(gh: GitHubClient, settings: BountySettings, tracked: TrackedRecord) -> HuntRecord:
    """Move a submitted or merged record forward from what GitHub now shows."""
    number, record, body = tracked
    bounty = record.bounty
    new_state = record.state
    if record.state is BountyState.AWAITING_REVIEW and await _bounty_gone(gh, record):
        new_state = BountyState.LOST
    if record.state is BountyState.SUBMITTED and record.upstream_pr:
        pull = await gh.get_pull(bounty.repo, record.upstream_pr) or {}
        if pull.get("merged"):
            new_state = BountyState.MERGED
        elif pull.get("state") == "closed":
            new_state = BountyState.LOST
    if new_state is BountyState.MERGED:
        comments = (await gh.issue_comments(bounty.repo, bounty.issue_number)
                    + await gh.issue_comments(bounty.repo, record.upstream_pr))
        if _payout_seen(comments, settings.github_login):
            new_state = BountyState.PAID
    if new_state is record.state:
        return record
    update: dict[str, Any] = {"state": new_state}
    if new_state is BountyState.PAID:
        update["revenue_usd"] = float(bounty.amount_usd)
    record = record.model_copy(update=update)
    await save(gh, settings, record, number=number, body=body)
    return record


async def sweep(gh: GitHubClient, settings: BountySettings,
                tracked: list[TrackedRecord]) -> list[HuntRecord]:
    """Advance every in-flight record; return the full, current record list."""
    out: list[HuntRecord] = []
    for item in tracked:
        try:
            out.append(await advance(gh, settings, item))
        except GitHubError as exc:
            log.warning("bounty: could not advance %s: %s", item[1].bounty.key, exc)
            out.append(item[1])
    return out


async def publish_ledger(gh: GitHubClient, settings: BountySettings, table: str) -> None:
    """Rewrite (or create) the single ledger issue."""
    issues = await gh.list_tracking_issues(settings.tracking_repo, tracker.LEDGER_LABEL, state="open")
    body = tracker.ledger_body(table)
    if issues:
        await gh.update_issue(settings.tracking_repo, int(issues[0]["number"]), body=body)
    else:
        await gh.create_issue(settings.tracking_repo, "Bounty hunter ledger", body,
                              [tracker.TRACK_LABEL, tracker.LEDGER_LABEL])


Scored = list[tuple[TriageInput, Verdict]]


def pick(scored: Scored, allocation: dict[str, int]) -> Scored:
    """Highest-scoring accepted candidates, within each agent's slot allowance."""
    left = dict(allocation)
    chosen: Scored = []
    for item, verdict in sorted(scored, key=lambda pair: pair[1].score, reverse=True):
        if verdict.accept and left.get(verdict.agent_id, 0) > 0:
            left[verdict.agent_id] -= 1
            chosen.append((item, verdict))
    return chosen


async def run_hunt(gh: GitHubClient, settings: BountySettings, chat: ChatFn | None) -> str:
    """One full scheduled run. Returns the markdown summary."""
    tracked = await load_records(gh, settings)
    records = await sweep(gh, settings, tracked)
    open_reviews = sum(1 for r in records if r.state is BountyState.AWAITING_REVIEW)
    slots = max(0, min(settings.max_attempts_per_run, settings.max_open_reviews - open_reviews))
    pnl = compute_pnl(records, ROSTER, settings.review_cost_usd)
    allocation = allocate(pnl, slots, settings.retire_after_attempts)
    lines = [f"Slots this run: {slots} (open reviews: {open_reviews})"]
    if slots and chat is not None:
        known = {r.bounty.key for r in records}
        candidates = await discover(gh, settings, known)
        scored = [(c, triage(c, settings, ROSTER)) for c in candidates]
        lines.append(f"Candidates: {len(candidates)}, accepted: {sum(v.accept for _, v in scored)}")
        for item, verdict in pick(scored, allocation):
            record = await attempt(gh, settings, item, verdict, chat)
            lines.append(f"- {record.bounty.key} → {record.state.value}")
            records.append(record)
    elif slots and chat is None:
        lines.append("No free tool-capable LLM provider configured; skipped solving.")
    pnl = compute_pnl(records, ROSTER, settings.review_cost_usd)
    table = render_ledger(pnl, allocation, settings.retire_after_attempts)
    await publish_ledger(gh, settings, table)
    return "\n".join([*lines, "", table])
