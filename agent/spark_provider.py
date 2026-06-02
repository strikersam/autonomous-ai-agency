"""agent/spark_provider.py — SPARK API Integration

Inspired by SPARK API (spark-bsv.uk) — GPU inference + blockchain notarization
for AI agents. Provides optional integration with the AgentSats infrastructure
for content notarization, agent identity, and credit-based GPU inference.

Features:
  - Agent registration (BSV address + API key)
  - Content notarization (hash → blockchain via OP_RETURN)
  - Hash verification against blockchain
  - GPU inference (OpenAI-compatible endpoint)
  - Credit topup via BSV transactions
  - Agent registry listing

All calls are optional and require SPARK_API_KEY env var to be set.
When not configured, the provider is silently skipped.

Usage::

    from agent.spark_provider import SparkProvider

    spark = SparkProvider()
    if spark.is_configured:
        result = await spark.notarize("sha256-hash-of-content")
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

log = logging.getLogger("qwen-spark")

# Default API base URL
_SPARK_BASE_URL: str = os.environ.get("SPARK_BASE_URL", "https://api.spark-bsv.uk")

# Timeout for SPARK API calls
_SPARK_TIMEOUT: float = float(os.environ.get("SPARK_TIMEOUT", "30.0"))


@dataclass
class SparkAgentIdentity:
    """Agent identity registered on SPARK."""
    api_key: str
    bsv_address: str
    daily_credits: int = 0
    topup_address: str = ""
    registered_at: float = field(default_factory=time.time)


@dataclass
class NotarizeResult:
    """Result of content notarization."""
    success: bool
    txid: str = ""
    status: str = ""  # confirmed | pending | failed
    credits_remaining: int = 0
    verify_url: str = ""
    error: str = ""


@dataclass
class VerifyResult:
    """Result of hash verification."""
    confirmed: bool
    bsv_address: str = ""
    timestamp: int = 0
    txid: str = ""
    verify_url: str = ""
    error: str = ""


class SparkProvider:
    """Integrate with SPARK API for blockchain notarization and GPU inference.

    This is an OPTIONAL provider — when SPARK_API_KEY is not set,
    is_configured returns False and all methods become no-ops.

    Usage::

        spark = SparkProvider()
        if spark.is_configured:
            result = await spark.notarize(content_hash)
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        base_url: str = _SPARK_BASE_URL,
        timeout: float = _SPARK_TIMEOUT,
    ) -> None:
        self._api_key = api_key or os.environ.get("SPARK_API_KEY", "").strip()
        self._bsv_address = os.environ.get("SPARK_BSV_ADDRESS", "").strip()
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._identity: SparkAgentIdentity | None = None

    # ── Properties ──────────────────────────────────────────────────────────

    @property
    def is_configured(self) -> bool:
        """Return True if SPARK API key is set."""
        return bool(self._api_key)

    @property
    def identity(self) -> SparkAgentIdentity | None:
        return self._identity

    # ── Public API: Identity ────────────────────────────────────────────────

    async def register(self, bsv_address: str | None = None) -> SparkAgentIdentity | None:
        """Register this agent on the SPARK network.

        If *bsv_address* is not provided, uses SPARK_BSV_ADDRESS env var.
        """
        addr = bsv_address or self._bsv_address
        if not addr:
            log.warning("SparkProvider: cannot register — no BSV address provided")
            return None

        try:
            # Step 1: Get PoW challenge
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                challenge_resp = await client.get(
                    f"{self._base_url}/register/challenge",
                    params={"bsv_address": addr},
                )
                if challenge_resp.status_code != 200:
                    log.warning("SparkProvider: failed to get challenge: %s", challenge_resp.text)
                    return None
                challenge_data = challenge_resp.json()

            # Step 2: Solve PoW challenge (offload to thread to avoid blocking event loop)
            challenge = challenge_data.get("challenge", "")
            difficulty = challenge_data.get("difficulty", 16)
            nonce = await asyncio.to_thread(self._solve_pow, challenge, addr, difficulty)
            if nonce is None:
                log.warning("SparkProvider: failed to solve PoW challenge")
                return None

            # Step 3: Register with solved PoW
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                reg_resp = await client.post(
                    f"{self._base_url}/register",
                    json={
                        "bsv_address": addr,
                        "challenge": challenge,
                        "nonce": nonce,
                    },
                )
                if reg_resp.status_code not in (200, 201):
                    log.warning("SparkProvider: registration failed: %s", reg_resp.text)
                    return None

                data = reg_resp.json()
                identity = SparkAgentIdentity(
                    api_key=data.get("api_key", ""),
                    bsv_address=data.get("bsv_address", addr),
                    daily_credits=data.get("daily_credits", 50),
                    topup_address=data.get("topup_address", ""),
                )
                self._identity = identity
                self._api_key = identity.api_key
                log.info("SparkProvider: agent registered — address=%s credits=%d",
                         identity.bsv_address, identity.daily_credits)
                return identity

        except Exception as exc:
            log.warning("SparkProvider: registration error: %s", exc)
            return None

    # ── Public API: Notarization ────────────────────────────────────────────

    async def notarize(self, content: str | bytes) -> NotarizeResult:
        """Notarize content hash on the BSV blockchain.

        Args:
            content: String or bytes to hash and notarize.

        Returns:
            NotarizeResult with txid and status.
        """
        if not self._api_key:
            return NotarizeResult(success=False, error="SPARK not configured")

        # Hash the content
        if isinstance(content, str):
            content_bytes = content.encode("utf-8")
        else:
            content_bytes = content
        content_hash = hashlib.sha256(content_bytes).hexdigest()

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/notarize",
                    json={
                        "api_key": self._api_key,
                        "bsv_address": self._bsv_address,
                        "hash": content_hash,
                    },
                )
                if resp.status_code not in (200, 201):
                    return NotarizeResult(
                        success=False,
                        error=f"Notarization failed: {resp.text[:200]}",
                    )

                data = resp.json()
                result = NotarizeResult(
                    success=data.get("success", False),
                    txid=data.get("txid", ""),
                    status=data.get("status", "unknown"),
                    credits_remaining=data.get("credits_remaining", 0),
                    verify_url=data.get("verify_url", ""),
                )
                log.info("SparkProvider: content notarized — txid=%s status=%s",
                         result.txid, result.status)
                return result

        except Exception as exc:
            log.warning("SparkProvider: notarize error: %s", exc)
            return NotarizeResult(success=False, error=str(exc))

    async def verify(self, content_hash: str) -> VerifyResult:
        """Verify a hash against the BSV blockchain.

        Args:
            content_hash: SHA-256 hash to verify.

        Returns:
            VerifyResult with confirmation status.
        """
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{self._base_url}/notarize/status",
                    params={"hash": content_hash},
                )
                if resp.status_code != 200:
                    return VerifyResult(
                        confirmed=False,
                        error=f"Verification failed: {resp.text[:200]}",
                    )

                data = resp.json()
                return VerifyResult(
                    confirmed=data.get("confirmed", False),
                    bsv_address=data.get("bsv_address", ""),
                    timestamp=data.get("timestamp", 0),
                    txid=data.get("txid", ""),
                    verify_url=data.get("verify_url", ""),
                )

        except Exception as exc:
            log.warning("SparkProvider: verify error: %s", exc)
            return VerifyResult(confirmed=False, error=str(exc))

    @staticmethod
    def hash_content(content: str | bytes) -> str:
        """Hash content for notarization."""
        if isinstance(content, str):
            content = content.encode("utf-8")
        return hashlib.sha256(content).hexdigest()

    # ── Public API: GPU Inference ───────────────────────────────────────────

    async def chat_completion(self, messages: list[dict[str, str]], **kwargs: Any) -> dict[str, Any]:
        """Make an OpenAI-compatible chat completion request to SPARK GPU.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            **kwargs: Additional parameters (temperature, max_tokens, etc.).

        Returns:
            OpenAI-compatible response dict.
        """
        if not self._api_key:
            return {"error": "SPARK not configured"}

        try:
            payload = {
                "model": kwargs.get("model", "agentsats"),
                "messages": messages,
            }
            if "temperature" in kwargs:
                payload["temperature"] = kwargs["temperature"]
            if "max_tokens" in kwargs:
                payload["max_tokens"] = kwargs["max_tokens"]

            headers = {
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
            }

            async with httpx.AsyncClient(timeout=120.0) as client:
                resp = await client.post(
                    f"{self._base_url}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                )
                if resp.status_code != 200:
                    return {"error": f"GPU inference failed: {resp.text[:200]}"}
                return resp.json()

        except Exception as exc:
            log.warning("SparkProvider: chat completion error: %s", exc)
            return {"error": str(exc)}

    # ── Public API: Credits ─────────────────────────────────────────────────

    async def topup(self, txid: str, satoshis: int) -> dict[str, Any]:
        """Add credits via BSV transaction ID.

        Args:
            txid: BSV transaction ID.
            satoshis: Amount in satoshis (1 credit = 500 sats).

        Returns:
            API response dict.
        """
        if not self._api_key:
            return {"error": "SPARK not configured"}

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/topup",
                    json={
                        "api_key": self._api_key,
                        "txid": txid,
                        "satoshis": satoshis,
                    },
                )
                if resp.status_code not in (200, 201):
                    return {"error": f"Topup failed: {resp.text[:200]}"}
                data = resp.json()
                credits = satoshis // 500
                log.info("SparkProvider: topped up %d credits from %d sats (txid=%s)",
                         credits, satoshis, txid)
                return data

        except Exception as exc:
            log.warning("SparkProvider: topup error: %s", exc)
            return {"error": str(exc)}

    # ── Public API: Registry ────────────────────────────────────────────────

    async def list_in_registry(
        self,
        capability: str,
        description: str = "",
        price_per_call: int = 5,
        endpoint: str = "",
        tags: str = "",
    ) -> dict[str, Any]:
        """List this agent in the SPARK agent registry.

        Args:
            capability: Agent's capability (e.g., 'code-review').
            description: Description of the service.
            price_per_call: Credits per call.
            endpoint: Your agent's endpoint URL.
            tags: Comma-separated tags.

        Returns:
            API response dict.
        """
        if not self._api_key:
            return {"error": "SPARK not configured"}

        try:
            payload: dict[str, Any] = {
                "api_key": self._api_key,
                "capability": capability,
            }
            if description:
                payload["description"] = description
            if price_per_call:
                payload["price_per_call"] = price_per_call
            if endpoint:
                payload["endpoint"] = endpoint
            if tags:
                payload["tags"] = tags

            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.post(
                    f"{self._base_url}/registry/list",
                    json=payload,
                )
                if resp.status_code not in (200, 201):
                    return {"error": f"Registry listing failed: {resp.text[:200]}"}
                log.info("SparkProvider: listed in registry — capability=%s", capability)
                return resp.json()

        except Exception as exc:
            log.warning("SparkProvider: registry list error: %s", exc)
            return {"error": str(exc)}

    # ── Internal ────────────────────────────────────────────────────────────

    @staticmethod
    def _solve_pow(challenge: str, address: str, difficulty: int, max_attempts: int = 100_000) -> str | None:
        """Solve a proof-of-work challenge.

        Find nonce where SHA256(challenge + address + nonce) < 2^(256 - difficulty).
        """
        target = 2 ** (256 - difficulty)
        prefix = f"{challenge}{address}".encode()

        for nonce in range(max_attempts):
            candidate = prefix + str(nonce).encode()
            digest = hashlib.sha256(candidate).digest()
            value = int.from_bytes(digest, "big")
            if value < target:
                return str(nonce)

        return None


# ── Singleton ─────────────────────────────────────────────────────────────────

_spark_instance: SparkProvider | None = None


def get_spark_provider() -> SparkProvider:
    """Get or create the singleton SparkProvider."""
    global _spark_instance
    if _spark_instance is None:
        _spark_instance = SparkProvider()
    return _spark_instance
