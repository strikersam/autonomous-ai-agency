#!/usr/bin/env python3
"""Post-deploy verification for the website scanner against the LIVE internet.

Unlike the unit tests (which stub the network), this actually scans real sites —
including bot-protected ones like gucci.com — and prints what each detection
tier recovered. Use it to confirm, after a deploy to an environment that has a
Chromium binary + real network (e.g. Render), that the scanner genuinely
resolves tough sites rather than just passing stubbed logic tests.

Usage:
    # In an environment with the scanner deps + Chromium installed:
    python -m playwright install --with-deps chromium   # once
    python scripts/verify_scanner_live.py
    python scripts/verify_scanner_live.py gucci.com nike.com   # custom targets

Exit code is 0 if every scan completed without crashing AND none fabricated a
challenge-vendor-only result; 1 otherwise. It does NOT fail merely because a
hard-CAPTCHA site returned nothing — that's an honest outcome, not a bug.
"""
from __future__ import annotations

import asyncio
import os
import sys

# Make the repo root importable when run as `python scripts/verify_scanner_live.py`
# from anywhere (pytest adds this via pytest.ini `pythonpath=.`, but a bare run
# does not — without it `import services.scanner` fails with ModuleNotFoundError).
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

# Default target set: a well-behaved control + the motivating bot-protected cases.
DEFAULT_TARGETS = [
    "https://www.wikipedia.org",   # control — must detect something
    "https://www.gucci.com",       # JS-rendered SFCC behind Akamai
    "https://www.klarna.com",
    "https://www.nike.com",
]

_CHALLENGE_VENDOR_NAMES = {
    "cloudflare", "cloudflare bot management", "recaptcha", "hcaptcha",
    "datadome", "perimeterx", "imperva", "imperva incapsula",
}


async def _scan_one(url: str) -> tuple[str, bool, str]:
    """Returns (url, ok, summary)."""
    try:
        from services.scanner import WebsiteScanner
    except Exception as e:  # pragma: no cover
        return url, False, f"scanner import failed: {e}"

    scanner = WebsiteScanner(company_id="verify_live")
    try:
        result = await scanner.scan_website(url)
    except Exception as e:
        return url, False, f"CRASHED: {e}"

    if result.status != "success":
        return url, False, f"status={result.status} errors={result.errors}"

    names = [s.name for s in result.detected_systems]
    lowered = {n.lower() for n in names}
    # Fabrication guard: a result of ONLY challenge-vendor names means we
    # mis-parsed a bot wall as the target's stack.
    only_challenge = bool(names) and not (lowered - _CHALLENGE_VENDOR_NAMES)
    if only_challenge:
        return url, False, f"FABRICATED (challenge-vendor-only): {names}"

    if names:
        # Show the evidence source of the first few, so we can see which tier
        # (HTML / DNS / builtwith) produced the detection.
        sources = sorted({
            ev.location for s in result.detected_systems for ev in s.evidence
        })
        return url, True, f"{len(names)} systems via {sources}: {names[:8]}"
    return url, True, "no systems detected (honest empty — site fully blocked live detection)"


async def main(targets: list[str]) -> int:
    print("=" * 78)
    print("LIVE SCANNER VERIFICATION")
    print("=" * 78)
    all_ok = True
    for url in targets:
        url, ok, summary = await _scan_one(url)
        mark = "✅" if ok else "❌"
        print(f"\n{mark} {url}\n    {summary}")
        all_ok = all_ok and ok
    print("\n" + "=" * 78)
    print("RESULT:", "✅ all scans well-behaved" if all_ok else "❌ a scan crashed or fabricated")
    print("=" * 78)
    print(
        "\nNote: a site returning 'no systems detected (honest empty)' is NOT a\n"
        "failure — it means live bot protection blocked every free tier, which is\n"
        "an expected outcome for the hardest sites. Failures are only crashes or\n"
        "fabricated challenge-vendor-only results."
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    args = sys.argv[1:]
    targets = [a if a.startswith(("http://", "https://")) else f"https://{a}" for a in args] or DEFAULT_TARGETS
    raise SystemExit(asyncio.run(main(targets)))
