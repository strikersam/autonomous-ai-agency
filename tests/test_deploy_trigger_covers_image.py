"""Regression guard: the Render deploy trigger must cover everything the image ships.

Sibling of ``test_dockerfile_ships_root_modules.py``. That test asks "is the
module *in* the image?"; this one asks the question that bit us next: "does
changing it actually *deploy*?"

``.github/workflows/deploy-backend.yml`` fires the Render deploy hook on a
``paths:`` filter. That filter had drifted away from ``Dockerfile.backend``'s
``COPY`` list in two ways:

* Four directories the image ships were missing entirely — ``packages/`` (the
  whole AI layer: router, brain config, providers, traffic director),
  ``loops/``, ``voice/`` and ``.claude/``. A change confined to any of them
  produced no deploy at all, so the fix would sit on master looking shipped.
* The Dockerfile moved to ``COPY *.py ./`` precisely because copying root
  modules one-by-one kept dropping new ones, but this filter still listed 11
  root modules by name — leaving 24 shipped modules (``proxy.py``,
  ``chat_handlers.py``, ``telegram_bot.py``, ``app_settings.py`` …) unable to
  trigger a deploy on their own.

Both are silent failures: nothing errors, the change simply never reaches
production. This test fails if the two files drift apart again.
"""
from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile.backend"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-backend.yml"

# Build stages copy into the image but are not deploy inputs in their own right
# (the frontend stage's sources are covered by the `frontend/**` entry).
_IGNORED_COPY_SOURCES = {"--from=frontend-build"}


def _image_copy_sources() -> set[str]:
    """Top-level paths ``Dockerfile.backend`` copies into the runtime image."""
    text = DOCKERFILE.read_text()
    sources: set[str] = set()
    for match in re.finditer(r"^COPY\s+(?!--from)(\S+)\s", text, re.MULTILINE):
        src = match.group(1)
        if src in _IGNORED_COPY_SOURCES:
            continue
        if src.endswith("/"):
            sources.add(src.rstrip("/"))
        elif src == "*.py":
            sources.add("*.py")
        elif "/" in src:
            sources.add(src.split("/")[0])
        else:
            sources.add(src)
    return sources


def _workflow_trigger_paths() -> set[str]:
    """Top-level path prefixes in the deploy workflow's push ``paths:`` filter."""
    # PyYAML parses the bare `on:` key as the boolean True.
    spec = yaml.safe_load(WORKFLOW.read_text())
    triggers = spec.get("on") or spec.get(True)
    raw = triggers["push"]["paths"]
    out: set[str] = set()
    for entry in raw:
        head = entry.split("/")[0]
        out.add(head.replace("**", "") or entry)
    return out


def test_every_directory_in_the_image_can_trigger_a_deploy() -> None:
    copied = _image_copy_sources()
    triggers = _workflow_trigger_paths()
    missing = sorted(
        src for src in copied if src != "*.py" and src not in triggers
    )
    assert not missing, (
        "Dockerfile.backend ships these into the image but a change to them "
        f"does not trigger a Render deploy: {missing}. Add them to the "
        "`paths:` filter in .github/workflows/deploy-backend.yml."
    )


def test_root_modules_trigger_a_deploy_wholesale() -> None:
    """The filter must take root modules wholesale, matching `COPY *.py ./`.

    Listing them individually is the exact drift this guard exists to stop: the
    Dockerfile abandoned that approach after it repeatedly dropped new modules,
    and the workflow kept doing it for another 24 files.
    """
    triggers = _workflow_trigger_paths()
    assert "*.py" in triggers, (
        "deploy-backend.yml must include '*.py' in its paths filter so every "
        "root module shipped by `COPY *.py ./` can trigger a deploy."
    )


def test_packages_dir_specifically_triggers_a_deploy() -> None:
    """`packages/` holds the AI layer — the most deploy-sensitive code there is."""
    assert "packages" in _workflow_trigger_paths(), (
        "A change to packages/ (router, brain config, providers) must deploy."
    )


def test_deploy_verification_cannot_pass_silently_on_failure() -> None:
    """The health step must be able to fail.

    It previously polled for any 200 starting 20s after triggering the deploy —
    while Render still served the *old* instance — and ran `exit 0` on timeout.
    A failed Render build therefore reported a green deploy job. The step must
    compare the live commit against the pushed SHA and exit non-zero when the
    new build never arrives.
    """
    text = WORKFLOW.read_text()
    assert "github.sha" in text, "the deploy check must know which commit it expects"
    assert re.search(r"^\s*exit 1\b", text, re.MULTILINE), (
        "the deploy verification step must be able to fail the job"
    )
    assert ".commit" in text, (
        "the deploy check must read the live build commit from /api/health, "
        "otherwise it cannot tell the new instance from the old one"
    )
