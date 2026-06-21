"""
Secure Telegram control plane for qwen-server.

Provides remote command/control of the local LLM proxy via a Telegram bot.
All commands are auth-gated by Telegram user ID. Admin commands require approval.

Setup:
  1. Create a bot via @BotFather — get TELEGRAM_BOT_TOKEN
  2. Find your user ID via @userinfobot — set TELEGRAM_ALLOWED_USER_IDS
  3. Set TELEGRAM_ADMIN_USER_IDS (subset of ALLOWED, can run mutating commands)
  4. Add both to .env and restart

  Shortcut: for a single-operator setup, set only TELEGRAM_BOT_TOKEN and
  TELEGRAM_CHAT_ID. TELEGRAM_CHAT_ID is used as a fallback for BOTH
  TELEGRAM_ALLOWED_USER_IDS and TELEGRAM_ADMIN_USER_IDS (bot auth) and for
  outbound notifications/approval-gate pushes — so the same ID does not need
  to be repeated under multiple env var names.

Run:
  python telegram_bot.py

Dependencies:
  pip install python-telegram-bot httpx python-dotenv

Command reference:
  READ-ONLY (any allowed user):
    /status          — proxy + ollama + tunnel health
    /models          — loaded Ollama models
    /cost            — local infra cost projection
    /help            — show all commands

  ADMIN-ONLY (immediate):
    /start <svc>     — start ollama|proxy|tunnel|stack
    /stop <svc>      — stop service
    /restart <svc>   — restart service

  ADMIN-ONLY (requires confirmation):
    /agent <task>    — run an agent task (reply 'yes' within 30s to confirm)
    /keylist         — list API key records
    /keycreate <email> <dept> — create new API key

Security model:
  - All messages from non-allowlisted user IDs are silently dropped.
  - Admin commands from non-admin IDs return a permission error.
  - Approval-required commands time out after 30 seconds.
  - The proxy API key used by this bot is stored in TELEGRAM_PROXY_API_KEY.
  - This bot never exposes API keys or secrets in Telegram messages.
  - Rate limiting: max 5 commands per user per minute (in-memory).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import defaultdict
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

log = logging.getLogger("qwen-telegram")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] telegram-bot %(message)s",
)

# ─── Configuration ─────────────────────────────────────────────────────────────

TELEGRAM_BOT_TOKEN: str = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
# Telegram tokens MUST not contain any whitespace — a common copy-paste error
# from BotFather. Strip all whitespace (not just leading/trailing) defensively.
TELEGRAM_BOT_TOKEN = "".join(TELEGRAM_BOT_TOKEN.split())
PROXY_BASE_URL: str = os.environ.get("PROXY_BASE_URL", "http://localhost:8000").rstrip("/")
PROXY_ADMIN_SECRET: str = os.environ.get("ADMIN_SECRET", "").strip()
PROXY_API_KEY: str = os.environ.get("TELEGRAM_PROXY_API_KEY", "").strip()

_raw_allowed = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
_raw_admins = os.environ.get("TELEGRAM_ADMIN_USER_IDS", "").strip()
_raw_chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()


def _parse_user_ids(raw: str) -> set[int]:
    """Extract numeric Telegram user IDs from a raw env value, tolerantly.

    Accepts comma/space/semicolon separators and ignores wrapping quotes,
    brackets, or stray characters (e.g. ``"123, 456"``, ``[123 456]``,
    ``@name`` is dropped — usernames are not valid IDs). Splits on separators,
    strips wrapping quotes/brackets, and validates each token is purely numeric.
    """
    import re as _re
    if not raw:
        return set()
    # Split on common separators: comma, semicolon, whitespace
    tokens = _re.split(r'[,;\s]+', raw.strip())
    result = set()
    for token in tokens:
        if not token:
            continue
        # Strip surrounding quotes, brackets, parentheses
        cleaned = token.strip().strip('"\'[](){}')
        # Only accept tokens that are purely numeric (with optional leading minus)
        if _re.match(r'^-?\d+$', cleaned):
            result.add(int(cleaned))
        elif cleaned:
            log.debug(
                "Rejected Telegram user ID token %r (cleaned as %r) — must be purely numeric.",
                token, cleaned,
            )
    return result


def _resolve_bot_user_ids(raw_allowed: str, raw_admin: str, raw_chat_id: str) -> tuple[set[int], set[int]]:
    """Resolve the ALLOWED/ADMIN Telegram user-ID sets.

    ``TELEGRAM_CHAT_ID`` is the single-var convention (Autonomy Charter G1):
    when ``TELEGRAM_ALLOWED_USER_IDS`` / ``TELEGRAM_ADMIN_USER_IDS`` are unset,
    the same chat/user ID drives bot auth (allowed + admin) AND notification
    delivery, so operators do not need to set the same ID under multiple env
    var names.
    """
    chat_ids = _parse_user_ids(raw_chat_id)
    allowed = _parse_user_ids(raw_allowed) or chat_ids
    admin = _parse_user_ids(raw_admin) or chat_ids
    return allowed, admin


ALLOWED_USER_IDS: set[int]
ADMIN_USER_IDS: set[int]
ALLOWED_USER_IDS, ADMIN_USER_IDS = _resolve_bot_user_ids(_raw_allowed, _raw_admins, _raw_chat_id)

APPROVAL_TIMEOUT_SECONDS = 30
MAX_COMMANDS_PER_MINUTE = 5

# In-memory pending approvals: user_id → {expires, action, payload}
_pending_approvals: dict[int, dict] = {}
# In-memory rate limiter: user_id → [timestamps]
_rate_buckets: dict[int, list[float]] = defaultdict(list)
# In-memory FreeBuff session state: user_id → {task, models, model}
_freebuff_state: dict[int, dict] = {}

# Strong references to fire-and-forget background tasks (e.g. the approval-gate
# resume). Without this, asyncio may garbage-collect a running task mid-flight
# (Ruff RUF006). Tasks remove themselves on completion.
_bg_tasks: set[asyncio.Task] = set()

# One-shot throttle flag for the silent-drop remediation WARNING. Set to True
# the first time a tele-driven message arrives while ALLOWED_USER_IDS is empty;
# subsequent drops downgrade to INFO so a curious operator pushing the bot
# repeatedly doesn't fill the log with the same line. The flag lives at
# module scope so the check-set is atomic across the bot's single asyncio
# event loop (no awaits between the check and the set). It is NOT reset on
# config reload — that's acceptable because a process restart clears it.
_EMPTY_ALLOWLIST_WARNED: bool = False


# ─── Auth helpers ──────────────────────────────────────────────────────────────

def _is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS or user_id in ADMIN_USER_IDS


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


def _log_silent_drop(user_id: int) -> None:
    global _EMPTY_ALLOWLIST_WARNED
    """Log a single non-allowlisted telegram drop, with one-shot remediation hint.

    When ``ALLOWED_USER_IDS`` is empty (the operator's "did not trigger
    any responses" bootstrap symptom), fire a WARNING with a remediation
    hint ONCE per process. Subsequent drops downgrade to INFO so the log
    doesn't flood. The non-empty case keeps the original single-line
    WARNING per drop.

    Module-scope ``_EMPTY_ALLOWLIST_WARNED`` flag is read+written here so
    ``_process_update`` (the caller) does not need a ``global``. The flag
    stays TRUE until process restart — acceptable in practice.
    """
    if not ALLOWED_USER_IDS:
        if not _EMPTY_ALLOWLIST_WARNED:
            log.warning(
                "Ignored telegram message from user=%d (allowlist EMPTY — "
                "set TELEGRAM_CHAT_ID or TELEGRAM_ALLOWED_USER_IDS to your "
                "numeric Telegram user ID from @userinfobot, then restart)",
                user_id,
            )
            _EMPTY_ALLOWLIST_WARNED = True
        else:
            log.info(
                "Ignored telegram message from user=%d (allowlist empty — see prior WARNING)",
                user_id,
            )
    else:
        log.warning("Ignored message from non-allowlisted user %d", user_id)


def _poller_disabled() -> bool:
    """True when TELEGRAM_POLLER_DISABLED is set to a truthy value.

    Centralised so the /diag handler and the run_bot() long-poll can never
    drift apart on what counts as truthy. Accepts ``1``, ``true``, ``yes``,
    ``on`` (case-insensitive); any other value (including unset) is False.
    """
    return (
        os.environ.get("TELEGRAM_POLLER_DISABLED", "").strip().lower()
        in ("1", "true", "yes", "on")
    )


def _check_rate_limit(user_id: int) -> bool:
    now = time.time()
    bucket = _rate_buckets[user_id]
    _rate_buckets[user_id] = [t for t in bucket if now - t < 60]
    if len(_rate_buckets[user_id]) >= MAX_COMMANDS_PER_MINUTE:
        return False
    _rate_buckets[user_id].append(now)
    return True


# ─── Proxy API calls ───────────────────────────────────────────────────────────

def _admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {PROXY_ADMIN_SECRET}"}


def _api_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {PROXY_API_KEY}"}


async def _proxy_get(path: str, use_admin: bool = True) -> dict:
    headers = _admin_headers() if use_admin else _api_headers()
    async with httpx.AsyncClient(timeout=10.0) as client:
        r = await client.get(f"{PROXY_BASE_URL}{path}", headers=headers)
        r.raise_for_status()
        return r.json()


async def _proxy_post(path: str, body: dict, use_admin: bool = True) -> dict:
    headers = _admin_headers() if use_admin else _api_headers()
    async with httpx.AsyncClient(timeout=60.0) as client:
        r = await client.post(f"{PROXY_BASE_URL}{path}", json=body, headers=headers)
        r.raise_for_status()
        return r.json()


# ─── Command handlers ──────────────────────────────────────────────────────────

async def cmd_status(user_id: int) -> str:
    try:
        data = await _proxy_get("/admin/api/status")
        services = data.get("services", {})
        tunnel_url = data.get("tunnel_url", "unknown")
        lines = ["*Service status:*"]
        for svc, info in services.items():
            state = "running" if info.get("running") else "stopped"
            icon = "🟢" if info.get("running") else "🔴"
            lines.append(f"  {icon} {svc}: {state}")
        lines.append(f"\nTunnel: `{tunnel_url}`")
        return "\n".join(lines)
    except Exception as exc:
        return f"Status check failed: {exc}"


async def cmd_models(user_id: int) -> str:
    try:
        data = await _proxy_get("/health", use_admin=False)
        models = data.get("models", [])
        if not models:
            return "No models loaded."
        return "*Loaded models:*\n" + "\n".join(f"  • `{m}`" for m in models)
    except Exception as exc:
        return f"Model check failed: {exc}"


async def cmd_cost(user_id: int) -> str:
    try:
        from infra_cost import project_session_cost
        proj = project_session_cost()
        return f"*Local infra cost estimate:*\n```\n{proj.summary()}\n```"
    except Exception as exc:
        return f"Cost model error: {exc}"


async def cmd_control(user_id: int, action: str, target: str) -> str:
    if not _is_admin(user_id):
        return "Permission denied. Admin only."
    valid_actions = {"start", "stop", "restart"}
    valid_targets = {"ollama", "proxy", "tunnel", "stack"}
    if action not in valid_actions or target not in valid_targets:
        return f"Invalid action/target. Use: {valid_actions} / {valid_targets}"
    try:
        data = await _proxy_post("/admin/api/control", {"action": action, "target": target})
        return f"{action} {target}: `{data.get('status', 'ok')}`"
    except Exception as exc:
        return f"Control failed: {exc}"


async def cmd_keylist(user_id: int) -> str:
    if not _is_admin(user_id):
        return "Permission denied. Admin only."
    try:
        data = await _proxy_get("/admin/api/users")
        records = data.get("records", [])
        if not records:
            return "No keys found."
        lines = [f"*API Keys ({len(records)}):*"]
        for rec in records[:10]:
            lines.append(f"  • `{rec['key_id']}` — {rec['email']} ({rec['department']})")
        if len(records) > 10:
            lines.append(f"  …and {len(records) - 10} more")
        return "\n".join(lines)
    except Exception as exc:
        return f"Key list failed: {exc}"


def _request_approval(user_id: int, action: str, payload: dict) -> None:
    _pending_approvals[user_id] = {
        "expires": time.time() + APPROVAL_TIMEOUT_SECONDS,
        "action": action,
        "payload": payload,
    }


def _pop_approval(user_id: int) -> dict | None:
    pending = _pending_approvals.get(user_id)
    if not pending:
        return None
    if time.time() > pending["expires"]:
        del _pending_approvals[user_id]
        return None
    del _pending_approvals[user_id]
    return pending


# ─── Telegram update processing ────────────────────────────────────────────────

async def _send_voice(bot_token: str, chat_id: int, voice_bytes: bytes) -> None:
    """Send an OGG voice note to a Telegram chat."""
    import httpx
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendVoice",
                data={"chat_id": chat_id},
                files={"voice": ("voice.ogg", voice_bytes, "audio/ogg")},
            )
            resp.raise_for_status()
    except Exception as exc:
        log.warning("Failed to send voice note: %s", exc)


async def _send_message(bot_token: str, chat_id: int, text: str, parse_mode: str = "Markdown") -> Optional[int]:
    """Send a plaintext Markdown-v1 message and return its Telegram message_id.

    Returns ``None`` when the bot's response parsing fails (no message_id in
    payload, network error, OR Telegram rejected with a 4xx). Existing call
    sites assign the result to ``None`` so adding a return type doesn't break
    them. The new inbound-router callers use ``_send_message_with_id`` (an
    alias below) so it's obvious the bot_message_links linkage depends on the
    message_id being returned.
    """
    return await _send_message_with_id(bot_token, chat_id, text, parse_mode=parse_mode)


async def _send_message_with_id(
    bot_token: str,
    chat_id: int,
    text: str,
    parse_mode: str = "Markdown",
) -> Optional[int]:
    """Send a message and return the Telegram ``message_id``.

    Used by ``telegram_inbound_handlers`` so ``bot_message_links.link_message``
    can capture the outbound ID. Never raises — the webhook must not 5xx on
    a transient Telegram API error.
    """
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            r = await client.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json=payload,
            )
        if r.status_code != 200:
            log.warning(
                "_send_message_with_id non-200 chat_id=%s status=%s",
                chat_id, r.status_code,
            )
            return None
        try:
            body = r.json()
        except Exception as exc:  # pragma: no cover - malformed JSON
            log.warning("_send_message_with_id json_decode_failed: %s", exc)
            return None
        return int(((body or {}).get("result") or {}).get("message_id") or 0) or None
    except Exception as exc:  # noqa: BLE001 - any network error -> None
        log.warning("_send_message_with_id failed chat_id=%s exc=%s", chat_id, exc)
        return None


async def _send_keyboard(
    bot_token: str, chat_id: int, text: str, keyboard: list[list[dict]], parse_mode: str = "Markdown"
) -> None:
    """Send a message with an inline keyboard (list of button rows)."""
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "reply_markup": {"inline_keyboard": keyboard},
    }
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
        )


async def _edit_message(
    bot_token: str,
    chat_id: int,
    message_id: int,
    text: str,
    keyboard: list[list[dict]] | None = None,
    parse_mode: str = "Markdown",
) -> None:
    """Edit an existing message's text and (optionally) its inline keyboard."""
    payload: dict = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": parse_mode,
    }
    if keyboard is not None:
        payload["reply_markup"] = {"inline_keyboard": keyboard}
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/editMessageText",
            json=payload,
        )


