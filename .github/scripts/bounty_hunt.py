#!/usr/bin/env python3
"""GitHub Actions entry point for the bounty hunter (packages/bounty).

    python .github/scripts/bounty_hunt.py hunt
    python .github/scripts/bounty_hunt.py approve --issue N
    python .github/scripts/bounty_hunt.py decline --issue N

``approve`` and ``decline`` run from the ``issues: labeled`` trigger, so the
operator's label on a tracking issue is the only thing that publishes a PR.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from packages.bounty import hunt, tracker  # noqa: E402
from packages.bounty.github_client import GitHubClient  # noqa: E402
from packages.bounty.solver import router_chat  # noqa: E402
from packages.config.autonomy_limits import kill_switch_engaged  # noqa: E402
from packages.config.bounty_settings import BountySettings, load_bounty_settings  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("qwen-proxy")


def _summary(text: str) -> None:
    path = load_bounty_settings().step_summary_path
    if path:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(text + "\n")
    log.info("%s", text)


async def _decide(gh: GitHubClient, settings: BountySettings, number: int, approve: bool) -> str:
    issue = await gh.get_issue(settings.tracking_repo, number) or {}
    body = str(issue.get("body") or "")
    record = tracker.parse_record(body)
    if record is None:
        return f"#{number} carries no bounty record; nothing to do."
    if approve:
        record = await hunt.submit(gh, settings, number, body, record)
    else:
        record = await hunt.decline(gh, settings, number, body, record)
    return f"#{number} → {record.state.value}"


async def _main(args: argparse.Namespace) -> int:
    settings = load_bounty_settings()
    if kill_switch_engaged():
        _summary("AGENCY_KILL_SWITCH is on — bounty hunter idle.")
        return 0
    if not (settings.github_login and settings.github_token and settings.tracking_repo):
        _summary("BOUNTY_GITHUB_LOGIN, GH_TOKEN and GITHUB_REPOSITORY are all required.")
        return 1
    gh = GitHubClient(settings.github_token)
    try:
        if args.command == "hunt":
            if not settings.enabled:
                _summary("BOUNTY_HUNTER_ENABLED is off — nothing to do.")
                return 0
            _summary(await hunt.run_hunt(gh, settings, router_chat()))
        else:
            _summary(await _decide(gh, settings, args.issue, args.command == "approve"))
    finally:
        await gh.aclose()
    return 0


def main() -> int:
    """Parse arguments and run one command."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["hunt", "approve", "decline"])
    parser.add_argument("--issue", type=int, default=0)
    args = parser.parse_args()
    if args.command != "hunt" and args.issue <= 0:
        parser.error("--issue is required for approve/decline")
    return asyncio.run(_main(args))


if __name__ == "__main__":
    sys.exit(main())
