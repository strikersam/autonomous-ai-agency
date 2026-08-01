"""packages/security/redact.py — strip secrets out of strings before they reach a log line.

Never log a raw connection string: CLAUDE.md's constitution requires secrets
stay env-only, and a ``mongodb(+srv)://`` (or postgres/mysql/amqp/redis) URI
carries its password inline as ``user:pass@host``. This is the one shared
place that knows how to strip that, so every caller gets the same coverage
instead of each module reimplementing — and under-covering — its own regex.
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
