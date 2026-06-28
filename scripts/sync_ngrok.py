#!/usr/bin/env python3
"""Refresh Render OLLAMA_BASE_URL + platform brain config after every ngrok tunnel rotation.

When the local ngrok tunnel restarts it gets a new public URL.  Two pieces of
state on Render need to track that URL or the next agent run will hit the old
tunnel (or ``http://localhost:11434`` which is unreachable from Render):

  1. The Render dashboard env var ``OLLAMA_BASE_URL`` (cold-start fallback when
     the sqlite mirror is wiped).
  2. The DB-persisted brain config — ``ollama_base_url`` field, set via
     ``PATCH /admin/api/policy/brain``.

This script detects the current local ngrok URL, PATCHes the brain config (always),
and updates the Render env var when ``RENDER_API_KEY`` + ``RENDER_SERVICE_ID``
are set.  Without the Render API token it prints the exact dashboard steps to
do manually.

The platform-brain PATCH is delegated to ``scripts/switch_brain.py`` so model
detection, role assignment, and auth all stay in one place.

Usage:
    python scripts/sync_ngrok.py                  # detect + PATCH brain, print Render steps if no API key
    python scripts/sync_ngrok.py --dry-run       # show what would change
    python scripts/sync_ngrok.py --ngrok-url URL # override the detected URL

Environment:
    RENDER_API_KEY     Render API token (Dashboard → Account Settings → API Keys)
    RENDER_SERVICE_ID  ``srv-...`` ID for the local-llm-server web service
    PLATFORM_URL       Agency platform URL (default: https://local-llm-server.onrender.com)
    ADMIN_EMAIL/PASSWORD or PLATFORM_TOKEN or SERVICE_TOKEN — see switch_brain.py
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys

import httpx

NGROK_API = "http://localhost:4040/api/tunnels"
RENDER_API_BASE = "https://api.render.com/v1"

_USE_ASCII = not sys.stdout.isatty() or os.environ.get("SYNC_NGROK_ASCII", "").strip().lower() in ("1", "true", "yes")

if _USE_ASCII:
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


def detect_ngrok_url() -> str | None:
    """Return the first running ngrok tunnel's public URL, or None."""
    try:
        resp = httpx.get(NGROK_API, timeout=3)
        if resp.status_code != 200:
            return None
        data = resp.json()
        for tunnel in data.get("tunnels", []):
            public = (tunnel.get("public_url") or "").rstrip("/")
            if public:
                return public
    except Exception:
        pass
    return None


def patch_platform_brain_via_switch_brain(tunnel_url: str, dry_run: bool) -> bool:
    """Delegate the brain PATCH to scripts/switch_brain.py via subprocess.

    Decoupling lets switch_brain own model detection + role assignment + auth —
    this script only owns ngrok discovery and Render env-var refresh.
    """
    cmd = [
        sys.executable,
        "scripts/switch_brain.py",
        "ollama",
        "--ollama-url",
        tunnel_url,
        "--no-tunnel",
    ]
    if dry_run:
        cmd.append("--dry-run")

    print(info("Delegating brain PATCH to scripts/switch_brain.py"))
    print(dim(f"  $ {' '.join(cmd)}"))
    result = subprocess.run(cmd, env=os.environ.copy())
    return result.returncode == 0


def patch_render_env_var(render_api_key: str, service_id: str, env_key: str, value: str, dry_run: bool) -> bool:
    """Update a single env var on a Render service via the Render REST API."""
    url = f"{RENDER_API_BASE}/services/{service_id}/env-vars/{env_key}"
    headers = {
        "Authorization": f"Bearer {render_api_key}",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    body = {"value": value}

    if dry_run:
        print(header("DRY RUN — would PUT Render env var:"))
        print(f"  URL:    {url}")
        print(f"  body:   {json.dumps(body)}")
        return True

    print(info(f"PUT {env_key} on Render service {service_id}..."))
    try:
        resp = httpx.put(url, json=body, headers=headers, timeout=20)
        if resp.status_code in (200, 204):
            print(ok(f"Render env var {env_key} updated. Service is restarting with the new value."))
            return True
        print(fail(f"Render API failed: HTTP {resp.status_code} — {resp.text[:300]}"))
        return False
    except httpx.RequestError as exc:
        print(fail(f"Cannot reach Render API: {exc}"))
        return False


def print_manual_render_steps(env_key: str, value: str) -> None:
    """Print the manual dashboard steps for setting an env var when no API key is available."""
    print(header("Manual Render Dashboard Steps"))
    print("  1. Open https://dashboard.render.com and select the local-llm-server service.")
    print("  2. Click Environment -> Add Environment Variable.")
    print(f"  3. Key:    {env_key}")
    print(f"     Value:  {value}")
    print("  4. Save Changes -- Render triggers an automatic redeploy.")
    print()
    print(dim("Optional: automate next time by setting RENDER_API_KEY + RENDER_SERVICE_ID in .env"))
    print(dim("  (Dashboard -> Account Settings -> API Keys, then /v1/services list to copy the srv-... ID)"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Refresh Render OLLAMA_BASE_URL + platform brain config after every ngrok restart.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dry-run", action="store_true", help="Show what would change without applying.")
    parser.add_argument(
        "--ngrok-url",
        help="Override the detected ngrok URL (e.g. after a fresh tunnel that the API hasn't picked up yet).",
    )
    parser.add_argument(
        "--env-key",
        default="OLLAMA_BASE_URL",
        help="The Render env var to refresh (default: OLLAMA_BASE_URL; you can also pass OLLAMA_BASE).",
    )
    parser.add_argument(
        "--skip-render",
        action="store_true",
        help="Only patch the platform brain DB; never write to the Render dashboard.",
    )
    parser.add_argument(
        "--skip-platform",
        action="store_true",
        help="Only refresh the Render env var; never PATCH the platform brain DB.",
    )
    args = parser.parse_args()

    tunnel_url = (args.ngrok_url or detect_ngrok_url() or "").rstrip("/")
    if not tunnel_url:
        print(fail("No ngrok tunnel running. Start one with `ngrok http 8000` or pass --ngrok-url."))
        sys.exit(1)
    print(ok(f"Detected ngrok tunnel: {tunnel_url}"))

    # 1. PATCH the platform brain (skipped when --skip-platform is set).
    if not args.skip_platform:
        print(header("Step 1 / 2 -- Patch platform brain config"))
        patched = patch_platform_brain_via_switch_brain(tunnel_url, dry_run=args.dry_run)
        if not patched and not args.dry_run:
            print(fail("Brain PATCH failed -- aborting before Render touch."))
            sys.exit(2)
    else:
        print(dim("--skip-platform passed; not patching the platform brain DB."))
        patched = True

    # 2. PATCH the Render env var (only if RENDER_API_KEY + RENDER_SERVICE_ID provided).
    print(header("Step 2 / 2 -- Refresh Render env var"))
    render_key = os.environ.get("RENDER_API_KEY", "").strip()
    render_service_id = os.environ.get("RENDER_SERVICE_ID", "").strip()

    if args.skip_render or not render_key or not render_service_id:
        print_manual_render_steps(args.env_key, tunnel_url)
        if not patched and not args.dry_run:
            sys.exit(3)
        return

    updated = patch_render_env_var(render_key, render_service_id, args.env_key, tunnel_url, dry_run=args.dry_run)
    if (not patched or not updated) and not args.dry_run:
        sys.exit(4)


if __name__ == "__main__":
    main()
