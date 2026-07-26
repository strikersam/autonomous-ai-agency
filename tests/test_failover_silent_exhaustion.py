"""Regression tests for a chain that fails silently.

From a real incident: `/api/doctor/public` reported 4/14 brain providers usable
while every dispatched task died with "All brain providers exhausted — none
configured or all in cooldown". Both were true at once, because the terminal
message was built only from the recorded failures and ignored what was actually
attempted — so a chain that ran four providers and got 410 Gone for every model
was worded identically to a deployment with no API keys at all.
"""
from __future__ import annotations

from packages.ai.failover_client import BrainFailoverExhausted, _untried_paid


class _P:
    def __init__(self, pid: str, tier: str = "free", healthy: bool = True) -> None:
        self.id = pid
        self.tier = tier
        self.is_healthy = healthy


class _FM:
    def __init__(self, providers: list[_P]) -> None:
        self._p = providers

    def get_providers(self) -> list[_P]:
        return self._p


# ── The terminal message ──────────────────────────────────────────────────────


def test_attempted_providers_are_named_not_denied() -> None:
    """The incident case: providers ran, none reported a reason."""
    exc = BrainFailoverExhausted("", {"groq", "nvidia"}, [])
    msg = str(exc)
    assert "none configured" not in msg, "must not deny that the chain ran"
    assert "2 provider(s)" in msg
    assert "groq" in msg and "nvidia" in msg
    # Points at the actual cause rather than sending the operator to check keys.
    assert "410" in msg


def test_nothing_attempted_still_reports_nothing_configured() -> None:
    """The genuinely-empty chain keeps its original, correct wording."""
    assert "none configured" in str(BrainFailoverExhausted("", set(), []))


def test_recorded_failures_take_precedence() -> None:
    exc = BrainFailoverExhausted("groq 429", {"groq"}, ["groq 429 rate-limited"])
    assert "1 brain provider attempt(s) failed" in str(exc)
    assert "groq 429 rate-limited" in str(exc)


def test_the_three_outcomes_are_distinguishable() -> None:
    """Each cause must read differently, or diagnosis is guesswork."""
    silent = str(BrainFailoverExhausted("", {"groq"}, []))
    empty = str(BrainFailoverExhausted("", set(), []))
    failed = str(BrainFailoverExhausted("x", {"groq"}, ["groq 500"]))
    assert len({silent, empty, failed}) == 3


# ── The paid reserve ──────────────────────────────────────────────────────────


def test_reserve_ignores_a_switched_off_paid_provider(monkeypatch) -> None:
    """A reserve held for an unreachable provider starves the free tier.

    `next_provider` filters disabled providers out, so counting one here made
    the chain hold back its last attempts for a provider it could never select.
    """
    monkeypatch.setattr(
        "services.brain_failover.disabled_providers",
        lambda force=False: {"anthropic": "auto: 402 out of credit"},
    )
    fm = _FM([_P("groq"), _P("anthropic", tier="paid")])
    assert _untried_paid(fm, set()) == set()


def test_reserve_ignores_a_cooling_paid_provider(monkeypatch) -> None:
    monkeypatch.setattr("services.brain_failover.disabled_providers", lambda force=False: {})
    fm = _FM([_P("groq"), _P("anthropic", tier="paid", healthy=False)])
    assert _untried_paid(fm, set()) == set()


def test_reserve_still_counts_a_usable_paid_provider(monkeypatch) -> None:
    """The cost-control behaviour itself must survive the fix."""
    monkeypatch.setattr("services.brain_failover.disabled_providers", lambda force=False: {})
    fm = _FM([_P("groq"), _P("anthropic", tier="paid")])
    assert _untried_paid(fm, set()) == {"anthropic"}


def test_reserve_excludes_already_tried_paid_providers(monkeypatch) -> None:
    monkeypatch.setattr("services.brain_failover.disabled_providers", lambda force=False: {})
    fm = _FM([_P("anthropic", tier="paid")])
    assert _untried_paid(fm, {"anthropic"}) == set()


def test_reserve_survives_a_failing_disabled_lookup(monkeypatch) -> None:
    """Reserve logic must never break the chain it is meant to protect."""
    def _boom(force=False):
        raise RuntimeError("store down")
    monkeypatch.setattr("services.brain_failover.disabled_providers", _boom)
    fm = _FM([_P("anthropic", tier="paid")])
    assert _untried_paid(fm, set()) == {"anthropic"}
