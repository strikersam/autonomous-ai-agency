"""packages/ai/failover_client.py — one dispatcher for the brain-failover chain.

``services/brain_failover`` decides *which* provider to try next; this module is
the single place that actually performs the HTTP call against it, handling the
per-status failover rules and the Anthropic wire format.

Why it exists
-------------
The dispatch loop used to live inline inside ``AgentRunner._chat_text``, which
meant only the agent loop could reach the env-configured provider chain
(nvidia, groq, cerebras, zai, zhipu, deepseek, together, dashscope, moonshot,
mistral, aerolink, openrouter, minimax, google, anthropic, ollama). Everything
routed through ``backend.server.call_llm`` — the CEO strategic assessment above
all — fell back only across the DB-configured ``providers`` records, so when
those were rate-limited the CEO dropped straight to its rule-based path while
the agent loop still had a dozen untried providers available.

Extracting the loop here gives both callers the same breadth from one
implementation, per the repository rule that no logic may be duplicated.

Policy is unchanged: paid providers are admitted to the chain only by
``services.brain_failover._build_registry``, which gates them behind
``ALLOW_PAID_BRAIN`` or the Providers UI toggle. This module never widens that.
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("qwen-proxy")

# Models tried per provider before moving on. A provider that 410s its default
# model may still serve an alternate, but past three the next provider is the
# better bet.
_MAX_MODELS_PER_PROVIDER = 3

_DEFAULT_TIMEOUT_SEC = 120.0
_CONNECT_TIMEOUT_SEC = 10.0


def _env_int(name: str, default: int) -> int:
    try:
        return max(1, int((os.environ.get(name) or "").strip() or default))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return max(1.0, float((os.environ.get(name) or "").strip() or default))
    except (TypeError, ValueError):
        return default


# ── Fan-out budget ───────────────────────────────────────────────────────────
#
# Without a cap the attempt count MULTIPLIES and self-inflicts the very 429s it
# is trying to route around. Measured on the real registry:
#
#   14 providers x 3 models                        =  42 HTTP calls per call
#   x up to 4 _chat_json parse retries             = 168 per planning step
#   x _DISPATCH_RETRY_LIMIT (5) task re-queues     = 840 per task
#
# ...and the agency runs many tasks plus 34 loops concurrently. No free tier
# survives that, so every provider returns 429 and every task ends up BLOCKED —
# which looks like "all providers are broken" when the caller is the cause.
#
# These two budgets bound one logical completion. BRAIN_MAX_PROVIDER_ATTEMPTS is
# the total HTTP attempts across ALL providers and models (not per provider), so
# the worst case is linear instead of the product above. Raise it if you have
# paid capacity and want more breadth; lower it to protect a tight free tier.
_MAX_TOTAL_ATTEMPTS = _env_int("BRAIN_MAX_PROVIDER_ATTEMPTS", 6)
_WALL_CLOCK_BUDGET_SEC = _env_float("BRAIN_FAILOVER_BUDGET_SEC", 180.0)

# ...but a flat cap alone STARVES the paid tier, which is the whole point of
# having one. Providers are ordered free → local → paid, so an operator with ten
# free keys configured spends all six attempts inside the free tier and the chain
# raises BrainFailoverExhausted having never contacted the paid provider they are
# actually paying for. Measured, not inferred: with ten free providers all
# returning 429 the chain stopped at the sixth free provider and never reached
# Aerolink — so paid capacity bought to cover exactly this situation (free tiers
# rate-limited) could not be used at all.
#
# This reserves a slice of the budget that ONLY paid-tier providers may spend.
# The reserve is inert unless a paid provider is both admitted (allow_paid, which
# is still the sole spend gate) and untried, so an operator running free-only
# keeps the entire budget for the free tier and sees no change.
_PAID_RESERVE_ATTEMPTS = _env_int("BRAIN_PAID_RESERVE_ATTEMPTS", 2)


class BrainFailoverExhausted(RuntimeError):
    """Every provider in the failover chain failed — the terminal error.

    Carries the reason **every** provider failed, not just the last one. Reporting
    only the last error made a whole-chain outage look like a single-provider
    problem: an operator seeing "401 Unauthorized for open.bigmodel.cn" would fix
    the Zhipu key and still be dead, because four other providers were also
    failing for their own reasons. ``failures`` lists each one so the real
    remediation is visible from the message alone.
    """

    def __init__(
        self,
        last_error: str,
        tried: set[str] | None = None,
        failures: list[str] | None = None,
    ) -> None:
        self.last_error = last_error
        self.tried = set(tried or ())
        self.failures = list(failures or ())
        if self.failures:
            detail = "; ".join(self.failures)
            super().__init__(
                f"All {len(self.failures)} brain provider attempt(s) failed: {detail}"
            )
        elif last_error:
            super().__init__(f"All brain providers exhausted. Last error: {last_error}")
        else:
            super().__init__(
                "All brain providers exhausted — none configured or all in cooldown."
            )


class _Budget:
    """Shared attempt + wall-clock budget for one logical completion.

    Bounds the whole chain rather than each provider, so the cost of a failing
    call is linear in the budget instead of the product of providers x models x
    parse retries x task re-queues.
    """

    def __init__(self, max_attempts: int, deadline_sec: float) -> None:
        self._max = max_attempts
        self._used = 0
        self._started = time.monotonic()
        self._deadline = deadline_sec

    def charge(self) -> None:
        self._used += 1

    def spent(self) -> bool:
        if self._used >= self._max:
            return True
        return (time.monotonic() - self._started) >= self._deadline

    def unpaid_slice_spent(self, reserve: int) -> bool:
        """True when free/local providers have used everything but the reserve.

        Only the attempt count is reserved, never the wall clock: holding back
        seconds would let the deadline expire with the reserve unspent, which is
        the starvation this exists to prevent.
        """
        return reserve > 0 and self._used >= max(self._max - reserve, 1)

    @property
    def used(self) -> int:
        return self._used

    def reason(self) -> str:
        if self._used >= self._max:
            return (
                f"attempt budget exhausted after {self._used} provider attempt(s) "
                f"(BRAIN_MAX_PROVIDER_ATTEMPTS={self._max})"
            )
        return (
            f"time budget exhausted after {self._used} attempt(s) "
            f"(BRAIN_FAILOVER_BUDGET_SEC={self._deadline:.0f}s)"
        )


@dataclass
class FailoverResult:
    """A successful completion plus the accounting its callers need."""

    text: str
    model: str
    provider_id: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms: int = 0
    attempts: list[str] = field(default_factory=list)


def _build_request(provider: Any) -> tuple[str, dict[str, str], bool]:
    """Return ``(url, headers, is_anthropic_native)`` for *provider*.

    Anthropic's native API has no ``/chat/completions`` route and rejects
    ``Authorization: Bearer``, so sending it the OpenAI-compatible shape returns
    a deterministic 400 for every model. OpenAI-compatible Claude gateways
    (OpenRouter, Aerolink) are not Anthropic-native and keep the standard path.
    """
    from packages.ai.router import (
        ProviderConfig,
        _openai_url,
        is_anthropic_base_url,
    )

    if is_anthropic_base_url(provider.base_url):
        cfg = ProviderConfig(
            provider_id=provider.id,
            type="anthropic",
            base_url=provider.base_url,
            api_key=provider.api_key or None,
        )
        return f"{cfg.normalized_base_url}/v1/messages", cfg.auth_headers(), True

    headers = {"Content-Type": "application/json"}
    if provider.api_key:
        headers["Authorization"] = f"Bearer {provider.api_key}"
    return _openai_url(provider.base_url, "/chat/completions"), headers, False


def _is_ollama(provider: Any) -> bool:
    return (
        "ollama" in (getattr(provider, "id", "") or "").lower()
        or ":11434" in (getattr(provider, "base_url", "") or "")
    )


_BILLING_SIGNALS: tuple[str, ...] = (
    "credit balance is too low",
    "insufficient balance",
    "insufficient_quota",
    "quota exceeded",
    "billing",
    "payment required",
    "exceeded your current quota",
)


def _is_billing_refusal(resp: httpx.Response) -> bool:
    """True when a 4xx body says the account is out of credit or quota.

    Providers disagree on the status code for "you have no money": DeepSeek uses
    402, Anthropic uses 400 with an ``invalid_request_error``. Both mean every
    model on that provider will refuse identically, so both must fail over to the
    next provider instead of burning the remaining model attempts.
    """
    if not (400 <= resp.status_code < 500):
        return False
    try:
        body = resp.text[:600].lower()
    except Exception:  # noqa: BLE001 — a body we cannot read is not a billing signal
        return False
    return any(signal in body for signal in _BILLING_SIGNALS)


def _auto_disable(provider_id: str, reason: str) -> None:
    """Take a permanently-broken provider out of rotation until a human returns it.

    Only called for states no retry can fix: an invalid key, an empty balance, or
    an account with no access to any of the provider's models. Transient states
    (429, 5xx, network) are deliberately excluded — they already have circuit
    breakers, and disabling on a 429 would switch off every free provider the
    first time a burst tripped a rate limit.
    """
    try:
        from services.brain_failover import auto_disable_provider
        auto_disable_provider(provider_id, reason)
    except Exception as exc:  # noqa: BLE001 — never fail a call over bookkeeping
        log.debug("brain_failover: auto-disable of %s failed: %s", provider_id, exc)


def _parse_success(resp: httpx.Response) -> tuple[str, int, int]:
    """Extract ``(text, prompt_tokens, completion_tokens)`` from a 2xx body.

    Raises ``ValueError``/``KeyError``/``IndexError``/``TypeError`` on a
    malformed body so the caller can treat it as a failed attempt and fail over
    rather than propagating the parse error out of the dispatcher.
    """
    data = resp.json()
    usage = data.get("usage") if isinstance(data, dict) else {}
    usage = usage if isinstance(usage, dict) else {}
    text = data["choices"][0]["message"]["content"]
    if text is None:
        raise ValueError("provider returned a null message content")
    return (
        text,
        int(usage.get("prompt_tokens") or 0),
        int(usage.get("completion_tokens") or 0),
    )


async def _try_provider(
    provider: Any,
    payload: dict[str, Any],
    fm: Any,
    attempts: list[str],
    timeout_sec: float,
    budget: "_Budget",
) -> tuple[FailoverResult | None, str]:
    """Try up to ``_MAX_MODELS_PER_PROVIDER`` models on one provider.

    Returns ``(result, last_error)``. ``result`` is ``None`` when every model on
    this provider failed, in which case the caller moves to the next provider.

    Every failure here is logged at WARNING, never ERROR: while the chain still
    has untried providers a single provider failing is a recoverable step, not an
    outage. Only the caller, once the whole chain is exhausted, logs an error.
    This also keeps ``agent/log_monitor``'s ERROR-triggered issue-filing from
    opening a ticket for a provider the system successfully failed over.
    """
    from packages.ai.router import ProviderRouter, with_ollama_reasoning_effort

    requested_model = str(payload.get("model") or "")
    chat_url, headers, is_anthropic = _build_request(provider)
    provider_model = fm.resolve_model(provider, requested_model)
    models_to_try = [provider_model] + [
        m for m in provider.models if m != provider_model
    ]
    last_error = ""

    for try_model in models_to_try[:_MAX_MODELS_PER_PROVIDER]:
        if budget.spent():
            return None, last_error or f"{provider.id} skipped (budget spent)"
        budget.charge()
        call_payload = {**payload, "model": try_model}
        post_payload = with_ollama_reasoning_effort(
            call_payload, is_ollama=_is_ollama(provider)
        )
        if is_anthropic:
            post_payload = ProviderRouter._anthropic_payload(post_payload)

        attempts.append(f"{provider.id}/{try_model}")
        call_start = time.perf_counter()
        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(timeout_sec, connect=_CONNECT_TIMEOUT_SEC)
            ) as client:
                resp = await client.post(chat_url, json=post_payload, headers=headers)
        except Exception as exc:  # noqa: BLE001 — network errors fail over
            log.warning("brain_failover: %s network error: %s", provider.id, exc)
            fm.record_failure(provider.id, "network_error")
            return None, f"{provider.id} network error: {exc}"

        call_ms = int((time.perf_counter() - call_start) * 1000)

        if resp.status_code < 400:
            fm.record_success(provider.id, latency_ms=call_ms)
            if is_anthropic:
                resp = ProviderRouter._anthropic_to_openai_response(resp, try_model)
            try:
                text, prompt_tokens, completion_tokens = _parse_success(resp)
            except (ValueError, KeyError, IndexError, TypeError) as exc:
                # A 2xx with an unusable body is a failed attempt, not a crash —
                # the dispatcher must never surface a partial result.
                last_error = f"{provider.id} malformed success response: {exc}"
                log.warning(
                    "brain_failover: %s returned an unparsable body: %s",
                    provider.id, exc,
                )
                continue
            return (
                FailoverResult(
                    text=text,
                    model=try_model,
                    provider_id=provider.id,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    latency_ms=call_ms,
                    attempts=list(attempts),
                ),
                last_error,
            )

        if resp.status_code == 410:
            # Model permanently gone — another model on this provider may serve.
            log.warning(
                "brain_failover: %s model %s 410 Gone - trying next model",
                provider.id, try_model,
            )
            continue

        # The remaining statuses fail identically for every model on this
        # provider, so trying another model here would repeat the same error.
        if resp.status_code in (429, 419):
            fm.record_failure(provider.id, "rate_limited", resp.status_code)
            return None, f"{provider.id} {resp.status_code} rate-limited"
        if resp.status_code == 413:
            fm.record_failure(provider.id, "payload_too_large", resp.status_code)
            return None, f"{provider.id} 413 payload too large"
        if resp.status_code in (401, 403):
            fm.record_failure(provider.id, "auth_failed", resp.status_code)
            _auto_disable(provider.id, f"{resp.status_code} invalid or expired API key")
            return None, f"{provider.id} {resp.status_code} unauthorized/forbidden"
        if resp.status_code == 402:
            fm.record_failure(provider.id, "payment_required", resp.status_code)
            _auto_disable(provider.id, "402 out of credit")
            return None, f"{provider.id} 402 payment required (out of credit)"
        if resp.status_code >= 500:
            fm.record_failure(provider.id, "server_error", resp.status_code)
            return None, f"{provider.id} {resp.status_code} server error"

        # A 4xx that is really a billing/quota refusal, not a bad request.
        # Anthropic returns 400 with "credit balance is too low" — semantically
        # the same class as 402: no model on this provider can succeed, so the
        # next two model attempts are guaranteed to repeat it verbatim.
        if _is_billing_refusal(resp):
            fm.record_failure(provider.id, "payment_required", resp.status_code)
            _auto_disable(provider.id, f"{resp.status_code} out of credit/quota")
            return None, (
                f"{provider.id} {resp.status_code} out of credit/quota: "
                f"{resp.text[:120]}"
            )

        last_error = f"{provider.id} {resp.status_code}: {resp.text[:200]}"
        log.warning(
            "brain_failover: %s model %s returned %d - trying next model",
            provider.id, try_model, resp.status_code,
        )

    fm.record_failure(provider.id, "all_models_failed")
    if "model_not_found" in (last_error or "") or "does not exist" in (last_error or ""):
        # Every model on this provider was rejected as unknown/inaccessible —
        # an account-entitlement or config problem, not something that self-heals.
        _auto_disable(provider.id, "no accessible model (404 model_not_found)")
    return None, last_error


def _log_recovery(result: FailoverResult, failures: list[str]) -> None:
    """Report a successful failover at INFO — recovery is not an incident.

    Everything logged before this point was a warning, so a call that recovered
    leaves no ERROR behind, and ``agent/log_monitor`` files no issue for it.
    """
    if failures:
        log.info(
            "brain_failover: recovered via %s/%s after %d failed attempt(s): %s",
            result.provider_id, result.model, len(failures), "; ".join(failures),
        )


def _log_exhaustion(attempted: list[str], failures: list[str]) -> None:
    """The one and only error-level log in the dispatch path.

    Emitted solely when the chain is exhausted and the caller genuinely cannot
    proceed, and it names every provider that failed so the log line alone is
    enough to act on.

    Takes ``attempted`` (an append-only list) rather than the caller's ``tried``
    set: ``tried`` is the exclusion set and ``_recover_all_unhealthy`` clears it
    so providers can be retried after a breaker reset, which made it wrong for
    reporting — production logs showed ``tried=[9 providers]`` beside 14 distinct
    failures, with one provider listed twice. ``failures`` is deduped by the
    caller for the same reason.
    """
    log.error(
        "brain_failover: all %d provider(s) exhausted (%s) — %s",
        len(attempted), ", ".join(attempted) or "none",
        "; ".join(failures) or "no provider attempted",
    )


def _untried_paid(fm: Any, tried: set[str]) -> set[str]:
    """Paid-tier providers admitted to the chain and not yet attempted.

    Empty when the operator has not enabled paid providers — ``_build_registry``
    is the sole spend gate and simply omits them — which is what keeps the paid
    reserve inert for a free-only deployment.
    """
    return {
        p.id for p in fm.get_providers()
        if getattr(p, "tier", "") == "paid" and p.id not in tried
    }


def _select_provider(
    fm: Any, budget: "_Budget", tried: set[str], requested_model: str
) -> Any | None:
    """Pick the next provider, honouring the paid reserve.

    Once free/local providers have spent everything but the reserve, they are
    excluded so the remaining attempts can only go to a paid provider. Without
    this the free tier consumes the whole budget and the paid escape hatch — the
    one an operator is paying for precisely because the free tiers are
    rate-limited — is never contacted.
    """
    exclude = tried
    paid = _untried_paid(fm, tried)
    if paid and budget.unpaid_slice_spent(_PAID_RESERVE_ATTEMPTS):
        exclude = tried | {p.id for p in fm.get_providers() if p.id not in paid}
        log.info(
            "brain_failover: free tier used %d of %d attempts — reserving the "
            "remainder for the paid tier (%s)",
            budget.used, _MAX_TOTAL_ATTEMPTS, ", ".join(sorted(paid)),
        )
    provider = fm.next_provider(exclude=exclude, requested_model=requested_model)
    if provider is None and exclude is not tried:
        # No paid provider is selectable (all in cooldown). Fall back to the
        # normal chain rather than giving up with budget still unspent.
        provider = fm.next_provider(exclude=tried, requested_model=requested_model)
    return provider


def _recover_all_unhealthy(
    fm: Any, tried: set[str], requested_model: str
) -> Any | None:
    """Reset every circuit breaker when they have all tripped, and re-select.

    Without this the system deadlocks with no usable brain until the 5-minute
    self-heal tick lands. Returns the next provider to try, or ``None`` when
    some providers are still healthy (so the exhaustion was genuine).
    """
    all_providers = fm.get_providers()
    if not all_providers or any(p.is_healthy for p in all_providers):
        return None
    log.warning(
        "brain_failover: all %d providers unhealthy — resetting circuit "
        "breakers inline (tried=%s)",
        len(all_providers), tried,
    )
    for p in all_providers:
        fm.record_success(p.id)
    tried.clear()
    return fm.next_provider(exclude=tried, requested_model=requested_model)


async def failover_chat_completion(
    payload: dict[str, Any],
    *,
    timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
) -> FailoverResult:
    """Run one chat completion across the brain-failover chain.

    Tries each healthy provider in ``services.brain_failover`` order (free, then
    local, then paid), and up to three models per provider. Raises
    :class:`BrainFailoverExhausted` when nothing succeeds — never returns a
    partial or placeholder result.
    """
    from services.brain_failover import get_failover_manager

    requested_model = str(payload.get("model") or "")
    fm = get_failover_manager()
    budget = _Budget(_MAX_TOTAL_ATTEMPTS, _WALL_CLOCK_BUDGET_SEC)
    tried: set[str] = set()          # exclusion set; cleared on breaker reset
    attempted: list[str] = []        # append-only record, for reporting
    attempts: list[str] = []
    failures: list[str] = []
    last_error = ""

    for _attempt in range(fm.max_attempts()):
        if budget.spent():
            failures = list(dict.fromkeys([*failures, budget.reason()]))
            break
        provider = _select_provider(fm, budget, tried, requested_model)
        if provider is None:
            provider = _recover_all_unhealthy(fm, tried, requested_model)
            if provider is None:
                # Falls through to the single terminal error below, not two.
                log.warning("brain_failover: no healthy providers left")
                break

        tried.add(provider.id)
        attempted = list(dict.fromkeys([*attempted, provider.id]))
        result, provider_error = await _try_provider(
            provider, payload, fm, attempts, timeout_sec, budget
        )
        if result is not None:
            _log_recovery(result, failures)
            return result
        if provider_error:
            failures = list(dict.fromkeys([*failures, provider_error]))
            last_error = provider_error

    _log_exhaustion(attempted, failures)
    raise BrainFailoverExhausted(last_error, set(attempted), failures)