async def _answer_callback(bot_token: str, callback_id: str, text: str = "") -> None:
    """Acknowledge a callback query so Telegram stops the button's loading spinner."""
    payload = {"callback_query_id": callback_id}
    if text:
        payload["text"] = text
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/answerCallbackQuery",
            json=payload,
        )


# ─── FreeBuff (free-NVIDIA coding agent) ────────────────────────────────────────

def _parse_callback(data: str) -> tuple[str, str | None]:
    """Parse callback_data of the form ``fb:<action>[:<arg>]`` (FreeBuff) or
    ``wfo:<action>:<run_id>`` (workflow-orchestrator approval gate, G1).

    Returns ``(action, arg)``; ``arg`` is None when absent. ``wfo:`` actions
    are returned as ``wfo_<action>`` (e.g. ``wfo_approve``) so callers can
    dispatch on them without colliding with FreeBuff action names. Unknown
    prefixes yield ``("", None)``.
    """
    if not data:
        return "", None
    if data.startswith("fb:"):
        parts = data.split(":", 2)
        action = parts[1] if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else None
        return action, arg
    if data.startswith("wfo:"):
        parts = data.split(":", 2)
        action = parts[1] if len(parts) > 1 else ""
        arg = parts[2] if len(parts) > 2 else None
        return (f"wfo_{action}" if action else ""), arg
    return "", None


