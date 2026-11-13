"""Outbound identity guard for agent network calls.

Rule 14 answers *where* an agent may send a request. This module answers a different
question: does the request itself carry the operator's identity — their email — out to a
third party? A URL path, a query string or a search query is model-chosen text, so a
model that saw the operator's address in a task can put it there without anyone
intending egress.

Off unless an operator switches it on (``WEB_REACH_EGRESS_IDENTITY_GUARD``) *and*
lists the addresses to protect (``OPERATOR_EMAILS``): with either missing nothing here
can change, which keeps the shipped default byte-identical (rule 1).

The refusal reason is a fixed string, never anything derived from the request: it is
returned to the model and emitted as a ``safety_event``, and neither may carry the
address it matched (rule 6). This is deliberately not a redaction change — the audit
trail keeps recording owner identities, as ``packages/security/redact.py`` explains.
"""
from __future__ import annotations

import logging
import urllib.parse

log = logging.getLogger("qwen-proxy")

# What callers may show or report. Fixed on purpose: no address, no host, no query.
GENERIC_REASON = "request carries a protected identity"

# Percent-encoding is a one-line bypass (`ops@example.com` -> `ops%40example.com`), and a
# doubly-encoded value is one more round; two rounds covers it without unbounded work.
_MAX_DECODE_ROUNDS = 2


def guard_enabled() -> bool:
    """True only when an operator switched the outbound identity guard on."""
    try:
        from packages.config import settings

        return bool(getattr(settings, "web_reach_egress_identity_guard", False))
    except Exception as exc:  # noqa: BLE001 - a broken settings read keeps the shipped default
        log.debug("egress identity guard: settings unreadable, staying off: %s", exc)
        return False


def protected_identities() -> tuple[str, ...]:
    """The configured operator addresses, lower-cased.

    Read through ``settings`` only (rule 5); a value without an ``@`` is ignored so a
    stray comma or a truncated entry cannot turn into a substring that matches
    innocent text.
    """
    try:
        from packages.config import settings

        raw = getattr(settings, "operator_emails", ()) or ()
        return tuple(
            value.strip().lower() for value in raw if value and "@" in value.strip()
        )
    except Exception as exc:  # noqa: BLE001 - never let config break web reach
        log.debug("egress identity guard: identities unreadable: %s", exc)
        return ()


def _decoded_variants(text: str) -> list[str]:
    """*text* plus its percent-decoded forms, so encoding cannot hide an address."""
    variants = [text]
    current = text
    for _ in range(_MAX_DECODE_ROUNDS):
        nxt = urllib.parse.unquote_plus(current)
        if nxt == current:
            break
        variants.append(nxt)
        current = nxt
    return variants


def egress_identity_reason(text: str) -> str | None:
    """Why *text* must not leave the process, or None when it may.

    *text* is the outbound URL, search query or body. A configured address anywhere in
    it — raw or percent-encoded, in any casing — refuses the request.
    """
    if not text or not guard_enabled():
        return None
    identities = protected_identities()
    if not identities:
        return None
    for variant in _decoded_variants(text):
        haystack = variant.lower()
        for identity in identities:
            if identity in haystack:
                return GENERIC_REASON
    return None
