"""
.github/scripts/generate_context.py

Generates a rich context document (implementation prompt + prioritized TODO list)
for any GitHub issue. Runs inside the issue-context-generator workflow.

Usage (environment vars set by the workflow):
  ISSUE_NUMBER, ISSUE_TITLE, ISSUE_BODY, ISSUE_LABELS must be set.
  NVIDIA_API_KEY or ANTHROPIC_API_KEY must be set (NVIDIA tried first).

Outputs /tmp/context_result.json:
  {
    "pr_description": str,   # Full Markdown PR body (prompt + TODOs)
    "context_doc": str,      # Markdown for docs/context/issue-N.md
    "title": str             # Suggested short PR title
  }
"""
from __future__ import annotations

import json
import logging
import os
import sys
import textwrap
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("generate_context")

RESULT_FILE = "/tmp/context_result.json"  # nosec: B108 - predictable temp path; matches implement_agent.py convention for inter-step communication
REPO_ROOT = Path(__file__).parent.parent.parent

# NVIDIA NIM models tried in order
NVIDIA_MODELS = [
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "qwen/qwen3-coder-480b-a35b-instruct",
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "meta/llama-3.3-70b-instruct",
]
CLAUDE_MODEL = "claude-opus-4-8"


# ---------------------------------------------------------------------------
# Codebase context loader
# ---------------------------------------------------------------------------

def _load_codebase_context() -> str:
    """Load CLAUDE.md + GRAPH_REPORT summary for LLM context."""
    parts: list[str] = []

    claude_md = REPO_ROOT / "CLAUDE.md"
    if claude_md.exists():
        parts.append("=== CLAUDE.md (project guide) ===")
        parts.append(claude_md.read_text()[:4000])

    graph_report = REPO_ROOT / "graphify-out" / "GRAPH_REPORT.md"
    if graph_report.exists():
        # Only first 2000 chars — the god-nodes section is the useful part
        parts.append("\n=== GRAPH_REPORT (codebase map) ===")
        parts.append(graph_report.read_text()[:2000])

    # Module map from CLAUDE.md codebase section (already included above)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a senior engineering architect for the local-llm-server project —
    a self-hosted, OpenAI-compatible proxy for Ollama with FastAPI, async I/O,
    Bearer-token auth, model routing, Langfuse observability, multi-agent
    orchestration, Telegram bot, and a React/Next.js admin dashboard.

    Your job: given a GitHub issue, produce:
    1. A rich **implementation prompt** for an AI coding agent (Claude Code / NIM).
       Be specific: name files, functions, patterns. Reference the codebase map.
    2. A **prioritized TODO list** — ordered, actionable, concrete steps with
       estimated complexity (S/M/L). Cover implementation, tests, docs, changelog.
    3. **Relevant files** — list of files the implementer must read first.
    4. **Risk flags** — note any risky modules (auth, key_store, agent/tools.py).
    5. A one-line **PR title** suggestion.

    Coding rules to embed in the prompt:
    - Type annotations on all public functions; `from __future__ import annotations`
    - No secrets in source; all config via env vars
    - Pydantic models for all API I/O
    - Async for all I/O; log with `logging`, not `print`
    - Update docs/changelog.md under [Unreleased]
    - Run `pytest -x` before and after changes
