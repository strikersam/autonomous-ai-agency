"""packages/config/code_mode_connectors.py — OpenAPI connectors for Code Mode.

Reads ``config/code_mode_openapi.yaml`` and, for a connector that names an
``auth_env``, that environment variable. This is the config module that owns
those reads (rule 5); ``agent/code_mode_connectors.py`` only asks it for a
token at request time and never hands the token to model-written code.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger("qwen-proxy")

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "code_mode_openapi.yaml"
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")


@dataclass(frozen=True)
class OpenApiConnectorSpec:
    """One OpenAPI connector as declared in the YAML file."""

    name: str
    description: str
    spec_url: str
    base_url: str
    auth_env: str = ""


def _parse(raw: object) -> OpenApiConnectorSpec | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "")
    spec_url = str(raw.get("spec_url") or "")
    base_url = str(raw.get("base_url") or "").rstrip("/")
    auth_env = str(raw.get("auth_env") or "")
    if not _NAME_RE.match(name) or not spec_url.startswith("https://") or not base_url.startswith("https://"):
        log.warning("code mode: skipping invalid OpenAPI connector entry %r", name)
        return None
    if auth_env and not _ENV_RE.match(auth_env):
        log.warning("code mode: connector %s has an invalid auth_env name; skipped", name)
        return None
    return OpenApiConnectorSpec(name, str(raw.get("description") or "")[:200], spec_url, base_url, auth_env)


def openapi_connectors(path: Path | None = None) -> list[OpenApiConnectorSpec]:
    """Connectors declared in the YAML file; an unreadable file declares none."""
    try:
        import yaml

        data = yaml.safe_load((path or CONFIG_PATH).read_text()) or {}
    except Exception as exc:  # noqa: BLE001 - a broken file must not break the agent
        log.warning("code mode: could not read %s: %s", path or CONFIG_PATH, exc)
        return []
    specs = [_parse(item) for item in (data.get("connectors") or [])]
    return [s for s in specs if s is not None]


def connector_token(spec: OpenApiConnectorSpec) -> str | None:
    """The bearer token for *spec*, read at call time so a rotated secret applies at once."""
    if not spec.auth_env:
        return None
    return os.environ.get(spec.auth_env) or None
