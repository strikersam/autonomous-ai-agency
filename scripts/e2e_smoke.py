#!/usr/bin/env python3
"""Real-API end-to-end smoke test for a *running* LLM Relay instance.

Unlike the unit/integration suite, this makes real HTTP calls to a live relay
and checks that core features actually work end to end. It is intended to run:
  - in CI via .github/workflows/e2e.yml against a deployed instance
    (URL + key supplied by the GitHub `test` environment), or
  - locally:  RELAY_BASE_URL=http://localhost:8000 RELAY_API_KEY=... python scripts/e2e_smoke.py

Skips cleanly (exit 0) when RELAY_BASE_URL is unset, so it never breaks a run
where no environment is configured. Exit code 1 if any checked feature fails.
Pure standard library.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error

BASE = os.environ.get("RELAY_BASE_URL", "").rstrip("/")
KEY = os.environ.get("RELAY_API_KEY", "")
TIMEOUT = float(os.environ.get("RELAY_E2E_TIMEOUT", "30"))


def _req(method: str, path: str, body: dict | None = None) -> tuple[int, dict | str]:
    url = BASE + path
    data = json.dumps(body).encode() if body is not None else None
    headers = {"Content-Type": "application/json"}
    if KEY:
        headers["Authorization"] = f"Bearer {KEY}"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
            raw = r.read().decode("utf-8", "replace")
            try:
                return r.status, json.loads(raw)
            except ValueError:
                return r.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:  # noqa: BLE001
        return 0, f"{type(e).__name__}: {e}"


CHECKS = []


def check(name):
    def deco(fn):
        CHECKS.append((name, fn))
        return fn
    return deco


@check("health endpoint responds")
def _health():
    for p in ("/health", "/healthz", "/api/health"):
        code, _ = _req("GET", p)
        if code == 200:
            return True, p
    return False, "no health endpoint returned 200"


@check("models list is non-empty")
def _models():
    code, body = _req("GET", "/v1/models")
    if code != 200:
        return False, f"HTTP {code}: {str(body)[:120]}"
    data = body.get("data") if isinstance(body, dict) else None
    return (bool(data), f"{len(data) if data else 0} models")


@check("chat completion returns content")
def _chat():
    code, body = _req("POST", "/v1/chat/completions", {
        "model": os.environ.get("RELAY_E2E_MODEL", "auto"),
        "messages": [{"role": "user", "content": "Reply with the single word: pong"}],
        "max_tokens": 16,
    })
    if code != 200:
        return False, f"HTTP {code}: {str(body)[:160]}"
    try:
        txt = body["choices"][0]["message"]["content"]
        return bool(txt), repr(txt[:60])
    except Exception:  # noqa: BLE001
        return False, f"unexpected shape: {str(body)[:160]}"


def main() -> int:
    if not BASE:
        print("RELAY_BASE_URL not set — skipping real-API E2E smoke (exit 0).")
        return 0
    print(f"E2E smoke against {BASE}\n" + "=" * 60)
    failures = 0
    for name, fn in CHECKS:
        try:
            ok, detail = fn()
        except Exception as e:  # noqa: BLE001
            ok, detail = False, f"raised {type(e).__name__}: {e}"
        print(f"  [{'PASS' if ok else 'FAIL'}] {name} — {detail}")
        if not ok:
            failures += 1
    print("=" * 60)
    print(f"{len(CHECKS)} checks, {failures} failed")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
