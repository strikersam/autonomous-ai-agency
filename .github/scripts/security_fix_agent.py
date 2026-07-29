#!/usr/bin/env python3
"""OpenClaw security fix helper.

Lightweight CLI used by CI to check/fix Dependabot and CodeQL alerts.
Designed to fail-safe: check commands print counts; fix commands attempt work and exit 0.
"""
from __future__ import annotations

import os
import sys
from typing import Any

import requests

GITHUB_API_URL = "https://api.github.com"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_REPOSITORY = os.environ.get("GITHUB_REPOSITORY", "")


def _repo_parts() -> tuple[str, str]:
    if not GITHUB_REPOSITORY or "/" not in GITHUB_REPOSITORY:
        raise RuntimeError("GITHUB_REPOSITORY is missing or invalid")
    return GITHUB_REPOSITORY.split("/", 1)


def _request(path: str, params: dict[str, Any] | None = None) -> Any:
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN is missing")
    url = f"{GITHUB_API_URL}{path}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
    }
    res = requests.get(url, headers=headers, params=params, timeout=30)
    res.raise_for_status()
    return res.json() if res.content else []


def dependabot_count() -> int:
    owner, repo = _repo_parts()
    data = _request(f"/repos/{owner}/{repo}/dependabot/alerts", {"state": "open"})
    return len(data)


def codeql_count() -> int:
    owner, repo = _repo_parts()
    data = _request(f"/repos/{owner}/{repo}/code-scanning/alerts", {"state": "open"})
    return len(data)


# Allowed base directories for the openclaw script
_OPENCLAW_ALLOWED_DIRS = ("/app/openclaw",)
_OPENCLAW_SCRIPT_NAME = "index.js"


def _resolve_openclaw_path() -> str | None:
    """Resolve the OpenClaw script path safely, preventing symlink traversal.

    Returns the validated absolute path if it exists inside an allowed
    directory, or None to fall back to npx.
    """
    for allowed_dir in _OPENCLAW_ALLOWED_DIRS:
        candidate = os.path.join(allowed_dir, _OPENCLAW_SCRIPT_NAME)
        if not os.path.exists(candidate):
            continue
        # Resolve symlinks and verify the real path stays inside the allowed dir
        real_path = os.path.realpath(candidate)
        real_dir = os.path.realpath(allowed_dir)
        if not real_path.startswith(real_dir + os.sep) and real_path != os.path.join(real_dir, _OPENCLAW_SCRIPT_NAME):
            print(f"WARNING: {candidate} resolved to {real_path} outside {real_dir} \u2014 ignoring (possible symlink attack)")
            continue
        return real_path
    return None


def main() -> int:
    import subprocess
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    cmd = sys.argv[1]
    # Allowed arguments only
    if cmd not in ("--check-dependabot", "--check-codeql", "--fix-dependabot", "--fix-codeql"):
        print(f"Unknown argument: {cmd}")
        return 1

    try:
        if cmd == "--check-dependabot":
            print(dependabot_count())
            return 0
        if cmd == "--check-codeql":
            print(codeql_count())
            return 0

        # For fixes, we use subprocess.run with shell=False (default) and list of args
        if cmd == "--fix-dependabot":
            print("Running OpenClaw for Dependabot alerts...")
            openclaw_path = _resolve_openclaw_path()
            if openclaw_path:
                subprocess.run(["node", openclaw_path, "--fix", "dependabot"], check=False)
            else:
                subprocess.run(["npx", "--yes", "openclaw", "--fix", "dependabot"], check=False)
            return 0
        if cmd == "--fix-codeql":
            print("Running OpenClaw for CodeQL alerts...")
            openclaw_path = _resolve_openclaw_path()
            if openclaw_path:
                subprocess.run(["node", openclaw_path, "--fix", "codeql"], check=False)
            else:
                subprocess.run(["npx", "--yes", "openclaw", "--fix", "codeql"], check=False)
            return 0

        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"security_fix_agent error: {exc}", file=sys.stderr)
        # Keep fix invocations non-fatal
        return 0 if cmd.startswith("--fix-") else 1


if __name__ == "__main__":
    raise SystemExit(main())
