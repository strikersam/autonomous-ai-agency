#!/usr/bin/env python3
"""Ask every configured provider what it actually serves.

Model ids in this repo were guessed for months, and the guesses rotted: four
separate outages, each one a hand-edited id that a vendor had retired. The
guessing was not laziness — it was unavoidable. The keys live in CI and Render,
a developer sandbox has no route to the vendors, and so nobody could check.

This closes that loop for *all* providers, not one. It reads
``config/llm/providers.yaml`` (plus the environment-derived defaults in
``packages/llm/config.py``), and for every provider that has a key it asks that
provider's own list-models endpoint what exists. Adding a provider stays a
config entry: this script learns about it automatically.

It is read-only. It never writes to the repo, and it never prints a key —
only whether one is present.

Usage::

    python .github/scripts/probe_catalogues.py                    # every provider
    python .github/scripts/probe_catalogues.py --provider nvidia  # just one
    python .github/scripts/probe_catalogues.py --filter nemotron  # dump raw records
    python .github/scripts/probe_catalogues.py --chat nvidia      # prove it answers
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, REPO_ROOT)

TIMEOUT = 30.0

# How to list models, per adapter kind. This is adapter knowledge — the shape of
# each vendor's API — not a list of models. No model id appears in this file.
#
#   path      appended to the provider's base_url
#   records   key in the JSON response holding the list
#   ident     key on each record holding the model id
_LIST_MODELS = {
    "openai": {"path": "models", "records": "data", "ident": "id"},
    "anthropic": {"path": "v1/models", "records": "data", "ident": "id"},
    "gemini": {"path": "models", "records": "models", "ident": "name"},
    "ollama": {"path": "api/tags", "records": "models", "ident": "name"},
}

# How to send a minimal completion, per adapter kind. Used only by --chat.
_CHAT = {
    "openai": {"path": "chat/completions", "wraps_max_tokens": "max_tokens"},
    "anthropic": {"path": "v1/messages", "wraps_max_tokens": "max_tokens"},
}


def _kind(provider) -> str:
    """The adapter kind, through the platform's own alias table.

    ``providers.yaml`` may say ``kind: lmstudio`` or ``kind: vllm``; both are
    OpenAI-compatible. Re-deriving that mapping here would be a second source of
    truth for exactly the kind of thing this repo keeps getting wrong.
    """
    from packages.llm.providers import resolve_kind

    return resolve_kind(provider.kind)


def _resolve_key(provider) -> str:
    """First non-empty value among the provider's declared key env names."""
    for name in provider.key_env or []:
        value = (os.environ.get(name) or "").strip()
        if value:
            return value
    return ""


def _auth_headers(provider, key: str) -> dict[str, str]:
    """Auth per the provider's declared style. Never logged."""
    style = (provider.auth_style or "bearer").lower()
    if not key or style == "none":
        return {}
    if style == "x-api-key":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    if style == "query":
        return {}  # carried in the URL instead
    return {"Authorization": f"Bearer {key}"}


def _request(provider, path: str, key: str, payload: dict | None = None) -> dict:
    """One request to a provider. Raises on transport or HTTP error."""
    base = (provider.base_url or "").rstrip("/")
    url = f"{base}/{path.lstrip('/')}"
    if (provider.auth_style or "").lower() == "query" and key:
        url = f"{url}?{urllib.parse.urlencode({'key': key})}"

    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Accept": "application/json", **_auth_headers(provider, key)}
    if data:
        headers["Content-Type"] = "application/json"
    headers.update(provider.extra_headers or {})

    req = urllib.request.Request(
        url, data=data, headers=headers, method="POST" if data else "GET"
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def list_models(provider, key: str) -> list[dict]:
    """Raw records from the provider's list-models endpoint."""
    kind = _kind(provider)
    spec = _LIST_MODELS.get(kind)
    if spec is None:
        raise ValueError(f"no list-models route known for kind {kind!r}")
    body = _request(provider, spec["path"], key)
    records = body.get(spec["records"]) or []
    return [record for record in records if isinstance(record, dict)]


def probe_chat(provider, key: str, model_id: str) -> bool:
    """Send the smallest possible completion.

    A model can be listed and still refuse to serve — that is exactly how the
    retired ids kept looking healthy. Listing is not proof; answering is.
    """
    kind = _kind(provider)
    spec = _CHAT.get(kind)
    if spec is None:
        print(f"    (no chat route known for kind {kind!r}; skipped)")
        return True

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "Reply with the word: ok"}],
        spec["wraps_max_tokens"]: 8,
    }
    try:
        body = _request(provider, spec["path"], key, payload)
    except urllib.error.HTTPError as exc:
        print(f"    {model_id}: HTTP {exc.code} — {exc.reason}")
        return False
    except Exception as exc:  # noqa: BLE001 - diagnostic, report anything
        print(f"    {model_id}: {type(exc).__name__}: {exc}")
        return False

    choices = body.get("choices") or body.get("content") or [{}]
    first = choices[0] if isinstance(choices, list) and choices else {}
    text = (first.get("message") or {}).get("content") or first.get("text") or ""
    print(f"    {model_id}: HTTP 200 — {str(text)[:80]!r}")
    return True


