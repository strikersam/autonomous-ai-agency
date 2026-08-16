"""services/pr_approval_gate.py — Telegram approve→auto-merge gate for green PRs.

The autonomous agency opens PRs continuously. Rather than merge them silently
(or leave the operator to babysit a queue that re-conflicts on every merge),
this gate posts a one-tap Telegram card — **✅ Approve & merge / ❌ Dismiss** —
for every open PR that has gone green, and on approve it enables **GitHub
auto-merge** (squash) so GitHub rebases-if-behind and lands the PR when checks
pass. That serialises the merges and dissolves the recurring ``CHANGELOG.md``
conflict without a human resolving anything.

Design:
  * The decision logic (`pr_is_green`, `select_notifiable`) is pure and unit
    tested — no network, no env.
  * `run_sweep` is a thin orchestrator over injectable adapters (list PRs, get
    checks, send the card, load/save the dedupe set) so the real GitHub/Telegram
    calls are swapped for fakes in tests.
  * Everything is fail-soft and gated by ``PR_APPROVAL_GATE_ENABLED`` (default
    off) — a misconfigured or unreachable dependency must never crash the
    background loop or spam the operator.

Merge itself goes through the existing service-token endpoint
``POST /admin/api/prs/{n}/merge`` (see the Telegram ``pr_merge`` callback in
``telegram_bot.py``); this module only decides *when to ask*.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Iterable

log = logging.getLogger("qwen-proxy")

# Conclusions that do NOT count as a failure. Mirrors the backend merge
# endpoint's own guard so the card is only shown for a PR the endpoint would
# actually accept.
_OK_CONCLUSIONS = frozenset({"success", "skipped", "neutral"})

_NOTIFIED_PATH = os.environ.get(
    "PR_APPROVAL_GATE_STATE_PATH",
    str(Path(os.environ.get("AGENCY_DATA_DIR", ".data")) / "pr_approval_notified.json"),
)


def gate_enabled() -> bool:
    return (os.environ.get("PR_APPROVAL_GATE_ENABLED", "false").strip().lower()
            in ("1", "true", "yes", "on"))


def interval_sec() -> float:
    try:
        return max(60.0, float(os.environ.get("PR_APPROVAL_GATE_INTERVAL_SEC", "300")))
    except (TypeError, ValueError):
        return 300.0


def pr_is_green(check_runs: Iterable[dict[str, Any]]) -> bool:
    """True only when every check run has completed and none failed.

    An empty check list is treated as *not green* — a PR with no checks yet
    hasn't started CI, and merging it would bypass the pipeline. Matches the
    ``merge_pr_route`` guard so the operator is never shown a card the merge
    endpoint would then reject.
    """
    runs = list(check_runs)
    if not runs:
        return False
    if any(cr.get("status") != "completed" for cr in runs):
        return False
    if any(cr.get("conclusion") not in _OK_CONCLUSIONS for cr in runs):
        return False
    return True


def _dedupe_key(number: int, head_sha: str) -> str:
    # Key on (pr, head_sha) so a new push re-notifies (the reviewed commit
    # changed) but a steady green PR is only carded once.
    return f"{number}:{head_sha}"


def select_notifiable(
    prs: Iterable[dict[str, Any]],
    checks_by_number: dict[int, list[dict[str, Any]]],
    notified: set[str],
) -> list[dict[str, Any]]:
    """Return the PRs that should get a fresh approval card.

    A PR qualifies when it is open, not a draft, its head commit is green, and
    ``(number, head_sha)`` has not already been carded. Pure — no I/O.
    """
    out: list[dict[str, Any]] = []
    for pr in prs:
        if pr.get("draft"):
            continue
        if pr.get("state") not in (None, "open"):
            continue
        number = pr.get("number")
        head_sha = (pr.get("head") or {}).get("sha", "")
        if not isinstance(number, int) or not head_sha:
            continue
        if _dedupe_key(number, head_sha) in notified:
            continue
        if not pr_is_green(checks_by_number.get(number, [])):
            continue
        out.append(pr)
    return out


# ── Persistent dedupe set (best-effort JSON; resets on ephemeral redeploy) ────

def load_notified(path: str | None = None) -> set[str]:
    p = Path(path or _NOTIFIED_PATH)
    try:
        return set(json.loads(p.read_text(encoding="utf-8")))
    except Exception:
        return set()


def save_notified(notified: set[str], path: str | None = None) -> None:
    p = Path(path or _NOTIFIED_PATH)
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        # Bound the file: keep only the most recent 500 keys.
        p.write_text(json.dumps(sorted(notified)[-500:]), encoding="utf-8")
    except Exception as exc:  # noqa: BLE001 — best-effort; never crash the sweep
        log.warning("pr_approval_gate: could not persist notified set: %s", exc)


async def run_sweep(
    *,
    list_open_prs: Callable[[], Awaitable[list[dict[str, Any]]]],
    get_check_runs: Callable[[str], Awaitable[list[dict[str, Any]]]],
    send_card: Callable[[dict[str, Any]], Awaitable[bool]],
    notified: set[str] | None = None,
    persist: bool = True,
) -> list[int]:
    """Run one sweep: card every newly-green open PR. Returns PR numbers carded.

    Fail-soft: any adapter error is logged and skipped; the sweep never raises.
    """
    notified = load_notified() if notified is None else notified
    try:
        prs = await list_open_prs()
    except Exception as exc:  # noqa: BLE001
        log.warning("pr_approval_gate: list PRs failed: %s", exc)
        return []

    checks_by_number: dict[int, list[dict[str, Any]]] = {}
    for pr in prs:
        if pr.get("draft"):
            continue
        number = pr.get("number")
        head_sha = (pr.get("head") or {}).get("sha", "")
        if not isinstance(number, int) or not head_sha:
            continue
        if _dedupe_key(number, head_sha) in notified:
            continue
        try:
            checks_by_number[number] = await get_check_runs(head_sha)
        except Exception as exc:  # noqa: BLE001
            log.warning("pr_approval_gate: check-runs for #%s failed: %s", number, exc)

    carded: list[int] = []
    for pr in select_notifiable(prs, checks_by_number, notified):
        number = pr["number"]
        head_sha = pr["head"]["sha"]
        try:
            ok = await send_card(pr)
        except Exception as exc:  # noqa: BLE001
            log.warning("pr_approval_gate: send card for #%s failed: %s", number, exc)
            ok = False
        if ok:
            notified.add(_dedupe_key(number, head_sha))
            carded.append(number)

    if carded and persist:
        save_notified(notified)
    return carded


# ── Real adapters (GitHub REST + Telegram Bot API) ───────────────────────────

def _repo() -> str:
    return os.environ.get("GITHUB_REPOSITORY") or "strikersam/autonomous-ai-agency"


def _gh_token() -> str | None:
    return (os.environ.get("GH_PAT") or os.environ.get("GH_TOKEN")
            or os.environ.get("GITHUB_TOKEN"))


def _telegram_chat_id() -> str | None:
    return (os.environ.get("PR_APPROVAL_GATE_CHAT_ID")
            or os.environ.get("TELEGRAM_ADMIN_CHAT_ID")
            or os.environ.get("TELEGRAM_CHAT_ID"))


def _gh_get(path: str) -> Any:
    import urllib.request as _r
    token = _gh_token()
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"token {token}"
    req = _r.Request(f"https://api.github.com{path}", headers=headers)
    with _r.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode())


async def _real_list_open_prs() -> list[dict[str, Any]]:
    import asyncio
    data = await asyncio.to_thread(
        _gh_get, f"/repos/{_repo()}/pulls?state=open&per_page=100"
    )
    return list(data) if isinstance(data, list) else []


async def _real_get_check_runs(head_sha: str) -> list[dict[str, Any]]:
    import asyncio
    data = await asyncio.to_thread(
        _gh_get, f"/repos/{_repo()}/commits/{head_sha}/check-runs?per_page=100"
    )
    return list((data or {}).get("check_runs", []))


def _card_text(pr: dict[str, Any]) -> str:
    number = pr.get("number")
    title = str(pr.get("title", ""))[:200]
    author = (pr.get("user") or {}).get("login", "?")
    url = pr.get("html_url", "")
    return (
        f"🟢 *PR #{number} is green*\n"
        f"_{title}_\n"
        f"author: `{author}`\n{url}\n\n"
        "Approve to enable auto-merge (squash) — GitHub rebases if behind and "
        "lands it when checks pass."
    )


def _card_keyboard(number: int) -> dict[str, Any]:
    return {
        "inline_keyboard": [[
            {"text": "✅ Approve & merge", "callback_data": f"fb:pr_merge:{number}"},
            {"text": "❌ Dismiss", "callback_data": f"fb:pr_reject:{number}"},
        ]]
    }


async def _real_send_card(pr: dict[str, Any]) -> bool:
    import asyncio
    import urllib.request as _r
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = _telegram_chat_id()
    if not token or not chat_id:
        log.warning("pr_approval_gate: TELEGRAM_BOT_TOKEN / chat id not set — cannot send card")
        return False
    payload = {
        "chat_id": chat_id,
        "text": _card_text(pr),
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
        "reply_markup": _card_keyboard(pr["number"]),
    }

    def _post() -> bool:
        req = _r.Request(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with _r.urlopen(req, timeout=20) as resp:
            return resp.status == 200

    try:
        return await asyncio.to_thread(_post)
    except Exception as exc:  # noqa: BLE001
        log.warning("pr_approval_gate: Telegram send failed: %s", exc)
        return False


async def default_run_sweep() -> list[int]:
    """Run one sweep against the real GitHub + Telegram APIs."""
    return await run_sweep(
        list_open_prs=_real_list_open_prs,
        get_check_runs=_real_get_check_runs,
        send_card=_real_send_card,
    )


async def pr_approval_gate_loop() -> None:
    """Background loop: sweep for green PRs every ``interval_sec`` seconds.

    Only started when ``PR_APPROVAL_GATE_ENABLED`` is on (see
    ``services/background.py``). Fail-soft: never raises out of the loop.
    """
    import asyncio
    await asyncio.sleep(float(os.environ.get("PR_APPROVAL_GATE_WARMUP_SEC", "30")))
    while True:
        try:
            carded = await default_run_sweep()
            if carded:
                log.info("pr_approval_gate: carded %d PR(s) for approval: %s", len(carded), carded)
        except Exception as exc:  # noqa: BLE001
            log.warning("pr_approval_gate: sweep iteration failed: %s", exc)
        await asyncio.sleep(interval_sec())
