"""Regression guard: the backend image must ship every root-level Python module
that production code imports (Autonomy Charter / issue #656 follow-up).

`Dockerfile.backend` historically copied root-level modules one-by-one, which
silently dropped newly-added modules from the image and caused
"works locally, ModuleNotFoundError in prod" outages — most visibly
`brain_policy.py` ("No module named brain_policy" crashed the agent brain so every
CEO/agent task blocked "after 10 failed dispatch attempts"), and
`telegram_service.py` (the Telegram approval gate + self-heal escalation never
fired). This test fails if the Dockerfile stops shipping all root modules.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile.backend"

# Root-level modules that production (web + worker) imports and therefore MUST be
# present in the image. Keep this list as documentation of the critical surface;
# the wholesale `COPY *.py` satisfies all of them at once.
CRITICAL_ROOT_MODULES = {
    "brain_policy",       # agent/loop.py + services/workflow_orchestrator.py
    "telegram_service",   # G1 approval gate + G2 self-heal escalation
    "social_auth",        # OAuth login
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
        "explicitly. This is the bug class behind 'No module named brain_policy'."
    )


def test_worker_start_command_module_is_shipped():
    """The worker's `python worker_main.py` start command needs worker_main.py."""
    text = _dockerfile_text()
    assert _ships_all_root_modules(text) or re.search(
        r"^\s*COPY\s+worker_main\.py\b", text, re.MULTILINE
    ), "worker_main.py (the worker start command) is not copied into the image"
