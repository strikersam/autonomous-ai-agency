"""Regression guard: Playwright's driver Node needs libatomic1 before --with-deps runs.

Browser E2E and Nightly Regression both build ``Dockerfile.backend``. Playwright
1.65.0 started shipping a driver ``node`` that links ``libatomic.so.1``, and the
Debian slim base has every other library that binary needs but not that one. The
build therefore died ~30 s into the Playwright layer with

    playwright/driver/node: error while loading shared libraries: libatomic.so.1
    ERROR: process "/bin/sh -c python -m playwright install --with-deps chromium"
           did not complete successfully: exit code: 127

``--with-deps`` cannot repair that itself: it installs its apt dependencies from
inside that same Node process, which never starts. So ``libatomic1`` has to be in
the image *before* the Playwright layer — installing it afterwards is the same
failure, which is why both the package and its position are pinned here.

``backend/requirements.txt`` leaves playwright unpinned (``playwright>=1.64.1``),
so a new Playwright release reaches this image without any code change; 1.64.1's
Node started fine, which is why the break only showed up when 1.65.0 was picked.
"""
from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile.backend"

_APT_INSTALL = "apt-get install"
_PLAYWRIGHT_WITH_DEPS = "playwright install --with-deps"


def _lines() -> list[str]:
    return DOCKERFILE.read_text(encoding="utf-8").splitlines()


def _index_of(fragment: str, *, extra: str = "") -> int:
    """First line index containing *fragment* (and *extra*, when given)."""
    for i, line in enumerate(_lines()):
        if fragment in line and extra in line and not line.lstrip().startswith("#"):
            return i
    raise AssertionError(f"Dockerfile.backend has no line containing {fragment!r}")


def test_libatomic1_is_installed() -> None:
    """The base image ships libstdc++/libgcc but not libatomic, so apt must add it."""
    _index_of(_APT_INSTALL, extra="libatomic1")


def test_libatomic1_installs_before_the_playwright_layer() -> None:
    apt_line = _index_of(_APT_INSTALL, extra="libatomic1")
    playwright_line = _index_of(_PLAYWRIGHT_WITH_DEPS)

    assert apt_line < playwright_line, (
        "Dockerfile.backend installs libatomic1 after "
        f"`{_PLAYWRIGHT_WITH_DEPS}` (line {apt_line + 1} vs {playwright_line + 1}). "
        "Playwright's --with-deps runs apt from inside its driver Node, so that "
        "Node has to start first; libatomic1 must be installed earlier or the "
        "build fails with exit code 127."
    )
