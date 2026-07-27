"""Regression guard: the backend image must ship every root-level Python module
that production code imports (Autonomy Charter / issue #656 follow-up).

`Dockerfile.backend` historically copied root-level modules one-by-one, which
silently dropped newly-added modules from the image and caused
"works locally, ModuleNotFoundError in prod" outages — most visibly
`brain_policy.py` ("No module named brain_policy" crashed the agent brain so every
CEO/agent task blocked "after 10 failed dispatch attempts"), and
`telegram_service.py` (the Telegram approval gate + self-heal escalation never
fired). This test fails if the Dockerfile stops shipping all root modules.

V2.0 Modernization note: `brain_policy` and `social_auth` moved to `packages/`
(Phase 2 + 3). They are no longer root modules — the test now also verifies
`COPY packages/ packages/` is present so the moved modules ship too.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile.backend"

# Root-level modules that production (web + worker) imports and therefore MUST be
# present in the image. Keep this list as documentation of the critical surface;
# the wholesale `COPY *.py` satisfies all of them at once.
#
# V2.0 Modernization: brain_policy + social_auth moved to packages/ (Phase 2 + 3).
# They're no longer root modules — covered by test_backend_image_ships_packages_dir.
CRITICAL_ROOT_MODULES = {
    "telegram_service",   # G1 approval gate + G2 self-heal escalation
    "chat_handlers",      # workflow/ide_bridge
    "audit",              # audit log
    "worker_main",        # the worker service start command: `python worker_main.py`
}


def _dockerfile_text() -> str:
    assert DOCKERFILE.exists(), f"{DOCKERFILE} not found"
    return DOCKERFILE.read_text()


def _ships_all_root_modules(text: str) -> bool:
    """True when the Dockerfile copies root .py modules wholesale (`COPY *.py ...`)."""
    return re.search(r"^\s*COPY\s+\*\.py\b", text, re.MULTILINE) is not None


def test_backend_image_ships_all_root_modules():
    text = _dockerfile_text()
    if _ships_all_root_modules(text):
        return  # wholesale copy guarantees every current + future root module
    # Otherwise every critical module must be copied explicitly.
    missing = [
        m for m in CRITICAL_ROOT_MODULES
        if not re.search(rf"^\s*COPY\s+{re.escape(m)}\.py\b", text, re.MULTILINE)
    ]
    assert not missing, (
        "Dockerfile.backend does not ship these root modules that production "
        f"imports: {sorted(missing)}. Add `COPY *.py ./` (preferred) or copy each "
        "explicitly."
    )


def test_worker_start_command_module_is_shiped():
    """The worker's `python worker_main.py` start command needs worker_main.py."""
    text = _dockerfile_text()
    assert _ships_all_root_modules(text) or re.search(
        r"^\s*COPY\s+worker_main\.py\b", text, re.MULTILINE
    ), "worker_main.py (the worker start command) is not copied into the image"


def test_backend_image_ships_packages_dir():
    """V2.0 Modernization: the image must ship `packages/` (provider_router,
    brain_policy, admin_auth, social_auth, rbac, scheduler, storage, etc.
    all moved there in Phases 2-5)."""
    text = _dockerfile_text()
    assert re.search(r"^\s*COPY\s+packages/\s+packages/", text, re.MULTILINE), (
        "Dockerfile.backend does not `COPY packages/ packages/` — the V2.0 "
        "moved modules (provider_router, brain_policy, admin_auth, scheduler, "
        "storage, etc.) will be missing from the image."
    )


# ── /api/health reports build identity (deploy verifiability) ────────────────
#
# A deploy could not be verified because /api/health looked identical before and
# after one: a poll run seconds after triggering happily passed against the old
# instance Render was still serving, so a failed build reported a green job.

def test_deployed_commit_prefers_render_then_falls_back(monkeypatch) -> None:
    import version

    for name in version._COMMIT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert version.deployed_commit() is None

    monkeypatch.setenv("SOURCE_COMMIT", "from-source")
    assert version.deployed_commit() == "from-source"
    monkeypatch.setenv("GIT_COMMIT", "from-git")
    assert version.deployed_commit() == "from-git"
    monkeypatch.setenv("RENDER_GIT_COMMIT", "from-render")
    assert version.deployed_commit() == "from-render"


def test_deployed_commit_ignores_blank_values(monkeypatch) -> None:
    """An env var set to empty string means unset, not a commit named ''."""
    import version

    for name in version._COMMIT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("RENDER_GIT_COMMIT", "   ")
    assert version.deployed_commit() is None


def test_health_endpoint_reports_version_and_commit(client, monkeypatch) -> None:
    monkeypatch.setenv("RENDER_GIT_COMMIT", "abc123def456")
    body = client.get("/api/health").json()
    assert body["commit"] == "abc123def456"
    assert body["version"]
    # The pre-existing contract must not regress.
    assert "status" in body and "storage" in body and "mongo" in body


def test_health_endpoint_commit_is_null_when_host_stamps_nothing(
    client, monkeypatch
) -> None:
    """Unknown must read as unknown — a deploy check treats None as
    'unverifiable' and must not mistake it for a mismatch."""
    import version

    for name in version._COMMIT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)
    assert client.get("/api/health").json()["commit"] is None