def _model_keyboard(models: list[str]) -> list[list[dict]]:
    """Build an inline keyboard mapping each free model to ``fb:model:<idx>``.

    Model IDs (e.g. ``nvidia/llama-3.3-nemotron-super-49b-v1``) can exceed Telegram's
    64-byte callback_data limit, so we send the index and resolve it server-side
    from the per-user stored model list.
    """
    return [[{"text": m, "callback_data": f"fb:model:{i}"}] for i, m in enumerate(models)]


def _review_keyboard() -> list[list[dict]]:
    """Accept / reject keyboard shown after a FreeBuff plan is generated."""
    return [[
        {"text": "✅ Accept & run", "callback_data": "fb:accept"},
        {"text": "❌ Reject", "callback_data": "fb:reject"},
    ]]


# ── FreeBuff backend: embedded (in-process agent) or HTTP (proxy) ───────────────
# Embedded mode runs FreeBuffAgent directly in this process — no proxy server
# needed — so the bot is a single self-contained 24x7 worker (Render/Docker).
# HTTP mode (default) talks to a running proxy at PROXY_BASE_URL.

def _embedded() -> bool:
    return os.environ.get("FREEBUFF_EMBEDDED", "").strip().lower() in {"true", "1", "yes"}


def _freebuff_max_steps() -> int:
    try:
        return max(1, min(20, int(os.environ.get("FREEBUFF_MAX_STEPS", "10"))))
    except ValueError:
        return 10


async def _fb_models() -> list[str]:
    """Return the free model list (embedded or via proxy)."""
    if _embedded():
        from agent.loop import FreeBuffAgent
        return FreeBuffAgent.available_models()
    data = await _proxy_get("/freebuff/models", use_admin=False)
    return data.get("models", [])


