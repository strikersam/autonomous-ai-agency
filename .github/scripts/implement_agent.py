from __future__ import annotations

"""
Agentic implementation loop (OpenAI-compatible tool use via ProviderRouter).

Reads URL content + task from args, loads repo context (CLAUDE.md + skills),
and runs a plan → implement → test cycle with real file editing and bash
execution through ``packages/ai/router.py`` (CLAUDE.md rule 2).

This script used to hold its own six-entry NVIDIA model list and its own
failover. That is precisely why the agency stopped producing work: on
2026-08-26 the last live entries reached end-of-life, every candidate answered
``410 Gone``, and the loop died on turn 1 with nothing else to try. The router
already owns the Cerebras → Groq → NVIDIA → Ollama chain *and* rule 4's
410 handling, so a retired model now costs one request instead of the agency.

Usage:
  python implement_agent.py <url> <issue_num> <task>

Writes /tmp/impl_result.json with {"success": bool, "summary": str}
"""


import asyncio
import json
import logging
import os
import subprocess
import sys
import textwrap
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# Repo root, so `packages.ai.router` imports the same router the rest of the
# platform uses rather than this script growing a second one.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from slop_gate import is_destructive_overwrite, looks_like_secret_file  # noqa: E402

# CLI script: log to stdout so messages stay visible and ordered in CI logs.
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("implement_agent")

# ---------------------------------------------------------------------------
# Args
# ---------------------------------------------------------------------------
def _load_optional(path):
    if not path:
        return ""
    p = Path(path)
    if not p.exists():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")

import argparse
_parser = argparse.ArgumentParser()
_parser.add_argument("url", nargs="?", default="")
_parser.add_argument("issue_num", nargs="?", default="?")
_parser.add_argument("task", nargs="?", default="")
_parser.add_argument("--body-file", default=None,
                    help="Path to issue body (written by process-quick-note capture step).")
_parser.add_argument("--comments-file", default=None,
                    help="Path to issue comments JSONL (written by capture step).")
_args, _unknown = _parser.parse_known_args()
URL = _args.url
ISSUE_NUM = _args.issue_num
TASK = _args.task
ISSUE_BODY_TEXT = _load_optional(_args.body_file)
ISSUE_COMMENTS_RAW = _load_optional(_args.comments_file)
RESULT_FILE = "/tmp/impl_result.json"  # nosec: B108 - Predictable temp file path used for backward compatibility; secure temp file used internally
MAX_TURNS = 120

OPUS_MODEL = "claude-opus-4-6"

# No model list lives here any more. The six hardcoded NVIDIA ids this replaced
# were, by 2026-08-27, all dead — four `410 Gone` (two retired on 2026-08-26)
# and one `404` — so the loop exhausted every candidate on turn 1 and the whole
# agency went quiet while its workflow still reported success. Model choice
# belongs to the router, which reads each provider's `default_model` and skips
# ids already flagged dead by a prior 410. This script names no model at all.


# ---------------------------------------------------------------------------
# Tool implementations (run on the host)
# ---------------------------------------------------------------------------
_API_KEY_ENV_VARS = (
    "NVIDIA_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
    "GEMINI_API_KEY", "GROQ_API_KEY", "MISTRAL_API_KEY",
)


def tool_bash(cmd: str) -> str:
    # Strip API keys when running pytest so tests that check model selection
    # are not affected by whatever keys are set in the CI environment.
    env = dict(os.environ)
    if "pytest" in cmd:
        for key in _API_KEY_ENV_VARS:
            env.pop(key, None)
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=120, env=env  # nosec B602
        )
        out = result.stdout[-6000:] if len(result.stdout) > 6000 else result.stdout
        err = result.stderr[-2000:] if len(result.stderr) > 2000 else result.stderr
        parts = []
        if out.strip():
            parts.append(out)
        if err.strip():
            parts.append(f"[stderr]\n{err}")
        parts.append(f"[exit {result.returncode}]")
        return "\n".join(parts)
    except subprocess.TimeoutExpired:
        return "[timeout after 120s]"
    except Exception as exc:
        return f"[error: {exc}]"


