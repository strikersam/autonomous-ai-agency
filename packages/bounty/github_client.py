"""packages/bounty/github_client.py — the GitHub REST calls the hunter makes.

Every URL is built from a fixed host plus an ``owner/name`` slug validated by
:func:`packages.bounty.models.valid_repo`, so no externally supplied URL is ever
requested (CLAUDE.md rule 14). Redirects are not followed.
"""
from __future__ import annotations

import asyncio
import base64
import logging
from typing import Any

import httpx

from packages.bounty.models import valid_repo

log = logging.getLogger("qwen-proxy")

API = "https://api.github.com"
POLICY_FILES = ("CONTRIBUTING.md", ".github/CONTRIBUTING.md", "AI_POLICY.md",
                ".github/AI_POLICY.md", "docs/CONTRIBUTING.md")


class GitHubError(RuntimeError):
    """A GitHub call failed in a way the caller should handle."""


def _repo(full_name: str) -> str:
    if not valid_repo(full_name):
        raise GitHubError(f"refusing invalid repository slug {full_name!r}")
    return full_name


class GitHubClient:
    """Thin async wrapper over the handful of REST endpoints the hunter needs."""

    def __init__(self, token: str, *, client: httpx.AsyncClient | None = None) -> None:
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = client or httpx.AsyncClient(base_url=API, headers=headers, timeout=30.0,
                                                 follow_redirects=False)

    async def aclose(self) -> None:
        """Close the underlying HTTP client."""
        await self._http.aclose()

    async def _call(self, method: str, path: str, **kwargs: Any) -> Any:
        resp = await self._http.request(method, path, **kwargs)
        if resp.status_code == 404:
            return None
        if resp.status_code >= 400:
            raise GitHubError(f"{method} {path} -> HTTP {resp.status_code}")
        return resp.json() if resp.content else {}

    async def search_issues(self, query: str, per_page: int = 50, page: int = 1) -> list[dict[str, Any]]:
        """Issue search, newest first."""
        data = await self._call("GET", "/search/issues", params={
            "q": query, "sort": "created", "order": "desc", "per_page": per_page, "page": page})
        return list((data or {}).get("items", []))

    async def get_repo(self, full_name: str) -> dict[str, Any] | None:
        """Repository metadata."""
        return await self._call("GET", f"/repos/{_repo(full_name)}")

    async def issue_comments(self, full_name: str, number: int) -> list[dict[str, Any]]:
        """Up to 100 comments on an issue or PR."""
        data = await self._call("GET", f"/repos/{_repo(full_name)}/issues/{int(number)}/comments",
                                params={"per_page": 100})
        return list(data or [])

    async def get_issue(self, full_name: str, number: int) -> dict[str, Any] | None:
        """One issue."""
        return await self._call("GET", f"/repos/{_repo(full_name)}/issues/{int(number)}")

    async def file_text(self, full_name: str, path: str) -> str:
        """Decoded text of a file on the default branch, or ``""``."""
        data = await self._call("GET", f"/repos/{_repo(full_name)}/contents/{path}")
        if not isinstance(data, dict) or data.get("encoding") != "base64":
            return ""
        try:
            return base64.b64decode(data.get("content", "")).decode("utf-8", errors="replace")
        except ValueError:
            return ""

    async def policy_text(self, full_name: str) -> str:
        """Concatenated contribution-policy files, for the AI-ban check."""
        texts = await asyncio.gather(*(self.file_text(full_name, p) for p in POLICY_FILES))
        return "\n".join(t for t in texts if t)

    async def list_tracking_issues(self, repo: str, label: str, state: str = "all") -> list[dict[str, Any]]:
        """Every issue in *repo* carrying *label* (paginated, capped at 1000)."""
        out: list[dict[str, Any]] = []
        for page in range(1, 11):
            data = await self._call("GET", f"/repos/{_repo(repo)}/issues", params={
                "labels": label, "state": state, "per_page": 100, "page": page})
            batch = [i for i in (data or []) if "pull_request" not in i]
            out.extend(batch)
            if len(data or []) < 100:
                break
        return out

    async def create_issue(self, repo: str, title: str, body: str, labels: list[str]) -> dict[str, Any]:
        """Open an issue."""
        return await self._call("POST", f"/repos/{_repo(repo)}/issues",
                                json={"title": title, "body": body, "labels": labels})

    async def update_issue(self, repo: str, number: int, **fields: Any) -> dict[str, Any]:
        """Patch title/body/labels/state on an issue."""
        return await self._call("PATCH", f"/repos/{_repo(repo)}/issues/{int(number)}", json=fields)

    async def comment(self, repo: str, number: int, body: str) -> dict[str, Any]:
        """Comment on an issue or PR."""
        return await self._call("POST", f"/repos/{_repo(repo)}/issues/{int(number)}/comments",
                                json={"body": body})

    async def ensure_fork(self, full_name: str, login: str) -> str:
        """Fork *full_name* into *login*'s account (idempotent); return the fork slug."""
        name = _repo(full_name).split("/", 1)[1]
        existing = await self.get_repo(f"{login}/{name}")
        if existing and existing.get("fork"):
            return str(existing["full_name"])
        data = await self._call("POST", f"/repos/{full_name}/forks", json={})
        fork = str((data or {}).get("full_name", f"{login}/{name}"))
        for _ in range(10):
            if await self.get_repo(fork):
                return fork
            await asyncio.sleep(3)
        raise GitHubError(f"fork {fork} did not become available")

    async def create_pull(self, full_name: str, *, head: str, base: str, title: str,
                          body: str) -> dict[str, Any]:
        """Open a pull request on *full_name*."""
        return await self._call("POST", f"/repos/{_repo(full_name)}/pulls", json={
            "head": head, "base": base, "title": title, "body": body,
            "maintainer_can_modify": True})

    async def get_pull(self, full_name: str, number: int) -> dict[str, Any] | None:
        """One pull request."""
        return await self._call("GET", f"/repos/{_repo(full_name)}/pulls/{int(number)}")