async def _fb_plan(task: str, model: str) -> dict:
    """Generate a read-only plan (embedded or via proxy). Shape: {model, plan}."""
    if _embedded():
        from agent.loop import FreeBuffAgent
        agent = FreeBuffAgent(model=model)
        plan = await agent.plan(
            instruction=task, history=[], requested_model=model,
            max_steps=_freebuff_max_steps(),
        )
        return {"model": agent.resolve_model(model), "plan": plan.model_dump()}
    return await _proxy_post(
        "/freebuff/plan", {"instruction": task, "model": model}, use_admin=False,
    )


async def _fb_run(task: str, model: str) -> dict:
    """Execute a FreeBuff task (embedded or via proxy). Shape: {result: {...}}."""
    if _embedded():
        return await _embedded_run(task, model)
    return await _proxy_post(
        "/freebuff/run",
        {"instruction": task, "model": model, "auto_commit": True, "open_pr": True},
        use_admin=False,
    )


async def _embedded_run(task: str, model: str) -> dict:
    """Run FreeBuffAgent in-process against a fresh clone, committing + opening a PR.

    Clones FREEBUFF_REPO_URL with the GitHub token so the agent edits a real
    checkout and its existing auto-push/PR path can open a draft PR. Returns the
    same ``{"result": {...}}`` shape as the proxy endpoint so callers are agnostic.
    """
    import re
    import shutil

    from agent.loop import FreeBuffAgent

    repo_url = os.environ.get("FREEBUFF_REPO_URL", "").strip()
    base_branch = os.environ.get("FREEBUFF_BASE_BRANCH", "master").strip() or "master"
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_PAT")
    workspace_root: str | None = None

    if repo_url and token:
        m = re.search(r"github\.com[:/]([^/]+)/([^/#?.]+)", repo_url)
        if m:
            from agent.github_tools import LocalWorkspace
            owner, repo = m.group(1), m.group(2)
            try:
                ws = LocalWorkspace(owner, repo, token)
                if ws.path.exists():
                    shutil.rmtree(ws.path, ignore_errors=True)
                await ws.clone_or_pull()
                workspace_root = str(ws.path)
            except Exception as exc:  # clone failure → run without PR, still report
                log.warning("FreeBuff clone failed (%s) — running without PR", exc)

    agent = FreeBuffAgent(
        model=model,
        workspace_root=workspace_root,
        github_token=token,
        repo_url=repo_url or None,
        base_branch=base_branch,
    )

    # Allow the agent run even when the host process runs in orchestrator mode
    # (e.g. embedded in the backend web service). FreeBuff is a sanctioned,
    # user-invoked path, so we set the orchestrator bypass for the duration of
    # this run — the same mechanism TaskExecutionCoordinator uses. Harmless when
    # the process is already in legacy mode (dedicated worker).
    bypass_token = None
    try:
        from services.workflow_orchestrator import _BYPASS
        bypass_token = _BYPASS.set(True)
    except Exception:
        _BYPASS = None  # type: ignore[assignment]
    try:
        result = await agent.run(
            instruction=task, history=[], requested_model=model,
            auto_commit=True, max_steps=_freebuff_max_steps(),
        )
    finally:
        if bypass_token is not None and _BYPASS is not None:
            _BYPASS.reset(bypass_token)
    return {"result": result}


async def cmd_freebuff(user_id: int, chat_id: int, bot_token: str, task: str) -> None:
    """Start a FreeBuff flow: fetch free models and present a picker keyboard."""
    if not _is_admin(user_id):
        await _send_message(bot_token, chat_id, "Permission denied. Admin only.")
        return
    if not task:
        await _send_message(bot_token, chat_id, "Usage: /freebuff <task description>")
        return
    try:
        models = await _fb_models()
    except Exception as exc:
        await _send_message(bot_token, chat_id, f"Could not load FreeBuff models: {exc}")
        return
    if not models:
        await _send_message(bot_token, chat_id, "No free models available.")
        return
    _freebuff_state[user_id] = {"task": task, "models": models, "model": None}
    await _send_keyboard(
        bot_token,
        chat_id,
        f"*FreeBuff task:* `{task[:200]}`\n\nPick a free NVIDIA model:",
        _model_keyboard(models),
    )


async def _process_callback(bot_token: str, callback: dict) -> None:
    """Handle an inline-button press for the FreeBuff accept/reject/model flow."""
    callback_id = callback.get("id", "")
    user_id = callback.get("from", {}).get("id", 0)
    message = callback.get("message", {}) or {}
    chat_id = message.get("chat", {}).get("id", 0)
    message_id = message.get("message_id", 0)
    data = callback.get("data", "")

    if not _is_allowed(user_id) or not _is_admin(user_id):
        await _answer_callback(bot_token, callback_id, "Not allowed.")
        return

    action, arg = _parse_callback(data)
    if not action:
        await _answer_callback(bot_token, callback_id)
        return

    if action.startswith("wfo_"):
        await _process_wfo_callback(bot_token, callback_id, chat_id, message_id, user_id, action, arg)
        return

    state = _freebuff_state.get(user_id)
    if not state:
        await _answer_callback(bot_token, callback_id, "Session expired. Start with /freebuff.")
        return

    if action == "model":
        models = state.get("models", [])
        try:
            model = models[int(arg)]
        except (TypeError, ValueError, IndexError):
            await _answer_callback(bot_token, callback_id, "Invalid model.")
            return
        state["model"] = model
        await _answer_callback(bot_token, callback_id, f"Planning with {model}…")
        await _edit_message(bot_token, chat_id, message_id, f"Generating plan with `{model}`…")
        try:
            result = await _fb_plan(state["task"], model)
            plan = result.get("plan", {})
            steps = plan.get("steps", [])
            lines = [f"*Plan* (`{model}`)", f"_{plan.get('goal', state['task'])[:300]}_", ""]
            for i, step in enumerate(steps[:10], start=1):
                lines.append(f"{i}. {str(step.get('description', ''))[:160]}")
            await _edit_message(bot_token, chat_id, message_id, "\n".join(lines), _review_keyboard())
        except Exception as exc:
            await _edit_message(bot_token, chat_id, message_id, f"Plan failed: {exc}")
        return

    if action == "reject":
        _freebuff_state.pop(user_id, None)
        await _answer_callback(bot_token, callback_id, "Rejected.")
        await _edit_message(bot_token, chat_id, message_id, "❌ FreeBuff task rejected.")
        return

    if action == "accept":
        model = state.get("model")
        if not model:
            await _answer_callback(bot_token, callback_id, "Pick a model first.")
            return
        await _answer_callback(bot_token, callback_id, "Running…")
        await _edit_message(bot_token, chat_id, message_id, f"Running FreeBuff with `{model}`… (this may take a while)")
        try:
            result = await _fb_run(state["task"], model)
            summary = result.get("result", {}).get("summary", str(result))
            pr_url = (result.get("result", {}) or {}).get("pr_url")
            text = f"*FreeBuff result* (`{model}`)\n```\n{summary[:3000]}\n```"
            if pr_url:
                text += f"\n\nPR: {pr_url}"
            await _edit_message(bot_token, chat_id, message_id, text)
        except Exception as exc:
            await _edit_message(bot_token, chat_id, message_id, f"FreeBuff run failed: {exc}")
        finally:
            _freebuff_state.pop(user_id, None)
        return

    await _answer_callback(bot_token, callback_id)