def tool_read_file(path: str) -> str:
    try:
        text = Path(path).read_text(errors="replace")
        if len(text) > 12000:
            return text[:12000] + f"\n\n[... truncated — file is {len(text)} chars total. Use bash(cmd='wc -l {path}') to check size, or read specific sections with bash(cmd='sed -n \"1,50p\" {path}')]"
        return text
    except Exception as exc:
        return f"[error reading {path}: {exc}]"


def tool_write_file(path: str, content: str) -> str:
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        # Safety guard: refuse to shrink an existing file by more than 10 lines.
        if p.exists():
            old_text = p.read_text(errors="replace")
            existing_lines = old_text.count("\n")
            new_lines = content.count("\n")
            if existing_lines > 20 and new_lines < existing_lines - 10:
                return (
                    f"[BLOCKED] write_file would reduce {path} from {existing_lines} lines to {new_lines} lines "
                    f"(lost {existing_lines - new_lines} lines). This usually means you read a truncated version "
                    f"of the file and are writing it back incomplete. "
                    f"For docs/changelog.md use add_changelog_entry instead. "
                    f"For source files, use bash(cmd='cat >> file') to append or make targeted edits."
                )
            destructive, why = is_destructive_overwrite(old_text, content)
            if destructive:
                return f"[BLOCKED] slop-gate: {path} — {why}"
        secretish, why = looks_like_secret_file(path, content)
        if secretish:
            return f"[BLOCKED] slop-gate: {path} — {why}"
        p.write_text(content)
        return f"Written {len(content)} chars to {path}"
    except Exception as exc:
        return f"[error writing {path}: {exc}]"


def tool_add_changelog_entry(entry: str) -> str:
    """Safely insert an entry under ## [Unreleased] without touching the rest of the file."""
    try:
        p = Path("docs/changelog.md")
        text = p.read_text(errors="replace")
        marker = "## [Unreleased]"
        idx = text.find(marker)
        if idx == -1:
            return "[error: '## [Unreleased]' marker not found in docs/changelog.md]"
        insert_at = idx + len(marker)
        # Find the next blank line after the marker to insert after the header
        rest = text[insert_at:]
        newline_pos = rest.find("\n")
        insert_at += newline_pos + 1
        new_text = text[:insert_at] + entry.rstrip() + "\n" + text[insert_at:]
        p.write_text(new_text)
        return f"Changelog updated — inserted {len(entry)} chars under ## [Unreleased]"
    except Exception as exc:
        return f"[error updating changelog: {exc}]"


def tool_list_files(pattern: str = "**/*.py") -> str:
    try:
        result = subprocess.run(
            ["git", "ls-files", "--", pattern],
            capture_output=True, text=True, timeout=30,
        )
        lines = result.stdout.strip().splitlines()
        return "\n".join(lines[:200]) if lines else "(no files matched)"
    except Exception as exc:
        return f"[error: {exc}]"


def tool_search(query: str) -> str:
    return tool_bash(f"grep -rnE '{query}' . --include='*.py' | head -50")


TOOL_DISPATCH = {
    "bash": lambda inp: tool_bash(inp.get("cmd") or inp.get("command") or inp.get("shell", "")),
    "read_file": lambda inp: tool_read_file(inp.get("path") or inp.get("file", "")),
    "write_file": lambda inp: tool_write_file(inp.get("path") or inp.get("file", ""), inp.get("content", "")),
    "add_changelog_entry": lambda inp: tool_add_changelog_entry(inp["entry"]),
    "list_files": lambda inp: tool_list_files(inp.get("pattern", "**/*.py")),
    "search_code": lambda inp: tool_search(inp["query"]),
}

