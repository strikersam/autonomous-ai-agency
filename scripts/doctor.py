#!/usr/bin/env python3
"""Agency Core doctor — fast environment & CI-parity diagnostics.

Answers the operator questions "why didn't this run?" and "why did CI fail but
local pass?" by checking the things that actually differ between a laptop and the
CI runner: Python version, required env, MongoDB/Ollama reachability, git state,
and whether core deps import.

Pure standard library. Never raises; prints a readable report. Exit code 0 unless
--strict is passed and a hard check FAILs.

Usage:
    python scripts/doctor.py            # report, always exit 0
    python scripts/doctor.py --strict   # exit 1 if any FAIL
"""
from __future__ import annotations

import argparse
import os
import socket
import shutil
import subprocess
import sys
import urllib.request
from typing import Literal, NamedTuple

Status = Literal["PASS", "WARN", "FAIL"]


class Check(NamedTuple):
    name: str
    status: Status
    detail: str


def _ok(name: str, detail: str) -> Check:
    return Check(name, "PASS", detail)


def _warn(name: str, detail: str) -> Check:
    return Check(name, "WARN", detail)


def _fail(name: str, detail: str) -> Check:
    return Check(name, "FAIL", detail)


def check_python() -> Check:
    v = sys.version_info
    cur = f"{v.major}.{v.minor}.{v.micro}"
    # CI runs on 3.13; mismatches are a top cause of "local passes, CI fails".
    if (v.major, v.minor) >= (3, 13):
        return _ok("python", f"{cur} (matches CI target 3.13)")
    return _warn("python", f"{cur} — CI uses 3.13; behaviour may differ")


def check_env() -> Check:
    have_api = bool(os.environ.get("API_KEYS"))
    have_admin = bool(os.environ.get("ADMIN_PASSWORD") or os.environ.get("SECRET_KEY"))
    missing = []
    if not have_api:
        missing.append("API_KEYS")
    if not have_admin:
        missing.append("ADMIN_PASSWORD/SECRET_KEY")
    if not missing:
        return _ok("env", "API_KEYS + admin secret present")
    return _warn("env", f"missing {', '.join(missing)} — backend runs in limited mode")


def _tcp_open(host: str, port: int, timeout: float = 2.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _parse_host_port(url: str, default_host: str, default_port: int) -> tuple[str, int]:
    rest = url.split("://", 1)[-1]
    hostpart = rest.split("/", 1)[0].split("@")[-1]
    if ":" in hostpart:
        host, _, p = hostpart.partition(":")
        try:
            return host or default_host, int(p)
        except ValueError:
            return host or default_host, default_port
    return hostpart or default_host, default_port


def check_mongo() -> Check:
    url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    host, port = _parse_host_port(url, "localhost", 27017)
    if _tcp_open(host, port):
        return _ok("mongodb", f"reachable at {host}:{port}")
    return _warn(
        "mongodb",
        f"unreachable at {host}:{port} — backend uses env-auth limited mode; "
        "CI provides a mongo:7 service so Mongo-only tests run there",
    )


def check_ollama() -> Check:
    base = os.environ.get("OLLAMA_BASE", "http://localhost:11434")
    try:
        with urllib.request.urlopen(base + "/api/tags", timeout=2.0) as r:
            if r.status == 200:
                return _ok("ollama", f"reachable at {base}")
            return _warn("ollama", f"{base} returned HTTP {r.status}")
    except Exception:
        return _warn("ollama", f"unreachable at {base} — local model routing unavailable")


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return ""


def check_git() -> Check:
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    if not branch:
        return _warn("git", "not a git repo / git unavailable")
    dirty = _git("status", "--porcelain")
    n = len([ln for ln in dirty.splitlines() if ln.strip()])
    state = "clean" if n == 0 else f"{n} uncommitted change(s)"
    return _ok("git", f"branch '{branch}', {state}")


def check_node() -> Check:
    if shutil.which("node") and shutil.which("npm"):
        ver = _node_version()
        return _ok("node", f"node {ver} present (frontend buildable)")
    return _warn("node", "node/npm not found — frontend tests/build unavailable locally")


def _node_version() -> str:
    try:
        return subprocess.run(
            ["node", "--version"], capture_output=True, text=True, timeout=10
        ).stdout.strip()
    except Exception:
        return "?"


def check_core_deps() -> Check:
    missing = []
    for mod in ("fastapi", "pydantic", "httpx"):
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if not missing:
        return _ok("deps", "fastapi, pydantic, httpx importable")
    return _fail("deps", f"cannot import {', '.join(missing)} — run: pip install -r requirements.txt")


CHECKS = (
    check_python,
    check_env,
    check_core_deps,
    check_mongo,
    check_ollama,
    check_node,
    check_git,
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Agency Core environment & CI-parity doctor")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any check FAILs")
    args = ap.parse_args()

    results = [c() for c in CHECKS]
    width = max(len(r.name) for r in results)
    print("\nAgency Core doctor")
    print("=" * 60)
    for r in results:
        print(f"  [{r.status:<4}] {r.name.ljust(width)}  {r.detail}")
    print("=" * 60)
    fails = sum(1 for r in results if r.status == "FAIL")
    warns = sum(1 for r in results if r.status == "WARN")
    print(f"  {len(results)} checks — {fails} FAIL, {warns} WARN\n")
    if args.strict and fails:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
