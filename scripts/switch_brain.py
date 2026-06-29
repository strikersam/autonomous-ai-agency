#!/usr/bin/env python3
"""One-command brain provider switcher for the agency platform.

Seamlessly switch the agency's brain between local Ollama and free cloud
providers (NVIDIA NIM, Cerebras, Groq) with a single command.

Usage:
    python scripts/switch_brain.py status          # Show current brain config
    python scripts/switch_brain.py ollama          # Switch to local Ollama (auto-detect)
    python scripts/switch_brain.py nvidia          # Switch to NVIDIA NIM cloud
    python scripts/switch_brain.py cerebras        # Switch to Cerebras cloud
    python scripts/switch_brain.py groq            # Switch to Groq cloud
    python scripts/switch_brain.py ollama --dry-run  # Preview without applying

For Ollama mode, the script auto-detects:
  - Whether Ollama is running (probes OLLAMA_BASE or localhost:11434)
  - Which models are pulled (reads GET /api/tags)
  - Maps the best models to planner/executor/verifier/judge roles
  - Starts an ngrok tunnel if needed and gets the public URL
  - Probes models through the tunnel before saving

For cloud modes, the script uses the provider presets from
services/brain_config_store.py (PROVIDER_PRESETS).

Authentication:
  - Reads ADMIN_EMAIL + ADMIN_PASSWORD from .env
  - Logs into the agency platform to get a JWT
  - Or set PLATFORM_TOKEN env var with a pre-existing JWT
  - Or set SERVICE_TOKEN for service-token auth

Environment:
  - PLATFORM_URL: agency backend URL (default: https://local-llm-server.onrender.com)
  - ADMIN_EMAIL / ADMIN_PASSWORD: admin credentials for JWT login
  - PLATFORM_TOKEN: skip login, use this JWT directly
  - SERVICE_TOKEN: use backend service-token auth
  - OLLAMA_BASE: local Ollama URL (default: http://localhost:11434)
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import httpx

# ── Constants ────────────────────────────────────────────────────────────────

# Provider presets — mirrors services/brain_config_store.py:PROVIDER_PRESETS
PROVIDER_PRESETS: dict[str, dict[str, str]] = {
    "cerebras": {
        "planner": "qwen-3-coder-480b",
        "executor": "qwen-3-coder-480b",
        "verifier": "llama-3.3-70b",
        "judge": "llama-3.3-70b",
    },
    "groq": {
        "planner": "deepseek-r1-distill-llama-70b",
        "executor": "llama-3.3-70b-versatile",
        "verifier": "deepseek-r1-distill-llama-70b",
        "judge": "llama-3.3-70b-versatile",
    },
    "nvidia": {
        "planner": "meta/llama-3.3-70b-instruct",
        "executor": "meta/llama-3.3-70b-instruct",
        "verifier": "meta/llama-3.3-70b-instruct",
        "judge": "meta/llama-3.3-70b-instruct",
    },
    "ollama": {
        "planner": "deepseek-r1:32b",
        "executor": "qwen3-coder:30b",
        "verifier": "deepseek-r1:32b",
        "judge": "deepseek-r1:32b",
    },
}

VALID_PROVIDERS = frozenset(PROVIDER_PRESETS.keys())

# Model → role mapping heuristics for Ollama auto-detection
# Priority: first match wins. Checked in order.
ROLE_PATTERNS: list[tuple[str, str]] = [
    # Planner: reasoning models first
    ("deepseek-r1", "planner"),
    ("qwq", "planner"),
    ("nemotron", "planner"),
    ("mixtral", "planner"),
    # Executor: coding models first
    ("qwen3-coder", "executor"),
    ("qwen2.5-coder", "executor"),
    ("codellama", "executor"),
    ("deepseek-coder", "executor"),
    ("starcoder", "executor"),
    # Fallback: general-purpose models
    ("qwen3", "executor"),
    ("qwen2.5", "executor"),
    ("llama3", "executor"),
    ("gemma", "executor"),
    ("mistral", "executor"),
    ("phi", "executor"),
    ("deepseek", "planner"),
]

NGROK_API = "http://localhost:4040/api/tunnels"
NGROK_START_WAIT = 8  # seconds to wait for ngrok to come up

# ── Color helpers ────────────────────────────────────────────────────────────

_USE_ASCII = not sys.stdout.isatty() or os.environ.get("SWITCH_BRAIN_ASCII", "").strip().lower() in ("1", "true", "yes")

if _USE_ASCII:
    # ASCII-safe output for non-TTY environments (piped, CI, some Windows terminals)
    def ok(text: str) -> str: return f"[OK] {text}"
    def warn(text: str) -> str: return f"[WARN] {text}"
    def fail(text: str) -> str: return f"[FAIL] {text}"
    def info(text: str) -> str: return f"> {text}"
    def header(text: str) -> str: return f"\n--- {text} ---"
    def dim(text: str) -> str: return text
else:
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    RED = "\033[31m"
    CYAN = "\033[36m"
    BOLD = "\033[1m"
    RESET = "\033[0m"
    def ok(text: str) -> str: return f"{GREEN}\u2713{RESET} {text}"
    def warn(text: str) -> str: return f"{YELLOW}\u26a0{RESET} {text}"
    def fail(text: str) -> str: return f"{RED}\u2717{RESET} {text}"
    def info(text: str) -> str: return f"{CYAN}\u2192{RESET} {text}"
    def header(text: str) -> str: return f"\n{BOLD}{text}{RESET}"
    def dim(text: str) -> str: return f"\033[2m{text}{RESET}"


# ── Auth ─────────────────────────────────────────────────────────────────────


def get_auth_headers(platform_url: str) -> dict[str, str]:
    """Get authentication headers for the agency platform.

    Precedence: SERVICE_TOKEN → PLATFORM_TOKEN → email/password login.
    """
    # Service token auth
    service_token = os.environ.get("SERVICE_TOKEN", "").strip()
    if service_token:
        return {"Authorization": f"Bearer {service_token}"}

    # Pre-existing JWT
    token = os.environ.get("PLATFORM_TOKEN", "").strip()
    if token:
        return {"Authorization": f"Bearer {token}"}

    # Email/password login
    email = os.environ.get("ADMIN_EMAIL", "admin@llmrelay.local").strip()
    password = os.environ.get("ADMIN_PASSWORD", "").strip()
    if not password:
        print(fail("No auth configured. Set ADMIN_PASSWORD in .env, or PLATFORM_TOKEN, or SERVICE_TOKEN."))
        sys.exit(1)

    try:
        resp = httpx.post(
            f"{platform_url}/api/auth/login",
            json={"email": email, "password": password},
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        token = data.get("access_token", "")
        if not token:
            print(fail("Login succeeded but no access_token returned."))
            sys.exit(1)
        return {"Authorization": f"Bearer {token}"}
    except httpx.HTTPStatusError as exc:
        print(fail(f"Login failed: HTTP {exc.response.status_code}"))
        if exc.response.status_code == 503:
            print(dim("  Platform may be in cold start (Render free tier). Wait 30s and retry."))
        sys.exit(1)
    except httpx.RequestError as exc:
        print(fail(f"Cannot reach platform at {platform_url}: {exc}"))
        print(dim("  Check your network connection and platform URL."))
        sys.exit(1)


# ── Platform API ─────────────────────────────────────────────────────────────


def get_brain_config(platform_url: str, headers: dict[str, str]) -> dict:
    """GET the current brain config from the agency platform."""
    try:
        resp = httpx.get(
            f"{platform_url}/admin/api/policy/brain",
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        print(fail(f"Failed to get brain config: HTTP {exc.response.status_code}"))
        if exc.response.status_code == 401:
            print(dim("  Check your admin credentials or token."))
        elif exc.response.status_code == 503:
            print(dim("  Platform may be in cold start (Render free tier)."))
        sys.exit(1)
    except httpx.RequestError as exc:
        print(fail(f"Cannot reach platform: {exc}"))
        print(dim("  Platform may be sleeping (Render free tier cold start)."))
        sys.exit(1)


def patch_brain_config(
    platform_url: str,
    headers: dict[str, str],
    payload: dict,
    dry_run: bool = False,
) -> dict:
    """PATCH the brain config on the agency platform."""
    if dry_run:
        print(header("DRY RUN — would PATCH:"))
        print(json.dumps(payload, indent=2))
        return {"dry_run": True, "payload": payload}

    print(info(f"Applying brain config to {platform_url}..."))
    try:
        resp = httpx.patch(
            f"{platform_url}/admin/api/policy/brain",
            json=payload,
            headers=headers,
            timeout=60,  # liveness probes can take time
        )
        if resp.status_code == 422:
            data = resp.json()
            detail = data.get("detail", str(data))
            print(fail(f"Platform refused config: {detail}"))
            # Show probe results if available
            probes = data.get("probes", [])
            if probes:
                print(header("Liveness probe results:"))
                for p in probes:
                    icon_fn = ok if p.get("live") else fail
                    print(f"  {icon_fn('')} {p['role']}: {p['model']} — {p.get('reason', '?')}")
            sys.exit(1)

        resp.raise_for_status()
        data = resp.json()
        return data

    except httpx.HTTPStatusError as exc:
        print(fail(f"PATCH failed: HTTP {exc.response.status_code}"))
        print(dim(f"  {exc.response.text[:300]}"))
        sys.exit(1)
    except httpx.RequestError as exc:
        print(fail(f"Cannot reach platform: {exc}"))
        sys.exit(1)


# ── Ollama detection ─────────────────────────────────────────────────────────


def detect_ollama_models(base_url: str) -> list[str]:
    """Detect available Ollama models via GET /api/tags."""
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=5)
        if resp.status_code != 200:
            return []
        data = resp.json()
        return [
            m["name"]
            for m in data.get("models", [])
            if isinstance(m, dict) and m.get("name")
        ]
    except Exception:
        return []


def is_ollama_reachable(base_url: str) -> bool:
    """Check if Ollama is responding."""
    try:
        resp = httpx.get(f"{base_url}/api/tags", timeout=5)
        return resp.status_code == 200
    except Exception:
        return False


def map_models_to_roles(models: list[str]) -> dict[str, str]:
    """Map available Ollama models to planner/executor/verifier/judge roles.

    Heuristic: reasoning models (deepseek-r1, qwq) → planner/verifier/judge;
    coding models (qwen-coder, codellama) → executor.
    """
    assigned: dict[str, str] = {}
    available = {m.lower(): m for m in models}  # preserve original casing

    # Find the best model for each role pattern
    role_candidates: dict[str, list[str]] = {"planner": [], "executor": [], "verifier": [], "judge": []}

    for model_lower, model_original in available.items():
        for pattern, role in ROLE_PATTERNS:
            if pattern in model_lower:
                if role == "planner":
                    role_candidates["planner"].append(model_original)
                    role_candidates["verifier"].append(model_original)
                    role_candidates["judge"].append(model_original)
                else:
                    role_candidates["executor"].append(model_original)
                break  # first match per model

    # Assign: first candidate for each role, preferring unassigned models
    used: set[str] = set()
    for role in ["planner", "executor", "verifier", "judge"]:
        candidates = role_candidates.get(role, [])
        # Prefer models not already assigned to another role
        unassigned = [m for m in candidates if m not in used]
        pick = next(iter(unassigned), next(iter(candidates), None))
        if pick:
            assigned[role] = pick
            used.add(pick)

    # Fill gaps: use any available model
    remaining = [m for m in models if m not in used]
    for role in ["planner", "executor", "verifier", "judge"]:
        if role not in assigned and remaining:
            assigned[role] = remaining.pop(0)

    return assigned


# ── Ngrok tunnel ─────────────────────────────────────────────────────────────


def get_ngrok_tunnel_url() -> str | None:
    """Get the public URL of the first running ngrok tunnel."""
    try:
        resp = httpx.get(NGROK_API, timeout=3)
        if resp.status_code != 200:
            return None
        data = resp.json()
        tunnels = data.get("tunnels", [])
        if tunnels:
            return tunnels[0].get("public_url", "").rstrip("/")
    except Exception:
        pass
    return None


def start_ngrok_tunnel(port: int, log_dir: str | None = None) -> str | None:
    """Start ngrok tunnel pointing to the given port. Returns public URL or None."""
    # Check if already running
    existing = get_ngrok_tunnel_url()
    if existing:
        print(ok(f"ngrok tunnel already running: {existing}"))
        return existing

    print(info(f"Starting ngrok tunnel → port {port}..."))
    try:
        log_dir = (Path(log_dir) if log_dir else Path(__file__).resolve().parent.parent / "logs").resolve()
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = str(log_dir / "tunnel-brainswitch.log")

        # ngrok has its own --log flag — use it instead of shell redirection
        subprocess.Popen(
            ["ngrok", "http", str(port), "--log", log_file],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Wait for ngrok to come up
        print(dim(f"  Waiting {NGROK_START_WAIT}s for ngrok to start..."))
        for _ in range(NGROK_START_WAIT):
            time.sleep(1)
            url = get_ngrok_tunnel_url()
            if url:
                print(ok(f"ngrok tunnel ready: {url}"))
                return url

        print(warn("ngrok started but tunnel URL not yet available. Check http://localhost:4040"))
        return get_ngrok_tunnel_url()
    except FileNotFoundError:
        print(fail("ngrok not found. Install it from https://ngrok.com/download"))
        print(dim("  Or start a tunnel manually and re-run with --ollama-url."))
        return None
    except Exception as exc:
        print(fail(f"Failed to start ngrok: {exc}"))
        return None


# ── Status display ───────────────────────────────────────────────────────────


def show_status(platform_url: str, ollama_base: str, headers: dict[str, str]) -> None:
    """Display the current brain config and local state."""
    print(header("Agency Brain Status"))
    print(f"  Platform: {platform_url}")

    # Platform brain config
    try:
        cfg = get_brain_config(platform_url, headers)
        config = cfg.get("config", {})
        provider = config.get("primary_provider", "?")
        print(f"  Provider:  {provider}")
        print(f"  Planner:   {config.get('planner_model', '?')}")
        print(f"  Executor:  {config.get('executor_model', '?')}")
        print(f"  Verifier:  {config.get('verifier_model', '?')}")
        print(f"  Judge:     {config.get('judge_model', '?')}")
        ollama_url = config.get("ollama_base_url", "")
        if ollama_url:
            print(f"  Ollama URL: {ollama_url}")
        updated = config.get("updated_at", "")
        if updated:
            print(f"  Updated:   {updated[:19]}")
        updated_by = config.get("updated_by", "")
        if updated_by:
            print(f"  By:        {updated_by}")

        # Show provider key status
        providers = cfg.get("providers", [])
        if providers:
            print(header("Provider Keys"))
            for p in providers:
                pid = p.get("provider", "?")
                has_key = p.get("key_present", False)
                icon_str = ok if has_key else warn
                print(f"  {icon_str('')} {pid}: {'key present' if has_key else 'no key'}")

    except SystemExit:
        raise
    except Exception as exc:
        print(warn(f"Could not fetch brain config: {exc}"))

    # Local Ollama state
    print(header("Local Ollama"))
    if is_ollama_reachable(ollama_base):
        models = detect_ollama_models(ollama_base)
        print(ok(f"Ollama reachable at {ollama_base}"))
        if models:
            print(f"  Models ({len(models)}):")
            for m in sorted(models):
                print(f"    - {m}")
        else:
            print(warn("No models found. Pull with: ollama pull <model>"))
    else:
        print(warn(f"Ollama not reachable at {ollama_base}"))

    # Ngrok tunnel
    tunnel = get_ngrok_tunnel_url()
    if tunnel:
        print(ok(f"ngrok tunnel: {tunnel}"))
    else:
        print(dim("No ngrok tunnel detected."))


# ── Switch command ───────────────────────────────────────────────────────────


def switch_to_ollama(
    platform_url: str,
    ollama_base: str,
    headers: dict[str, str],
    *,
    dry_run: bool = False,
    tunnel_port: int = 8000,
    skip_tunnel: bool = False,
    assume_yes: bool = False,
) -> None:
    """Switch the brain to local Ollama with auto-detection."""
    print(header("Switching to Local Ollama"))

    # 1. Check Ollama
    if not is_ollama_reachable(ollama_base):
        print(fail(f"Ollama is not reachable at {ollama_base}"))
        print(dim("  Start Ollama first: ollama serve"))
        sys.exit(1)

    models = detect_ollama_models(ollama_base)
    if not models:
        print(fail("No models pulled in Ollama."))
        print(dim("  Pull models first: ollama pull qwen3-coder:30b && ollama pull deepseek-r1:32b"))
        sys.exit(1)

    print(ok(f"Ollama reachable with {len(models)} model(s):"))
    for m in sorted(models):
        print(f"    - {m}")

    # 2. Map models to roles
    role_models = map_models_to_roles(models)
    print(header("Auto-assigned roles:"))
    for role in ["planner", "executor", "verifier", "judge"]:
        model = role_models.get(role, "(none)")
        print(f"  {role}: {model}")

    if not role_models:
        print(fail("Could not map any models to roles."))
        sys.exit(1)

    # Warn if no reasoning model was found (all roles get executor-type models)
    has_reasoning = any(
        "deepseek-r1" in m.lower() or "qwq" in m.lower()
        for m in role_models.values()
    )
    if not has_reasoning:
        print(warn("No reasoning model (deepseek-r1, qwq) detected — planner may perform poorly."))
        print(dim("  Consider: ollama pull deepseek-r1:32b"))

    # 3. Start ngrok tunnel (unless skipped)
    tunnel_url: str | None = None
    if not skip_tunnel:
        tunnel_url = start_ngrok_tunnel(port=tunnel_port)
        if not tunnel_url:
            print(warn("Could not start ngrok tunnel. The platform needs a public URL to reach Ollama."))
            print(dim("  Start a tunnel manually and pass it via --ollama-url, or set OLLAMA_BASE in your .env"))
            if not dry_run and not assume_yes:
                response = input("\nContinue without a tunnel URL? [y/N] ").strip().lower()
                if response != "y":
                    sys.exit(0)
        else:
            # Verify the tunnel actually reaches Ollama
            try:
                probe = httpx.get(f"{tunnel_url}/api/tags", timeout=10)
                if probe.status_code == 200:
                    tunnel_models = [
                        m["name"] for m in probe.json().get("models", [])
                        if isinstance(m, dict) and m.get("name")
                    ]
                    print(ok(f"Tunnel verified — {len(tunnel_models)} model(s) reachable via {tunnel_url}"))
                else:
                    print(warn(f"Tunnel returns HTTP {probe.status_code} — may need auth bypass"))
            except Exception as exc:
                print(warn(f"Tunnel probe failed: {exc}"))

    # 4. Build payload and apply
    payload: dict = {
        "primary_provider": "ollama",
        "planner_model": role_models.get("planner", "deepseek-r1:32b"),
        "executor_model": role_models.get("executor", "qwen3-coder:30b"),
        "verifier_model": role_models.get("verifier", "deepseek-r1:32b"),
        "judge_model": role_models.get("judge", "deepseek-r1:32b"),
    }
    if tunnel_url:
        payload["ollama_base_url"] = tunnel_url

    result = patch_brain_config(platform_url, headers, payload, dry_run=dry_run)
    if not dry_run:
        config = result.get("config", result)
        probes = result.get("probes", [])
        print(header("Result"))
        print(ok(f"Brain switched to {config.get('primary_provider', 'ollama')}"))
        if probes:
            for p in probes:
                icon_str = ok if p.get("live") else fail
                print(f"  {icon_str('')} {p['role']}: {p['model']} — {p.get('reason', '?')}")
        print(dim("  The next agent run will use local Ollama."))


def switch_to_cloud(
    provider: str,
    platform_url: str,
    headers: dict[str, str],
    dry_run: bool = False,
) -> None:
    """Switch the brain to a cloud provider using presets."""
    print(header(f"Switching to {provider.upper()} Cloud"))

    presets = PROVIDER_PRESETS.get(provider)
    if not presets:
        print(fail(f"Unknown provider: {provider}. Valid: {', '.join(sorted(VALID_PROVIDERS))}"))
        sys.exit(1)

    print("Using provider presets:")
    for role in ["planner", "executor", "verifier", "judge"]:
        print(f"  {role}: {presets[role]}")

    payload = {
        "primary_provider": provider,
        "planner_model": presets["planner"],
        "executor_model": presets["executor"],
        "verifier_model": presets["verifier"],
        "judge_model": presets["judge"],
        # Clear ollama_base_url when switching away from Ollama
        "ollama_base_url": "",
    }

    result = patch_brain_config(platform_url, headers, payload, dry_run=dry_run)
    if not dry_run:
        config = result.get("config", result)
        probes = result.get("probes", [])
        print(header("Result"))
        print(ok(f"Brain switched to {config.get('primary_provider', provider)}"))
        if probes:
            for p in probes:
                icon_str = ok if p.get("live") else fail
                print(f"  {icon_str('')} {p['role']}: {p['model']} — {p.get('reason', '?')}")
        print(dim("  The next agent run will use the cloud provider."))


# ── CLI ──────────────────────────────────────────────────────────────────────


def main() -> None:
    default_platform = os.environ.get("PLATFORM_URL", "https://local-llm-server.onrender.com").rstrip("/")
    default_ollama = os.environ.get("OLLAMA_BASE", "http://localhost:11434").rstrip("/")
    default_tunnel_port = int(os.environ.get("PROXY_PORT", "8000"))

    parser = argparse.ArgumentParser(
        description="One-command brain provider switcher for the agency platform.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/switch_brain.py status       # Show current brain config
  python scripts/switch_brain.py ollama       # Switch to local Ollama (auto-detect)
  python scripts/switch_brain.py nvidia       # Switch to NVIDIA NIM cloud
  python scripts/switch_brain.py ollama --dry-run  # Preview without applying
        """,
    )
    parser.add_argument(
        "action",
        nargs="?",
        default="status",
        choices=["status", "ollama", "nvidia", "cerebras", "groq"],
        help="Action: status (show config), or a provider name to switch to",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the PATCH payload without applying it",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompts (non-interactive mode)",
    )
    parser.add_argument(
        "--platform-url",
        default=default_platform,
        help=f"Agency platform URL (default: {default_platform})",
    )
    parser.add_argument(
        "--ollama-url",
        default=default_ollama,
        help=f"Ollama base URL (default: {default_ollama})",
    )
    parser.add_argument(
        "--no-tunnel",
        action="store_true",
        help="Skip ngrok tunnel setup (use existing OLLAMA_BASE)",
    )
    parser.add_argument(
        "--tunnel-port",
        type=int,
        default=default_tunnel_port,
        help=f"Port for ngrok tunnel (default: {default_tunnel_port})",
    )

    args = parser.parse_args()

    platform_url = args.platform_url.rstrip("/")
    ollama_base = args.ollama_url.rstrip("/")
    tunnel_port = args.tunnel_port

    # Auth
    headers = get_auth_headers(platform_url)

    # Dispatch
    if args.action == "status":
        show_status(platform_url, ollama_base, headers)
    elif args.action == "ollama":
        switch_to_ollama(
            platform_url, ollama_base, headers,
            dry_run=args.dry_run,
            tunnel_port=tunnel_port,
            skip_tunnel=args.no_tunnel,
            assume_yes=args.yes,
        )
    elif args.action in ("nvidia", "cerebras", "groq"):
        switch_to_cloud(args.action, platform_url, headers, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