# OpenAI-format tool schemas
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "bash",
            "description": (
                "Run a bash command in the repository root. "
                "Use for git operations, running pytest, installing packages, "
                "inspecting directory structure. stdout+stderr are returned."
            ),
            "parameters": {
                "type": "object",
                "properties": {"cmd": {"type": "string"}},
                "required": ["cmd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file (up to 12000 chars, truncated with notice if longer).",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": (
                "Write (overwrite) a file with the given content. Creates parent dirs. "
                "BLOCKED if the new content is more than 10 lines shorter than the existing file — "
                "this prevents accidentally writing back a truncated read. "
                "NEVER use this for docs/changelog.md — use add_changelog_entry instead. "
                "NEVER create backup files (e.g. proxy_original.py, proxy_backup.py)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "add_changelog_entry",
            "description": (
                "Safely insert a new entry into docs/changelog.md under ## [Unreleased]. "
                "Always use this instead of read_file + write_file for the changelog. "
                "Pass the full entry text including the ### Added / ### Fixed header."
            ),
            "parameters": {
                "type": "object",
                "properties": {"entry": {"type": "string"}},
                "required": ["entry"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List tracked files matching a git-ls-files glob pattern.",
            "parameters": {
                "type": "object",
                "properties": {"pattern": {"type": "string"}},
                "required": ["pattern"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_code",
            "description": "Grep for a regex pattern across all .py files.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"],
            },
        },
    },
]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------
SYSTEM = textwrap.dedent("""
    You are a senior software engineer implementing features in a Python/FastAPI repository.

    ## Mandatory workflow — follow in order

    1. **Read CLAUDE.md** to understand conventions, structure, and rules:
       bash(cmd="cat CLAUDE.md")

    2. **Survey the task area** — read relevant existing files before writing anything.

    3. **Implement the feature** — create new files or extend existing ones.
       - All public functions must have type annotations and return type annotations.
       - Use `logging.getLogger("qwen-proxy")` for logging, never `print`.
       - Pydantic models for all API I/O.
       - Tests go in `tests/` and must pass with `pytest -x -q --tb=short`.

    4. **Add a changelog entry** — this is REQUIRED for CI to pass:
       Use the `add_changelog_entry` tool — NEVER read_file + write_file the changelog.
       The changelog is large; writing it back from a read will truncate it and break CI.
       Example:
       add_changelog_entry(entry="### Added\n- `module.py` — brief description.\n")

    5. **Run tests and verify** — API keys are automatically stripped for pytest:
       bash(cmd="pytest -x -q --tb=short 2>&1 | tail -20")
       Fix any failures. Only proceed when all tests pass.
       If a test fails because an env var like NVIDIA_API_KEY changes routing,
       fix the test to mock/monkeypatch it instead of relying on env state.

    6. **Verify staged changes exist**:
       bash(cmd="git add -A && git diff --staged --stat")
       There must be changed files. If nothing is staged, check your write_file calls.

    7. **Signal completion** — call ONLY when pytest exits 0 AND staged changes exist:
       bash(cmd="echo IMPLEMENTATION_COMPLETE")

    ## Rules
    - Never signal IMPLEMENTATION_COMPLETE if the last pytest run had failures.
    - Always use add_changelog_entry for docs/changelog.md — NEVER write_file it.
    - Only implement features clearly supported by the URL content.
    - Minimal focused changes — ADD new code only. Do NOT delete, refactor, or rewrite existing code.
    - Never create backup files (proxy_original.py, any_file_backup.py, etc.).
    - Never hardcode secrets.
    - If the feature is already implemented, signal IMPLEMENTATION_COMPLETE immediately without changing any files.
    - DRAFT PR AWARENESS: if you discover the existing PR for this issue is in **draft** state, treat it as "yet to be implemented" -- do NOT signal IMPLEMENTATION_COMPLETE on a draft PR. The PR is a planning doc that needs real code commits. Only signal completion when pytest passes AND the code changes you made are committed to the branch AND the PR will be ready for review after this run.
""").strip()


def _read_claude_md() -> str:
    try:
        return Path("CLAUDE.md").read_text()[:3000]
    except Exception:
        return ""


def _run_baseline_pytest() -> str:
    # Strip API keys so routing tests see the same environment as tool_bash pytest calls.
    # Without this, NVIDIA_API_KEY in CI changes model-selection behaviour and causes
    # tests that assert local Ollama model names to fail spuriously.
    env = {k: v for k, v in os.environ.items() if k not in _API_KEY_ENV_VARS}
    # This is informational context for the agent's prompt, not a hard gate —
    # a slow or hung suite must never crash the whole automation. Confirmed in
    # production: the full suite (no path filter, thousands of tests) routinely
    # exceeds a 120s timeout on the Actions runner, and subprocess.TimeoutExpired
    # was uncaught, taking down main() and forcing an "Attempt 0 failed —
    # reopening for automatic retry" cycle that just repeats the same timeout.
    try:
        result = subprocess.run(
            ["python", "-m", "pytest", "-x", "-q", "--tb=line", "--no-header"],
            capture_output=True, text=True, timeout=480, env=env,
        )
        lines = (result.stdout + result.stderr).splitlines()
        return "\n".join(lines[-15:])
    except subprocess.TimeoutExpired:
        return (
            "(baseline pytest run timed out after 480s — skipped; "
            "this is informational context only, not a merge gate)"
        )
    except Exception as exc:  # nosec B110 -- baseline output is best-effort context
        return f"(baseline pytest run failed to execute: {exc})"


# ---------------------------------------------------------------------------
# Anthropic-native agent loop (Opus primary)
# ---------------------------------------------------------------------------

def _openai_tools_to_anthropic(tools: list[dict]) -> list[dict]:
    """Convert OpenAI function-calling tool schemas to Anthropic tool schemas."""
    result = []
    for t in tools:
        fn = t.get("function", {})
        result.append({
            "name": fn["name"],
            "description": fn.get("description", ""),
            "input_schema": fn.get("parameters", {"type": "object", "properties": {}}),
        })
    return result


def _run_anthropic_agent_loop(anthropic_key: str, user_msg: str) -> tuple[bool, str, int]:
    """Run the implementation agent loop using Claude Opus via Anthropic SDK.

    Returns (success, summary, turns_used).
    """
    import anthropic as _anthropic
    client = _anthropic.Anthropic(api_key=anthropic_key)
    anthropic_tools = _openai_tools_to_anthropic(TOOLS)

    messages: list[dict] = [{"role": "user", "content": user_msg}]
    success = False
    last_pytest_passed = False
    summary = "No implementation performed"
    turns = 0

    while turns < MAX_TURNS:
        turns += 1
        print(f"\n[agent] Turn {turns}/{MAX_TURNS} model={OPUS_MODEL} (Anthropic)", flush=True)

        try:
            resp = client.messages.create(
                model=OPUS_MODEL,
                max_tokens=8192,
                system=SYSTEM,
                tools=anthropic_tools,  # type: ignore[arg-type]
                messages=messages,      # type: ignore[arg-type]
            )
        except Exception as exc:
            # Permanent failures (bad key, access denied, unknown model) must not be
            # retried — they will never recover and would exhaust all 120 turns before
            # NVIDIA fallback can run.
            status = getattr(exc, "status_code", None)
            if status in (401, 403, 404):
                print(f"Anthropic permanent error ({status}): {exc} — falling back to NVIDIA", file=sys.stderr)
                break
            print(f"Anthropic transient error: {exc}", file=sys.stderr)
            time.sleep(5)
            continue  # retry transient errors (rate limit, server error, network)

        # Build assistant content list
        assistant_content: list[dict] = []
        text_content = ""
        tool_use_blocks: list = []

        for block in resp.content:
            if block.type == "text":
                text_content = block.text
                assistant_content.append({"type": "text", "text": block.text})
                print(f"[agent] {block.text[:400]}", flush=True)
            elif block.type == "tool_use":
                tool_use_blocks.append(block)
                assistant_content.append({
                    "type": "tool_use",
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        messages.append({"role": "assistant", "content": assistant_content})

        # No tool calls → terminal turn
        if not tool_use_blocks:
            summary = text_content or summary
            if text_content and "IMPLEMENTATION_COMPLETE" in text_content and last_pytest_passed:
                success = True
                summary = text_content[:500]
            break

        # Execute tool calls and collect results
        tool_results: list[dict] = []
        for call in tool_use_blocks:
            fn_name = call.name
            fn_args = call.input if isinstance(call.input, dict) else {}
            print(f"[tool] {fn_name}({list(fn_args.keys())})", flush=True)

            handler = TOOL_DISPATCH.get(fn_name)
            out = handler(fn_args) if handler else f"[unknown tool: {fn_name}]"
            print(f"[tool result] {str(out)[:300]}", flush=True)

            if fn_name == "bash":
                cmd = fn_args.get("cmd", "")
                if "pytest" in cmd:
                    last_pytest_passed = "[exit 0]" in out
                if "IMPLEMENTATION_COMPLETE" in out:
                    if last_pytest_passed:
                        success = True
                        summary = f"Agent signaled completion after {turns} turns."
                    else:
                        out = (
                            "[BLOCKED] IMPLEMENTATION_COMPLETE rejected: last pytest did not exit 0. "
                            "Fix all test failures first."
                        )

            tool_results.append({
                "type": "tool_result",
                "tool_use_id": call.id,
                "content": str(out),
            })

        messages.append({"role": "user", "content": tool_results})

        if success:
            break

    if not success and turns >= MAX_TURNS:
        summary = f"Agent hit turn limit ({MAX_TURNS}) without completing"

    return success, summary, turns


# ---------------------------------------------------------------------------
# Provider routing
# ---------------------------------------------------------------------------
def build_tool_calling_router() -> Any | None:
    """Return a router limited to providers that pass ``tools`` through intact.

    The type filter is not incidental. ``ProviderRouter`` rewrites the payload
    for three provider types on the way out — ``anthropic`` via
    ``_anthropic_payload``, ``bedrock`` via ``_openai_to_bedrock_converse``, and
    ``ollama``'s native ``/api/chat`` retry — and none of those converters carry
    a ``tools`` field. Routing a tool-calling turn through one would not error:
    it would drop every tool definition and leave the agent describing edits it
    can no longer make. Only ``openai-compatible`` providers forward the payload
    verbatim, so only those are eligible here.

    Commercial providers are excluded here as well, and that is load-bearing
    rather than redundant. ``allow_commercial_fallback=False`` alone does not
    hold: ``chat_completion`` guards with ``if not first_eligible and
    is_commercial_provider(...)``, so the *first* eligible provider is used
    whatever it costs. On a host whose only openai-compatible key is a paid one
    (OpenRouter, Zhipu, MiniMax, DeepSeek, Mistral), that would bill the
    operator on the very first turn. Filtering here closes it; the flag stays as
    the second line of defence.

    Returns ``None`` when no such provider is configured, so the caller can say
    so plainly instead of failing somewhere further down.
    """
    try:
        from packages.ai.router import ProviderRouter, is_commercial_provider
    except Exception as exc:  # pragma: no cover - import-environment dependent
        print(f"ERROR: could not import ProviderRouter: {exc}", file=sys.stderr)
        return None

    providers = [
        provider
        for provider in ProviderRouter.from_env().providers
        if provider.type == "openai-compatible"
        and not is_commercial_provider(provider)
    ]
    if not providers:
        return None

    log.info(
        "[agent] Tool-calling providers: %s",
        ", ".join(p.provider_id for p in providers),
    )
    return ProviderRouter(providers)


def _nvidia_candidates(router: Any) -> tuple[str, list[str]]:
    """Curated NVIDIA model ids, when NVIDIA is the provider that will answer.

    Needed because ``ProviderRouter``'s NVIDIA entry carries a hardcoded
    ``default_model`` (router.py:702) that reached end-of-life on 2026-08-26 and
    now answers ``410``. With no model named, ``_candidate_models`` returns that
    single dead id, so an NVIDIA-only runner would exhaust the provider on turn 1
    — exactly the outage this module was changed to prevent. The id is not
    repeated here: a dead id must never appear in this file, which is what
    ``tests/test_implement_agent_routing.py`` enforces.

    The ids come from ``.github/scripts/nvidia_models.py``, the repo's curated
    list, so nothing is invented here. Some may also be dead; the router's own
    ``_is_model_dead`` skips ids a prior ``410`` flagged, and having three
    candidates beats having one that is known bad.

    Only applies when NVIDIA is first in priority order: ``_candidate_models``
    honours the named model for the primary provider only, and handing an NVIDIA
    id to Cerebras or Groq would just fail.
    """
    if not router.providers or router.providers[0].provider_id != "nvidia-nim":
        return "", []
    try:
        from nvidia_models import resolve_model_ids
    except Exception:  # pragma: no cover - import-environment dependent
        return "", []
    model_ids = resolve_model_ids()
    if not model_ids:
        return "", []
    return model_ids[0], list(model_ids[1:])


def router_turn(router: Any, messages: list[dict]) -> tuple[dict, str]:
    """Run one turn; return the raw OpenAI-shaped body and who answered it.

    The provider id comes back because the router is priority-ordered and
    stateless between calls: re-sending the same payload reaches the same
    provider. A caller that needs to get away from a provider — one emitting
    XML tool calls, say — has to drop it explicitly, and cannot do that without
    knowing which one replied.

    A model is named only when NVIDIA leads the chain, and only from the repo's
    curated list — see ``_nvidia_candidates``. For every other provider the
    payload carries no model, so ``_candidate_models()`` uses that provider's own
    ``default_model``. Either way the router drops ids a previous ``410`` marked
    dead, so a retired model costs one request rather than the run.

    ``temperature`` is deliberately absent too. ``packages/ai/response_cache.py``
    keys on (model, messages, temperature, max_tokens, stop) — *not* on tools —
    and engages only at ``temperature == 0``. Omitting it keeps the cache out of
    the loop entirely; a cached hit here would replay a stale tool call.

    ``allow_commercial_fallback=False`` preserves the standing rule that this
    loop never escalates to a paid provider behind the operator's back.
    """
    model, fallbacks = _nvidia_candidates(router)
    payload = {
        "messages": messages,
        "tools": TOOLS,
        "tool_choice": "auto",
        "max_tokens": 8192,
    }
    if model:
        payload["model"] = model
    result = asyncio.run(
        router.chat_completion(
            payload,
            model_fallbacks=fallbacks,
            allow_commercial_fallback=False,
        )
    )
    return result.response.json(), result.provider.provider_id


def router_without(router: Any, provider_id: str) -> Any | None:
    """Return a copy of *router* with *provider_id* removed, or None if empty."""
    from packages.ai.router import ProviderRouter

    remaining = [p for p in router.providers if p.provider_id != provider_id]
    return ProviderRouter(remaining) if remaining else None


# ---------------------------------------------------------------------------
# Main agent loop
# ---------------------------------------------------------------------------
def main() -> None:
    # No key check here on purpose. This used to demand ANTHROPIC_API_KEY or
    # NVIDIA_API_KEY specifically, which would have refused to start on a box
    # configured with Cerebras or Groq alone — the same "one provider is the
    # world" assumption that took the agency down. The router reads whatever
    # keys are present and build_tool_calling_router() reports it plainly when
    # none of them can carry a tool call.

    note_path = Path("/tmp/note_content.txt")  # nosec: B108
    url_content = note_path.read_text() if note_path.exists() else ""

    print("Running baseline pytest...", flush=True)
    baseline = _run_baseline_pytest()
    print(f"Baseline pytest output:\n{baseline}", flush=True)

    claude_md = _read_claude_md()

    # Build a thread context block from the body + comments so the LLM
    # can see the FULL issue discussion (not just the URL-derived content).
    thread_block = ""
    if ISSUE_BODY_TEXT.strip():
        thread_block += f"\n### Issue body\n{ISSUE_BODY_TEXT.strip()}\n"
    if ISSUE_COMMENTS_RAW.strip():
        thread_block += "\n### User comments on this issue (consider ALL of them)\n"
        for line in ISSUE_COMMENTS_RAW.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                c = json.loads(line)
                thread_block += f"- **{c.get('author','?')}** ({c.get('created','?')}):\n  {c.get('body','')}\n"
            except Exception:
                thread_block += f"- {line}\n"
    if not thread_block and not url_content:
        thread_block = "\n(no source content captured -- URL was empty and issue body was empty)\n"

    # THREAD_CAP = 60_000 chars. Tail-truncation preserves the most recent comments
    # (most likely to be relevant). If earlier context is critical, the LLM can
    # read /tmp/issue_comments.jsonl directly via the bash tool.
    # 60K ≈ safe for NIM Nemotron Ultra (128K ctx) and Claude Sonnet (200K).
    # Qwen3-Coder 480B's 32K window will still overflow; that is handled by the
    # LLM client at the call site. Do not lower without re-running cost / quality audit.
    THREAD_CAP = 60_000
    if len(thread_block) > THREAD_CAP:
        head_chars = THREAD_CAP // 4
        tail_chars = THREAD_CAP - head_chars
        omitted = len(thread_block) - head_chars - tail_chars
        thread_block = (
            thread_block[:head_chars]
            + f"\n\n[... {omitted} chars of earlier thread omitted for context budget; "
            f"read /tmp/issue_comments.jsonl directly if a missing earlier comment is critical ...]\n\n"
            + thread_block[-tail_chars:]
        )

    user_msg = (
        f"Issue #{ISSUE_NUM}\n"
        f"URL: {URL}\n"
        f"Task: {TASK}\n"
        f"\n--- Full issue thread (body + every user comment) ---\n{thread_block}\n"
        f"--- Content from URL (may be truncated) ---\n{url_content[:4000]}\n\n"
        f"--- CLAUDE.md (repo conventions) ---\n{claude_md}\n\n"
        f"--- Baseline pytest (before your changes) ---\n{baseline}\n"
        "Fix any pre-existing failures if they are easy, but focus on the task.\n"
        "Read every user comment above before acting; if a comment contradicts the URL, follow the comment.\n"
        "Remember: always update docs/changelog.md before signaling IMPLEMENTATION_COMPLETE."
    )

    success = False
    summary = "No implementation performed"
    turns = 0
    final_model = "(no provider attempted)"

    # Every call goes through ProviderRouter (rule 2), which owns the
    # Cerebras → Groq → NVIDIA → Ollama chain and rule 4's 410 handling.
    router = build_tool_calling_router()
    if router is None:
        print(
            "ERROR: no openai-compatible provider is configured. Set at least one "
            "provider key (CEREBRAS_API_KEY, GROQ_API_KEY, NVIDIA_API_KEY, ...) — "
            "the anthropic/bedrock/ollama-native paths cannot carry tool calls.",
            file=sys.stderr,
        )
    else:

        messages: list[dict] = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": user_msg},
        ]

        last_pytest_passed = False

        while turns < MAX_TURNS:
            turns += 1
            print(f"\n[agent] Turn {turns}/{MAX_TURNS}", flush=True)

            try:
                data, answering_provider = router_turn(router, messages)
            except Exception as exc:
                # The router has already walked every eligible provider and model
                # by this point, so there is nothing left to fall back to.
                print(f"All providers and models failed: {exc}", file=sys.stderr)
                break

            final_model = str(data.get("model") or final_model)
            msg = ((data.get("choices") or [{}])[0] or {}).get("message") or {}
            content = msg.get("content") or ""
            tool_calls = msg.get("tool_calls") or []

            if content:
                print(f"[agent] ({final_model}) {content[:400]}", flush=True)

            # Serialise without null sentinel fields that NIM rejects with 422
            assistant_entry: dict = {"role": "assistant"}
            if content:
                assistant_entry["content"] = content
            if tool_calls:
                assistant_entry["tool_calls"] = [
                    {
                        "id": tc.get("id"),
                        "type": "function",
                        "function": {
                            "name": (tc.get("function") or {}).get("name"),
                            "arguments": (tc.get("function") or {}).get("arguments") or "{}",
                        },
                    }
                    for tc in tool_calls
                ]
            messages.append(assistant_entry)

            # No tool calls → check for XML-format tool calls (Qwen3 quirk) then terminal turn
            if not tool_calls:
                # Some models (e.g. Qwen3-coder) emit tool calls as XML text in
                # content instead of structured tool_calls. Retrying gives the
                # router a chance to land on a different provider; two in a row
                # means the one answering cannot do structured tool use, and
                # burning 120 turns on it would just be a slower failure.
                if "<tool_call>" in content or "<function=" in content:
                    # Retrying is pointless: the router is priority-ordered and
                    # holds no state between calls, so the same payload reaches
                    # the same provider and draws the same malformed reply. Drop
                    # the provider that answered and try the rest — this is what
                    # the old explicit model-advance did, at provider grain.
                    print(
                        f"[agent] {answering_provider} ({final_model}) emitted XML "
                        "tool calls in content — dropping it and failing over",
                        file=sys.stderr,
                    )
                    messages.pop()  # discard the malformed assistant turn
                    router = router_without(router, answering_provider)
                    if router is None:
                        print(
                            "No provider left that produces structured tool calls.",
                            file=sys.stderr,
                        )
                        break
                    turns -= 1  # don't count this as a real turn
                    continue
                summary = content or summary
                if content and "IMPLEMENTATION_COMPLETE" in content and last_pytest_passed:
                    success = True
                    summary = content[:500]
                break

            # Execute tool calls
            for tc in tool_calls:
                function = tc.get("function") or {}
                fn_name = function.get("name") or ""
                try:
                    fn_args = json.loads(function.get("arguments") or "{}")
                except json.JSONDecodeError:
                    fn_args = {}

                print(f"[tool] {fn_name}({list(fn_args.keys())})", flush=True)
                handler = TOOL_DISPATCH.get(fn_name)
                out = handler(fn_args) if handler else f"[unknown tool: {fn_name}]"
                print(f"[tool result] {str(out)[:300]}", flush=True)

                if fn_name == "bash":
                    cmd = fn_args.get("cmd", "")
                    if "pytest" in cmd:
                        last_pytest_passed = "[exit 0]" in out
                        print(f"pytest exit 0: {last_pytest_passed}", flush=True)
                    if "IMPLEMENTATION_COMPLETE" in out:
                        if last_pytest_passed:
                            success = True
                            summary = f"Agent signaled completion after {turns} turns."
                        else:
                            out = (
                                "[BLOCKED] IMPLEMENTATION_COMPLETE rejected: last pytest did not exit 0. "
                                "Fix all test failures first, then signal completion."
                            )

                messages.append(
                    {"role": "tool", "tool_call_id": tc.get("id"), "content": str(out)}
                )

            if success:
                break

        if not success and turns >= MAX_TURNS:
            summary = f"Agent hit turn limit ({MAX_TURNS}) without completing"

    # The run stays on free, openai-compatible providers. The Anthropic/Opus
    # fallback was removed because it silently burned paid credits whenever the
    # free chain failed; `allow_commercial_fallback=False` in router_turn() is
    # what keeps that true now that routing is delegated. A run that cannot
    # finish fails loudly so the operator can act, rather than escalating to a
    # paid provider behind the operator's back.

    result = {"success": success, "summary": summary, "turns": turns}
    with open(RESULT_FILE, "w") as f:
        json.dump(result, f)

    print(f"\n[agent] Done — success={success}, turns={turns}, model={final_model}", flush=True)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
