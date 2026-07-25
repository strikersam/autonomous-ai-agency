"""Guard against the recurring "works in CI, missing in prod" dependency drift.

``Dockerfile.backend`` — the image Render builds — installs
``backend/requirements.txt`` and NEVER the root ``requirements.txt`` that CI
installs. Any package imported by shipped code but listed only in the root file
is therefore absent in production, where it fails as a *silent degradation*
rather than an import error, because nearly every call site guards the import.

This has now happened four times:

* the website-scanner deps (``curl_cffi`` / ``dnspython``) → prod returned
  "No systems detected" while CI found systems;
* ``langfuse``           → no traces emitted despite the keys being set;
* ``e2b-code-interpreter`` → Providers screen stuck on
  "e2b OFFLINE — SDK not installed";
* ``anthropic``          → the loop's native Messages-API path silently
  fell through to an OpenAI-compatible call that 400s.

The parity list below is deliberately explicit rather than derived from an
import scan: it names the packages whose absence is known to break a production
feature, and each entry cites the call site that needs it.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
_BACKEND_REQS = _REPO_ROOT / "backend" / "requirements.txt"
_DOCKERFILE = _REPO_ROOT / "Dockerfile.backend"

# package name → the shipped module that imports it.
_REQUIRED_IN_PRODUCTION: dict[str, str] = {
    "anthropic": "agent/loop.py — native Anthropic Messages API path",
    "e2b-code-interpreter": "services/e2b_config.py — is_e2b_sdk_importable()",
    "pyyaml": "packages/ai/brain_config.py — config/models.yaml catalog loader",
    "psutil": "handlers/v3_models.py — GET /stats system statistics",
    "langfuse": "langfuse_obs.py — chat + agent run tracing",
    "curl_cffi": "services/scanner.py — Chrome TLS impersonation fetch",
    "dnspython": "services/scanner.py — MX/NS/TXT/CNAME analysis",
    "playwright": "services/scanner.py — headless render pass",
}


def _declared_packages(requirements: Path) -> set[str]:
    """Return the normalised distribution names declared in *requirements*."""
    names: set[str] = set()
    for raw in requirements.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line or line.startswith("-"):
            continue
        name = re.split(r"[<>=!\[;]", line, maxsplit=1)[0].strip()
        if name:
            # PEP 503 normalisation: "PyYAML" and "pyyaml" are the same dist,
            # as are "e2b-code-interpreter" and "e2b_code_interpreter".
            names.add(re.sub(r"[-_.]+", "-", name).lower())
    return names


@pytest.mark.parametrize(
    ("package", "call_site"),
    sorted(_REQUIRED_IN_PRODUCTION.items()),
)
def test_backend_requirements_declares_runtime_package(
    package: str, call_site: str
) -> None:
    declared = _declared_packages(_BACKEND_REQS)
    normalised = re.sub(r"[-_.]+", "-", package).lower()

    assert normalised in declared, (
        f"{package!r} is imported by shipped code ({call_site}) but is not in "
        f"backend/requirements.txt. Dockerfile.backend installs ONLY that file, "
        f"so the production image will not have it and the feature degrades "
        f"silently. Add it there (the root requirements.txt is CI-only)."
    )


def test_dockerfile_still_installs_backend_requirements_only() -> None:
    """If the Dockerfile ever installs the root file, this guard can relax.

    Until then the two files are genuinely different install sets and the
    parity list above is load-bearing.
    """
    dockerfile = _DOCKERFILE.read_text(encoding="utf-8")

    assert "pip install --no-cache-dir -r backend/requirements.txt" in dockerfile, (
        "Dockerfile.backend no longer installs backend/requirements.txt — "
        "update this test and the parity list to match the new install set."
    )
    installs_root = re.search(
        r"^\s*RUN\s+pip install[^\n]*\s-r\s+requirements\.txt",
        dockerfile,
        re.MULTILINE,
    )
    assert installs_root is None, (
        "Dockerfile.backend now installs the root requirements.txt too. That is "
        "a fine fix for this whole bug class — delete this test and the parity "
        "list, since the two files no longer diverge."
    )
