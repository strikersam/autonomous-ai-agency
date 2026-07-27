"""Single source of truth for the application version and brand.

Bump with ``python scripts/bump_version.py X.Y.Z`` — that propagates this value to
``frontend/src/version.js``, ``frontend/package.json``, ``frontend/public/index.html``,
and the README version badge. ``tests/test_version_consistency.py`` guards against drift.
"""

from __future__ import annotations

import os

__version__ = "5.0.0"

APP_NAME = "Autonomous AI Agency"
APP_TAGLINE = "Your AI-powered workforce"

# Human-facing label, e.g. "Autonomous AI Agency v5.0".
APP_LABEL = f"{APP_NAME} v{'.'.join(__version__.split('.')[:2])}"

# Environment variables a host may use to stamp the built commit into the
# running image. Render injects RENDER_GIT_COMMIT; the others are conventional
# fallbacks for other hosts and for local Docker builds that pass one in.
_COMMIT_ENV_VARS = ("RENDER_GIT_COMMIT", "GIT_COMMIT", "SOURCE_COMMIT")


def deployed_commit() -> str | None:
    """Return the git SHA of the running build, or None when unknown.

    This exists so a deploy can be *verified* rather than assumed. Without it
    ``/api/health`` looks identical before and after a deploy, so a health poll
    run seconds after triggering one happily passes against the **old**
    instance that is still serving — which is exactly how a failed Render build
    reported itself as a green "Deploy Backend to Render" job.

    Returning None is a first-class answer meaning "this host did not tell us
    what it built". Callers must treat it as *unverifiable* rather than as a
    mismatch, so a host that sets none of these variables degrades to the
    previous reachability-only behaviour instead of failing every deploy.
    """
    for name in _COMMIT_ENV_VARS:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return None
