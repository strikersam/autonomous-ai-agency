"""packages/llm/router.py — LLMRouter, the single LLM gateway.

Every agent, endpoint, and background loop reaches a model through this class.
Nothing above it constructs an HTTP client aimed at a model endpoint.

One request walks this path:

    policy      per-agent overrides merge into the request
    budget      pre-flight spend check
    cache       exact key, then optional semantic lookup
    dedupe      collapse onto an identical in-flight call
    queue       admission control and global concurrency
    candidates  provider x model pairs that satisfy the capabilities
    strategy    order the candidates
    attempt     bulkhead -> pace -> key -> HTTP -> classify
    record      health, metrics, budget

On failure the attempt loop penalises the narrowest scope that explains it —
key, model, or provider (ADR-008 §4) — then continues down the ordered
candidate list. A request only fails when every candidate is exhausted, the
attempt budget is spent, or the error was permanent.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from collections.abc import AsyncIterator
from dataclasses import replace
from typing import Any

import httpx

from packages.llm.budget import get_budget
from packages.llm.cache import get_cache, payload_key
from packages.llm.config import (
    AgentPolicy,
    LLMConfig,
    ModelConfig,
    ProviderConfig,
    get_config,
)
from packages.llm.context import ContextManager, build_summariser
from packages.llm.distributed import get_limiter
from packages.llm.health import get_tracker
from packages.llm.keys import get_ring, resolve_keys
from packages.llm.metrics import get_metrics
from packages.llm.providers import LLMProvider, build_provider
from packages.llm.queue import Bulkhead, Deduplicator, RequestQueue, request_fingerprint
from packages.llm.registry import get_registry
from packages.llm.retry import RetryBudget, compute_delay, is_retryable
from packages.llm.strategies import (
    Candidate,
    RoutingContext,
    get_strategy,
    strategy_names,
)
from packages.llm.types import (
    Attempt,
    LLMRequest,
    LLMResponse,
    PermanentError,
    Priority,
    RouterExhausted,
    StreamChunk,
    TransientError,
    Usage,
)

log = logging.getLogger("llm.router")


class LLMRouter:
    """The gateway. One instance per process; use :func:`get_router`."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self._config = config or get_config()
        self._providers: dict[str, LLMProvider] = {}
        self._client: httpx.AsyncClient | None = None
        self._client_lock = asyncio.Lock()

        self._health = get_tracker()
        self._keys = get_ring()
        self._cache = get_cache()
        self._metrics = get_metrics()
        self._budget = get_budget()
        self._registry = get_registry()
        self._limiter = get_limiter()

        routing = self._config.routing
        self._queue = RequestQueue(
            max_depth=routing.queue_max_depth,
            max_concurrency=routing.global_max_concurrency,
        )
        self._bulkhead = Bulkhead()
        self._dedupe: Deduplicator[LLMResponse] = Deduplicator(routing.dedupe_window_sec)
        self._context = ContextManager(summarise=build_summariser(self._summariser_chat))

        self._build_providers()

    # ── Setup ───────────────────────────────────────────────────────────────

    def _build_providers(self) -> None:
        for config in self._config.enabled_providers():
            if config.requires_key and not resolve_keys(config.key_env):
                log.debug("llm.router: %s has no key configured — skipping", config.id)
                continue
            self._providers[config.id] = build_provider(config)
            self._bulkhead.configure(config.id, config.max_concurrency)
        log.info(
            "llm.router: %d provider(s) ready: %s",
            len(self._providers), ", ".join(sorted(self._providers)) or "none",
        )

    async def _http(self) -> httpx.AsyncClient:
        """One shared connection pool. Reconnects if it was closed."""
        if self._client is None or self._client.is_closed:
            async with self._client_lock:
                if self._client is None or self._client.is_closed:
                    self._client = httpx.AsyncClient(
                        timeout=httpx.Timeout(120.0, connect=10.0),
                        limits=httpx.Limits(
                            max_connections=100, max_keepalive_connections=20
                        ),
                        follow_redirects=True,
                    )
        return self._client

    @property
    def config(self) -> LLMConfig:
        return self._config

    @property
    def providers(self) -> dict[str, LLMProvider]:
        return dict(self._providers)

    # ── Public API ──────────────────────────────────────────────────────────

    async def chat(self, request: LLMRequest) -> LLMResponse:
        """Route one completion, retrying and failing over until it succeeds."""
        request = self._apply_policy(request)
        self._budget.check_affordable()

        cached = self._lookup_cache(request)
        if cached is not None:
            return cached

        if not self._config.routing.queue_enabled:
            return await self._dispatch(request)

        fingerprint = request_fingerprint(self._cache_payload(request))

        async def run() -> LLMResponse:
            result, deduped = await self._dedupe.run(
                fingerprint, lambda: self._dispatch(request)
            )
            if deduped:
                # Never hand the same mutable object to two callers.
                return replace(result, cached=True)
            return result

        self._metrics.set_queue_depth(self._queue.depth)
        return await self._queue.submit(
            run, priority=request.priority, timeout=request.timeout_sec
        )

    async def stream(self, request: LLMRequest) -> AsyncIterator[StreamChunk]:
        """Stream one completion with the same failover behaviour.

        Failover applies only until the first chunk is delivered. Once the
        caller has seen output, switching providers mid-stream would splice two
        different generations together, so a later failure surfaces as an error
        rather than a silent restart.
        """
        request = self._apply_policy(replace(request, stream=True))
        candidates = self._candidates(request)
        if not candidates:
            raise RouterExhausted([], "no provider satisfies the request")

        budget = self._retry_budget(request)
        attempts: list[Attempt] = []
        client = await self._http()

        for candidate in candidates:
            if budget.exhausted():
                break
            provider = self._providers.get(candidate.provider.id)
            if provider is None or not self._health.is_available(candidate.provider.id):
                continue

            keys = resolve_keys(candidate.provider.key_env)
            api_key, key_index = self._keys.acquire(
                candidate.provider.id, keys, env_names=candidate.provider.key_env
            )
            if api_key is None:
                continue

            budget.charge()
            attempt = Attempt(
                provider=candidate.provider.id, model=candidate.model.id, key_index=key_index
            )
            started = time.monotonic()
            first_chunk = True
            try:
                async with self._bulkhead.slot(candidate.provider.id, timeout=15.0) as got_slot:
                    if not got_slot:
                        continue
                    async for chunk in provider.stream(
                        request, model=candidate.model.id, api_key=api_key, client=client
                    ):
                        if first_chunk:
                            first_chunk = False
                            attempt.ok = True
                        yield chunk
                latency_ms = int((time.monotonic() - started) * 1000)
                attempt.latency_ms = latency_ms
                attempts.append(attempt)
                self._health.record_success(candidate.provider.id, latency_ms=latency_ms)
                self._keys.record_success(candidate.provider.id, api_key)
                self._metrics.record_request(
                    provider=candidate.provider.id, model=candidate.model.id,
                    outcome="success", latency_sec=latency_ms / 1000.0,
                    agent=request.agent or "", fallbacks=len(attempts) - 1,
                )
                return
            except Exception as exc:
                latency_ms = int((time.monotonic() - started) * 1000)
                attempt.latency_ms = latency_ms
                attempt.error = str(exc)[:300]
                attempts.append(attempt)
                self._penalise(candidate, exc, api_key, latency_ms=latency_ms)
                if not first_chunk:
                    # Output already reached the caller — do not restart.
                    raise
                if isinstance(exc, PermanentError) and request.pin_model:
                    raise
                continue

        raise RouterExhausted(attempts, "streaming candidates exhausted")

    async def embed(self, texts: list[str], *, model: str | None = None) -> list[list[float]]:
        """Embed texts, caching each vector by content hash.

        Embeddings are perfectly cacheable — the same text always yields the
        same vector for a given model — so the cache is checked per input, not
        per batch.
        """
        from packages.llm.cache import text_key

        results: list[list[float]] = []
        pending: list[tuple[int, str]] = []
        for index, text in enumerate(texts):
            hit = self._cache.embedding.get(text_key(f"{model}:{text}"))
            results.append(hit if hit is not None else [])
            if hit is None:
                pending.append((index, text))

        if not pending:
            self._metrics.record_cache(layer="embedding", hit=True)
            return results

        candidates = self._registry.candidates(require_embeddings=True, require_chat=False)
        if model:
            spec = self._registry.get(model)
            if spec is not None:
                candidates = [spec, *candidates]
        client = await self._http()

        for spec in candidates:
            provider = self._providers.get(spec.provider)
            if provider is None or not self._health.is_available(spec.provider):
                continue
            keys = resolve_keys(provider.config.key_env)
            api_key, _index = self._keys.acquire(
                spec.provider, keys, env_names=provider.config.key_env
            )
            if api_key is None:
                continue
            try:
                response = await client.post(
                    f"{provider.config.base_url.rstrip('/')}/embeddings",
                    json={"model": spec.id, "input": [text for _i, text in pending]},
                    headers={"Content-Type": "application/json",
                             **provider.auth_headers(api_key)},
                    timeout=60.0,
                )
                if response.status_code >= 400:
                    raise TransientError(f"{spec.provider} HTTP {response.status_code}")
                vectors = [
                    list(entry.get("embedding") or [])
                    for entry in (response.json().get("data") or [])
                ]
            except Exception as exc:
                self._health.record_failure(spec.provider, error=str(exc)[:200])
                continue

            for (index, text), vector in zip(pending, vectors):
                results[index] = vector
                self._cache.embedding.put(text_key(f"{model}:{text}"), vector)
            self._health.record_success(spec.provider)
            self._metrics.record_cache(layer="embedding", hit=False)
            return results

        raise RouterExhausted([], "no embedding provider available")

    # ── Policy and candidates ───────────────────────────────────────────────

    def _apply_policy(self, request: LLMRequest) -> LLMRequest:
        """Merge the per-agent policy into the request.

        The request always wins over the policy: an explicit
        ``LLMRequest.strategy`` is a deliberate caller decision, while the
        policy is a default for that agent.
        """
        policy: AgentPolicy | None = self._config.policy_for(request.agent)
        if policy is None:
            if request.allow_paid is None:
                return replace(request, allow_paid=self._config.routing.allow_paid)
            return request

        allow_paid = request.allow_paid
        if allow_paid is None:
            allow_paid = (
                policy.allow_paid
                if policy.allow_paid is not None
                else self._config.routing.allow_paid
            )

        excluded = list(dict.fromkeys([*request.exclude_providers, *policy.exclude_providers]))
        priority = request.priority
        if policy.priority:
            try:
                priority = Priority[policy.priority.upper()]
            except KeyError:
                log.warning("llm.router: unknown priority %r in policy %r",
                            policy.priority, policy.name)

        return replace(
            request,
            strategy=request.strategy or policy.strategy or None,
            allow_paid=allow_paid,
            exclude_providers=excluded,
            providers=request.providers or (policy.prefer_providers or None),
            priority=priority,
        )

    def _candidates(self, request: LLMRequest) -> list[Candidate]:
        """Build and order the (provider, model) pairs that can serve ``request``."""
        routing = self._config.routing
        allow_paid = bool(request.allow_paid)
        needed_context = request.approx_prompt_tokens() + request.max_tokens

        pinned: ModelConfig | None = None
        if request.model:
            pinned = self._registry.get(request.model)

        pool: list[Candidate] = []
        for provider_id, provider in self._providers.items():
            config = provider.config
            if provider_id in request.exclude_providers:
                continue
            if request.providers and provider_id not in request.providers:
                continue
            if config.is_paid and not allow_paid:
                continue

            for model in self._models_for(config, pinned, request, allow_paid):
                if not model.supports_chat:
                    continue
                if request.requires_tools() and not (
                    model.supports_tools or model.supports_function_calling
                ):
                    continue
                if request.requires_vision() and not model.supports_images:
                    continue
                if request.stream and not model.supports_streaming:
                    continue
                pool.append(Candidate(
                    provider=config,
                    model=model,
                    in_flight=self._bulkhead.in_flight(provider_id),
                ))

        if not pool:
            return []

        # Prefer models that fit the prompt, but keep the rest as a tail: the
        # context manager can shrink the conversation to make a smaller model
        # work when nothing larger is reachable.
        fitting = [c for c in pool if c.model.context_window >= needed_context]
        ordered_pool = fitting if fitting else pool

        context = RoutingContext(
            request=request,
            health=self._health,
            routing=routing,
            in_flight=self._bulkhead.in_flight(),
            window_sec=self._config.health.window_sec,
        )
        strategy = get_strategy(request.strategy or routing.strategy)
        ordered = strategy(ordered_pool, context)

        if fitting and routing.escalate_context:
            # Append the non-fitting models so a context-overflow retry still
            # has somewhere to go rather than failing outright.
            ordered = ordered + [c for c in pool if c not in fitting]

        return self._limit(ordered, routing.max_providers_per_request,
                           routing.max_models_per_provider)

    def _models_for(
        self,
        config: ProviderConfig,
        pinned: ModelConfig | None,
        request: LLMRequest,
        allow_paid: bool,
    ) -> list[ModelConfig]:
        """The models to consider on one provider."""
        if pinned is not None and pinned.provider == config.id:
            if request.pin_model:
                return [pinned]
            others = [
                m for m in self._registry.for_provider(config.id) if m.id != pinned.id
            ]
            return [pinned, *others]
        if request.pin_model:
            # The pinned model lives elsewhere — this provider cannot serve it,
            # unless it is an OpenAI-compatible gateway that proxies model ids.
            if pinned is not None and config.kind not in {"openai", "litellm"}:
                return []
            if pinned is not None:
                return [self._registry.with_provider(pinned, config.id)]
            return []

        models = self._registry.for_provider(config.id)
        if not models and config.default_model:
            spec = self._registry.get(config.default_model)
            models = [spec] if spec else []
        if not allow_paid:
            models = [m for m in models if m.is_free]
        return models

    @staticmethod
    def _limit(
        candidates: list[Candidate], max_providers: int, max_models: int
    ) -> list[Candidate]:
        """Cap the breadth of one request's search so a failure is bounded."""
        per_provider: dict[str, int] = {}
        seen_providers: list[str] = []
        limited: list[Candidate] = []
        for candidate in candidates:
            provider_id = candidate.provider.id
            if provider_id not in seen_providers:
                if len(seen_providers) >= max_providers:
                    continue
                seen_providers.append(provider_id)
            used = per_provider.get(provider_id, 0)
            if used >= max_models:
                continue
            per_provider[provider_id] = used + 1
            limited.append(candidate)
        return limited

    # ── Dispatch ────────────────────────────────────────────────────────────

    def _retry_budget(self, request: LLMRequest) -> RetryBudget:
        retry = self._config.routing.retry
        return RetryBudget(
            max_attempts=request.max_attempts or retry.max_attempts,
            deadline_sec=min(retry.budget_sec, request.timeout_sec),
        )

    async def _dispatch(self, request: LLMRequest) -> LLMResponse:
        """Walk the ordered candidates until one succeeds."""
        candidates = self._candidates(request)
        if not candidates:
            raise RouterExhausted([], self._no_candidate_reason(request))

        budget = self._retry_budget(request)
        attempts: list[Attempt] = []
        last_error: BaseException | None = None
        client = await self._http()
        started = time.monotonic()

        for candidate in candidates:
            if budget.exhausted():
                break
            provider = self._providers.get(candidate.provider.id)
            if provider is None:
                continue
            if not self._health.is_available(candidate.provider.id):
                continue
            if not self._health.acquire_probe(candidate.provider.id):
                continue

            # Retry the same candidate while the failure is key-scoped and the
            # provider still has an uncooled key. A 429 on one key is evidence
            # about that key, not about the provider — leaving for another
            # provider would waste the healthy keys sitting right here, which
            # is the whole reason keys are pooled (ADR-008 §4).
            #
            # ``attempt`` is left set only while it still needs recording. It is
            # cleared once appended, so the post-loop append cannot duplicate it,
            # and an all-None triple means "this candidate was skipped entirely"
            # (no key free, bulkhead full, or rate-limit pacing gave up).
            provider_id = candidate.provider.id
            key_attempts = max(1, len(resolve_keys(candidate.provider.key_env)))
            attempt = response = error = None
            for _rotation in range(key_attempts):
                if budget.exhausted():
                    break
                attempt, response, error = await self._attempt(
                    provider, candidate, request, client, budget
                )
                if response is not None or attempt is None:
                    break                              # success, or nothing tried
                attempts.append(attempt)
                if getattr(error, "scope", None) != "key":
                    break                              # not a key problem — move on
                if self._keys.all_cooling(
                    provider_id, resolve_keys(candidate.provider.key_env)
                ):
                    log.debug("llm.router: every key for %s is cooling", provider_id)
                    break
                self._metrics.record_retry(provider=provider_id, reason="key_rotation")
                attempt = None                         # recorded; do not append twice

            if attempt is not None and response is not None:
                attempts.append(attempt)
            if attempt is None and response is None and error is None:
                continue                               # candidate skipped, not failed

            if response is not None:
                response.attempts = attempts
                self._finalise(response, request, started)
                return response

            last_error = error
            if isinstance(error, PermanentError):
                if request.pin_model or self._is_fatal(error):
                    raise error
                # A permanent error on one candidate (bad model name, unsupported
                # parameter) is not permanent for the next — keep going.
                continue

            delay = compute_delay(
                budget.used,
                self._config.routing.retry,
                retry_after=getattr(error, "retry_after", None),
            )
            if budget.can_wait(delay) and delay > 0:
                self._metrics.record_retry(
                    provider=candidate.provider.id,
                    reason=str(getattr(error, "status", "") or "error"),
                )
                await asyncio.sleep(delay)

        self._budget.record_error(
            provider=attempts[-1].provider if attempts else "", agent=request.agent or ""
        )
        reason = budget.reason() if budget.exhausted() else str(last_error or "all candidates failed")
        raise RouterExhausted(attempts, reason)

    async def _attempt(
        self,
        provider: LLMProvider,
        candidate: Candidate,
        request: LLMRequest,
        client: httpx.AsyncClient,
        budget: RetryBudget,
    ) -> tuple[Attempt | None, LLMResponse | None, BaseException | None]:
        """One provider/model/key attempt. Never raises; returns the outcome."""
        config = candidate.provider
        keys = resolve_keys(config.key_env)
        api_key, key_index = self._keys.acquire(
            config.id, keys, env_names=config.key_env
        )
        if api_key is None:
            log.debug("llm.router: every key for %s is cooling — skipping", config.id)
            return None, None, None

        if config.requests_per_minute:
            paced = await self._limiter.acquire(
                config.id, requests_per_minute=config.requests_per_minute, max_wait_sec=2.0
            )
            if not paced:
                return None, None, None

        prepared = await self._fit_context(request, candidate)
        budget.charge()
        attempt = Attempt(provider=config.id, model=candidate.model.id, key_index=key_index)
        started = time.monotonic()

        try:
            async with self._bulkhead.slot(config.id, timeout=10.0) as got_slot:
                if not got_slot:
                    return None, None, None
                response = await provider.chat(
                    prepared, model=candidate.model.id, api_key=api_key, client=client
                )
        except Exception as exc:
            latency_ms = int((time.monotonic() - started) * 1000)
            attempt.latency_ms = latency_ms
            attempt.error = str(exc)[:300]
            attempt.status = getattr(exc, "status", None)
            self._penalise(candidate, exc, api_key, latency_ms=latency_ms)
            if not is_retryable(exc, self._config.routing.retry) and not isinstance(
                exc, PermanentError
            ):
                return attempt, None, PermanentError(str(exc))
            return attempt, None, exc

        latency_ms = response.latency_ms or int((time.monotonic() - started) * 1000)
        attempt.ok = True
        attempt.latency_ms = latency_ms
        self._health.record_success(config.id, latency_ms=latency_ms)
        self._keys.record_success(config.id, api_key)
        return attempt, response, None

    async def _fit_context(self, request: LLMRequest, candidate: Candidate) -> LLMRequest:
        """Shrink the conversation to this candidate's window if it overflows."""
        model = candidate.model
        if self._context.fits(
            request.messages,
            context_window=model.context_window,
            max_output_tokens=request.max_tokens,
        ):
            return request

        query = ""
        for message in reversed(request.messages):
            if message.get("role") == "user" and isinstance(message.get("content"), str):
                query = message["content"]
                break

        result = await self._context.fit(
            request.messages,
            context_window=model.context_window,
            max_output_tokens=request.max_tokens,
            query=query,
            allow_summary=self._config.routing.escalate_context,
        )
        log.info(
            "llm.router: context fitted for %s — %d → %d tokens via %s",
            model.id, result.original_tokens, result.final_tokens,
            ", ".join(result.strategies_applied) or "none",
        )
        return replace(request, messages=result.messages)

    def _penalise(
        self, candidate: Candidate, error: BaseException, api_key: str, *, latency_ms: int
    ) -> None:
        """Attribute a failure to the narrowest scope that explains it."""
        provider_id = candidate.provider.id
        status = getattr(error, "status", None)
        scope = getattr(error, "scope", "provider")
        timeout = isinstance(error, (asyncio.TimeoutError, TimeoutError)) or isinstance(
            error, httpx.TimeoutException
        )

        self._metrics.record_failure(
            provider=provider_id, status=str(status or "error"), scope=scope
        )

        if scope == "key" and status == 429:
            quota = "quota" in str(error).lower()
            self._keys.record_rate_limit(
                provider_id, api_key,
                retry_after=getattr(error, "retry_after", None),
                quota_exhausted=quota,
                error=str(error)[:200],
            )
            self._metrics.record_key_rotation(
                provider=provider_id, reason="quota" if quota else "rate_limit"
            )
            # A 429 says nothing about whether the provider is up. Only trip the
            # breaker once every key is cooling — then the provider really is
            # unusable for now.
            counts = self._keys.all_cooling(provider_id, resolve_keys(candidate.provider.key_env))
            self._health.record_failure(
                provider_id, status=status, latency_ms=latency_ms,
                error=str(error)[:200], counts_against_breaker=counts,
            )
            return

        if scope == "model":
            self._keys.record_failure(provider_id, api_key, str(error)[:200])
            self._health.record_failure(
                provider_id, status=status, latency_ms=latency_ms,
                error=str(error)[:200], counts_against_breaker=False,
            )
            return

        self._keys.record_failure(provider_id, api_key, str(error)[:200])
        self._health.record_failure(
            provider_id, status=status, latency_ms=latency_ms,
            error=str(error)[:200], timeout=timeout,
            counts_against_breaker=not isinstance(error, PermanentError),
        )
        if self._health.get(provider_id).state.value == "open":
            self._metrics.record_breaker_trip(provider=provider_id)

    @staticmethod
    def _is_fatal(error: PermanentError) -> bool:
        """Errors that mean the request itself is wrong, not the provider.

        A 413 or 422 will be rejected identically by every provider, so trying
        five more is pure latency.
        """
        return error.status in {413, 414, 422}

    def _no_candidate_reason(self, request: LLMRequest) -> str:
        if not self._providers:
            return (
                "no providers configured — set at least one API key or point "
                "OLLAMA_BASE at a local daemon"
            )
        if request.requires_tools():
            return "no configured model supports tool calling"
        if request.pin_model and request.model:
            return f"model {request.model!r} is not available on any configured provider"
        if not request.allow_paid:
            return (
                "no free provider is available — set ALLOW_PAID_BRAIN=true to "
                "permit paid fallback"
            )
        return "no provider satisfies the request constraints"

    # ── Bookkeeping ─────────────────────────────────────────────────────────

    def _finalise(self, response: LLMResponse, request: LLMRequest, started: float) -> None:
        """Record metrics, budget, and cache after a successful completion."""
        if not response.latency_ms:
            response.latency_ms = int((time.monotonic() - started) * 1000)
        if not response.cost_usd:
            provider = self._providers.get(response.provider)
            if provider is not None:
                response.cost_usd = provider.cost(response.model, response.usage)

        self._metrics.record_request(
            provider=response.provider, model=response.model, outcome="success",
            latency_sec=response.latency_ms / 1000.0, agent=request.agent or "",
            fallbacks=response.fallback_count,
        )
        self._metrics.record_tokens(
            provider=response.provider, model=response.model,
            prompt=response.usage.prompt_tokens,
            completion=response.usage.completion_tokens,
            cost_usd=response.cost_usd,
        )
        self._budget.record(
            usage=response.usage, cost_usd=response.cost_usd,
            provider=response.provider, model=response.model,
            agent=request.agent or "", workflow=request.workflow or "",
        )
        self._store_cache(request, response)
        self._refresh_gauges()

    def _cache_payload(self, request: LLMRequest) -> dict[str, Any]:
        return {
            "model": request.model or "",
            "messages": request.messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "response_format": request.response_format,
            "tools": request.tools,
        }

    def _lookup_cache(self, request: LLMRequest) -> LLMResponse | None:
        if not self._cache.is_cacheable(request):
            return None
        body = self._cache.get_response(payload_key(self._cache_payload(request)))
        if body is None:
            self._metrics.record_cache(layer="response", hit=False)
            return None
        self._metrics.record_cache(layer="response", hit=True)
        return LLMResponse(
            text=str(body.get("text") or ""),
            model=str(body.get("model") or ""),
            provider=str(body.get("provider") or ""),
            usage=Usage(**(body.get("usage") or {})) if body.get("usage") else Usage(),
            finish_reason=body.get("finish_reason"),
            cached=True,
        )

    def _store_cache(self, request: LLMRequest, response: LLMResponse) -> None:
        if not self._cache.is_cacheable(request) or not response.text:
            return
        self._cache.put_response(payload_key(self._cache_payload(request)), {
            "text": response.text,
            "model": response.model,
            "provider": response.provider,
            "usage": {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "cached_tokens": response.usage.cached_tokens,
            },
            "finish_reason": response.finish_reason,
        })

    def _refresh_gauges(self) -> None:
        self._metrics.set_queue_depth(self._queue.depth)
        self._metrics.set_in_flight(self._bulkhead.in_flight())
        for entry in self._health.snapshot():
            provider = str(entry["provider"])
            self._metrics.set_breaker_state(provider, str(entry["state"]))
            self._metrics.set_success_rate(provider, float(entry["success_rate"]))
        for layer in self._cache.stats()["layers"]:
            self._metrics.set_cache_hit_rate(str(layer["name"]), float(layer["hit_rate"]))
        budget = self._budget.snapshot()["budget"]
        if budget["daily_usd"]:
            self._metrics.set_budget_ratio(
                "daily", budget["spend_today_usd"] / budget["daily_usd"]
            )
        if budget["monthly_usd"]:
            self._metrics.set_budget_ratio(
                "monthly", budget["spend_month_usd"] / budget["monthly_usd"]
            )

    async def _summariser_chat(self, **kwargs: Any) -> LLMResponse:
        """Cheap-model chat used by the context summariser.

        Routes with ``cost_optimized`` and marks the call uncacheable so a
        summary never displaces a real completion in the cache.
        """
        return await self._dispatch(LLMRequest(
            messages=kwargs.get("messages") or [],
            max_tokens=int(kwargs.get("max_tokens") or 800),
            temperature=float(kwargs.get("temperature") or 0.0),
            strategy="cost_optimized",
            agent="context-summariser",
            cacheable=False,
            max_attempts=2,
        ))

    # ── Introspection ───────────────────────────────────────────────────────

    async def health_check(self, provider_id: str | None = None) -> list[dict[str, Any]]:
        """Actively probe providers and fold the result into the tracker."""
        client = await self._http()
        targets = (
            [self._providers[provider_id]] if provider_id and provider_id in self._providers
            else list(self._providers.values())
        )
        results: list[dict[str, Any]] = []
        for provider in targets:
            keys = resolve_keys(provider.config.key_env)
            api_key = keys[0] if keys else ""
            probe = await provider.health(api_key=api_key, client=client)
            probe["provider"] = provider.id
            probe["tier"] = provider.config.tier
            results.append(probe)
            if probe.get("healthy"):
                self._health.record_success(
                    provider.id, latency_ms=int(probe.get("latency_ms") or 0)
                )
            else:
                self._health.record_failure(
                    provider.id, status=probe.get("status"),
                    error=str(probe.get("error") or "probe failed"),
                )
        return results

    async def discover_models(self) -> dict[str, list[str]]:
        """Ask every provider what models it serves and register the new ones."""
        client = await self._http()
        discovered: dict[str, list[str]] = {}
        for provider in self._providers.values():
            keys = resolve_keys(provider.config.key_env)
            api_key = keys[0] if keys else ""
            try:
                models = await provider.list_models(api_key=api_key, client=client)
            except Exception as exc:
                log.debug("llm.router: discovery failed for %s (%s)", provider.id, exc)
                continue
            discovered[provider.id] = models
            self._registry.register_discovered(provider.id, models)
        return discovered

    def status(self) -> dict[str, Any]:
        """Everything the dashboard needs, in one call."""
        health_by_id = {entry["provider"]: entry for entry in self._health.snapshot()}
        keys_by_id = self._keys.snapshot()
        in_flight = self._bulkhead.in_flight()

        providers: list[dict[str, Any]] = []
        for provider_id, provider in sorted(self._providers.items()):
            config = provider.config
            health = health_by_id.get(provider_id, {})
            providers.append({
                "id": provider_id,
                "kind": config.kind,
                "tier": config.tier,
                "base_url": config.base_url,
                "priority": config.priority,
                "weight": config.weight,
                "enabled": config.enabled,
                "default_model": config.default_model,
                "models": [m.id for m in self._registry.for_provider(provider_id)],
                "max_concurrency": config.max_concurrency,
                "in_flight": in_flight.get(provider_id, 0),
                "keys": keys_by_id.get(provider_id, []),
                "key_count": len(resolve_keys(config.key_env)),
                "health": health,
                "state": health.get("state", "closed"),
                "available": health.get("available", True),
                "notes": config.notes,
            })

        return {
            "enabled": True,
            "strategy": self._config.routing.strategy,
            "strategies": strategy_names(),
            "prefer_local": self._config.routing.prefer_local,
            "allow_paid": self._config.routing.allow_paid,
            "providers": providers,
            "queue": self._queue.stats(),
            "bulkheads": self._bulkhead.snapshot(),
            "dedupe": self._dedupe.stats(),
            "cache": self._cache.stats(),
            "budget": self._budget.snapshot(),
            "config_dir": self._config.source_dir,
        }

    async def aclose(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
        self._client = None


_router: LLMRouter | None = None
_lock = threading.Lock()


def get_router() -> LLMRouter:
    """The process-wide router. Every LLM call goes through this."""
    global _router
    if _router is None:
        with _lock:
            if _router is None:
                _router = LLMRouter()
    return _router


def reset() -> None:
    """Test hook — rebuild the router on next access."""
    global _router
    with _lock:
        _router = None
