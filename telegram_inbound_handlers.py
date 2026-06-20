"""telegram_inbound_handlers.py

Step 1 inbound-routing handlers for the FreeBuff Telegram bot.

Three concerns, all wired by ``telegram_bot._process_update``:
  1. ``/redirect <run_id_or_dec_id> <free-text instruction>``
       Dispatch by prefix (``wfo_`` vs ``dec_``). Routes through
       ``services.workflow_orchestrator.update_task`` so the next phase of an
       in-flight run picks the operator's redline up.
  2. **Big-paste policy** — when ``len(text) > DEFAULT_BIG_PASTE_CHARS``, write
     the paste to a workspace file and reply with a short pointer so the
     original message never crosses Telegram's 4096-character hard cap.
  3. **Plain-text fallback** — when the operator sends a bare message with
     no ``/`` command, classify via ``agent.intent.classify_direct_chat_intent``
     and route to the orchestrator (``execute_now`` / ``execute_after_approval``),
     chat back (``answer_only``), or ask for clarification (``clarify_needed``).
  4. **Reply-to-decision lookup** — when the message replies to a bot message
     that was previously linked via ``bot_message_links``, the linked
     ``decision_id`` is resolved (or the in-flight ``run_id`` is updated via
     ``update_task`` if the bot message carried an approval gate).

All functions are async-safe and handle edge cases (missing token, missing
session) without raising — the Telegram webhook must never 5xx, otherwise
Telegram will retry and the operator sees chaos.
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from services import inbound_router as ir
from telegram_bot import (
    _answer_callback,
    _edit_message,
    _is_admin,
    _is_allowed,
)
import telegram_bot as _tb

log = logging.getLogger("qwen-telegram-inbound")

# Maximum Telegram Markdown-v1 body length we deliver (with format overhead
# already accounted for). The hard ceiling is 4096, but Markdown-v1's reserved
# characters (``* _ ` [``) plus triple-backtick fences consume ~12% of the
# payload, so we trim delivered text to <= 3840 to leave headroom. Pastes larger
# than this hit ``save_paste`` and reply with a short pointer.
_MAX_DELIVERED_CHARS = 3840

# Admin commands opened up by this slice. There is no ``/paste`` yet because the
# paste read endpoint is not implemented; operators can ``cat`` the file from
# their terminal. ``/redirect`` is admin-only because it mutates a paused run.
_REDIRECT_PREFIX_WFO = "wfo_"
_REDIRECT_PREFIX_DEC = "dec_"

# Decision-store module handle; either resolves the singleton or fails fast
# (test path stays usable).
def _get_decisions_store():
    try:
        from services.decisions_store import get_decisions_store
    except ImportError as exc:  # pragma: no cover - depends on import surface
        log.warning("telegram_inbound: decisions_store import failed: %s", exc)
        return None
    try:
        return get_decisions_store()
    except Exception as exc:  # noqa: BLE001 - never raise from web handler
        log.warning("telegram_inbound: get_decisions_store failed: %s", exc)
        return None


def _get_workflow_orchestrator():
    try:
        from services.workflow_orchestrator import get_workflow_orchestrator
    except ImportError as exc:  # pragma: no cover
        log.warning("telegram_inbound: workflow_orchestrator import failed: %s", exc)
        return None
    try:
        return get_workflow_orchestrator()
    except Exception as exc:  # noqa: BLE001
        log.warning("telegram_inbound: get_workflow_orchestrator failed: %s", exc)
        return None


# ─── Reply-to-decision lookup ─────────────────────────────────────────────────

async def _resolve_reply_to_decision(
    message: dict,
) -> Optional[dict[str, Any]]:
    """Look up a linked decision_id/run_id if this message replies to a bot msg.

    Returns None when the message is not a reply, when the bot didn't link the
    parent, or when the SQLite lookup fails. Never raises — the bot's
    ``_process_update`` for-loop must not crash on a lookup failure.
    """
    reply_to = message.get("reply_to_message") or {}
    if not reply_to:
        return None
    chat_id = int(message.get("chat", {}).get("id", 0) or 0)
    parent_msg_id = int(reply_to.get("message_id", 0) or 0)
    if not chat_id or not parent_msg_id:
        return None

    store = _get_decisions_store()
    if store is None:
        return None
    try:
        return store.lookup_by_message(chat_id=chat_id, telegram_message_id=parent_msg_id)
    except Exception as exc:  # noqa: BLE001
        log.debug("telegram_inbound: lookup_by_message exc=%s", exc)
        return None


# ─── Big-paste policy ─────────────────────────────────────────────────────────

async def _handle_big_paste(
    bot_token: str,
    chat_id: int,
    user_id: int,
    text: str,
    *,
    workspace_root: Optional[str] = None,
) -> bool:
    """If ``len(text) > ir.DEFAULT_BIG_PASTE_CHARS``, write to disk and short-reply.

    Returns True when a paste was written (and a short pointer sent). Returns
    False when the message fits the delivered-character budget — let the
    caller handle it normally.
    """
    if not ir.should_big_paste(text):
        return False

    out_path = ir.save_paste(text, workspace_root=workspace_root)
    if out_path is None:
        # Paste write failed — best-effort: still reply with a short preview so
        # the operator gets SOMETHING, but flag that the full text isn't saved.
        await _tb._send_message(
            bot_token, chat_id,
            f"⚠️ Big-paste write failed (>3500 chars). "
            f"First {ir.DEFAULT_BIG_PASTE_CHARS - 1} chars:\n{ir.sanitize_paste_for_preview(text, max_chars=1024)}",
        )
        return True

    line_count = text.count("\n") + (0 if text.endswith("\n") else 1)
    await _tb._send_message(
        bot_token, chat_id,
        f"📋 Paste saved → `{out_path}`\n"
        f"({len(text)} chars, {line_count} lines)\n"
        f"An admin can `cat` the file. The inline preview would have exceeded "
        f"Telegram's 4096-char budget.",
    )
    return True


# ─── Plain-text fallback ─────────────────────────────────────────────────────

def _build_execution_request(
    *,
    user_id: int,
    text: str,
    intent: str = "execute_after_approval",
    metadata: Optional[dict[str, Any]] = None,
) -> Optional[Any]:
    """Build a minimal ``ExecutionRequest`` for plain-text → orchestrator.execute.

    Returns None when the orchestrator module or model is unavailable so the
    caller can fall back to a chat-only reply.

    Auto-approval policy (routine work runs hands-free; the gate only fires when
    the agent can't safely decide on its own):

    * ``auto_approve=True`` only when ALL hold — the classifier was confident
      enough to return ``execute_now`` (uncertain asks come back as
      ``clarify_needed`` / ``execute_after_approval`` and keep gating), the
      sender is an admin (so it's the operator steering their own agency), and
      the request is not sensitive (auth/keys/secrets never auto-approve, as a
      belt-and-braces floor independent of the classifier).
    * Everything else keeps ``auto_approve=False`` → the orchestrator's
      ApprovalGate pushes an inline-keyboard for human review.

    Outward-facing actions (e.g. merging to a protected branch) remain guarded
    separately by the agent autonomy gate even when ``auto_approve=True``.
    """
    try:
        from services.workflow_orchestrator import ExecutionRequest
    except ImportError:
        return None
    auto_approve = (
        intent == "execute_now"
        and _is_admin(int(user_id))
        and not ir.is_sensitive(text)
    )
    request_meta: dict[str, Any] = {
        "source": "telegram_plain_text",
        "telegram_user_id": int(user_id),
        "intent": intent,
        "auto_approved": auto_approve,
    }
    if metadata:
        request_meta.update(metadata)
    return ExecutionRequest(
        request=text,
        user_id=f"telegram:{user_id}",
        auto_approve=auto_approve,
        max_steps=20,
        metadata=request_meta,
    )


async def _route_plain_text(
    bot_token: str,
    chat_id: int,
    user_id: int,
    text: str,
) -> None:
    """Classify plain-text and route to agent / orchestrator / chat.

    ``execute_now`` and ``execute_after_approval`` → orchestrate the request
    via ``services.workflow_orchestrator.execute``. The ApprovalGate will
    push an inline-keyboard message back via Telegram automatically — the
    bot's own ``_process_wfo_callback`` will see it next poll.

    ``plan_only`` → ask the operator to ``yes`` to proceed.

    ``clarify_needed`` → ask for more detail.

    ``answer_only`` → chat back with a short status read-out (no run).
    """
    intent = ir.classify_plain_text(text)
    log.info(
        "telegram_inbound: plain-text chat_id=%s user=%s intent=%s len=%d",
        chat_id, user_id, intent, len(text),
    )

    if intent in ("execute_now", "execute_after_approval"):
        request = _build_execution_request(user_id=user_id, text=text, intent=intent)
        if request is None:
            await _tb._send_message(
                bot_token, chat_id,
                f"*[{intent}]* workflow_orchestrator unavailable. Try `/freebuff {text[:120]}`.",
            )
            return
        orchestrator = _get_workflow_orchestrator()
        if orchestrator is None:
            await _tb._send_message(
                bot_token, chat_id,
                f"*[{intent}]* orchestrator module unavailable right now.",
            )
            return

        # Fire-and-forget so the webhook returns fast. The orchestrator will
        # push an ApprovalGate via the NotificationDispatcher; the bot's normal
        # callback pump will pick it up via ``_process_wfo_callback``.
        async def _run_in_background() -> None:
            try:
                run = await orchestrator.execute(request)
                log.info(
                    "telegram_inbound: launched run=%s status=%s intent=%s",
                    run.run_id, run.status, intent,
                )
            except Exception as exc:  # noqa: BLE001
                log.exception("telegram_inbound: orchestrator.execute failed: %s", exc)

        try:
            import asyncio as _aio
            from telegram_bot import _bg_tasks
            _task = _aio.create_task(_run_in_background())
            _bg_tasks.add(_task)
            _task.add_done_callback(_bg_tasks.discard)
        except Exception as exc:  # pragma: no cover
            log.warning("telegram_inbound: background launch failed: %s", exc)

        from telegram_bot import ADMIN_USER_IDS
        # Reflect the ACTUAL approval decision (auto_approve), not just the intent:
        # a non-admin / sensitive execute_now still gates, so don't tell the
        # operator it's running hands-free when it isn't.
        auto_approved = bool(getattr(request, "metadata", {}) and request.metadata.get("auto_approved"))
        sentinel = "✅" if auto_approved else "🔒"
        gate_note = (
            " Running hands-free (routine, admin-initiated)."
            if auto_approved else
            " You'll see an approval-gate button in seconds for review."
        )
        await _tb._send_message(
            bot_token, chat_id,
            f"{sentinel} *[{intent}]* launched in background.{gate_note}\n"
            f"Task: `{text[:240]}`\n"
            f"User: `telegram:{user_id}` (admin={'yes' if int(user_id) in ADMIN_USER_IDS else 'no'})",
        )
        return

    if intent == "plan_only":
        await _tb._send_message(
            bot_token, chat_id,
            f"📝 *plan_only* confirmed.\n"
            f"You wrote: `{text[:240]}`\n"
            f"Reply `yes` to dispatch an execution_now run, or refine the prompt.",
        )
        return

    if intent == "clarify_needed":
        await _tb._send_message(
            bot_token, chat_id,
            f"❓ Need more detail.\n"
            f"You wrote: `{text[:240]}`\n"
            f"Please include: goal + repo path + acceptance criteria.",
        )
        return

    # answer_only — chat back gently so the operator knows the bot heard them.
    await _tb._send_message(
        bot_token, chat_id,
        f"💬 Noted (answer_only).\n"
        f"`{text[:240]}`\n"
        f"Use `/freebuff <task>` to actually execute, or `/agent <task>` for a confirm-then-run flow.",
    )


# ─── /redirect command ───────────────────────────────────────────────────────

async def handle_redirect(
    bot_token: str,
    chat_id: int,
    user_id: int,
    parts: list[str],
) -> None:
    """Handle ``/redirect <run_id_or_dec_id> <instruction>``.

    Parts layout (set by the caller):
      parts[0] = "/redirect"
      parts[1] = id token (``wfo_xxx`` or ``dec_xxx``)
      parts[2] = free-text instruction

    Operator must be admin and the id must match either the orchestrator's
    WorkflowRun or the decisions store's pending decision.
    """
    if not _is_admin(user_id):
        await _tb._send_message(
            bot_token, chat_id,
            "⛔ /redirect is admin-only. Set TELEGRAM_ADMIN_USER_IDS to grant access.",
        )
        return
    if len(parts) < 3:
        await _tb._send_message(
            bot_token, chat_id,
            "Usage: /redirect <wfo_xxx|dec_xxx> <new instruction>",
        )
        return

    target_id = parts[1].strip()
    instruction = " ".join(parts[2:]).strip()
    if not instruction:
        await _tb._send_message(
            bot_token, chat_id,
            "Usage: /redirect <wfo_xxx|dec_xxx> <new instruction> (instruction required).",
        )
        return

    # Try orchestrator first (wfo_*) — it has the mutating surface and the
    # checkpoint story. If the id is dec_*, route through the decisions store.
    if target_id.startswith(_REDIRECT_PREFIX_DEC):
        store = _get_decisions_store()
        if store is None:
            await _tb._send_message(bot_token, chat_id, "decisions_store unavailable.")
            return
        decision = store.get(target_id)
        if decision is None:
            await _tb._send_message(
                bot_token, chat_id,
                f"⚠️ Decision `{target_id}` not found.",
            )
            return
        # Resolve the decision's parent run via lookup tables or the decision row.
        parent_run_id = decision.get("parent_run_id") or decision.get("parent_run")
        if parent_run_id:
            # Found a parent run — admin wants to redirect the orchestrator run.
            target_id = parent_run_id
            # fall through to WFO branch below
        else:
            # Pending decision with no parent run — auto-approve with new instruction.
            try:
                store.resolve(
                    target_id,
                    outcome="redirected",
                    resolver=f"telegram:{user_id}",
                )
            except Exception as exc:  # noqa: BLE001
                await _tb._send_message(bot_token, chat_id, f"resolve failed: {exc}")
                return
            await _tb._send_message(
                bot_token, chat_id,
                f"✅ Decision `{target_id}` resolved as redirected.\n"
                f"New instruction: `{instruction[:240]}`\n"
                f"(no parent run — start a fresh /freebuff if you want execution).",
            )
            return

    # WFO branch
    if not target_id.startswith(_REDIRECT_PREFIX_WFO):
        await _tb._send_message(
            bot_token, chat_id,
            f"⚠️ Unrecognised id `{target_id}` — expected `wfo_xxx` or `dec_xxx`.",
        )
        return

    orchestrator = _get_workflow_orchestrator()
    if orchestrator is None:
        await _tb._send_message(bot_token, chat_id, "Orchestrator unavailable right now.")
        return
    try:
        await orchestrator.update_task(
            target_id,
            additional_instructions=instruction,
            operator=f"telegram:{user_id}",
        )
    except KeyError:
        await _tb._send_message(bot_token, chat_id, f"⚠️ Run `{target_id}` not found.")
        return
    except ValueError as exc:
        await _tb._send_message(bot_token, chat_id, f"⚠️ `{target_id}` cannot accept new instructions: {exc}")
        return
    except Exception as exc:  # noqa: BLE001
        await _tb._send_message(bot_token, chat_id, f"Redirect failed: {exc}")
        return

    await _tb._send_message(
        bot_token, chat_id,
        f"✅ Run `{target_id}` redirect queued.\n"
        f"New instruction (added to metadata):\n```\n{instruction[:480]}\n```",
    )


# ─── /paste command (read big-paste files) ───────────────────────────────────

async def handle_paste(
    bot_token: str,
    chat_id: int,
    user_id: int,
    parts: list[str],
) -> None:
    """``/paste <path>`` — read up to 700 chars of a previously saved paste.

    Mirrors the SVG behaviour of paste-discussion channels: paste first, ask
    questions after. Anything larger than 700 chars is truncated and the
    operator is asked to ``cat`` the file.
    """
    if not _is_admin(user_id):
        await _tb._send_message(bot_token, chat_id, "⛔ /paste is admin-only.")
        return
    if len(parts) < 2:
        await _tb._send_message(bot_token, chat_id, "Usage: /paste <path>")
        return
    from pathlib import Path as _P
    target = _P(parts[1].strip()).expanduser()
    if not target.is_absolute():
        await _tb._send_message(bot_token, chat_id, "Path must be absolute.")
        return
    if not target.exists():
        await _tb._send_message(bot_token, chat_id, f"⚠️ Not found: `{target}`")
        return
    try:
        body = target.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        await _tb._send_message(bot_token, chat_id, f"read failed: {exc}")
        return
    preview = ir.sanitize_paste_for_preview(body, max_chars=700)
    if len(body) > 700:
        await _tb._send_message(
            bot_token, chat_id,
            f"📄 `{target}` (truncated to 700 chars, total {len(body)} chars):\n{preview}",
        )
        return
    await _tb._send_message(bot_token, chat_id, f"📄 `{target}`:\n{preview}")
