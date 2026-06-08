"""LIVE integration tests for the website scanner — these actually hit the real
internet (no mocks), including bot-protected sites like gucci.com.

Excluded from the default test run (`pytest.ini` sets `-m "not integration"`)
because they depend on third-party site availability and on a Chromium binary
being installed; they must NEVER block CI on external flakiness. Run explicitly:

    pip install playwright && python -m playwright install --with-deps chromium
    pytest -m integration tests/test_scanner_live.py -v

They are wired into a dedicated, non-blocking `e2e.yml` job and mirrored by the
runnable `scripts/verify_scanner_live.py` for post-deploy verification.

The contract these assert (the honest one):
  * the scanner must NEVER crash on a live bot-protected site;
  * it must return a successful WebsiteScanResult (status == "success");
  * it must either detect real systems OR honestly report nothing — it must
    NEVER fabricate a detection of the *challenge vendor* (Cloudflare /
    reCAPTCHA / Akamai bot manager) as if it were the target's own stack.

We deliberately do NOT hard-assert "gucci.com yields Salesforce Commerce Cloud",
because that depends on live bot-protection state we can't control. Instead we
assert the invariants that must hold regardless, and we *print* what was found
so the CI log / verification run shows the real outcome.
"""
from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration


def _scanner():
    try:
        from services.scanner import WebsiteScanner
    except (ImportError, ModuleNotFoundError) as e:  # pragma: no cover
        pytest.skip(f"scanner not importable: {e}")
    return WebsiteScanner(company_id="live_test_co")


# Challenge-vendor names that must never appear as a *sole* detection — if the
# only thing we "found" is the wall itself, we mis-parsed a challenge page.
_CHALLENGE_VENDOR_NAMES = {
    "cloudflare", "cloudflare bot management", "recaptcha", "hcaptcha",
    "datadome", "perimeterx", "imperva", "imperva incapsula",
}


def _assert_scan_contract(result, label: str) -> None:
    """The invariants that must hold for any live scan, bot-protected or not."""
    assert result is not None, f"{label}: scanner returned None"
    # Never a hard failure / 5xx-equivalent on a reachable site.
    assert result.status == "success", f"{label}: status={result.status} errors={result.errors}"

    names = [s.name for s in result.detected_systems]
    lowered = {n.lower() for n in names}
    print(f"\n[live] {label}: {len(names)} systems → {names}")

    # The critical anti-fabrication invariant: we must not have returned ONLY
    # challenge-vendor detections (which would mean we parsed a CAPTCHA wall as
    # if it were the target's stack). Real detections alongside a CDN are fine;
    # a result consisting *exclusively* of challenge vendors is the failure mode.
    if names:
        non_challenge = lowered - _CHALLENGE_VENDOR_NAMES
        assert non_challenge or not (lowered & _CHALLENGE_VENDOR_NAMES), (
            f"{label}: detected ONLY challenge-vendor names {names} — "
            f"a bot wall was likely mis-parsed as results"
        )


@pytest.mark.asyncio
async def test_live_scan_well_behaved_site_detects_systems():
    """A normal, non-bot-protected site must yield real detections. This is the
    positive control — if this finds nothing, the whole pipeline is broken, not
    just the bot-protection path."""
    scanner = _scanner()
    result = await scanner.scan_website("https://www.wikipedia.org")
    _assert_scan_contract(result, "wikipedia.org")
    # Wikipedia exposes plenty of static markers; we expect *something*.
    assert result.detected_systems, "expected at least one system on a well-behaved site"


@pytest.mark.asyncio
async def test_live_scan_gucci_does_not_crash_or_fabricate():
    """gucci.com — the motivating case: JS-rendered Salesforce Commerce Cloud
    behind Akamai. We assert the honest contract (success, no crash, no
    fabricated challenge-vendor detection) and print whatever the full chain
    (live fetch → headless → DNS/CNAME → BuiltWith fallback) recovered. We do
    NOT require a specific platform, since that depends on uncontrollable live
    bot-protection state."""
    scanner = _scanner()
    result = await scanner.scan_website("https://www.gucci.com")
    _assert_scan_contract(result, "gucci.com")


@pytest.mark.asyncio
@pytest.mark.parametrize("url", [
    "https://www.klarna.com",   # known to have worked via static detection
    "https://www.nike.com",     # another large JS/bot-protected storefront
])
async def test_live_scan_bot_protected_storefronts(url):
    """Representative large storefronts that commonly sit behind bot protection.
    Same honest contract: never crash, never fabricate."""
    scanner = _scanner()
    result = await scanner.scan_website(url)
    _assert_scan_contract(result, url)


@pytest.mark.asyncio
async def test_live_builtwith_fallback_path_is_safe():
    """Directly exercise the BuiltWith fallback against the live builtwith.com.
    builtwith.com is itself Cloudflare-fronted, so this is the real test of the
    challenge-gating: the call must return a list (possibly empty if a hard
    CAPTCHA blocks us) and must NEVER raise, and must never contain only
    challenge-vendor names."""
    scanner = _scanner()
    systems = await scanner._query_builtwith("gucci.com")
    names = [s.name for s in systems]
    print(f"\n[live] builtwith fallback for gucci.com: {len(names)} systems → {names}")
    assert isinstance(systems, list)  # never raises; may be [] if hard-blocked
    if names:
        lowered = {n.lower() for n in names}
        non_challenge = lowered - _CHALLENGE_VENDOR_NAMES
        assert non_challenge or not (lowered & _CHALLENGE_VENDOR_NAMES), (
            f"builtwith fallback returned only challenge-vendor names {names}"
        )