async def _process_wfo_callback(
    bot_token: str,
    callback_id: str,
    chat_id: int,
    message_id: int,
    user_id: int,
    action: str,
    run_id: str | None,
) -> None:
    """Handle an inline Approve/Reject button on a WorkflowOrchestrator
    approval-gate message (Autonomy Charter G1).

    The embedded Telegram bot runs in the same process as the
    WorkflowOrchestrator singleton (``RUN_BACKGROUND_IN_WEB=true``), so this
    calls ``get_workflow_orchestrator()`` directly — no extra HTTP/auth surface.
    The caller (``_process_callback``) has already verified the user is
    allowed and admin.
    """
    if not run_id:
        await _answer_callback(bot_token, callback_id, "Missing run id.")
        return

    try:
        from services.workflow_orchestrator import get_workflow_orchestrator
        orchestrator = get_workflow_orchestrator()
    except Exception as exc:
        log.warning("WorkflowOrchestrator unavailable for wfo callback: %s", exc)
        await _answer_callback(bot_token, callback_id, "Orchestrator unavailable.")
        return

    if action == "wfo_approve":
        try:
            orchestrator.approve(run_id, approved_by=f"telegram:{user_id}")
        except KeyError:
            await _answer_callback(bot_token, callback_id, "Run not found.")
            await _edit_message(
                bot_token, chat_id, message_id,
                f"⚠️ Run `{run_id}` not found — it may have expired or already been resolved.",
            )
            return
        except ValueError as exc:
            await _answer_callback(bot_token, callback_id, "Already resolved.")
            await _edit_message(bot_token, chat_id, message_id, f"ℹ️ Run `{run_id}`: {exc}")
            return

        # Queue the resume FIRST, before the best-effort Telegram UI updates
        # below (Codex P2): if _answer_callback/_edit_message raised a transport
        # error after approve() but before scheduling, the run would be left
        # approved-but-not-queued (stuck awaiting_approval). approve_async is
        # idempotent on the approval transition (the sync approve() above
        # already validated + transitioned the run), and resumes via the FIFO
        # queue / inline fallback without blocking the bot's update loop.
        _task = asyncio.create_task(
            orchestrator.approve_async(run_id, approved_by=f"telegram:{user_id}")
        )
        _bg_tasks.add(_task)
        _task.add_done_callback(_bg_tasks.discard)

        await _answer_callback(bot_token, callback_id, "Approved — resuming…")
        await _edit_message(
            bot_token, chat_id, message_id,
            f"✅ Approved by telegram:{user_id}. Resuming run `{run_id}`…",
        )
        return

    if action == "wfo_reject":
        if orchestrator.cancel_run(run_id):
            await _answer_callback(bot_token, callback_id, "Rejected.")
            await _edit_message(bot_token, chat_id, message_id, f"❌ Rejected by telegram:{user_id}. Run `{run_id}` cancelled.")
        else:
            await _answer_callback(bot_token, callback_id, "Run not found.")
            await _edit_message(
                bot_token, chat_id, message_id,
                f"⚠️ Run `{run_id}` not found — it may have already been resolved.",
            )
        return

    await _answer_callback(bot_token, callback_id)


async def _download_telegram_file(bot_token: str, file_id: str) -> bytes | None:
    """Download a file from Telegram servers by file_id. Returns raw bytes."""
    try:
        import httpx
        async with httpx.AsyncClient(timeout=30) as client:
            # Step 1: get file path
            info = await client.get(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                params={"file_id": file_id},
            )
            info.raise_for_status()
            file_path = info.json().get("result", {}).get("file_path")
            if not file_path:
                return None
            # Step 2: download file
            dl = await client.get(
                f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
            )
            dl.raise_for_status()
            return dl.content
    except Exception as exc:
        log.warning("Failed to download Telegram file %s: %s", file_id, exc)
        return None


