"""packages/config/bounty_settings.py — knobs for the bounty-hunter loop.

The hunter runs in GitHub Actions (``.github/workflows/bounty-hunter.yml``), so
these values arrive as repository variables mapped into the job environment.
They are read on every call rather than cached, matching ``autonomy_limits``.

``BOUNTY_GITHUB_LOGIN`` is the account that owns forks, commits and claims. It
must be the account whose Algora profile receives payouts.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

_TRUTHY = {"1", "true", "yes", "on"}


def _int(name: str, default: int, minimum: int = 0) -> int:
    raw = os.environ.get(name, "").strip()
    try:
        value = int(raw) if raw else default
    except ValueError:
        value = default
    return max(minimum, value)


@dataclass(frozen=True)
class BountySettings:
    """Effective configuration for one hunter run."""

    enabled: bool
    platforms: str
    github_login: str
    github_token: str
    tracking_repo: str
    min_usd: int
    max_attempts_per_run: int
    max_open_reviews: int
    max_competitors: int
    max_issue_age_days: int
    max_repo_idle_days: int
    review_cost_usd: int
    retire_after_attempts: int
    solver_max_steps: int
    max_diff_lines: int
    step_summary_path: str


def load_bounty_settings() -> BountySettings:
    """Read the bounty-hunter configuration from the environment."""
    return BountySettings(
        enabled=os.environ.get("BOUNTY_HUNTER_ENABLED", "").strip().lower() in _TRUTHY,
        platforms=os.environ.get("BOUNTY_PLATFORMS", "").strip() or "algora,opire",
        github_login=os.environ.get("BOUNTY_GITHUB_LOGIN", "").strip(),
        github_token=os.environ.get("GH_TOKEN", "").strip(),
        tracking_repo=os.environ.get("GITHUB_REPOSITORY", "").strip(),
        min_usd=_int("BOUNTY_MIN_USD", 50),
        max_attempts_per_run=_int("BOUNTY_MAX_ATTEMPTS_PER_RUN", 2),
        max_open_reviews=_int("BOUNTY_MAX_OPEN_REVIEWS", 5),
        max_competitors=_int("BOUNTY_MAX_COMPETITORS", 2),
        max_issue_age_days=_int("BOUNTY_MAX_ISSUE_AGE_DAYS", 90, minimum=1),
        max_repo_idle_days=_int("BOUNTY_MAX_REPO_IDLE_DAYS", 60, minimum=1),
        review_cost_usd=_int("BOUNTY_REVIEW_COST_USD", 5),
        retire_after_attempts=_int("BOUNTY_RETIRE_AFTER_ATTEMPTS", 10, minimum=1),
        solver_max_steps=_int("BOUNTY_SOLVER_MAX_STEPS", 40, minimum=1),
        max_diff_lines=_int("BOUNTY_MAX_DIFF_LINES", 400, minimum=1),
        step_summary_path=os.environ.get("GITHUB_STEP_SUMMARY", "").strip(),
    )
