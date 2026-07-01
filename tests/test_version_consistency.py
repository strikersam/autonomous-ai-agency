"""Guard the version single-source-of-truth: every place that hardcodes the
version must agree with version.__version__. Bump them together with
``python scripts/bump_version.py X.Y.Z``.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from packages.shared.version import __version__

_ROOT = Path(__file__).resolve().parent.parent


def test_frontend_package_json_matches() -> None:
    pkg = json.loads((_ROOT / "frontend/package.json").read_text())
    assert pkg["version"] == __version__


def test_frontend_version_js_matches() -> None:
    text = (_ROOT / "frontend/src/version.js").read_text()
    m = re.search(r"APP_VERSION = '(\d+\.\d+\.\d+)'", text)
    assert m, "APP_VERSION not found in frontend/src/version.js"
    assert m.group(1) == __version__


def test_readme_badge_matches() -> None:
    text = (_ROOT / "README.md").read_text(encoding="utf-8")
    m = re.search(r"version-(\d+\.\d+\.\d+)-blue", text)
    assert m, "version badge not found in README.md"
    assert m.group(1) == __version__


def test_index_html_has_no_stale_version() -> None:
    text = (_ROOT / "frontend/public/index.html").read_text()
    minor = ".".join(__version__.split(".")[:2])
    assert f"Autonomous AI Agency v{minor}" in text
    # The old brand/version must be gone.
    assert "LLM Relay v4.1" not in text
    assert "Agency Core v" not in text
