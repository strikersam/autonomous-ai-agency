"""packages/security/redact.py — strip secrets out of strings before they reach a log line.

Never log a raw connection string: CLAUDE.md's constitution requires secrets
stay env-only, and a ``mongodb(+srv)://`` (or postgres/mysql/amqp/redis) URI
carries its password inline as ``user:pass@host``. This is the one shared
place that knows how to strip that, so every caller gets the same coverage
instead of each module reimplementing — and under-covering — its own regex.

Also the one home for the secret-value and PII patterns: the governance audit
trail and every agent memory store (``redact_secrets``) redact with the same
list, so a token pattern added here is covered everywhere at once.
"""
from __future__ import annotations

import re

# Userinfo segment of a URI: scheme://user:pass@host/...
_USERINFO_RE = re.compile(r"://[^/@]+@")

# Query-string parameters that carry a secret value even when the userinfo
# segment is already clean — MongoDB's tlsCertificateKeyFilePassword is the
# motivating case, but the same shape covers any *password/*pwd/*secret
# parameter name a driver might add.
_SECRET_QUERY_PARAM_RE = re.compile(r"(?i)([?&][\w.]*(?:password|pwd|secret)[\w.]*=)[^&]*")


def redact_connection_url(url: str) -> str:
    """Strip embedded credentials from a connection URI before logging it.

    Covers both the ``user:pass@host`` userinfo segment and secret-bearing
    query parameters, leaving the host, database, and non-secret parameters
    visible for debugging.
    """
    redacted = _USERINFO_RE.sub("://***:***@", url)
    redacted = _SECRET_QUERY_PARAM_RE.sub(r"\1***", redacted)
    return redacted


# Secret-shaped values that appear inside otherwise innocent strings — a shell
# command, a URL, a diff. Keyed on the vendor prefixes this repo actually
# handles plus generic bearer/assignment forms.
_VALUE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{16,}"),            # GitHub tokens
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9\-_]{16,}"),                 # OpenAI-style
    re.compile(r"\bnvapi-[A-Za-z0-9\-_]{16,}"),              # NVIDIA NIM
    re.compile(r"\bcsk-[A-Za-z0-9\-_]{16,}"),                # Cerebras
    re.compile(r"\bgsk_[A-Za-z0-9]{16,}"),                   # Groq
    re.compile(r"\be2b_[A-Za-z0-9]{16,}"),                   # E2B
    re.compile(r"\bsk-ant-[A-Za-z0-9\-_]{16,}"),             # Anthropic
    re.compile(r"(?i)\bbearer\s+[A-Za-z0-9\-._~+/]{16,}"),
    re.compile(
        r"(?i)\b(?:token|secret|password|api[_-]?key)\b\s*[=:]\s*[\"']?([^\s\"'&]{8,})"
    ),
)


# Personally-identifiable values that are not secrets but must not linger in a
# stored audit row. Kept deliberately narrow: a US SSN and a payment-card
# number. Email and phone are *excluded* on purpose — the audit event
# legitimately records an owner identity (frequently an email), so a blanket
# email/phone redaction would gut the trail's debuggability for near-zero gain,
# and both shapes are far too common in ordinary tool arguments to redact
# safely. SSNs are matched only in their separated form (a bare run of nine
# digits collides with too many innocent ids), and card numbers are
# Luhn-validated so a 16-digit order ref or snowflake id is not mistaken for a
# PAN.
_SSN_RE = re.compile(r"\b\d{3}[-\s]\d{2}[-\s]\d{4}\b")
_CARD_CANDIDATE_RE = re.compile(r"\b(?:\d[ -]?){13,19}\b")


def _luhn_ok(digits: str) -> bool:
    """True when ``digits`` (bare, no separators) satisfies the Luhn checksum."""
    total = 0
    for i, ch in enumerate(reversed(digits)):
        d = ord(ch) - 48
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        total += d
    return total % 10 == 0


def _redact_pii(text: str) -> str:
    """Redact SSNs and Luhn-valid payment-card numbers from a string.

    Runs after the secret-value pass in :func:`_scrub_text`. A card candidate
    is only redacted when its digits (separators stripped) pass Luhn, keeping
    false positives on ordinary long numbers negligible.
    """

    def _card(match: re.Match[str]) -> str:
        digits = re.sub(r"[ -]", "", match.group(0))
        if 13 <= len(digits) <= 19 and _luhn_ok(digits):
            return "***"
        return match.group(0)

    redacted = _CARD_CANDIDATE_RE.sub(_card, text)
    redacted = _SSN_RE.sub("***", redacted)
    return redacted


def redact_secrets(text: str) -> str:
    """Strip secret-shaped substrings and PII from free text before it is persisted.

    Covers connection-URI credentials, vendor API tokens, bearer headers,
    ``key=value`` secret assignments, SSNs and Luhn-valid card numbers. Used on
    every write into agent memory: a lesson built from a failed step's error
    text is exactly where a leaked token would otherwise land on disk.
    """
    if not text:
        return text
    redacted = redact_connection_url(text)
    for pattern in _VALUE_PATTERNS:
        redacted = pattern.sub(
            lambda m: m.group(0).replace(m.group(1), "***") if m.groups() else "***",
            redacted,
        )
    return _redact_pii(redacted)
