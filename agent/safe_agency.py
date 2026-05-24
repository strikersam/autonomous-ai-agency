"""agent/safe_agency.py — Safe GitHub operations for the workflow engine.

All functions are async, use httpx, and redact tokens from logs.
They raise descriptive errors rather than returning ambiguous None values.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("qwen-proxy")

_GH_API = "https://api.github.com"
_TIMEOUT = 15.0


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


async def verify_pr_exists(
    github_token: str,
    owner: str,
    repo: str,
    pr_number: int,
) -> bool:
    """Return True if the PR exists and is open or merged; False if 404."""
    url = f"{_GH_API}/repos/{owner}/{repo}/pulls/{pr_number}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_headers(github_token))
    if resp.status_code == 404:
        return False
    resp.raise_for_status()
    state = resp.json().get("state", "")
    merged = resp.json().get("merged", False)
    return state in ("open",) or merged


async def get_default_branch(
    github_token: str,
    owner: str,
    repo: str,
) -> str:
    """Return the default branch name (e.g. 'master' or 'main')."""
    url = f"{_GH_API}/repos/{owner}/{repo}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_headers(github_token))
    resp.raise_for_status()
    return resp.json()["default_branch"]


async def get_branch_sha(
    github_token: str,
    owner: str,
    repo: str,
    branch: str,
) -> str:
    """Return the HEAD SHA for *branch*. Raises httpx.HTTPStatusError if not found."""
    url = f"{_GH_API}/repos/{owner}/{repo}/git/ref/heads/{branch}"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, headers=_headers(github_token))
    resp.raise_for_status()
    return resp.json()["object"]["sha"]


async def safe_create_branch(
    github_token: str,
    owner: str,
    repo: str,
    branch_name: str,
    base_sha: str,
) -> dict[str, Any]:
    """Create *branch_name* from *base_sha*.

    If the branch already exists, returns its current ref data without error.
    """
    url = f"{_GH_API}/repos/{owner}/{repo}/git/refs"
    payload = {"ref": f"refs/heads/{branch_name}", "sha": base_sha}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=_headers(github_token))

    if resp.status_code == 422:
        # Branch already exists — fetch it
        log.debug("Branch %s already exists; fetching current ref", branch_name)
        sha = await get_branch_sha(github_token, owner, repo, branch_name)
        return {"ref": f"refs/heads/{branch_name}", "object": {"sha": sha}}

    resp.raise_for_status()
    return resp.json()


async def safe_create_pr(
    github_token: str,
    owner: str,
    repo: str,
    title: str,
    body: str,
    head: str,
    base: str,
    *,
    draft: bool = False,
) -> dict[str, Any]:
    """Create a pull request. Returns the PR object dict.

    If a PR already exists for *head* → *base*, returns the existing PR.
    """
    url = f"{_GH_API}/repos/{owner}/{repo}/pulls"
    payload = {
        "title": title,
        "body": body,
        "head": head,
        "base": base,
        "draft": draft,
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(url, json=payload, headers=_headers(github_token))

    if resp.status_code == 422:
        # PR likely already exists — find it
        err = resp.json()
        log.debug("PR creation 422: %s — searching for existing PR", err)
        return await _find_existing_pr(github_token, owner, repo, head, base)

    resp.raise_for_status()
    data = resp.json()
    log.info(
        "Created PR #%s: %s  url=%s",
        data.get("number"),
        title[:60],
        data.get("html_url"),
    )
    return data


async def _find_existing_pr(
    github_token: str,
    owner: str,
    repo: str,
    head: str,
    base: str,
) -> dict[str, Any]:
    """Return the first open PR matching head → base, or raise if not found."""
    url = f"{_GH_API}/repos/{owner}/{repo}/pulls"
    params = {"state": "open", "head": f"{owner}:{head}", "base": base}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(url, params=params, headers=_headers(github_token))
    resp.raise_for_status()
    prs = resp.json()
    if not prs:
        raise RuntimeError(f"No open PR found for {head} → {base}")
    return prs[0]


async def add_pr_comment(
    github_token: str,
    owner: str,
    repo: str,
    pr_number: int,
    body: str,
) -> dict[str, Any]:
    """Post a comment on a PR's issue thread."""
    url = f"{_GH_API}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(
            url,
            json={"body": body},
            headers=_headers(github_token),
        )
    resp.raise_for_status()
    return resp.json()
