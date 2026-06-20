"""services/inbound_router.py
Helpers for the Telegram inbound router.

Three small reusable functions used by ``telegram_bot._process_update``:
  - ``classify_plain_text(text)``
        Maps a plain-text Telegram message into one of the four direct-chat
        intent categories (mirrors ``agent.intent.classify_direct_chat_intent``)
        so the bot can route bare messages to the orchestrator without the
        user having to type ``/agent``.
  - ``should_big_paste(text, max_chars)``
        True when the message exceeds the Telegram Markdown-v1 delivered
        character budget. We write long pastes to disk and reply with a
        short pointer so the message itself never hits Telegram's 4096-char
        hard cap or Markdown-v1's reserved-char budget.
  - ``save_paste(text, workspace_root)``
        Writes big-paste text to ``<workspace>/pastes/digest-<ts>.md`` with
        an isolated, deterministic filename pattern. Returns the absolute
        path or None on filesystem failure.

These are pure async/await-safe functions and have no side effects beyond
writing to the filesystem, so they're safe to call from the webhook handler
without polluting the bot's update loop.  The bot wires them together inside
``_process_update`` after the plain-text classifier has decided what kind of
action to take.
"""
from __future__ import annotations

import logging
import os
import re
import time
from pathlib import Path
from typing import Any, Literal, Optional

log = logging.getLogger("qwen-telegram-inbound")

# Top-level import of the intent classifier so an import failure surfaces at
# module-load time (a single WARNING in the bot startup log) rather than
# silently degrading to "answer_only" on every plain-text message. The
# runtime fallback inside classify_plain_text() is still defensive in case
# the classifier raises at call time, but the missing-import case is loud.
try:
    from agent.intent import classify_direct_chat_intent as _classify_direct_chat_intent
except ImportError as exc:  # pragma: no cover \u2014 depends on agent module install
    log.warning(
        "inbound_router.classify_direct_chat_intent unavailable at import: %s "
        "\u2014 plain-text messages will silently route to answer_only",
        exc,
    )
    _classify_direct_chat_intent = None  # type: ignore[assignment]  # noqa: F841

# Default Telegram Markdown-v1 reserved-char budget. The hard cap is 4096
# characters, but parse-mode overhead plus operator-visible formatting
# (bullets, backticks, links) eats ~10% on top of the literal. 3840 caps the
# *delivered* budget comfortably below the limit while still being wide
# enough for normal paste plumbing.
DEFAULT_BIG_PASTE_CHARS = 3500

# Sensitive targets that always escalate to "execute_after_approval". The
# exact strings mirror agent/intent.classify_direct_chat_intent so behaviour
# is consistent across both surfaces (Direct Chat UI + Telegram).
_SENSITIVE_TARGETS: tuple[str, ...] = (
    "admin_auth",
    "key_store",
    "secrets",
    "password",
    "credential",
    "private key",
    "service_manager",
)


def classify_plain_text(text: str) -> Literal[
    "answer_only", "clarify_needed", "plan_only", "execute_now", "execute_after_approval"
]:
    """Classify plain-text into one of the direct-chat intent categories.

    Re-uses ``agent.intent.classify_direct_chat_intent`` (imported at module
    load time \u2014 see the top-level try/except) so behaviour is identical to
    the Direct Chat UI path: a plain-text message that classified as
    ``execute_now`` in the dashboard will trigger the same workflow via
    Telegram, and admin_auth / key_store / secrets references escalate to
    ``execute_after_approval`` on both surfaces.

    Falls back to ``answer_only`` if the classifier is unavailable so the
    bot surface degrades to a chat reply instead of a hard error.
    """
    if not text or not isinstance(text, str):
        return "answer_only"

    if _classify_direct_chat_intent is None:  # import failed at module load
        log.debug("inbound_router.classify_plain_text classifier_unavailable")
        return "answer_only"

    try:
        result = _classify_direct_chat_intent(text)
    except Exception as exc:  # noqa: BLE001 \u2014 must never crash the webhook
        log.warning("inbound_router.classify_plain_text failed: %s", exc)
        return "answer_only"

    # Belt-and-braces: agent.intent's classifier returns the lower-level
    # INTENT_* labels too. Map them if a refactor ever leaks through.
    lowered = result.lower() if isinstance(result, str) else "answer_only"
    if lowered in {
        "answer_only", "clarify_needed", "plan_only",
        "execute_now", "execute_after_approval",
    }:
        return lowered  # type: ignore[return-value]
    return "answer_only"


