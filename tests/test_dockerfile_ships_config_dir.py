"""Regression guard: the backend image must ship ``config/``.

`config/llm/*.yaml` holds the LLM router's provider, model, routing, health,
and cache definitions. Every one of those files is optional by design — a
missing `config/` does not raise, it falls back to defaults derived from the
environment variables the platform already reads.

That graceful degradation is what made this expensive to notice. The image
never copied `config/`, so the deployed router ran with no `providers.yaml` at
all: `groq.tokens_per_minute` resolved to 0 ("unmetered"), `_usable_window`
returned the advertised 131,072-token context window, and requests were still
sized past Groq's real 12,000 TPM ceiling — the exact failure fixed in #1172,
still live in production because only the code half of that change reached the
image. Nothing logged an error; the router simply used different numbers than
the repository said it would.

The same Dockerfile builds both the web service and the worker
(`render.yaml`), so this one file covers both.
"""
from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCKERFILE = REPO_ROOT / "Dockerfile.backend"
CONFIG_DIR = REPO_ROOT / "config"

# Config the router reads at runtime. Listed explicitly so that adding a file
# here without shipping it fails loudly rather than degrading to a default.
REQUIRED_CONFIG_FILES = (
    "llm/providers.yaml",
    "llm/models.yaml",
    "llm/routing.yaml",
    "llm/keys.yaml",
    "llm/health.yaml",
    "llm/cache.yaml",
)


def _dockerfile_text() -> str:
    assert DOCKERFILE.exists(), f"{DOCKERFILE} not found"
    return DOCKERFILE.read_text()


def test_backend_image_ships_the_config_dir():
    """Without this COPY the router silently runs on defaults in production."""
    assert re.search(r"^\s*COPY\s+config/\s+config/", _dockerfile_text(), re.MULTILINE), (
        "Dockerfile.backend must `COPY config/ config/` — otherwise "
        "config/llm/*.yaml is absent in the image and the LLM router falls "
        "back to env-derived defaults without logging anything"
    )


def test_the_config_files_the_router_reads_exist_in_the_repo():
    """A shipped directory is worthless if the files moved out of it."""
    missing = [name for name in REQUIRED_CONFIG_FILES
               if not (CONFIG_DIR / name).is_file()]
    assert not missing, f"missing router config file(s): {missing}"


def test_config_is_not_excluded_from_the_build_context():
    """A .dockerignore entry would defeat the COPY without touching it."""
    dockerignore = REPO_ROOT / ".dockerignore"
    if not dockerignore.exists():
        return
    patterns = [
        line.strip() for line in dockerignore.read_text().splitlines()
        if line.strip() and not line.startswith("#")
    ]
    offenders = [p for p in patterns if p.rstrip("/*") in {"config", "config/llm"}]
    assert not offenders, f".dockerignore excludes the router config: {offenders}"


def test_every_local_provider_is_opt_in():
    """A keyless local provider must not join the chain just by existing.

    ``ollama`` was the one local provider in this file with no ``enabled``
    gate. Because it also needs no API key, nothing else could exclude it — so
    the first deploy that shipped this config put it in the ready set of a
    Render host with no Ollama, at the lowest priority number in the file.
    Production confirmed it: "8 provider(s) ready: ... nvidia, ollama, ...".
    """
    providers = (CONFIG_DIR / "llm" / "providers.yaml").read_text()
    blocks = re.split(r"\n  (?=\w)", providers)
    ungated = []
    for block in blocks:
        name = block.split(":", 1)[0].strip()
        if "requires_key: false" not in block:
            continue
        if "enabled:" not in block:
            ungated.append(name)
    assert not ungated, (
        f"keyless provider(s) {ungated} have no `enabled:` gate — they will be "
        "built on any host, reachable or not, and consume routing attempts"
    )


def test_ollama_is_off_and_bounded_by_default():
    """The two properties that made the ungated entry expensive in production."""
    providers = (CONFIG_DIR / "llm" / "providers.yaml").read_text()
    block = re.split(r"\n  (?=\w)", providers.split("  ollama:", 1)[1])[0]

    enabled = re.search(r"enabled:\s*\$\{OLLAMA_ENABLED:-(\w+)\}", block)
    assert enabled and enabled.group(1) == "false", (
        "ollama must default off — it is the local daemon, not a cloud fallback"
    )
    timeout = re.search(r"timeout_sec:\s*\$\{OLLAMA_TIMEOUT_SEC:-(\d+)\}", block)
    assert timeout and int(timeout.group(1)) <= 120, (
        "a 300s timeout against an unreachable host is a five-minute hang per "
        "attempt; OLLAMA_BASE is sync:false and points at a rotating tunnel"
    )


def test_groq_declares_its_per_minute_budget():
    """The ceiling that #1172 added must survive in the file that ships.

    Sized against the advertised context window instead, a 17.6k-token agent
    planning prompt is sent to Groq and refused with a 413, which is how this
    surfaced in the first place.
    """
    providers = (CONFIG_DIR / "llm" / "providers.yaml").read_text()
    groq_block = providers.split("groq:", 1)
    assert len(groq_block) == 2, "no groq provider in config/llm/providers.yaml"
    # Read to the next top-level provider key (two-space indent).
    body = re.split(r"\n  \w[\w-]*:\n", groq_block[1])[0]

    declared = re.search(r"tokens_per_minute:\s*(\S+)", body)
    assert declared, (
        "groq must declare tokens_per_minute — without it the router sizes "
        "requests against the 131k context window and ignores the account's "
        "12k TPM budget"
    )
    # Assert the value, not just the field: `tokens_per_minute: 0` parses fine
    # and means "unmetered", which is the exact bug this guards against. The
    # documented default is 12000, overridable per account.
    value = declared.group(1)
    override = re.fullmatch(r"\$\{GROQ_TOKENS_PER_MINUTE:-(\d+)\}", value)
    budget = int(override.group(1)) if override else int(value)
    assert budget == 12000, (
        f"groq tokens_per_minute is {budget}, expected the documented 12000 "
        "free-tier ceiling (raise it via GROQ_TOKENS_PER_MINUTE after a tier "
        "upgrade rather than editing this default away)"
    )
