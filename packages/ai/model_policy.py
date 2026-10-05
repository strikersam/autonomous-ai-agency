"""packages/ai/model_policy.py — operator deny-list for model ids.

``DENIED_MODEL_IDS`` (Settings → Platform controls) names models that must
never be dispatched: a known-bad id, one that is too expensive, or one an
operator is not allowed to use. It is the proactive counterpart to the
reactive dead-model list in ``packages/ai/router.py`` (410 Gone) and the
catalogue probe, which only learn about a bad model after a request fails.

Entries are model ids, matched case-insensitively; ``fnmatch`` globs are
allowed (``claude-opus-*``). The value is read through ``settings`` on every
call, so an override from the dashboard takes effect without a restart.
"""
from __future__ import annotations

import fnmatch
import logging

log = logging.getLogger("qwen-proxy")


def is_model_denied(model: str) -> bool:
    """True when *model* matches an entry in DENIED_MODEL_IDS."""
    from packages.config import settings

    patterns = settings.denied_model_patterns
    if not patterns or not model:
        return False
    name = model.strip().lower()
    return any(fnmatch.fnmatchcase(name, p) for p in patterns)


def drop_denied(models: list[str]) -> list[str]:
    """*models* without denied ids, order preserved; logs what it removed."""
    kept = [m for m in models if not is_model_denied(m)]
    if len(kept) != len(models):
        log.info(
            "model_policy: skipping denied model(s) %s (DENIED_MODEL_IDS)",
            sorted(set(models) - set(kept)),
        )
    return kept