def is_sensitive(text: str) -> bool:
    """True if *text* references a sensitive target (auth / keys / secrets / …).

    Used as a hard safety floor for auto-approval: a sensitive request must NEVER
    auto-approve, even if the intent classifier returns ``execute_now`` (a
    misclassification or prompt-injection must not be able to bypass the human
    gate for credential/auth changes). Activates the ``_SENSITIVE_TARGETS`` list
    as an explicit, defense-in-depth check independent of the classifier.
    """
    if not text or not isinstance(text, str):
        return False
    lowered = text.lower()
    return any(target in lowered for target in _SENSITIVE_TARGETS)


def should_big_paste(text: str, *, max_chars: int = DEFAULT_BIG_PASTE_CHARS) -> bool:
    """True when the message exceeds the delivered-character budget.

    Uses ``len(text)`` (character count, not byte count) so multi-byte
    CJK / emoji-heavy pastes trip the threshold at the right place.
    """
    if not text:
        return False
    return len(text) > max_chars


def save_paste(
    text: str,
    *,
    workspace_root: Optional[str] = None,
) -> Optional[str]:
    """Write ``text`` to a deterministic paste file and return its path.

    Writes under ``<workspace_root>/pastes/digest-<epoch>.md``. The
    ``digest-`` prefix mirrors daily_digest.py so the cleanup loop can
    sweep both directories uniformly. Returns None when the write fails
    (e.g. readonly workspace) so the bot can fall back to a short reply
    that still completes \u2014 we never want a paste write to 5xx the webhook.

    Defense-in-depth: rejects ``workspace_root`` values that contain ``..``
    segments so an attacker-controlled caller cannot escape the data sandbox.
    """
    if text is None:
        return None
    raw_root = (
        workspace_root
        if workspace_root
        else (
            os.environ.get("AGENCY_WORKSPACE_ROOT")
            or os.environ.get("FREEBUFF_REPO_DIR")
            or "~/.qwen-server"
        )
    )
    # Path-traversal guard: refuse any workspace_root with parent-dir segments.
    if ".." in Path(raw_root).parts:
        log.warning(
            "save_paste rejected (path traversal in workspace_root=%r)", raw_root,
        )
        return None
    root = Path(raw_root).expanduser()
    target_dir = root / "pastes"
    epoch = int(time.time())
    out_path = target_dir / f"digest-{epoch}.md"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        # Encode content as UTF-8 once so emoji + multi-byte CJK round-trip
        # through ``Write-File`` on Windows without cp1252 corruption.
        out_path.write_text(text, encoding="utf-8", errors="replace")
        return str(out_path.resolve())
    except OSError as exc:  # pragma: no cover \u2014 filesystem races
        log.warning("save_paste failed (workspace=%s exc=%s)", root, exc)
        return None


# Pre-compiled marker for the retry / sanitize regex used by telegram_bot
# to detect escaped Markdown-v1 sequences inside paste text. Kept here so
# downstream callers (e.g. the /paste preview endpoint) can reuse it.
_PASTE_MARKDOWN_RESERVED = re.compile(r"(?<!\\)([*_`\[\]])")


def sanitize_paste_for_preview(text: str, *, max_chars: int = 700) -> str:
    """Return a Markdown-v1-safe preview string under ``max_chars``.

    Used by the preview endpoint and by the bot's own short reply when
    confirming a paste was written. Escapes single reserved characters
    (``* _ ` [``) only \u2014 we deliberately don't touch triple-backtick
    fences so code dumps round-trip correctly on the next Telegram reply.
    """
    if not text:
        return ""
    rendered = _PASTE_MARKDOWN_RESERVED.sub(lambda m: "\\" + m.group(1), text)
    if len(rendered) <= max_chars:
        return rendered
    return rendered[: max(0, max_chars - 1)] + "\u2026"


__all__ = [
    "DEFAULT_BIG_PASTE_CHARS",
    "classify_plain_text",
    "should_big_paste",
    "save_paste",
    "sanitize_paste_for_preview",
]