""")


def _build_user_message(
    issue_number: str,
    title: str,
    body: str,
    labels: list[str],
    codebase_ctx: str,
) -> str:
    label_str = ", ".join(labels) if labels else "none"
    return textwrap.dedent(f"""\
        ## GitHub Issue #{issue_number}

        **Title:** {title}
        **Labels:** {label_str}

        **Body:**
        {body or "(no body provided)"}

        ---
        ## Codebase Context

        {codebase_ctx}

        ---
        ## Your Output Format

        Return **valid JSON only** — no markdown fences, no preamble:

        {{
          "title": "<one-line PR title, max 70 chars, prefix feat:/fix:/refactor:>",
          "prompt": "<full implementation prompt for the AI coding agent, 300-600 words>",
          "todos": [
            {{"step": 1, "task": "<task>", "complexity": "S|M|L", "file": "<primary file or null>"}},
            ...
          ],
          "relevant_files": ["<file1>", "<file2>"],
          "risk_flags": ["<flag1>"] | [],
          "notes": "<any architectural notes or open questions>"
        }}
    """)


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------

def _call_nvidia(prompt: str, user_msg: str) -> dict:
    from openai import OpenAI

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not set")

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

    for model in NVIDIA_MODELS:
        log.info("Trying NVIDIA model: %s", model)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": user_msg},
                ],
                temperature=0.3,
                max_tokens=2048,
                timeout=120,
            )
            text = resp.choices[0].message.content or ""
            return _parse_json(text)
        except Exception as exc:
            log.warning("Model %s failed: %s — trying next", model, exc)
            time.sleep(2)

    raise RuntimeError("All NVIDIA models exhausted")


def _call_claude(prompt: str, user_msg: str) -> dict:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=prompt,
        messages=[{"role": "user", "content": user_msg}],
    )
    text = resp.content[0].text if resp.content else ""
    return _parse_json(text)


def _parse_json(text: str) -> dict:
    """Extract JSON from LLM output, stripping any markdown fences."""
    text = text.strip()
    # Strip ```json ... ``` fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    # Find first { and last }
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError(f"No JSON object found in response: {text[:200]}")
    return json.loads(text[start:end])


# ---------------------------------------------------------------------------
# Output builder
# ---------------------------------------------------------------------------

def _build_pr_description(issue_number: str, title: str, result: dict) -> str:
    todos_md = "\n".join(
        f"- [ ] **[{t.get('complexity','?')}]** {t.get('task','')} "
        f"`{t.get('file','') or ''}`"
        for t in result.get("todos", [])
    )
    relevant = "\n".join(f"- `{f}`" for f in result.get("relevant_files", []))
    risks = result.get("risk_flags", [])
    risk_md = (
        "\n".join(f"- ⚠️ {r}" for r in risks)
        if risks
        else "_No risky modules flagged._"
    )
    notes = result.get("notes", "")

    return textwrap.dedent(f"""\
        ## Context Plan — Issue #{issue_number}: {title}

        > Auto-generated by the **issue-context-generator** workflow.
        > This is a **DRAFT PR** — implement by triggering the Process Quick Note
        > workflow or by opening a Claude Code session on this branch.

        ---

        ## Implementation Prompt

        {result.get('prompt', '(prompt generation failed)')}

        ---

        ## TODO List

        {todos_md or '_No TODOs generated._'}

        ---

        ## Relevant Files to Read First

        {relevant or '_None identified._'}

        ---

        ## Risk Flags

        {risk_md}

        ---

        ## Architectural Notes

        {notes or '_None._'}

        ---

        *Closes #{issue_number}*
    """)


def _build_context_doc(issue_number: str, title: str, result: dict, pr_description: str) -> str:
    return textwrap.dedent(f"""\
        # Issue #{issue_number}: {title}

        _Generated: {time.strftime('%Y-%m-%d')}_

        {pr_description}
    """)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    issue_number = sys.argv[1] if len(sys.argv) > 1 else os.environ.get("ISSUE_NUMBER", "?")
    title = os.environ.get("ISSUE_TITLE", "Untitled issue")
    body = os.environ.get("ISSUE_BODY", "")
    labels_raw = os.environ.get("ISSUE_LABELS", "[]")

    try:
        label_objs = json.loads(labels_raw)
        labels = [l.get("name", "") if isinstance(l, dict) else str(l) for l in label_objs]
    except (json.JSONDecodeError, TypeError):
        labels = []

    log.info("Generating context for issue #%s: %s", issue_number, title)

    codebase_ctx = _load_codebase_context()
    user_msg = _build_user_message(issue_number, title, body, labels, codebase_ctx)

    result: dict = {}
    errors: list[str] = []

    # Try NVIDIA first, Claude as fallback
    for caller_name, caller in [("NVIDIA NIM", _call_nvidia), ("Claude", _call_claude)]:
        try:
            log.info("Calling %s ...", caller_name)
            result = caller(SYSTEM_PROMPT, user_msg)
            log.info("Success with %s", caller_name)
            break
        except Exception as exc:
            log.warning("%s failed: %s", caller_name, exc)
            errors.append(f"{caller_name}: {exc}")

    if not result:
        log.error("All LLM providers failed: %s", errors)
        sys.exit(1)

    pr_description = _build_pr_description(issue_number, title, result)
    context_doc = _build_context_doc(issue_number, title, result, pr_description)

    output = {
        "title": result.get("title", f"plan: {title[:60]} (#{issue_number})"),
        "pr_description": pr_description,
        "context_doc": context_doc,
    }

    Path(RESULT_FILE).write_text(json.dumps(output, indent=2))
    log.info("Context written to %s", RESULT_FILE)
    log.info("Generated title: %s", output["title"])


if __name__ == "__main__":
    main()
