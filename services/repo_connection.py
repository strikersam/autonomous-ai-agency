"""services/repo_connection.py — RepoConnection + DeliveryPolicy (Autonomy Charter G5).

Gives each onboarded Company a typed connection to its code repo and a
**detected delivery policy**, so the agentic SDLC (Loop 3) lands changes the way
each repo expects instead of guessing:

  - ``parse_repo_url`` / ``provider_of`` — GitHub-only this pass; GitLab and
    Bitbucket are surfaced as *coming soon* (typed skip), never mis-handled.
  - ``detect_delivery_policy`` — reads the default branch + branch protection
    via an injectable GitHub probe and infers ``direct_push`` vs ``pr_required``.
    **Uncertain or protected ⇒ ``pr_required``** (charter §8 safest-path rule).
  - ``decide_merge`` — at land time, returns whether to pause
    (``awaiting_repo_connection``), force the **first-unattended-merge Telegram
    gate** (🔴, regardless of policy), open a PR, or push directly.
  - ``attach_repo_connection`` — best-effort persistence onto the Company during
    onboarding.

All detection is mockable (pass a fake ``probe``); no network is required for
unit tests.
"""
from __future__ import annotations

import logging
import os
import re
from typing import Any, Protocol

import httpx

from models.company_graph import DeliveryPolicy, RepoConnection
from pydantic import BaseModel, Field

log = logging.getLogger("qwen-proxy")

# When the default branch is unprotected, only emit ``direct_push`` if direct
# push is *explicitly* allowed; otherwise keep the PR-required safe default.
ALLOW_DIRECT_PUSH = os.environ.get("REPO_ALLOW_DIRECT_PUSH", "false").strip().lower() == "true"

# Providers we recognise but do not yet support (honest "coming soon").
COMING_SOON_PROVIDERS = ("gitlab", "bitbucket", "azure_devops")

_GITHUB_URL_RE = re.compile(
    r"github\.com[/:]+([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+?)(?:\.git)?/?$",
    re.IGNORECASE,
)
_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


class UnsupportedProviderError(Exception):
    """Raised for a non-GitHub repo URL — carries the detected provider name."""

    def __init__(self, provider: str, url: str) -> None:
        self.provider = provider
        self.url = url
        super().__init__(f"{provider} repos are coming soon — not yet supported: {url}")


def provider_of(url: str) -> str:
    """Return the git provider for a repo URL: ``github`` / a coming-soon name / ``unknown``."""
    low = (url or "").lower()
    if "github.com" in low:
        return "github"
    for prov in COMING_SOON_PROVIDERS:
        if prov.replace("_", "") in low.replace("_", "") or prov in low:
            return prov
    return "unknown"


def parse_repo_url(url: str) -> tuple[str, str] | None:
    """Parse ``owner, repo`` from a GitHub URL, or None if it is not GitHub.

    Raises :class:`UnsupportedProviderError` for a recognised non-GitHub provider
    (GitLab / Bitbucket) so callers surface "coming soon" rather than fabricating.
    """
    if not url:
        return None
    prov = provider_of(url)
    if prov in COMING_SOON_PROVIDERS:
        raise UnsupportedProviderError(prov, url)
    m = _GITHUB_URL_RE.search(url.strip())
    if not m:
        return None
    owner, repo = m.group(1), m.group(2)
    if not (_NAME_RE.match(owner) and _NAME_RE.match(repo)):
        return None
    return owner, repo


# ── GitHub policy probe (injectable) ─────────────────────────────────────────


class RepoPolicyProbe(Protocol):
    """Minimal interface ``detect_delivery_policy`` needs; mock it in tests."""

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]: ...

    async def get_branch_protection(
        self, owner: str, repo: str, branch: str
    ) -> dict[str, Any] | None:
        """Return protection settings, ``None`` if unprotected (404), or raise on uncertainty."""
        ...


class GitHubPolicyProbe:
    """Default :class:`RepoPolicyProbe` backed by the GitHub REST API."""

    def __init__(self, token: str | None = None) -> None:
        self.token = token or (
            os.environ.get("GH_TOKEN")
            or os.environ.get("GH_PAT")
            or os.environ.get("GITHUB_TOKEN")
        )
        self.base_url = "https://api.github.com"

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers

    async def get_repo(self, owner: str, repo: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}", headers=self._headers()
            )
            resp.raise_for_status()
            return resp.json()

    async def get_branch_protection(
        self, owner: str, repo: str, branch: str
    ) -> dict[str, Any] | None:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(
                f"{self.base_url}/repos/{owner}/{repo}/branches/{branch}/protection",
                headers=self._headers(),
            )
            if resp.status_code == 404:
                return None  # branch exists but is not protected
            resp.raise_for_status()
            return resp.json()


