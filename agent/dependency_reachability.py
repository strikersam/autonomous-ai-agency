"""agent/dependency_reachability.py — is a vulnerable dependency actually used?

Adapted from the NVIDIA AI Blueprint for Vulnerability Analysis, whose core
point is that a scanner hit alone does not show the affected code is present
or reachable. The blueprint answers that with an LLM agent over the container
filesystem; this is the cheap, deterministic first cut of the same question:
does any first-party module import the package?

A package with no first-party import is most likely transitive. That lowers
priority; it never dismisses the finding, because a transitive dependency can
still be reached through the package that pulls it in.
"""
from __future__ import annotations

import functools
import logging
import re
from importlib import metadata
from pathlib import Path

log = logging.getLogger("qwen-proxy")

_EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
_IMPORT_RE = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_]*)", re.MULTILINE)
# Distribution names whose import name differs, for when the package is not
# installed locally and importlib.metadata cannot say.
_KNOWN_ALIASES: dict[str, set[str]] = {
    "pyyaml": {"yaml"},
    "beautifulsoup4": {"bs4"},
    "python-jose": {"jose"},
    "python-dotenv": {"dotenv"},
    "python-multipart": {"multipart"},
    "pillow": {"PIL"},
    "scikit-learn": {"sklearn"},
    "pyjwt": {"jwt"},
    "protobuf": {"google"},
    "opencv-python": {"cv2"},
}


def _normalize(dist: str) -> str:
    return re.sub(r"[-_.]+", "-", dist).lower()


def first_party_imports(root: Path) -> set[str]:
    """Top-level module names imported anywhere in *root*'s Python files."""
    names: set[str] = set()
    for path in root.rglob("*.py"):
        if any(part in _EXCLUDE_DIRS for part in path.relative_to(root).parts):
            continue
        try:
            names.update(_IMPORT_RE.findall(path.read_text(encoding="utf-8", errors="ignore")))
        except OSError:
            continue
    return names


@functools.lru_cache(maxsize=1)
def _installed_modules() -> dict[str, tuple[str, ...]]:
    """Normalised distribution name -> the top-level modules it installs."""
    out: dict[str, list[str]] = {}
    for module, dists in metadata.packages_distributions().items():
        for d in dists:
            out.setdefault(_normalize(d), []).append(module)
    return {k: tuple(v) for k, v in out.items()}


def import_names(dist: str) -> set[str]:
    """Import names a distribution provides (installed metadata, aliases, or its own name)."""
    key = _normalize(dist)
    names = set(_KNOWN_ALIASES.get(key, ()))
    try:
        names.update(_installed_modules().get(key, ()))
    except Exception as exc:  # noqa: BLE001 - metadata is a best-effort hint
        log.debug("reachability: package metadata unavailable: %s", exc)
    names.add(key.replace("-", "_"))
    return names


def is_directly_imported(dist: str, imports: set[str]) -> bool:
    """True when first-party code imports any module *dist* provides."""
    wanted = {n.lower() for n in import_names(dist)}
    return any(i.lower() in wanted for i in imports)
