#!/usr/bin/env python3
"""Entry point for the always-on FreeBuff Telegram bot (Render worker / Docker).

Runs the Telegram long-poll bot in *embedded* mode: the FreeBuff agent executes
in-process (no separate proxy server, no MongoDB, no CEO agency), edits a fresh
clone of the target repo, and opens a draft PR via the GitHub token. This keeps
the 24x7 footprint small and lets you drive repo edits from your phone anywhere.

Required env (set in Render dashboard / .env):
    TELEGRAM_BOT_TOKEN          BotFather token
    TELEGRAM_ALLOWED_USER_IDS   comma-separated Telegram user IDs allowed to use the bot
    TELEGRAM_ADMIN_USER_IDS     subset allowed to run /freebuff (writes code)
    NVIDIA_API_KEY              free NVIDIA NIM key (powers the agent)
    GITHUB_TOKEN (or GH_PAT)    token used to push branches + open PRs

Optional env (sensible defaults applied below):
    FREEBUFF_REPO_URL           default: this repo
    FREEBUFF_BASE_BRANCH        default: master
    FREEBUFF_MODELS             override the free-model list
    GIT_AUTHOR_NAME / GIT_AUTHOR_EMAIL   commit identity
"""
from __future__ import annotations

import logging
import os
import subprocess  # nosec B404 — constant git argv, list form (no shell)

log = logging.getLogger("freebuff-bot-launcher")


def _default(key: str, value: str) -> None:
    """Set an env var only when the operator hasn't already provided one."""
    if not os.environ.get(key):
        os.environ[key] = value


def _configure() -> None:
    # Embedded mode: run the agent in-process; legacy workflow mode so
    # FreeBuffAgent.run() is not blocked by the orchestrator gate; auto-PR on.
    _default("FREEBUFF_EMBEDDED", "true")
    _default("AGENCY_WORKFLOW_MODE", "legacy")
    _default("AGENT_AUTO_PR_ENABLED", "true")
    _default("FREEBUFF_BASE_BRANCH", "master")
    _default("FREEBUFF_REPO_URL", "https://github.com/strikersam/local-llm-server")

    # Git identity for agent commits inside the cloned workspace.
    name = os.environ.get("GIT_AUTHOR_NAME", "FreeBuff Bot")
    email = os.environ.get("GIT_AUTHOR_EMAIL", "freebuff-bot@users.noreply.github.com")
    for args in (
        ["git", "config", "--global", "user.name", name],
        ["git", "config", "--global", "user.email", email],
        ["git", "config", "--global", "safe.directory", "*"],
    ):
        try:
            subprocess.run(args, check=False, capture_output=True)  # nosec - constant git argv, list form (no shell)
        except OSError as exc:
            log.warning("git config failed (%s): %s", args, exc)


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    _configure()
    import asyncio

    from telegram_bot import run_bot

    log.info("Starting FreeBuff Telegram bot (embedded=%s)", os.environ.get("FREEBUFF_EMBEDDED"))
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