async def _process_update(bot_token: str, update: dict) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    user_id: int = message.get("from", {}).get("id", 0)
    chat_id: int = message.get("chat", {}).get("id", 0)
    text: str = (message.get("text") or "").strip()

    # ── Voice note / audio message handling (issue #664, Jarvis OS voice pipeline) ──
    # If the user sent a voice note or audio file, download + transcribe it to text
    # then process it as a regular command/message. This lets you speak to the CEO
    # agent from your phone via Telegram voice notes.
    voice_or_audio = message.get("voice") or message.get("audio")
    if voice_or_audio and not text:
        file_id = voice_or_audio.get("file_id")
        if file_id and _is_allowed(message.get("from", {}).get("id", 0)):
            try:
                from voice.stt import transcribe as _stt_transcribe
                audio_bytes = await _download_telegram_file(bot_token, file_id)
                if audio_bytes:
                    transcribed = await _stt_transcribe(audio_bytes, "voice.ogg")
                    if transcribed:
                        text = transcribed
                        await _send_message(
                            bot_token, chat_id,
                            f"🎤 _Heard:_ {text}",
                        )
                        # Store in memory kernel
                        try:
                            from voice.memory_kernel import get_memory_kernel
                            await get_memory_kernel().store(
                                f"CEO said via voice: {text}",
                                source="telegram_voice",
                            )
                        except Exception as _mem_exc:
                            log.debug("Memory kernel store failed: %s", _mem_exc)
                    else:
                        await _send_message(bot_token, chat_id,
                                            "🎤 Could not transcribe audio. Please try again or type your command.")
                        return
            except ImportError:
                await _send_message(bot_token, chat_id,
                                    "🎤 Voice pipeline not installed. Run: pip install faster-whisper gtts pydub")
                return
            except Exception as _voice_exc:
                log.warning("Voice transcription failed: %s", _voice_exc)
                await _send_message(bot_token, chat_id,
                                    f"🎤 Transcription error: {_voice_exc}")
                return

    # Silent drop for non-allowlisted users. The throttle logic lives in
    # ``_log_silent_drop`` (module-scope, no ``global``) so a curious operator
    # pushing the bot repeatedly doesn't fill the log with the same line.
    if not _is_allowed(user_id):
        _log_silent_drop(user_id)
        return

    # Rate limiting
    if not _check_rate_limit(user_id):
        await _send_message(bot_token, chat_id, "Rate limit reached. Please wait a minute.")
        return

    # Check for pending approval confirmation
    if text.lower() in ("yes", "confirm", "y"):
        approval = _pop_approval(user_id)
        if approval:
            action = approval["action"]
            payload = approval["payload"]
            if action == "agent":
                await _send_message(bot_token, chat_id, "Running agent task… (this may take a while)")
                try:
                    result = await _proxy_post("/agent/run", payload, use_admin=False)
                    summary = result.get("result", {}).get("summary", str(result))
                    await _send_message(bot_token, chat_id, f"*Agent result:*\n```\n{summary[:3000]}\n```")
                except Exception as exc:
                    await _send_message(bot_token, chat_id, f"Agent failed: {exc}")
            return
        # No pending approval — treat as regular message

    if text.lower() in ("no", "cancel", "n"):
        _pop_approval(user_id)
        await _send_message(bot_token, chat_id, "Cancelled.")
        return

    # Command dispatch
    parts = text.split(maxsplit=2)
    cmd = parts[0].lower().split("@")[0] if parts else ""

    response = ""

    # ── Step 1 inbound-routing commands: /redirect and /paste.
    # Imported lazily so the bot's import surface stays stable when the
    # inbound-routing module is missing (test paths / minimal deploys).
    if cmd == "/redirect":
        try:
            from telegram_inbound_handlers import handle_redirect
            await handle_redirect(bot_token, chat_id, user_id, parts)
        except ImportError as exc:
            log.warning("telegram_bot: inbound_handlers import failed: %s", exc)
            await _send_message(
                bot_token, chat_id,
                "telegram_inbound_handlers is not installed; /redirect is offline.",
            )
        return

    if cmd == "/paste":
        try:
            from telegram_inbound_handlers import handle_paste
            await handle_paste(bot_token, chat_id, user_id, parts)
        except ImportError as exc:
            log.warning("telegram_bot: inbound_handlers import failed: %s", exc)
            await _send_message(
                bot_token, chat_id,
                "telegram_inbound_handlers is not installed; /paste is offline.",
            )
        return

    if cmd == "/help":
        response = (
            "*Available commands:*\n"
            "/status — service health\n"
            "/models — loaded models\n"
            "/cost — local infra cost estimate\n"
            "/diag — bot config + allowlist diagnostics (admin)\n"
            "/redirect <wfo_xxx|dec_xxx> <new instruction> — mid-flight retarget (admin)\n"
            "/paste <abs path> — read a previously saved paste file (admin)\n"
            "\n*Voice commands (Jarvis OS):*\n"
            "🎤 Send a voice note — I'll transcribe and execute it\n"
            "/memory [query] — recall CEO memory facts\n"
            "/remember <fact> — store a fact in CEO memory\n"
            "/forget <fact-id> — remove a memory fact\n"
            "\n*Admin only:*\n"
            "/start|stop|restart <svc> — control ollama|proxy|tunnel|stack\n"
            "/agent <task> — run agent task (requires confirmation)\n"
            "/freebuff <task> — free-NVIDIA coding agent (pick model, review, accept)\n"
            "/keylist — list API keys\n"
        )

    elif cmd == "/diag":
        if not _is_admin(user_id):
            response = "Permission denied. Admin only."
        else:
            token_present = bool(TELEGRAM_BOT_TOKEN)
            # Mask the token as first-4 … last-4 only when the two regions
            # are guaranteed not to overlap (length ≥ 16). Shorter tokens go
            # to `<too short>` rather than risk leaking the full value.
            safe_token = TELEGRAM_BOT_TOKEN or ""
            if token_present and len(safe_token) >= 16:
                token_prefix = f"`{safe_token[:4]}\u2026{safe_token[-4:]}`"
            elif token_present:
                token_prefix = "`<too short to mask safely>`"
            else:
                token_prefix = "`<empty>`"
            allowed = sorted(ALLOWED_USER_IDS)
            admin = sorted(ADMIN_USER_IDS)
            poller_label = (
                "DISABLED (TELEGRAM_POLLER_DISABLED=true)"
                if _poller_disabled()
                else "ACTIVE (long-polling getUpdates)"
            )

            def _render_ids(ids: list[int]) -> str:
                if not ids:
                    return "EMPTY — messages silently dropped"
                if len(ids) <= 20:
                    return ", ".join(str(i) for i in ids)
                head = ", ".join(str(i) for i in ids[:20])
                return f"{head}, …(+{len(ids) - 20} more)"

            response = (
                "*Telegram bot diagnostic*\n"
                f"Token:        {token_prefix} (`{token_present}`)\n"
                f"Allowed IDs:  `{_render_ids(allowed)}`\n"
                f"Admin IDs:    `{_render_ids(admin)}`\n"
                f"Poller:       {poller_label}\n"
                f"Proxy base:   `{PROXY_BASE_URL}`\n"
                f"You:          `telegram:{user_id}` (admin={'yes' if user_id in ADMIN_USER_IDS else 'no'})\n"
                "If Allowed/Admin are EMPTY, set `TELEGRAM_CHAT_ID` (or "
                "`TELEGRAM_ALLOWED_USER_IDS`) to your numeric Telegram user ID "
                "from @userinfobot, then restart the bot."
            )

    elif cmd == "/status":
        response = await cmd_status(user_id)

    elif cmd == "/models":
        response = await cmd_models(user_id)

    elif cmd == "/cost":
        response = await cmd_cost(user_id)

    elif cmd in ("/start", "/stop", "/restart"):
        action = cmd[1:]
        target = parts[1].lower() if len(parts) > 1 else ""
        if cmd == "/start" and not target:
            # Bare /start is the Telegram "begin" tap — greet + show help.
            response = (
                "👋 *FreeBuff bot online.*\n"
                "Send `/freebuff <task>` to edit the repo (pick a model → review → accept).\n"
                "Use /help for all commands."
            )
        elif not target:
            response = f"Usage: {cmd} <ollama|proxy|tunnel|stack>"
        else:
            response = await cmd_control(user_id, action, target)

    elif cmd == "/memory":
        query = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
        try:
            from voice.memory_kernel import get_memory_kernel
            facts = await get_memory_kernel().recall(query, limit=10)
            if not facts:
                response = "🧠 No memories found." + (f" (query: {query})" if query else "")
            else:
                lines = [f"🧠 *CEO Memory* ({len(facts)} facts):
"]
                for f in facts:
                    import datetime
                    age = datetime.datetime.utcfromtimestamp(f.updated_at).strftime("%Y-%m-%d")
                    lines.append(f"• `{f.fact_id}` [{f.source}] _{age}_
  {f.content[:120]}")
                response = "
".join(lines)
        except Exception as exc:
            response = f"Memory recall failed: {exc}"

    elif cmd == "/remember":
        fact_text = " ".join(parts[1:]).strip() if len(parts) > 1 else ""
        if not fact_text:
            response = "Usage: /remember <fact to store>"
        else:
            try:
                from voice.memory_kernel import get_memory_kernel
                fact = await get_memory_kernel().store(fact_text, source="telegram_text")
                response = f"🧠 Stored: `{fact.fact_id}` — {fact_text[:100]}"
            except Exception as exc:
                response = f"Memory store failed: {exc}"

    elif cmd == "/forget":
        fid = parts[1].strip() if len(parts) > 1 else ""
        if not fid:
            response = "Usage: /forget <fact-id>"
        else:
            try:
                from voice.memory_kernel import get_memory_kernel
                removed = await get_memory_kernel().forget(fid)
                response = f"🧠 {'Forgotten' if removed else 'Not found'}: `{fid}`"
            except Exception as exc:
                response = f"Memory forget failed: {exc}"

    elif cmd == "/keylist":
        response = await cmd_keylist(user_id)

    elif cmd == "/freebuff":
        task = " ".join(parts[1:]) if len(parts) > 1 else ""
        await cmd_freebuff(user_id, chat_id, bot_token, task)
        return

    elif cmd == "/agent":
        if not _is_admin(user_id):
            response = "Permission denied. Admin only."
        else:
            task = " ".join(parts[1:]) if len(parts) > 1 else ""
            if not task:
                response = "Usage: /agent <task description>"
            else:
                _request_approval(user_id, "agent", {"instruction": task})
                response = (
                    f"*Agent task:* `{task[:200]}`\n"
                    f"Reply *yes* within {APPROVAL_TIMEOUT_SECONDS}s to confirm, or *no* to cancel."
                )

    else:
        # ── Step 1 plain-text routing + big-paste policy + reply-to-decision ──
        # Bare message (no `/` command). Big-paste check first so a 5k-char wall
        # of text gets persisted to disk and replied with a pointer instead of
        # tripping Telegram's 4096-char hard cap.
        try:
            from telegram_inbound_handlers import (
                _handle_big_paste,
                _route_plain_text,
                _resolve_reply_to_decision,
            )
            # Reply-to-decision: when the operator replies to a bot message that
            # was linked to a pending decision via bot_message_links, surface the
            # decision context inline so the operator can confirm before executing.
            linked = await _resolve_reply_to_decision(message)
            if linked is not None:
                decision_id = linked.get("decision_id") or ""
                run_id = linked.get("run_id") or ""
                ref = f"`{decision_id}` (run `{run_id}`)" if run_id else f"`{decision_id}`"
                await _send_message(
                    bot_token, chat_id,
                    f"↩️ Reply-to detected → decision {ref}\n"
                    f"Use `/redirect {decision_id.split('_', 1)[1] if '_' in decision_id else decision_id} <new instruction>` to retarget, "
                    f"or send a new plain-text message to dispatch a fresh run.",
                )
                return

            # Big-paste policy: write to disk + short pointer reply.
            if await _handle_big_paste(bot_token, chat_id, user_id, text):
                return
            # Plain-text fallback: classify + route.
            await _route_plain_text(bot_token, chat_id, user_id, text)
        except ImportError as exc:
            log.warning("telegram_bot: inbound_handlers import failed (plain-text path): %s", exc)
            await _send_message(
                bot_token, chat_id,
                "Unknown command. Use /help to see available commands.",
            )

    if response:
        await _send_message(bot_token, chat_id, response)
        # If the user sent a voice note, also reply with a voice note (TTS)
        if voice_or_audio:
            try:
                from voice.tts import synthesize as _tts_synthesize
                voice_bytes = await _tts_synthesize(response)
                if voice_bytes:
                    await _send_voice(bot_token, chat_id, voice_bytes)
            except Exception as _tts_exc:
                log.debug("TTS voice reply failed: %s", _tts_exc)


# ─── Long-poll main loop ───────────────────────────────────────────────────────

async def _tg_call(method: str, params: dict | None = None) -> dict:
    """Call a Telegram Bot API method and return the parsed JSON (best-effort)."""
    try:
        async with httpx.AsyncClient(timeout=35.0) as client:
            r = await client.get(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/{method}",
                params=params or {},
            )
        return r.json()
    except Exception as exc:  # network / decode errors shouldn't crash startup
        return {"ok": False, "description": f"request failed: {exc}"}


async def run_bot() -> None:
    # Re-parse allowlists from the environment at startup so the bot is robust to
    # import order (e.g. when launched in-process by the web service after env is set).
    global ALLOWED_USER_IDS, ADMIN_USER_IDS, TELEGRAM_BOT_TOKEN
    ALLOWED_USER_IDS, ADMIN_USER_IDS = _resolve_bot_user_ids(
        os.environ.get("TELEGRAM_ALLOWED_USER_IDS", ""),
        os.environ.get("TELEGRAM_ADMIN_USER_IDS", ""),
        os.environ.get("TELEGRAM_CHAT_ID", ""),
    )

    if not TELEGRAM_BOT_TOKEN:
        log.warning(
            "TELEGRAM_BOT_TOKEN is not set — telegram bot is disabled. "
            "Set TELEGRAM_BOT_TOKEN in the environment to enable it."
        )
        return
    # Defensively strip any internal whitespace from the token (common copy-paste error).
    safe_token = "".join(TELEGRAM_BOT_TOKEN.split())
    if safe_token != TELEGRAM_BOT_TOKEN:
        TELEGRAM_BOT_TOKEN = safe_token  # allow the global to be reassigned
        log.warning(
            "TELEGRAM_BOT_TOKEN contained whitespace — stripped to %d chars. "
            "Fix the env var to avoid this warning.",
            len(TELEGRAM_BOT_TOKEN),
        )
    if not ALLOWED_USER_IDS:
        raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "")
        chat_raw = os.environ.get("TELEGRAM_CHAT_ID", "")
        log.error(
            "Neither TELEGRAM_ALLOWED_USER_IDS nor TELEGRAM_CHAT_ID produced any "
            "numeric IDs (TELEGRAM_ALLOWED_USER_IDS=%r, TELEGRAM_CHAT_ID=%r). "
            "Use the NUMERIC id from @userinfobot (e.g. 8120976), comma-separated — "
            "not your @username, and without quotes. No one can use the bot.",
            raw,
            chat_raw,
        )
        return

    # Single-poller guard (issue #656). Telegram allows only ONE getUpdates
    # consumer per bot token; running a second poller (e.g. the embedded
    # in-web bot AND the dedicated worker on the same token) triggers a storm
    # of 409 "conflict" / 429 "Too Many Requests" errors and neither receives
    # updates reliably. Set TELEGRAM_POLLER_DISABLED=true on the service that
    # should NOT poll (typically the web service, leaving the dedicated worker
    # to own the long-poll). Env is per-service, so this disables exactly one.
    if _poller_disabled():
        log.info(
            "TELEGRAM_POLLER_DISABLED is set — this process will NOT long-poll "
            "getUpdates (another instance owns the bot token)."
        )
        # Idle instead of returning (Codex P2): a dedicated worker whose entry
        # point is run_bot() (e.g. scripts/run_freebuff_bot.py) would otherwise
        # exit immediately and churn/restart on Render. Block forever so the
        # process stays healthy without polling. When run_bot() is launched as a
        # background task inside the web service, this idle task is simply never
        # the poller. Cancellation (shutdown) breaks out cleanly.
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            log.info("Disabled-poller idle task cancelled — exiting run_bot().")
        return

    # Verify the token and identify the bot — surfaces a bad token immediately
    # in the logs instead of silently failing to receive messages.
    me = await _tg_call("getMe")
    if not me.get("ok"):
        log.error("Telegram getMe failed (%s). Check TELEGRAM_BOT_TOKEN.", me.get("description"))
        return
    bot_username = me.get("result", {}).get("username", "?")
    log.info(
        "Bot @%s online. Allowed users: %s  Admin users: %s",
        bot_username, ALLOWED_USER_IDS, ADMIN_USER_IDS,
    )

    # If this bot was previously set up with a webhook (or is being "reused"),
    # getUpdates is rejected with HTTP 409 until the webhook is removed. Clear it
    # so long-polling works for the reused bot.
    dw = await _tg_call("deleteWebhook")
    log.info("Cleared any existing webhook (deleteWebhook ok=%s).", dw.get("ok"))

    offset = 0
    # Exponential backoff for repeated errors (conflict / 429 / 5xx / network)
    # so a transient outage or a second poller does not generate a tight error
    # storm. Resets to the floor after any successful poll. (issue #656)
    _BACKOFF_FLOOR = 5.0
    _BACKOFF_CEIL = 60.0
    backoff = _BACKOFF_FLOOR

    while True:
        try:
            async with httpx.AsyncClient(timeout=35.0) as client:
                r = await client.get(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                    params={
                        "offset": offset,
                        "timeout": 30,
                        "allowed_updates": ["message", "callback_query"],
                    },
                )
            data = r.json()
            if not data.get("ok"):
                desc = str(data.get("description", ""))
                error_code = data.get("error_code")
                # Honour Telegram's own retry_after hint (429) when present.
                retry_after = 0
                try:
                    retry_after = int((data.get("parameters") or {}).get("retry_after") or 0)
                except (TypeError, ValueError):
                    retry_after = 0

                if error_code == 409 or "conflict" in desc.lower() or "webhook" in desc.lower():
                    log.error(
                        "getUpdates conflict: %s — another process/instance is polling "
                        "this bot token, or a webhook is set. Set TELEGRAM_POLLER_DISABLED=true "
                        "on the duplicate service (see issue #656). Re-clearing webhook; "
                        "backing off %.0fs.", desc, backoff,
                    )
                    await _tg_call("deleteWebhook")
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, _BACKOFF_CEIL)
                elif error_code == 429:
                    wait = max(retry_after, backoff)
                    log.warning("getUpdates rate-limited (429) — retrying in %.0fs.", wait)
                    await asyncio.sleep(wait)
                    backoff = min(backoff * 2, _BACKOFF_CEIL)
                else:
                    log.error("getUpdates error: %s — backing off %.0fs.", data, backoff)
                    await asyncio.sleep(backoff)
                    backoff = min(backoff * 2, _BACKOFF_CEIL)
                continue

            # Successful poll — reset the backoff floor.
            backoff = _BACKOFF_FLOOR
            for update in data.get("result", []):
                offset = update["update_id"] + 1
                try:
                    if update.get("callback_query"):
                        await _process_callback(TELEGRAM_BOT_TOKEN, update["callback_query"])
                    else:
                        await _process_update(TELEGRAM_BOT_TOKEN, update)
                except Exception as exc:
                    log.exception("Error processing update %d: %s", update.get("update_id"), exc)

        except asyncio.CancelledError:
            log.info("Bot stopped.")
            return
        except Exception as exc:
            log.error("Long-poll error: %s — retrying in %.0fs.", exc, backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, _BACKOFF_CEIL)


if __name__ == "__main__":
    asyncio.run(run_bot())
