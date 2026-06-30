"""packages/tools/github_tool.py — GitHub operations tool.

Wraps GitHub API operations as a reusable platform tool. Supports
repository listing, file reading, PR creation, and issue management.

Uses the existing GitHubTools infrastructure (agent/github_tools.py)
but exposes it through the unified Tool interface.
"""
from __future__ import annotations

import logging
from typing import Any

from packages.tools.base import Tool, ToolResult, ToolSchema

log = logging.getLogger("tool.github")


class GitHubTool(Tool):
    """GitHub operations tool for repository management.

    Provides agents with the ability to:
    - List repositories
    - Read file contents
    - Create branches
    - Create pull requests
    - List issues
    """

    @property
    def name(self) -> str:
        return "github"

    @property
    def description(self) -> str:
        return "List repos, read files, create branches, create PRs, manage issues on GitHub"

    @property
    def capabilities(self) -> list[str]:
        return ["code", "git", "github", "repository", "ci"]

    @property
    def requires_auth(self) -> bool:
        return True

    async def execute(self, **kwargs: Any) -> ToolResult:
        """Execute a GitHub action.

        Args:
            action: One of 'list_repos', 'read_file', 'create_branch', 'create_pr', 'list_issues'
            owner: Repository owner
            repo: Repository name
            path: File path (for read_file)
            branch: Branch name (for create_branch)
            from_branch: Source branch (for create_branch/create_pr)
            title: PR title (for create_pr)
            body: PR body (for create_pr)
        """
        action = kwargs.get("action", "")
        try:
            if action == "list_repos":
                return await self._list_repos()
            elif action == "read_file":
                return await self._read_file(kwargs.get("owner", ""), kwargs.get("repo", ""), kwargs.get("path", ""))
            elif action == "create_branch":
                return await self._create_branch(kwargs.get("owner", ""), kwargs.get("repo", ""), kwargs.get("branch", ""), kwargs.get("from_branch", "main"))
            elif action == "create_pr":
                return await self._create_pr(kwargs.get("owner", ""), kwargs.get("repo", ""), kwargs.get("title", ""), kwargs.get("body", ""), kwargs.get("head", ""), kwargs.get("base", "main"))
            elif action == "list_issues":
                return await self._list_issues(kwargs.get("owner", ""), kwargs.get("repo", ""))
            else:
                return ToolResult(success=False, error=f"Unknown action: {action}")
        except Exception as exc:
            log.exception("GitHub tool error: %s", exc)
            return ToolResult(success=False, error=str(exc))

    def _get_token(self) -> str | None:
        """Get GitHub token from env."""
        import os
        return os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")

    async def _list_repos(self) -> ToolResult:
        """List repositories for the authenticated user."""
        import httpx
        token = self._get_token()
        if not token:
            return ToolResult(success=False, error="GITHUB_TOKEN not set")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                "https://api.github.com/user/repos",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                params={"per_page": 30, "sort": "updated"},
            )
            if resp.status_code != 200:
                return ToolResult(success=False, error=f"GitHub API error: {resp.status_code}")
            repos = [{"name": r["name"], "full_name": r["full_name"], "url": r["html_url"]} for r in resp.json()]
            return ToolResult(success=True, output=repos, metadata={"count": len(repos)})

    async def _read_file(self, owner: str, repo: str, path: str) -> ToolResult:
        """Read a file from a GitHub repository."""
        import httpx
        token = self._get_token()
        if not owner or not repo or not path:
            return ToolResult(success=False, error="owner, repo, and path are required")
        headers = {"Accept": "application/vnd.github.v3.raw"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/contents/{path}",
                headers=headers,
            )
            if resp.status_code != 200:
                return ToolResult(success=False, error=f"GitHub API error: {resp.status_code}")
            return ToolResult(success=True, output=resp.text[:10000], metadata={"owner": owner, "repo": repo, "path": path})

    async def _create_branch(self, owner: str, repo: str, branch: str, from_branch: str) -> ToolResult:
        """Create a new branch."""
        import httpx
        token = self._get_token()
        if not token:
            return ToolResult(success=False, error="GITHUB_TOKEN not set")
        async with httpx.AsyncClient(timeout=15) as client:
            # Get the SHA of the source branch
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/git/refs/heads/{from_branch}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
            )
            if resp.status_code != 200:
                return ToolResult(success=False, error=f"Failed to get source branch: {resp.status_code}")
            sha = resp.json()["object"]["sha"]
            # Create the new branch
            resp = await client.post(
                f"https://api.github.com/repos/{owner}/{repo}/git/refs",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                json={"ref": f"refs/heads/{branch}", "sha": sha},
            )
            if resp.status_code != 201:
                return ToolResult(success=False, error=f"Failed to create branch: {resp.status_code}")
            return ToolResult(success=True, output={"branch": branch, "from": from_branch})

    async def _create_pr(self, owner: str, repo: str, title: str, body: str, head: str, base: str) -> ToolResult:
        """Create a pull request."""
        import httpx
        token = self._get_token()
        if not token:
            return ToolResult(success=False, error="GITHUB_TOKEN not set")
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                json={"title": title, "body": body, "head": head, "base": base},
            )
            if resp.status_code != 201:
                return ToolResult(success=False, error=f"Failed to create PR: {resp.status_code}")
            pr = resp.json()
            return ToolResult(success=True, output={"number": pr["number"], "url": pr["html_url"]})

    async def _list_issues(self, owner: str, repo: str) -> ToolResult:
        """List open issues in a repository."""
        import httpx
        token = self._get_token()
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/issues",
                headers=headers,
                params={"state": "open", "per_page": 20},
            )
            if resp.status_code != 200:
                return ToolResult(success=False, error=f"GitHub API error: {resp.status_code}")
            issues = [{"number": i["number"], "title": i["title"], "url": i["html_url"]} for i in resp.json() if "pull_request" not in i]
            return ToolResult(success=True, output=issues, metadata={"count": len(issues)})

    async def health(self) -> bool:
        """Check if GitHub token is configured."""
        import os
        return bool(os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT"))

    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="github",
            description="GitHub repository operations: list repos, read files, create branches/PRs, list issues",
            parameters={
                "action": {"type": "string", "enum": ["list_repos", "read_file", "create_branch", "create_pr", "list_issues"]},
                "owner": {"type": "string", "description": "Repository owner"},
                "repo": {"type": "string", "description": "Repository name"},
                "path": {"type": "string", "description": "File path (for read_file)"},
                "branch": {"type": "string", "description": "New branch name (for create_branch)"},
                "from_branch": {"type": "string", "description": "Source branch (default: main)"},
                "title": {"type": "string", "description": "PR title (for create_pr)"},
                "body": {"type": "string", "description": "PR body (for create_pr)"},
                "head": {"type": "string", "description": "Head branch (for create_pr)"},
                "base": {"type": "string", "description": "Base branch (default: main)"},
            },
        )
