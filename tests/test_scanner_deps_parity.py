"""Guard against the CI-vs-production dependency drift that made gucci.com (and
all bot-protected / DNS-detectable sites) silently return "No systems detected"
in production while CI found 19 systems.

Root cause that prompted this test: the production Docker image installs
``backend/requirements.txt`` (see ``Dockerfile.backend``), NOT the root
``requirements.txt`` that CI installs. The scanner imports ``curl_cffi`` and
``dnspython``, but those were only in the root file — so the production image
lacked them and both the anti-bot HTTP fetch and the DNS analysis silently
yielded nothing.

These tests assert that every third-party package the scanner actually imports
is declared in ``backend/requirements.txt``, so the two can't drift again.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_REQS = REPO_ROOT / "backend" / "requirements.txt"
SCANNER_SRC = REPO_ROOT / "services" / "scanner.py"

# Third-party top-level import name -> the distribution name as it appears
# (case-insensitively) in requirements. Stdlib modules are intentionally absent.
THIRD_PARTY_IMPORT_TO_DIST = {
    "curl_cffi": "curl_cffi",
    "dns": "dnspython",        # `import dns.resolver` ships in the `dnspython` dist
    "bs4": "beautifulsoup4",   # `from bs4 import BeautifulSoup`
    "playwright": "playwright",
    "httpx": "httpx",
}


def _declared_packages() -> set[str]:
    if not BACKEND_REQS.exists():  # pragma: no cover
        pytest.skip("backend/requirements.txt not found")
    pkgs: set[str] = set()
    for line in BACKEND_REQS.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        # Strip version specifiers / extras: "uvicorn[standard]>=0.48" -> "uvicorn"
        name = re.split(r"[\[<>=!~ ]", line, maxsplit=1)[0].strip().lower()
        if name:
            pkgs.add(name)
    return pkgs


def _scanner_imports() -> set[str]:
    """Top-level module names imported anywhere in services/scanner.py."""
    src = SCANNER_SRC.read_text()
    names: set[str] = set()
    for m in re.finditer(r"^\s*import\s+([a-zA-Z_][\w.]*)", src, re.MULTILINE):
        names.add(m.group(1).split(".")[0])
    for m in re.finditer(r"^\s*from\s+([a-zA-Z_][\w.]*)\s+import", src, re.MULTILINE):
        names.add(m.group(1).split(".")[0])
    return names


def test_scanner_third_party_deps_declared_in_backend_requirements():
    """Every third-party package the scanner imports must be in the file the
    PRODUCTION image installs (backend/requirements.txt) — not just the root
    requirements.txt that CI uses."""
    declared = _declared_packages()
    missing = []
    for import_name, dist in THIRD_PARTY_IMPORT_TO_DIST.items():
        # Only enforce for deps the scanner actually imports.
        if import_name in _scanner_imports() and dist.lower() not in declared:
            missing.append(f"{import_name} (dist: {dist})")
    assert not missing, (
        "Scanner imports these third-party packages, but they are MISSING from "
        "backend/requirements.txt (the file Dockerfile.backend installs in "
        f"production): {missing}. Production would silently fail to detect "
        "systems while CI passes. Add them to backend/requirements.txt."
    )


def test_critical_scanner_deps_explicitly_present():
    """Belt-and-suspenders: the two deps whose absence caused the gucci.com
    production regression must always be declared, regardless of import parsing."""
    declared = _declared_packages()
    for dist in ("curl_cffi", "dnspython"):
        assert dist.lower() in declared, (
            f"{dist} must be in backend/requirements.txt — without it the "
            "production scanner silently returns no systems for bot-protected / "
            "DNS-detectable sites (the gucci.com 'No systems detected' bug)."
        )
