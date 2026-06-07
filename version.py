"""Single source of truth for the application version and brand.

Bump with ``python scripts/bump_version.py X.Y.Z`` — that propagates this value to
``frontend/src/version.js``, ``frontend/package.json``, ``frontend/public/index.html``,
and the README version badge. ``tests/test_version_consistency.py`` guards against drift.
"""

from __future__ import annotations

__version__ = "5.0.1"

APP_NAME = "Agency Core"
APP_TAGLINE = "Autonomous AI Platform"

# Human-facing label, e.g. "Agency Core v5.0".
APP_LABEL = f"{APP_NAME} v{'.'.join(__version__.split('.')[:2])}"
