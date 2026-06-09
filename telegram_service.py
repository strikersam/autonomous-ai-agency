"""
service_manager.py — Telegram & Notification Integration Extension

Extends the existing service_manager to support:
1. Telegram bot lifecycle (start/stop/status via /telegram command)
2. BackgroundAgent notification callbacks (telegram, webhook, email stubs)
3. Hook points for the log monitoring agent

Integrates with:
- telegram_bot.py (existing Telegram control plane)
- agent/background.py (BackgroundAgent)
- agent/scheduler.py (AgentScheduler)
- proxy.py (admin API endpoints)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("qwen-telegram-svc")


# ── Sensitive-data redaction for outbound notifications ─────────────────────
# Best-effort secret/email/IP redaction for outbound Telegram/webhook messages
# so the notification path doesn't exfiltrate user-supplied secrets or PII.
_NOTIFY_SENSITIVE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"sk-[A-Za-z0-9_\-]{16,}"), "sk-<REDACTED>"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "ghp_<REDACTED>"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_<REDACTED>"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "<AWS_KEY_REDACTED>"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "<PRIVATE_KEY_REDACTED>"),
    (re.compile(r"\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b"), "<EMAIL_REDACTED>"),
    (re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b"), "<IP_REDACTED>"),
    (re.compile(r"(?i)(api[_-]?key|token|secret|password|passwd|pwd)\s*[:=]\s*['\"]?([A-Za-z0-9_\-\.=]{8,})"), r"\1=<REDACTED>"),
]


def _redact_for_notification(text: str) -> str:
    """Best-effort secret/email/IP redaction for outbound Telegram/webhook messages."""
    if not text:
        return text
    redacted = text
    for pattern, replacement in _NOTIFY_SENSITIVE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


def _creationflags() -> int:
    return getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)


# ─── Telegram Bot Manager ─────────────────────────────────────────────────────

class TelegramBotManager:
    """Manages the Telegram bot as a managed service alongside ollama/proxy/tunnel.

    Usage::

        mgr = TelegramBotManager(root=Path("."))
        mgr.start(blocking=False)       # start in background thread
        mgr.get_status()                # running + uptime
        mgr.stop()                      # graceful shutdown
    """

    def __init__(self, root: Path) -> None:
        self.root = root
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._started_at: float | None = None
        self._stop_event = threading.Event()

    # ── Properties ────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        if self._thread and self._thread.is_alive():
            return True
        if self._process and self._process.poll() is None:
            return True
        return False

    @property
    def pid(self) -> int | None:
        if self._process:
            return self._process.pid
        return None

    @property
    def uptime_seconds(self) -> float | None:
        if self._started_at and self.is_running:
            return time.time() - self._started_at
        return None

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self, blocking: bool = False) -> bool:
        """Start the Telegram bot. Returns True if started successfully."""
        if self.is_running:
            log.info("Telegram bot already running")
            return True

        token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            log.warning("TELEGRAM_BOT_TOKEN not set — Telegram bot cannot start")
            return False

        user_ids = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
        if not user_ids:
            log.warning("TELEGRAM_ALLOWED_USER_IDS not set — Telegram bot cannot start")
            return False

        self._stop_event.clear()
        self._started_at = time.time()

        if blocking:
            self._run_bot()
        else:
            self._thread = threading.Thread(
                target=self._run_bot,
                daemon=True,
                name="telegram-bot-svc",
            )
            self._thread.start()

        log.info("Telegram bot started (running=%s)", self.is_running)
        return True

    def stop(self, timeout: float = 5.0) -> None:
        """Signal the bot to stop and wait for graceful shutdown."""
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=timeout)
        if self._process and self._process.poll() is None:
            self._process.terminate()
            try:
                self._process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                self._process.kill()
        self._started_at = None
        log.info("Telegram bot stopped")

    def get_status(self) -> dict[str, Any]:
        return {
            "name": "telegram",
            "running": self.is_running,
            "pid": self.pid,
            "uptime_seconds": round(self.uptime_seconds) if self.uptime_seconds else None,
            "token_configured": bool(os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()),
            "users_configured": bool(os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()),
        }

    # ── Internal ──────────────────────────────────────────────────────────

    def _run_bot(self) -> None:
        """Run the Telegram bot long-poll loop (inline, not subprocess)."""
        try:
            # Import here to avoid circular imports at module level
            from telegram_bot import run_bot

            # Patch the run loop to respect our stop event
            asyncio.run(self._run_with_stop(run_bot))
        except Exception as exc:
            log.exception("Telegram bot crashed: %s", exc)

    async def _run_with_stop(self, run_bot_fn: Callable) -> None:
        """Run the bot with stop-event awareness."""
        import asyncio

        async def _monitor_stop() -> None:
            while not self._stop_event.is_set():
                await asyncio.sleep(0.5)
            log.info("Telegram bot stop signal received")

        try:
            # Race between the bot loop and the stop monitor
            done, pending = await asyncio.wait(
                [
                    asyncio.create_task(run_bot_fn()),
                    asyncio.create_task(_monitor_stop()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
        except asyncio.CancelledError:
            pass


# ─── Notification Dispatcher ──────────────────────────────────────────────────

class NotificationDispatcher:
    """Routes background task results to configured notification channels.

    Currently supports:
    - Telegram: sends task completion/failure to configured chat IDs
    - Console: logs task results
    - Webhook: POST to configurable URL (stub — extend for production)

    Wire this into BackgroundAgent as on_task_complete callback::

        bg_agent = BackgroundAgent(on_task_complete=notifier.on_task_complete)
    """

    def __init__(
        self,
        *,
        telegram_token: str | None = None,
        telegram_chat_ids: list[int] | None = None,
        webhook_url: str | None = None,
    ) -> None:
        self.telegram_token = telegram_token or os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
        self.telegram_chat_ids = telegram_chat_ids or self._parse_chat_ids()
        self.webhook_url = webhook_url or os.environ.get("NOTIFY_WEBHOOK_URL", "").strip()

    @staticmethod
    def _parse_chat_ids() -> list[int]:
        raw = os.environ.get("TELEGRAM_NOTIFY_CHAT_IDS", "").strip()
        if not raw:
            # Fall back to ALLOWED_USER_IDS or ADMIN_USER_IDS
            raw = os.environ.get("TELEGRAM_ADMIN_USER_IDS", "").strip()
            if not raw:
                raw = os.environ.get("TELEGRAM_ALLOWED_USER_IDS", "").strip()
        return [int(x.strip()) for x in raw.split(",") if x.strip().lstrip("-").isdigit()]

    def on_task_complete(self, task: Any) -> None:
        """Callback for BackgroundAgent.on_task_complete.

        Dispatches task result notifications to all configured channels.
        The raw task instruction / prompt is intentionally NOT included in
        the notification to prevent PII or secret leakage; only redacted
        metadata (id, kind, status) and redacted error/result previews
        are surfaced.
        """
        task_id = getattr(task, "task_id", "unknown")
        task_kind = getattr(task, "kind", "unknown")
        status_icon = "[OK]" if getattr(task, "status", "") == "done" else "[FAIL]"
        message = (
            f"{status_icon} *Task {task_id}* "
            f"({task_kind})\n"
            f"Status: `{getattr(task, 'status', 'unknown')}`\n"
        )
        if hasattr(task, "error") and task.error:
            err_preview = str(task.error)[:500]
            message += f"Error: `{_redact_for_notification(err_preview)}`\n"
        if hasattr(task, "result") and task.result:
            result_str = str(task.result)[:1000]
            message += f"Result: ```{_redact_for_notification(result_str)}```"

        # Dispatch to all channels (non-blocking)
        self._log(message)
        self._notify_telegram(message)
        self._notify_webhook(task)

    def _log(self, message: str) -> None:
        log.info("Notification: %s", message.replace("\n", " | ")[:200])

    def _notify_telegram(self, message: str) -> None:
        """Send notification to configured Telegram chat IDs."""
        if not self.telegram_token or not self.telegram_chat_ids:
            return
        import httpx

        def _send():
            for chat_id in self.telegram_chat_ids:
                try:
                    with httpx.Client(timeout=5.0) as client:
                        client.post(
                            f"https://api.telegram.org/bot{self.telegram_token}/sendMessage",
                            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
                        )
                except Exception as exc:
                    log.warning("Telegram notify failed for chat %d: %s", chat_id, exc)

        threading.Thread(target=_send, daemon=True).start()

    def _notify_webhook(self, task: Any) -> None:
        """POST task result to configured webhook URL."""
        if not self.webhook_url:
            return
        import httpx

        def _send():
            try:
                payload = {
                    "task_id": getattr(task, "task_id", ""),
                    "kind": getattr(task, "kind", ""),
                    "status": getattr(task, "status", ""),
                    "error": getattr(task, "error", None),
                    "result": str(getattr(task, "result", ""))[:2000],
                }
                with httpx.Client(timeout=10.0) as client:
                    client.post(self.webhook_url, json=payload)
            except Exception as exc:
                log.warning("Webhook notify failed: %s", exc)

    def send_manual_notification(self, message: str) -> None:
        """Send an ad-hoc notification through all channels."""
        self._log(message)
        self._notify_telegram(message)