_PROBE_TOOL = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Get the current weather for a city.",
        "parameters": {
            "type": "object",
            "properties": {"city": {"type": "string"}},
            "required": ["city"],
        },
    },
}


def probe_tools(provider, key: str, model_id: str) -> bool:
    """Does this model actually emit a tool call?

    ``config/llm/models.yaml`` declares ``supports_tools`` per model, and
    ``packages/llm/registry.py`` filters tool-calling requests on it — giving
    anything undeclared ``supports_tools: false``. So an undeclared model is
    silently excluded from every tool-calling request. Declaring it needs
    evidence, and this is the evidence.
    """
    kind = _kind(provider)
    spec = _CHAT.get(kind)
    if spec is None:
        print(f"    (no chat route known for kind {kind!r}; tools not probed)")
        return False

    payload = {
        "model": model_id,
        "messages": [{"role": "user", "content": "What is the weather in Paris?"}],
        "tools": [_PROBE_TOOL],
        "tool_choice": "auto",
        spec["wraps_max_tokens"]: 128,
    }
    try:
        body = _request(provider, spec["path"], key, payload)
    except Exception as exc:  # noqa: BLE001 - diagnostic, report anything
        print(f"    tools {model_id}: {type(exc).__name__}: {exc}")
        return False

    choices = body.get("choices") or [{}]
    message = (choices[0] or {}).get("message") or {}
    calls = message.get("tool_calls") or []
    named = [((c.get("function") or {}).get("name")) for c in calls if isinstance(c, dict)]
    print(f"    tools {model_id}: {'YES' if named else 'no tool_calls'} {named or ''}")
    return bool(named)


def _providers(only: str | None):
    from packages.llm.config import load_config

    config = load_config()
    items = sorted(config.providers.values(), key=lambda p: (p.priority, p.id))
    if only:
        items = [p for p in items if p.id == only]
        if not items:
            known = ", ".join(sorted(config.providers))
            raise SystemExit(f"unknown provider {only!r}; configured: {known}")
    return items


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", default=None, help="probe only this provider id")
    parser.add_argument(
        "--filter",
        default="",
        help="dump raw records whose id contains this substring",
    )
    parser.add_argument(
        "--chat",
        action="append",
        default=[],
        help="provider id whose default model should be called; repeatable",
    )
    parser.add_argument(
        "--tools",
        action="store_true",
        help="also send a tool-calling request, to establish supports_tools by evidence",
    )
    parser.add_argument(
        "--model",
        action="append",
        default=[],
        help=(
            "specific model id to call on the --chat provider; repeatable. "
            "A catalogue listing is not proof a model serves — this is how you "
            "check a candidate before making it a default."
        ),
    )
    args = parser.parse_args(argv)

    reachable = 0
    unreachable: list[str] = []
    unservable: list[str] = []

    for provider in _providers(args.provider):
        key = _resolve_key(provider)
        # Presence only — never the value, never a prefix of it.
        state = "yes" if key else "no"
        print(f"\n=== {provider.id} ({_kind(provider)}, tier={provider.tier})")
        print(f"    base_url: {provider.base_url or '(unset)'}")
        print(f"    key present: {state}")

        if provider.requires_key and not key:
            print("    skipped — no key configured here")
            continue
        if not provider.base_url:
            print("    skipped — no base_url configured")
            continue

        try:
            records = list_models(provider, key)
        except urllib.error.HTTPError as exc:
            print(f"    list-models failed: HTTP {exc.code} — {exc.reason}")
            unreachable.append(provider.id)
            continue
        except Exception as exc:  # noqa: BLE001 - diagnostic, report anything
            print(f"    list-models failed: {type(exc).__name__}: {exc}")
            unreachable.append(provider.id)
            continue

        reachable += 1
        ident = _LIST_MODELS[_kind(provider)]["ident"]
        ids = [str(r.get(ident) or "") for r in records if r.get(ident)]
        print(f"    models served: {len(ids)}")
        for model_id in ids:
            print(f"      - {model_id}")

        if args.filter:
            matched = [r for r in records if args.filter.lower() in str(r.get(ident, "")).lower()]
            print(f"    raw records matching {args.filter!r}: {len(matched)}")
            for record in matched:
                print(json.dumps(record, indent=2, sort_keys=True))

        if provider.id in args.chat:
            targets = list(args.model) or [provider.default_model or (ids[0] if ids else "")]
            for target in [t for t in targets if t]:
                if not probe_chat(provider, key, target):
                    unservable.append(f"{provider.id}:{target}")
                elif args.tools:
                    probe_tools(provider, key, target)
            if not [t for t in targets if t]:
                print("    --chat: no model to call")

    print(f"\nreachable providers: {reachable}")
    if unreachable:
        print(f"unreachable: {', '.join(unreachable)}")
    if unservable:
        print(f"listed but would not answer: {', '.join(unservable)}")
    # A probe that cannot reach anything must not look like a healthy one.
    if unreachable or unservable or reachable == 0:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
