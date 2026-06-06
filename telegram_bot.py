"""
Secure Telegram control plane for qwen-server.

Provides remote command/control of the local LLM proxy via a Telegram bot.
All commands are auth-gated by Telegram user ID. Admin commands require approval.

Setup:
  1. Create a bot via @BotFather — get TELEGRAM_BOT_TOKEN
  2. Find your user ID via @userinfobot — set TELEGRAM_ALLOWED_USER_IDS
  3. Set TELEGRAM_ADMIN_USER_IDS (subset of ALLOWED, can run mutating commands)
  4. Add both to .env and restart

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
PROXY_BASE_URL: str = os.environ.get("PROXY_BASE_URL", "http://localhost:8000").rstrip("/")
PROXY_ADMIN_SECRET: str = os.environ.get("ADMIN_SECRET", "").strip()
PROXY_API_KEY: str = os.environ.get("TELEGRAM_PROXY_API_KEY", "").strip()

_raw_allowed = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
_raw_admins = os.environ.get("TELEGRAM_ADMIN_USER_IDS", "").strip()

ALLOWED_USER_IDS: set[int] = {
    int(x.strip()) for x in _raw_allowed.split(",") if x.strip().lstrip("-").isdigit()
}
ADMIN_USER_IDS: set[int] = {
    int(x.strip()) for x in _raw_admins.split(",") if x.strip().lstrip("-").isdigit()
}

APPROVAL_TIMEOUT_SECONDS = 30
MAX_COMMANDS_PER_MINUTE = 5

# In-memory pending approvals: user_id → {expires, action, payload}
_pending_approvals: dict[int, dict] = {}
# In-memory rate limiter: user_id → [timestamps]
_rate_buckets: dict[int, list[float]] = defaultdict(list)
# In-memory FreeBuff session state: user_id → {task, models, model}
_freebuff_state: dict[int, dict] = {}


# ─── Auth helpers ──────────────────────────────────────────────────────────────

def _is_allowed(user_id: int) -> bool:
    return user_id in ALLOWED_USER_IDS


def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_USER_IDS


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

async def _send_message(bot_token: str, chat_id: int, text: str, parse_mode: str = "Markdown") -> None:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
        )


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
    """Parse callback_data of the form ``fb:<action>[:<arg>]``.

    Returns ``(action, arg)``; ``arg`` is None when absent. Non-FreeBuff data
    yields ``("", None)``.
    """
    if not data or not data.startswith("fb:"):
        return "", None
    parts = data.split(":", 2)
    action = parts[1] if len(parts) > 1 else ""
    arg = parts[2] if len(parts) > 2 else None
    return action, arg


def _model_keyboard(models: list[str]) -> list[list[dict]]:
    """Build an inline keyboard mapping each free model to ``fb:model:<idx>``.

    Model IDs (e.g. ``nvidia/nemotron-3-super-120b-a12b``) can exceed Telegram's
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
    result = await agent.run(
        instruction=task, history=[], requested_model=model,
        auto_commit=True, max_steps=_freebuff_max_steps(),
    )
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


async def _process_update(bot_token: str, update: dict) -> None:
    message = update.get("message") or update.get("edited_message")
    if not message:
        return

    user_id: int = message.get("from", {}).get("id", 0)
    chat_id: int = message.get("chat", {}).get("id", 0)
    text: str = (message.get("text") or "").strip()

    # Silent drop for non-allowlisted users
    if not _is_allowed(user_id):
        log.warning("Ignored message from non-allowlisted user %d", user_id)
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

    if cmd == "/help":
        response = (
            "*Available commands:*\n"
            "/status — service health\n"
            "/models — loaded models\n"
            "/cost — local infra cost estimate\n"
            "\n*Admin only:*\n"
            "/start|stop|restart <svc> — control ollama|proxy|tunnel|stack\n"
            "/agent <task> — run agent task (requires confirmation)\n"
            "/freebuff <task> — free-NVIDIA coding agent (pick model, review, accept)\n"
            "/keylist — list API keys\n"
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
        response = "Unknown command. Use /help to see available commands."

    if response:
        await _send_message(bot_token, chat_id, response)


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
    if not TELEGRAM_BOT_TOKEN:
        log.error("TELEGRAM_BOT_TOKEN is not set. Set it in the environment and restart.")
        return
    if not ALLOWED_USER_IDS:
        log.error(
            "TELEGRAM_ALLOWED_USER_IDS is empty or unparsable (must be comma-separated "
            "numeric user IDs from @userinfobot). No one can use the bot."
        )
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
                if data.get("error_code") == 409 or "conflict" in desc.lower() or "webhook" in desc.lower():
                    log.error(
                        "getUpdates conflict: %s — another process/instance is polling "
                        "this bot token, or a webhook is set. Stop the other bot that uses "
                        "this token. Re-clearing webhook and retrying.", desc,
                    )
                    await _tg_call("deleteWebhook")
                else:
                    log.error("getUpdates error: %s", data)
                await asyncio.sleep(5)
                continue

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
            log.error("Long-poll error: %s — retrying in 5s", exc)
            await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(run_bot())
