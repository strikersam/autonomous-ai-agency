from __future__ import annotations

"""
Agentic implementation loop using NVIDIA NIM (OpenAI-compatible tool use).

Reads URL content + task from args, loads repo context (CLAUDE.md + skills),
and runs a plan → implement → test cycle with real file editing and bash
execution via OpenAI function-calling against the NVIDIA NIM API.

Usage:
  python implement_agent.py <url> <issue_num> <task>

Writes /tmp/impl_result.json with {"success": bool, "summary": str}
"""


import json
import logging
import os
import random  # nosec B311 — used only for jitter in rate-limit backoff, not crypto
import subprocess  # nosec B404 - used for constant-argv git/pytest calls below
import sys
import textwrap
import time
from pathlib import Path

from openai import OpenAI

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

# Shared NVIDIA model list — inject .github/scripts/ on sys.path so the
# import works when this script is run directly (python implement_agent.py).
_sd = os.path.dirname(os.path.abspath(__file__))
if _sd not in sys.path:
    sys.path.insert(0, _sd)
from nvidia_models import NVIDIA_CANDIDATE_MODELS  # shared source of truth
# Keep old name as alias
CANDIDATE_MODELS = NVIDIA_CANDIDATE_MODELS


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
        # This prevents the agent from accidentally overwriting files with truncated reads.
        if p.exists():
            existing_lines = p.read_text(errors="replace").count("\n")
            new_lines = content.count("\n")
            if existing_lines > 20 and new_lines < existing_lines - 10:
                return (
                    f"[BLOCKED] write_file would reduce {path} from {existing_lines} lines to {new_lines} lines "
                    f"(lost {existing_lines - new_lines} lines). This usually means you read a truncated version "
                    f"of the file and are writing it back incomplete. "
                    f"For docs/changelog.md use add_changelog_entry instead. "
                    f"For source files, use bash(cmd='cat >> file') to append or make targeted edits."
                )
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
        result = subprocess.run(  # nosec B603 B607 - constant git argv, list form (no shell)
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
    result = subprocess.run(  # nosec B603 B607 - constant pytest argv, list form (no shell)
        ["python", "-m", "pytest", "-x", "-q", "--tb=line", "--no-header"],
        capture_output=True, text=True, timeout=120, env=env,
    )
    lines = (result.stdout + result.stderr).splitlines()
    return "\n".join(lines[-15:])


# ---------------------------------------------------------------------------
# Hardened model fallback helpers
# ---------------------------------------------------------------------------
def _classify_error(exc: Exception) -> str:
    """Classify an exception from the NVIDIA NIM API.

    Returns one of: '429_rate_limit', 'timeout', '404_not_found',
    '422_unprocessable', or 'unknown'.
    """
    exc_msg = str(exc).lower()
    exc_name = type(exc).__name__
    if "429" in exc_msg or "rate limit" in exc_msg or "too many requests" in exc_msg:
        return "429_rate_limit"
    if "timeout" in exc_msg or "timed out" in exc_msg or exc_name.endswith("Timeout"):
        return "timeout"
    if "404" in exc_msg or "not found" in exc_msg:
        return "404_not_found"
    if "422" in exc_msg or "unprocessable" in exc_msg:
        return "422_unprocessable"
    return "unknown"


# Main agent loop — NVIDIA NIM only (Anthropic fallback removed to prevent
# burning paid credits when free models fail. Fail cleanly instead.)
# ---------------------------------------------------------------------------
def main() -> None:
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")

    if not nvidia_key:
        log.error("ERROR: NVIDIA_API_KEY not set — cannot run agent")
        sys.exit(1)

    note_path = Path("/tmp/note_content.txt")  # nosec: B108
    url_content = note_path.read_text() if note_path.exists() else ""

    log.info("Running baseline pytest...")
    baseline = _run_baseline_pytest()
    log.info(f"Baseline pytest output:\n{baseline}")

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
    final_model = NVIDIA_CANDIDATE_MODELS[0][0]

    log.info("[agent] Using NVIDIA NIM as the primary engine")
    client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)

    messages: list[dict] = [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": user_msg},
    ]

    last_pytest_passed = False
    model_idx = 0
    model = NVIDIA_CANDIDATE_MODELS[model_idx][0]
    final_model = model

    while turns < MAX_TURNS:
        turns += 1
        log.info(f"\n[agent] Turn {turns}/{MAX_TURNS} model={model}")

        try:
            res = client.chat.completions.create(
                model=model,
                max_tokens=8192,
                tools=TOOLS,  # type: ignore[arg-type]
                tool_choice="auto",
                messages=messages,  # type: ignore[arg-type]
            )
        except Exception as exc:
            err_kind = _classify_error(exc)
            log.error(f"Model {model} error [{err_kind}]: {exc}")

            # 429 rate-limit — transient; retry same model with exponential
            # backoff + jitter before advancing. Up to 3 attempts.
            if err_kind == "429_rate_limit":
                retry_succeeded = False
                for backoff_attempt in range(3):
                    delay = (2 ** backoff_attempt) + random.uniform(0, 1)  # nosec B311 — jitter only, not crypto
                    log.warning(
                        f"Model {model} rate-limited (429) — retrying in {delay:.1f}s "
                        f"(attempt {backoff_attempt+1}/3)"
                    )
                    time.sleep(delay)
                    try:
                        res = client.chat.completions.create(
                            model=model,
                            max_tokens=8192,
                            tools=TOOLS,
                            tool_choice="auto",
                            messages=messages,
                        )
                        log.info(f"Model {model} recovered after rate-limit backoff")
                        retry_succeeded = True
                        break
                    except Exception as retry_exc:
                        retry_kind = _classify_error(retry_exc)
                        log.warning(
                            f"Model {model} retry {backoff_attempt+1}/3 failed [{retry_kind}]: {retry_exc}"
                        )
                        # If retry also gives 404/422, drop immediately (non-transient)
                        if retry_kind in ("404_not_found", "422_unprocessable"):
                            log.warning(
                                f"Model {model} returned {retry_kind} on retry — "
                                "dropping from rotation"
                            )
                            break
                if retry_succeeded:
                    pass  # fall through to msg processing below
                else:
                    # Either all 3 retries exhausted or 404/422 on retry — advance
                    model_idx += 1
                    if model_idx >= len(NVIDIA_CANDIDATE_MODELS):
                        log.error("All NVIDIA candidate models exhausted — failing cleanly.")
                        break
                    model = NVIDIA_CANDIDATE_MODELS[model_idx][0]
                    final_model = model
                    log.warning(f"Switching to: {model}")
                    turns -= 1
                    continue

            # Timeout — advance immediately, no backoff
            elif err_kind == "timeout":
                log.warning(f"Model {model} timed out — advancing immediately")
                model_idx += 1
                if model_idx >= len(NVIDIA_CANDIDATE_MODELS):
                    log.error("All NVIDIA candidate models exhausted — failing cleanly.")
                    break
                model = NVIDIA_CANDIDATE_MODELS[model_idx][0]
                final_model = model
                log.warning(f"Switching to: {model}")
                turns -= 1
                continue

            # 404 / 422 — model is not available or incompatible; drop and advance
            elif err_kind in ("404_not_found", "422_unprocessable"):
                log.warning(
                    f"Model {model} returned {err_kind} — dropping from rotation for this run"
                )
                model_idx += 1
                if model_idx >= len(NVIDIA_CANDIDATE_MODELS):
                    log.error("All NVIDIA candidate models exhausted — failing cleanly.")
                    break
                model = NVIDIA_CANDIDATE_MODELS[model_idx][0]
                final_model = model
                log.warning(f"Switching to: {model}")
                turns -= 1
                continue

            # Unknown error — advance to next model
            else:
                model_idx += 1
                if model_idx >= len(NVIDIA_CANDIDATE_MODELS):
                    log.error("All NVIDIA candidate models exhausted — failing cleanly.")
                    break
                model = NVIDIA_CANDIDATE_MODELS[model_idx][0]
                final_model = model
                log.warning(f"Switching to: {model}")
                turns -= 1
                continue

        msg = res.choices[0].message

        if msg.content:
            log.info(f"[agent] {msg.content[:400]}")

        # Serialise without null sentinel fields that NIM rejects with 422
        assistant_entry: dict = {"role": "assistant"}
        if msg.content:
            assistant_entry["content"] = msg.content
        if msg.tool_calls:
            assistant_entry["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": "function",
                    "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                }
                for tc in msg.tool_calls
            ]
        messages.append(assistant_entry)

        # No tool calls → check for XML-format tool calls (Qwen3 quirk) then terminal turn
        if not msg.tool_calls:
            content = msg.content or ""
            # Some models (e.g. Qwen3-coder) emit tool calls as XML text in content
            # instead of structured tool_calls. Detect and switch models.
            if "<tool_call>" in content or "<function=" in content:
                log.warning(f"[agent] {model} emitted XML tool calls in content — switching model")
                messages.pop()  # discard the malformed assistant turn
                model_idx += 1
                if model_idx < len(NVIDIA_CANDIDATE_MODELS):
                    model = NVIDIA_CANDIDATE_MODELS[model_idx][0]
                    final_model = model
                    log.info(f"[agent] Switched to: {model}")
                    turns -= 1  # don't count this as a real turn
                else:
                    log.error("All candidate models exhausted.")
                    break
                continue
            summary = content or summary
            if content and "IMPLEMENTATION_COMPLETE" in content and last_pytest_passed:
                success = True
                summary = content[:500]
            break

        # Execute tool calls
        for tc in msg.tool_calls:
            fn_name = tc.function.name
            try:
                fn_args = json.loads(tc.function.arguments)
            except json.JSONDecodeError:
                fn_args = {}

            log.info(f"[tool] {fn_name}({list(fn_args.keys())})")
            handler = TOOL_DISPATCH.get(fn_name)
            out = handler(fn_args) if handler else f"[unknown tool: {fn_name}]"
            log.info(f"[tool result] {str(out)[:300]}")

            if fn_name == "bash":
                cmd = fn_args.get("cmd", "")
                if "pytest" in cmd:
                    last_pytest_passed = "[exit 0]" in out
                    log.info(f"pytest exit 0: {last_pytest_passed}")
                if "IMPLEMENTATION_COMPLETE" in out:
                    if last_pytest_passed:
                        success = True
                        summary = f"Agent signaled completion after {turns} turns."
                    else:
                        out = (
                            "[BLOCKED] IMPLEMENTATION_COMPLETE rejected: last pytest did not exit 0. "
                            "Fix all test failures first, then signal completion."
                        )

            messages.append({"role": "tool", "tool_call_id": tc.id, "content": str(out)})

        if success:
            break

    if not success and turns >= MAX_TURNS:
        summary = f"Agent hit turn limit ({MAX_TURNS}) without completing"

    result = {"success": success, "summary": summary, "turns": turns}
    with open(RESULT_FILE, "w") as f:
        json.dump(result, f)

    log.info(f"\n[agent] Done — success={success}, turns={turns}, model={final_model}")
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