async def detect_delivery_policy(
    owner: str,
    repo: str,
    *,
    probe: RepoPolicyProbe | None = None,
    allow_direct_push: bool = ALLOW_DIRECT_PUSH,
) -> DeliveryPolicy:
    """Detect a repo's :class:`DeliveryPolicy` (GitHub-only).

    - Protected default branch ⇒ ``pr_required`` (with detected review/check reqs).
    - Unprotected **and** ``allow_direct_push`` ⇒ ``direct_push``.
    - Anything uncertain (API error, missing data) ⇒ ``pr_required`` (safe default).
    """
    probe = probe or GitHubPolicyProbe()
    default_branch = "main"
    try:
        meta = await probe.get_repo(owner, repo)
        default_branch = str((meta or {}).get("default_branch") or "main")
    except Exception as exc:  # noqa: BLE001 — uncertainty ⇒ safe PR default
        log.warning("repo-connection: get_repo failed for %s/%s: %s", owner, repo, exc)
        return DeliveryPolicy(
            mode="pr_required", default_branch=default_branch, protected=True,
            detection_note="uncertain (repo metadata unavailable) → pr_required",
        )

    try:
        protection = await probe.get_branch_protection(owner, repo, default_branch)
    except Exception as exc:  # noqa: BLE001 — uncertainty ⇒ safe PR default
        log.warning(
            "repo-connection: branch-protection probe failed for %s/%s@%s: %s",
            owner, repo, default_branch, exc,
        )
        return DeliveryPolicy(
            mode="pr_required", default_branch=default_branch, protected=True,
            detection_note="uncertain (protection probe failed) → pr_required",
        )

    if protection:
        reviews = (
            (protection.get("required_pull_request_reviews") or {})
            .get("required_approving_review_count", 0)
        )
        checks = bool(protection.get("required_status_checks"))
        return DeliveryPolicy(
            mode="pr_required",
            default_branch=default_branch,
            protected=True,
            required_reviews=int(reviews or 0),
            required_status_checks=checks,
            detection_note="default branch protected → pr_required",
        )

    # Unprotected default branch.
    if allow_direct_push:
        return DeliveryPolicy(
            mode="direct_push",
            default_branch=default_branch,
            protected=False,
            detection_note="unprotected + direct push explicitly allowed → direct_push",
        )
    return DeliveryPolicy(
        mode="pr_required",
        default_branch=default_branch,
        protected=False,
        detection_note="unprotected but direct push not allowed → pr_required (safe default)",
    )


def build_repo_connection(
    url: str,
    *,
    token_ref: str | None = None,
    policy: DeliveryPolicy | None = None,
) -> RepoConnection:
    """Build a GitHub :class:`RepoConnection` from a repo URL.

    Raises :class:`UnsupportedProviderError` for non-GitHub providers and
    ``ValueError`` for an unparseable URL.
    """
    parsed = parse_repo_url(url)
    if parsed is None:
        raise ValueError(f"Could not parse a GitHub owner/repo from URL: {url!r}")
    owner, repo = parsed
    return RepoConnection(
        provider="github",
        owner=owner,
        repo=repo,
        default_branch=(policy.default_branch if policy else "main"),
        token_ref=token_ref,
        policy=policy,
    )


# ── Merge-time decision (land step) ──────────────────────────────────────────


class MergeDecision(BaseModel):
    """What the SDLC should do when it wants to land a change."""
    model_config = {"frozen": True, "extra": "forbid"}

    action: str = Field(
        ...,
        description="awaiting_repo_connection | telegram_gate | open_pr | direct_push",
    )
    requires_approval: bool = Field(
        default=False, description="True ⇒ pause for the Telegram approval gate (🔴)"
    )
    reason: str = Field(default="", description="Why this action was chosen")


def decide_merge(connection: RepoConnection | None) -> MergeDecision:
    """Decide how to land a change given a company's repo connection.

    1. No connection ⇒ ``awaiting_repo_connection`` (URL-only company, Loop 5).
    2. First unattended merge on a newly connected repo ⇒ ``telegram_gate`` (🔴),
       regardless of the detected mode, until the operator records consent.
    3. Thereafter, follow the detected policy: ``pr_required`` ⇒ ``open_pr``;
       ``direct_push`` ⇒ ``direct_push``.
    """
    if connection is None:
        return MergeDecision(
            action="awaiting_repo_connection",
            requires_approval=False,
            reason="no repo connected — code work pauses until a repo + token is connected",
        )
    policy = connection.policy
    if policy is None or not policy.first_merge_consent:
        return MergeDecision(
            action="telegram_gate",
            requires_approval=True,
            reason="first unattended merge on a newly connected repo — gating for operator consent",
        )
    if policy.mode == "direct_push":
        return MergeDecision(
            action="direct_push",
            requires_approval=False,
            reason="repo delivery policy allows direct push",
        )
    return MergeDecision(
        action="open_pr",
        requires_approval=False,
        reason="repo delivery policy requires a pull request",
    )


def record_first_merge_consent(connection: RepoConnection) -> RepoConnection:
    """Return a copy of ``connection`` with first-merge consent recorded.

    Subsequent merges then follow the detected policy instead of re-gating.
    """
    policy = connection.policy or DeliveryPolicy()
    new_policy = policy.model_copy(update={"first_merge_consent": True})
    return connection.model_copy(update={"policy": new_policy})


async def attach_repo_connection(
    company_id: str,
    repo_url: str,
    *,
    store: Any,
    token_ref: str | None = None,
    probe: RepoPolicyProbe | None = None,
) -> RepoConnection | None:
    """Detect + persist a :class:`RepoConnection` onto a Company (best-effort).

    Returns the connection, or ``None`` when the URL is non-GitHub/unparseable or
    the company can't be loaded — never raises into the onboarding flow.
    """
    try:
        parsed = parse_repo_url(repo_url)
    except UnsupportedProviderError as exc:
        log.info("repo-connection: %s — skipping (coming soon)", exc)
        return None
    if parsed is None:
        return None
    owner, repo = parsed

    policy = await detect_delivery_policy(owner, repo, probe=probe)
    connection = build_repo_connection(repo_url, token_ref=token_ref, policy=policy)

    try:
        company = await store.get_company(company_id)
        if company is None:
            return connection
        updated = company.model_copy(update={"repo_connection": connection})
        await store.update_company(updated)
        log.info(
            "repo-connection: attached %s to company %s (mode=%s)",
            connection.full_name, company_id, policy.mode,
        )
    except Exception as exc:  # noqa: BLE001 — persistence is best-effort
        log.warning("repo-connection: failed to persist for %s: %s", company_id, exc)
    return connection
