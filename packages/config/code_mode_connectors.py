"""packages/config/code_mode_connectors.py — the APIs Code Mode programs can read.

A hybrid catalogue, so every API the agency already holds credentials for is
reachable without hand-written YAML, and any other API can be added by config:

* **Built-in connectors** (``BUILTIN_CONNECTORS``) for services this platform
  already integrates with — GitHub (``GH_PAT``) and Render (``RENDER_API_KEY``).
  Each switches on by itself when its credential is configured. Their GET
  operations are declared inline, verified against the vendors' API
  references (2026-10-23): the full GitHub OpenAPI document is several MB,
  too heavy to parse on the 512 MB Render instance, and inline declarations
  cost no network round trip. Endpoints that return secret values (Render
  env vars and secret files) are deliberately absent.
* **Config connectors** from ``config/code_mode_openapi.yaml`` — either a
  ``spec_url`` (an OpenAPI document read host-side) or inline ``operations``.
  An entry with a built-in's name overrides it; ``enabled: false`` turns one off.

Tokens are read here, at call time, from settings or from the environment
variable an entry names (rule 5); they never reach model-written code. A
built-in's server credential follows the same multi-tenant guard as
``services/workflow_orchestrator.py:_resolve_push_token``: a user's own token
wins (GitHub), and the server token serves a user-initiated run only when
``ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS`` is on.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-proxy")

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "code_mode_openapi.yaml"
_NAME_RE = re.compile(r"^[a-z][a-z0-9_]{0,31}$")
_ENV_RE = re.compile(r"^[A-Z][A-Z0-9_]{0,63}$")
_OP_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{0,63}$")
_PARAM_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,63}$")
# Non-secret request headers a connector may set; Authorization is always host-built.
SAFE_HEADERS = frozenset({"accept", "x-github-api-version", "user-agent"})


@dataclass(frozen=True)
class OpenApiConnectorSpec:
    """One API: where it lives, how it authenticates, and (optionally) its GET operations."""

    name: str
    description: str
    spec_url: str
    base_url: str
    auth_env: str = ""
    # Built-ins name a settings attribute instead of an env var.
    token_setting: str = ""
    # Inline OpenAPI ``paths`` (GET only). When set, spec_url is not fetched.
    operations: dict[str, Any] = field(default_factory=dict)
    headers: tuple[tuple[str, str], ...] = ()
    builtin: bool = False
    # The per-user token this API accepts in place of the server's (only "github").
    user_token_kind: str = ""


def _q(*names: str) -> list[dict[str, Any]]:
    return [{"name": n, "in": "query"} for n in names]


def _p(*names: str) -> list[dict[str, Any]]:
    return [{"name": n, "in": "path", "required": True} for n in names]


def _get(op_id: str, summary: str, params: list[dict[str, Any]]) -> dict[str, Any]:
    return {"get": {"operationId": op_id, "summary": summary, "parameters": params}}


_PAGE = ("per_page", "page")
_GITHUB_PATHS: dict[str, Any] = {
    "/repos/{owner}/{repo}": _get("get-repo", "Get a repository", _p("owner", "repo")),
    "/repos/{owner}/{repo}/issues": _get(
        "list-repo-issues", "List repository issues (includes pull requests)",
        _p("owner", "repo") + _q("state", "labels", "sort", "direction", "since", *_PAGE)),
    "/repos/{owner}/{repo}/issues/{issue_number}": _get(
        "get-issue", "Get an issue", _p("owner", "repo", "issue_number")),
    "/repos/{owner}/{repo}/pulls": _get(
        "list-pulls", "List pull requests", _p("owner", "repo") + _q("state", "head", "base", "sort", "direction", *_PAGE)),
    "/repos/{owner}/{repo}/pulls/{pull_number}": _get(
        "get-pull", "Get a pull request", _p("owner", "repo", "pull_number")),
    "/repos/{owner}/{repo}/actions/runs": _get(
        "list-workflow-runs", "List GitHub Actions workflow runs for a repository",
        _p("owner", "repo") + _q("branch", "event", "status", "actor", *_PAGE)),
    "/repos/{owner}/{repo}/commits": _get(
        "list-commits", "List commits", _p("owner", "repo") + _q("sha", "path", "since", "until", *_PAGE)),
    "/search/issues": _get("search-issues", "Search issues and pull requests", _q("q", "sort", "order", *_PAGE)),
}
_RENDER_PATHS: dict[str, Any] = {
    "/services": _get("list-services", "List services", _q("name", "type", "limit", "cursor")),
    "/services/{serviceId}": _get("retrieve-service", "Retrieve a service", _p("serviceId")),
    "/services/{serviceId}/deploys": _get(
        "list-deploys", "List deploys of a service", _p("serviceId") + _q("limit", "cursor")),
    "/services/{serviceId}/deploys/{deployId}": _get(
        "retrieve-deploy", "Retrieve a deploy", _p("serviceId", "deployId")),
    "/services/{serviceId}/events": _get(
        "list-events", "List recent events of a service", _p("serviceId") + _q("limit", "cursor")),
}

BUILTIN_CONNECTORS: tuple[OpenApiConnectorSpec, ...] = (
    OpenApiConnectorSpec(
        name="github", description="GitHub REST API (repos, issues, pull requests, Actions runs, commits, search)",
        spec_url="", base_url="https://api.github.com",
        token_setting="gh_pat",  # nosec B106 - names a settings attribute, not a secret
        operations=_GITHUB_PATHS, headers=(("Accept", "application/vnd.github+json"),), builtin=True,
        user_token_kind="github",
    ),
    OpenApiConnectorSpec(
        name="render", description="Render API (services, deploys, service events)",
        spec_url="", base_url="https://api.render.com/v1",
        token_setting="render_api_key",  # nosec B106 - names a settings attribute, not a secret
        operations=_RENDER_PATHS, headers=(("Accept", "application/json"),), builtin=True,
    ),
)


def _valid_operations(raw: Any, name: str) -> dict[str, Any] | None:
    """Inline operations: GET only, sane ids and parameter names; None when invalid."""
    if not isinstance(raw, dict):
        return None
    out: dict[str, Any] = {}
    for path, item in raw.items():
        get = item.get("get") if isinstance(item, dict) else None
        if not (isinstance(path, str) and path.startswith("/") and isinstance(get, dict)):
            log.warning("code mode: connector %s: skipping operation %r (GET with a /path only)", name, path)
            continue
        op_id = str(get.get("operationId") or "")
        params = get.get("parameters") or []
        if not isinstance(params, list) or not _OP_ID_RE.match(op_id) or not all(
            isinstance(p, dict) and _PARAM_RE.match(str(p.get("name", ""))) and p.get("in") in ("path", "query")
            for p in params
        ):
            log.warning("code mode: connector %s: skipping operation %r (bad id or parameters)", name, path)
            continue
        out[path] = {"get": {"operationId": op_id, "summary": str(get.get("summary") or "")[:200], "parameters": params}}
    return out or None


def _headers(raw: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw, dict):
        return ()
    return tuple((str(k), str(v)) for k, v in raw.items() if str(k).lower() in SAFE_HEADERS)


def _parse(raw: object) -> OpenApiConnectorSpec | None:
    if not isinstance(raw, dict):
        return None
    name = str(raw.get("name") or "")
    spec_url = str(raw.get("spec_url") or "")
    base_url = str(raw.get("base_url") or "").rstrip("/")
    auth_env = str(raw.get("auth_env") or "")
    operations = _valid_operations(raw.get("operations"), name) if raw.get("operations") else None
    if not _NAME_RE.match(name) or not base_url.startswith("https://"):
        log.warning("code mode: skipping invalid OpenAPI connector entry %r", name)
        return None
    if operations is None and not spec_url.startswith("https://"):
        log.warning("code mode: connector %s needs an https spec_url or inline operations; skipped", name)
        return None
    if auth_env and not _ENV_RE.match(auth_env):
        log.warning("code mode: connector %s has an invalid auth_env name; skipped", name)
        return None
    # An override of a built-in still accepts the run's own token for that API.
    user_kind = next((b.user_token_kind for b in BUILTIN_CONNECTORS if b.name == name), "")
    return OpenApiConnectorSpec(
        name, str(raw.get("description") or "")[:200], spec_url, base_url, auth_env,
        operations=operations or {}, headers=_headers(raw.get("headers")), user_token_kind=user_kind,
    )


def _load_yaml(path: Path) -> list[Any]:
    try:
        import yaml

        data = yaml.safe_load(path.read_text()) or {}
    except Exception as exc:  # noqa: BLE001 - a broken file must not break the agent
        log.warning("code mode: could not read %s: %s", path, exc)
        return []
    entries = data.get("connectors") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        if entries is not None or not isinstance(data, dict):
            log.warning("code mode: %s must be a mapping with a `connectors` list; ignored", path)
        return []
    return entries


def openapi_connectors(
    path: Path | None = None, *, include_builtins: bool = True,
    user_id: str | None = None, user_token: str | None = None,
) -> list[OpenApiConnectorSpec]:
    """Built-ins with a token usable by this run, then config entries (which override by name).

    ``user_id`` None is an internal system run; pass the run's user and token otherwise.
    """
    entries = _load_yaml(path or CONFIG_PATH)
    disabled = {str(e.get("name")) for e in entries if isinstance(e, dict) and e.get("enabled") is False}
    by_name: dict[str, OpenApiConnectorSpec] = {}
    if include_builtins:
        for spec in BUILTIN_CONNECTORS:
            if spec.name not in disabled and connector_token(spec, user_id=user_id, user_token=user_token):
                by_name[spec.name] = spec
    for raw in entries:
        if isinstance(raw, dict) and raw.get("enabled") is False:
            continue
        try:
            spec = _parse(raw)
        except Exception as exc:  # noqa: BLE001 - one malformed entry must not break the tool prompt
            log.warning("code mode: skipping malformed connector entry: %s", exc)
            continue
        if spec is None:
            continue
        # A user run without the opt-in gets an authenticated connector only with its own token.
        needs_token = spec.auth_env or spec.user_token_kind
        if needs_token and not server_token_allowed(user_id) and not connector_token(
            spec, user_id=user_id, user_token=user_token,
        ):
            by_name.pop(spec.name, None)
            continue
        by_name[spec.name] = spec
    return list(by_name.values())


def server_token_allowed(user_id: str | None) -> bool:
    """Whether a server-held credential may serve this run (mirrors ``_resolve_push_token``)."""
    if user_id is None:
        return True
    flag = os.environ.get("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", "")
    return flag.strip().lower() in ("1", "true", "yes", "on")


def _server_tokens() -> set[str]:
    """Every GitHub credential the server itself holds."""
    try:
        from packages.config import settings

        held = {str(getattr(settings, "gh_pat", "") or "")}
    except Exception:  # noqa: BLE001 - no settings: only the environment counts
        held = set()
    held |= {os.environ.get(name, "") for name in ("GH_PAT", "GH_TOKEN", "GITHUB_TOKEN")}
    return {t for t in held if t}


def connector_token(
    spec: OpenApiConnectorSpec, *, user_id: str | None = None, user_token: str | None = None,
) -> str | None:
    """The bearer token for *spec* on this run, read at call time so a rotated secret applies at once."""
    if spec.user_token_kind and user_token:
        # Some callers hand a runner the server's own token as its "user" token
        # (proxy.py, telegram_bot.py); that must not slip past the guard.
        if server_token_allowed(user_id) or user_token not in _server_tokens():
            return user_token
    # Every token this module can read is the server's, built-in or `auth_env`.
    if (spec.builtin or spec.auth_env) and not server_token_allowed(user_id):
        return None
    if spec.token_setting:
        try:
            from packages.config import settings

            return str(getattr(settings, spec.token_setting, "") or "") or None
        except Exception:  # noqa: BLE001 - no settings, no token
            return None
    if not spec.auth_env:
        return None
    return os.environ.get(spec.auth_env) or None
