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
import re
import subprocess  # nosec B404 - used only to invoke the trusted local fetch_url.py script
import sys
import textwrap
import time
from pathlib import Path

# context_rules lives beside this script. Import by path so the module still
# resolves when the bulk workflow copies these scripts to /tmp and runs them
# from a working tree where .github/scripts is no longer checked out.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import context_rules  # noqa: E402
import nvidia_models  # noqa: E402 - shared NVIDIA discovery, one source of truth

logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("generate_context")

RESULT_FILE = "/tmp/context_result.json"  # nosec: B108 - predictable temp path; matches implement_agent.py convention for inter-step communication
# Allow callers to override REPO_ROOT so the script works when copied to /tmp
# and executed after a git branch switch removes it from the working tree.
REPO_ROOT = Path(os.environ.get("REPO_ROOT", str(Path(__file__).parent.parent.parent)))

# NVIDIA model ids come from the shared discovery module (nvidia_models) — the
# single source of truth review_agent.py / apply_review.py already use — so a
# NVIDIA retirement is handled by live discovery, not a hand-edit here. This
# script previously carried its own copy; by 2026-09 all three ids in it were
# dead (two answered 410, one was on the retired list), so context generation
# silently produced nothing on every open issue.
CEREBRAS_MODEL = "gpt-oss-120b"
GROQ_MODEL = "openai/gpt-oss-120b"
MISTRAL_MODEL = "mistral-small-latest"
CLAUDE_MODEL = "claude-opus-4-8"


# ---------------------------------------------------------------------------
# Codebase context loader
# ---------------------------------------------------------------------------

RULES_MARKER = "## 1. The Rules"
STANDING_INSTRUCTIONS_MARKER = "## 2. Standing Instructions"
REFERENCE_MARKER = "## 3. What this repo is"


def _load_codebase_context() -> str:
    """Load CLAUDE.md + GRAPH_REPORT summary for LLM context.

    A flat first-N-chars excerpt cuts CLAUDE.md mid-ruleset, so §1 (the 44
    binding rules) and §2 (Standing Instructions) are carved out and sent
    whole — together ~1,300 words, and the only part of the file an
    autonomous agent must not receive truncated. The leading excerpt covers
    the header; §3 onward is reference material and is deliberately dropped.
    """
    parts: list[str] = []

    claude_md = REPO_ROOT / "CLAUDE.md"
    if claude_md.exists():
        full_text = claude_md.read_text()
        rules_idx = full_text.find(RULES_MARKER)
        ref_idx = full_text.find(REFERENCE_MARKER)

        parts.append("=== CLAUDE.md (project guide) ===")
        parts.append(full_text[:rules_idx] if rules_idx > 0 else full_text[:4000])

        if rules_idx >= 0 and ref_idx > rules_idx:
            # §1 + §2 verbatim: the binding ruleset, never truncated.
            parts.append("\n=== CLAUDE.md §1-§2 — Rules + Standing Instructions (mandatory, full text) ===")
            parts.append(full_text[rules_idx:ref_idx])
        else:
            # Layout changed — fall back to the old behaviour rather than
            # silently shipping a context with no rules in it.
            marker_idx = full_text.find(STANDING_INSTRUCTIONS_MARKER)
            parts.append(full_text[:4000])
            if marker_idx >= 4000:
                parts.append("\n=== CLAUDE.md — Standing Instructions (mandatory, full text) ===")
                parts.append(full_text[marker_idx:])

    graph_report = REPO_ROOT / "graphify-out" / "GRAPH_REPORT.md"
    if graph_report.exists():
        # Only first 2000 chars — the god-nodes section is the useful part
        parts.append("\n=== GRAPH_REPORT (codebase map) ===")
        parts.append(graph_report.read_text()[:2000])

    # Module map from CLAUDE.md codebase section (already included above)
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# URL article fetcher — reuses the battle-tested fetch_url.py multi-strategy
# fetcher so quick-note context is grounded in the ACTUAL article, not a guess.
# ---------------------------------------------------------------------------

def _extract_url(title: str, body: str) -> str | None:
    """Return the first http(s) URL found in the issue title or body."""
    m = re.search(r"https?://[^\s>)\]]+", f"{title}\n{body}")
    return m.group(0) if m else None


def _fetch_url_content(url: str) -> str:
    """Fetch article text via the shared fetch_url.py script (multi-strategy).

    Returns up to 6000 chars of plain text, or "" if the fetch fails. The fetch
    script writes to /tmp/note_content.txt; we read it back. FETCH_URL_SCRIPT
    overrides the script path so this works after the bulk workflow copies the
    scripts to /tmp (git branch switches remove them from the working tree).
    """
    script = os.environ.get(
        "FETCH_URL_SCRIPT", str(Path(__file__).parent / "fetch_url.py")
    )
    out_file = "/tmp/note_content.txt"  # nosec: B108 - shared convention with fetch_url.py
    try:
        if os.path.exists(out_file):
            os.remove(out_file)
    except OSError:
        pass

    log.info("Fetching article content from %s ...", url)
    try:
        subprocess.run(  # nosec B603 - sys.executable + fixed script path, url is the only arg
            [sys.executable, script, url], timeout=150, check=False,
            capture_output=True, text=True,
        )
    except (subprocess.TimeoutExpired, OSError) as exc:
        log.warning("URL fetch failed for %s: %s", url, exc)
        return ""

    if os.path.exists(out_file):
        try:
            content = Path(out_file).read_text()[:6000]
            log.info("Fetched %d chars of article content", len(content))
            return content
        except OSError:
            return ""
    log.warning("URL fetch produced no content for %s", url)
    return ""


# ---------------------------------------------------------------------------
# Prompt builder
# ---------------------------------------------------------------------------

SYSTEM_PROMPT = textwrap.dedent("""\
    You are a senior engineering architect for **autonomous-ai-agency** — a
    self-hosted, OpenAI-compatible AI proxy and multi-agent platform (FastAPI,
    async I/O, Bearer-token auth, multi-provider model routing with failover,
    Langfuse observability, a plan/execute/verify agent loop, a Telegram bot,
    and a React admin dashboard).

    You are given a GitHub issue that links an external artifact — a repo, a
    gist, a skill file, a blog post, a paper. Your job is to decide what, if
    anything, this repository should take from it, and to write a plan an
    implementing agent can execute without re-reading the source.

    ## The rules you are graded against

    Your output is checked by an automated gate. Violations are fed back to you
    for one repair attempt, then published as unmet rules for a human to see.

    R2  Open with what the artifact ACTUALLY IS and does, in plain sentences,
        drawn from the fetched content — not from the URL or the issue title.
    R3  Reach a verdict: `adopt`, `adapt`, or `reject`, with a specific reason.
        **`reject` is a valid and frequently correct answer.** Most linked
        artifacts do not belong in this codebase. Inventing a feature to justify
        the issue is a worse outcome than rejecting it. Reject when the source
        targets a different problem domain, duplicates something this repo
        already has, or would violate the architecture rules in CLAUDE.md.
    R4  Every TODO states a `done_when` — what is observably true once it is
        finished, checkable without doing the other TODOs. "Endpoint returns 200
        with the `served_models` field" qualifies. "Improve the endpoint" does not.
    R5  Never emit a TODO that opens with Review / Investigate / Explore /
        Research / Understand / Consider / Analyze / Identify / Determine unless
        it names a target file AND its done_when is more than a restatement.
        Reading the source is YOUR job and it has already happened.
    R6  Never write: "such as", "e.g.", "if necessary", "if applicable", "may
        need to", "might need", "potentially", "as appropriate", "various",
        "and so on", "etc." Each is a claim you did not check. Where you truly
        do not know, write `Assuming X (unverified) — if wrong, Y changes`.
    R7  List a module in `risk_flags` ONLY if one of your TODOs modifies it.
        Precautionary flags train readers to ignore the risk section.
    R8  Every path in `relevant_files` must be a real path in the codebase
        context you were given. Mark a file you intend to create with a trailing
        ` (new)`. Do not guess plausible-looking paths.
    R9  Do NOT restate rules from CLAUDE.md — pytest, type hints, Pydantic,
        logging over print, changelog updates, secrets handling. The implementing
        agent already loads them. Repeating them pads a thin plan.
    R10 The project is `autonomous-ai-agency`. Never call it `local-llm-server`.
    R11 Name at least one EXISTING module the change hooks into.

    ## What makes a good prompt field

    Specific to this change and this codebase: which existing function is
    extended, what the new call path looks like, which behaviour must stay
    identical (CLAUDE.md §0 — no user-visible behaviour changes unless asked).
    Write it for someone who will not open the source URL.
""")


def _build_user_message(
    issue_number: str,
    title: str,
    body: str,
    labels: list[str],
    codebase_ctx: str,
    article_content: str = "",
) -> str:
    label_str = ", ".join(labels) if labels else "none"

    # Built as a list of lines (no source indentation) to avoid textwrap.dedent
    # failing when interpolated multi-line values have zero leading whitespace.
    article_section = (
        f"---\n## Linked Article Content (fetched from the issue URL)\n\n"
        f"{article_content}\n\n"
        f"Base your prompt and TODOs on what this article ACTUALLY describes — "
        f"do not guess or assume.\n\n"
        if article_content
        else "---\n## Linked Article Content\n\n"
        "_No URL content available — base the plan on the issue body and your "
        "knowledge of the topic, and state assumptions explicitly._\n\n"
    )

    output_format = (
        "{\n"
        '  "title": "<one-line PR title, max 70 chars, prefix feat:/fix:/refactor:>",\n'
        '  "source_summary": "<R2: what the linked artifact IS and does, 2-4 '
        'sentences drawn from the fetched content, min 120 chars>",\n'
        '  "verdict": "adopt|adapt|reject",\n'
        '  "verdict_reason": "<R3: why, specifically. reject is a valid answer>",\n'
        '  "prompt": "<implementation prompt for the coding agent, 300-600 words. '
        'For a reject verdict, explain what was considered and ruled out>",\n'
        '  "todos": [\n'
        '    {"step": 1, "task": "<task>", "done_when": "<R4: observable '
        'completion condition, min 20 chars>", "complexity": "S|M|L", '
        '"file": "<primary file, or null>"}\n'
        "  ],\n"
        '  "relevant_files": ["<R8: real paths only; append \' (new)\' to files '
        'the plan creates>"],\n'
        '  "risk_flags": ["<R7: only modules a TODO above actually modifies>"],\n'
        '  "notes": "<architectural notes or open questions, marked per '
        'CLAUDE.md §2 rule 47>"\n'
        "}"
    )

    return (
        f"## GitHub Issue #{issue_number}\n\n"
        f"**Title:** {title}\n"
        f"**Labels:** {label_str}\n\n"
        f"**Body:**\n{body or '(no body provided)'}\n\n"
        f"{article_section}"
        f"---\n## Codebase Context\n\n{codebase_ctx}\n\n"
        f"---\n## Your Output Format\n\n"
        f"Return **valid JSON only** — no markdown fences, no preamble. "
        f"An empty `todos` list is correct when the verdict is `reject`:\n\n"
        f"{output_format}\n"
    )


# ---------------------------------------------------------------------------
# LLM callers
# ---------------------------------------------------------------------------

def _call_nvidia(prompt: str, messages: list[dict]) -> tuple[dict, str, str]:
    """Return (parsed, raw_text, model_label). Tries each NVIDIA model in turn."""
    from openai import OpenAI

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        raise RuntimeError("NVIDIA_API_KEY not set")

    client = OpenAI(
        base_url="https://integrate.api.nvidia.com/v1",
        api_key=api_key,
    )

    # Ask the provider which models it actually serves (memoised); the static
    # floor in nvidia_models is only used when discovery cannot run.
    model_ids = nvidia_models.resolve_model_ids(api_key)
    if not model_ids:
        raise RuntimeError("No NVIDIA models available")
    for model in model_ids:
        log.info("Trying NVIDIA model: %s", model)
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[{"role": "system", "content": prompt}, *messages],
                temperature=0.3,
                max_tokens=2048,
                timeout=240,
            )
            text = resp.choices[0].message.content or ""
            return _parse_json(text), text, model
        except Exception as exc:
            log.warning("Model %s failed: %s — trying next", model, exc)
            time.sleep(2)

    raise RuntimeError("All NVIDIA models exhausted")


def _call_openai_compatible(
    label: str, base_url: str, api_key_env: str, model: str,
    prompt: str, messages: list[dict],
) -> tuple[dict, str, str]:
    """Shared OpenAI-compatible caller for the free cloud gateways (Cerebras, Groq).

    Both speak the OpenAI chat-completions shape, so the only per-provider
    differences are the base URL, the key variable, and the model id.
    """
    from openai import OpenAI

    api_key = os.environ.get(api_key_env, "")
    if not api_key:
        raise RuntimeError(f"{api_key_env} not set")

    client = OpenAI(base_url=base_url, api_key=api_key)
    log.info("Trying %s model: %s", label, model)
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "system", "content": prompt}, *messages],
        temperature=0.3,
        max_tokens=2048,
        timeout=240,
    )
    text = resp.choices[0].message.content or ""
    return _parse_json(text), text, model


def _call_cerebras(prompt: str, messages: list[dict]) -> tuple[dict, str, str]:
    return _call_openai_compatible(
        "Cerebras", "https://api.cerebras.ai/v1", "CEREBRAS_API_KEY",
        CEREBRAS_MODEL, prompt, messages,
    )


def _call_groq(prompt: str, messages: list[dict]) -> tuple[dict, str, str]:
    return _call_openai_compatible(
        "Groq", "https://api.groq.com/openai/v1", "GROQ_API_KEY",
        GROQ_MODEL, prompt, messages,
    )


def _call_claude(prompt: str, messages: list[dict]) -> tuple[dict, str, str]:
    import anthropic

    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")

    client = anthropic.Anthropic(api_key=api_key)
    resp = client.messages.create(
        model=CLAUDE_MODEL,
        max_tokens=2048,
        system=prompt,
        messages=messages,
    )
    text = resp.content[0].text if resp.content else ""
    return _parse_json(text), text, CLAUDE_MODEL


def _call_mistral(prompt: str, messages: list[dict]) -> tuple[dict, str, str]:
    """Call Mistral as a fallback when NVIDIA models are exhausted."""
    from openai import OpenAI

    api_key = os.environ.get("MISTRAL_API_KEY", "")
    if not api_key:
        raise RuntimeError("MISTRAL_API_KEY not set")

    client = OpenAI(
        base_url="https://api.mistral.ai/v1",
        api_key=api_key,
    )
    log.info("Trying Mistral model: %s", MISTRAL_MODEL)
    resp = client.chat.completions.create(
        model=MISTRAL_MODEL,
        messages=[{"role": "system", "content": prompt}, *messages],
        temperature=0.3,
        max_tokens=2048,
        timeout=240,
    )
    text = resp.choices[0].message.content or ""
    return _parse_json(text), text, MISTRAL_MODEL


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

VERDICT_BADGES = {
    "adopt": "✅ **ADOPT** — build largely as described in the source.",
    "adapt": "🔧 **ADAPT** — the idea is useful; the source's implementation is not a fit.",
    "reject": "🛑 **REJECT** — nothing here belongs in this repository.",
}


def _build_grounding_block(provenance: dict) -> str:
    """Render the Source Grounding table — rulebook R1.

    A reader must be able to tell in one glance whether this plan was derived
    from retrieved content or from the URL slug alone. That distinction was
    previously invisible, which is what let ungrounded plans read as researched.
    """
    url = provenance.get("url") or ""
    chars = provenance.get("source_chars", 0)
    fetched = provenance.get("source_fetched", False)
    fetch_cell = (
        f"✅ fetched — {chars:,} chars of content"
        if fetched
        else "⚠️ **NOT FETCHED** — the plan below is unverified against the source"
    )
    return (
        "## Source Grounding\n\n"
        "| | |\n"
        "|---|---|\n"
        f"| Source URL | {url or '_none found in the issue_'} |\n"
        f"| Fetch status | {fetch_cell} |\n"
        f"| Generated by | {provenance.get('provider', '?')} · `{provenance.get('model', '?')}` |\n"
        f"| Repair rounds | {provenance.get('repair_rounds', 0)} |\n"
        "| Rulebook | `docs/QUICK_NOTE_CONTEXT_RULEBOOK.md` |\n"
    )


def _build_todos_md(todos: list[dict]) -> str:
    """Render TODOs with their done-conditions — rulebook R4."""
    lines: list[str] = []
    for todo in todos:
        file_ref = str(todo.get("file", "") or "").strip()
        suffix = f" — `{file_ref}`" if file_ref else ""
        lines.append(
            f"- [ ] **[{todo.get('complexity', '?')}]** {todo.get('task', '')}{suffix}\n"
            f"      <br/>_Done when:_ {todo.get('done_when') or '**(no done-condition given)**'}"
        )
    return "\n".join(lines)


def _build_pr_description(
    issue_number: str, title: str, result: dict, provenance: dict, gate_md: str
) -> str:
    todos = result.get("todos") or []
    relevant = "\n".join(f"- `{f}`" for f in result.get("relevant_files", []))
    risks = result.get("risk_flags", [])
    risk_md = (
        "\n".join(f"- ⚠️ `{r}`" for r in risks)
        if risks
        else "_No risky modules flagged._"
    )
    verdict = str(result.get("verdict", "") or "").strip().lower()
    verdict_md = VERDICT_BADGES.get(verdict, f"❓ _no verdict recorded_ ({verdict or 'missing'})")

    # A reject verdict has no plan to render. Emitting empty TODO/risk sections
    # would read as a failed generation rather than a deliberate decision.
    if verdict == "reject":
        plan_md = (
            "## Decision\n\n"
            f"{verdict_md}\n\n"
            f"{result.get('verdict_reason', '_No reason given._')}\n\n"
            "---\n\n"
            "## What was considered\n\n"
            f"{result.get('prompt', '_Not recorded._')}\n\n"
        )
    else:
        plan_md = (
            "## Decision\n\n"
            f"{verdict_md}\n\n"
            f"{result.get('verdict_reason', '_No reason given._')}\n\n"
            "---\n\n"
            "## Implementation Prompt\n\n"
            f"{result.get('prompt', '(prompt generation failed)')}\n\n"
            "---\n\n"
            "## TODO List\n\n"
            f"{_build_todos_md(todos) or '_No TODOs generated._'}\n\n"
            "---\n\n"
            "## Relevant Files to Read First\n\n"
            f"{relevant or '_None identified._'}\n\n"
            "---\n\n"
            "## Risk Flags\n\n"
            f"{risk_md}\n\n"
        )

    # Built by joining lines with no source indentation — textwrap.dedent does
    # NOT work here because the interpolated multi-line values (todos_md, prompt)
    # start at column 0, which defeats dedent's common-whitespace detection and
    # leaves the template lines indented (renders as a code block on GitHub).
    return (
        f"## Context Plan — Issue #{issue_number}: {title}\n\n"
        f"> Auto-generated by the **issue-context-generator** workflow.\n"
        f"> This is a **DRAFT PR** — implement by triggering the Process Quick Note\n"
        f"> workflow or by opening a Claude Code session on this branch.\n\n"
        f"---\n\n"
        f"{_build_grounding_block(provenance)}\n"
        f"---\n\n"
        f"## What the source actually is\n\n"
        f"{result.get('source_summary') or '_Not established — see Quality Gate below._'}\n\n"
        f"---\n\n"
        f"{plan_md}"
        f"---\n\n"
        f"## Architectural Notes\n\n"
        f"{result.get('notes') or '_None._'}\n\n"
        f"---\n\n"
        f"{gate_md}\n"
        f"---\n\n"
        f"*Closes #{issue_number}*\n"
    )


def _build_context_doc(issue_number: str, title: str, result: dict, pr_description: str) -> str:
    return (
        f"# Issue #{issue_number}: {title}\n\n"
        f"_Generated: {time.strftime('%Y-%m-%d')}_\n\n"
        f"{pr_description}\n"
    )


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

    # Fetch the linked article so the plan is grounded in real content, not a
    # guess. Quick-note issues carry their entire value in the URL.
    article_content = ""
    url = _extract_url(title, body)
    if url:
        article_content = _fetch_url_content(url)

    user_msg = _build_user_message(
        issue_number, title, body, labels, codebase_ctx, article_content
    )

    result: dict = {}
    errors: list[str] = []
    messages: list[dict] = [{"role": "user", "content": user_msg}]

    caller_name, model_label, raw = "", "", ""
    for caller_name, caller in _build_caller_chain():
        try:
            log.info("Calling %s ...", caller_name)
            result, raw, model_label = caller(SYSTEM_PROMPT, messages)
            log.info("Success with %s (%s)", caller_name, model_label)
            break
        except Exception as exc:
            log.warning("%s failed: %s", caller_name, exc)
            errors.append(f"{caller_name}: {exc}")

    if not result:
        log.error("All LLM providers failed: %s", errors)
        sys.exit(1)

    # Quality gate — one repair round, then publish the violations rather than
    # shipping slop silently. See docs/QUICK_NOTE_CONTEXT_RULEBOOK.md.
    result, violations, repair_rounds = _enforce_rulebook(
        result, raw, messages, bool(article_content), title, caller_name, model_label
    )

    provenance = {
        "url": url,
        "source_fetched": bool(article_content),
        "source_chars": len(article_content),
        "provider": caller_name,
        "model": model_label,
        "repair_rounds": repair_rounds,
    }

    gate_md = context_rules.format_violations(violations)
    pr_description = _build_pr_description(
        issue_number, title, result, provenance, gate_md
    )
    context_doc = _build_context_doc(issue_number, title, result, pr_description)

    output = {
        "title": result.get("title", f"plan: {title[:60]} (#{issue_number})"),
        "pr_description": pr_description,
        "context_doc": context_doc,
        "verdict": str(result.get("verdict", "") or "").strip().lower(),
        "violations": [str(v) for v in violations],
    }

    Path(RESULT_FILE).write_text(json.dumps(output, indent=2))
    log.info("Context written to %s", RESULT_FILE)
    log.info("Generated title: %s", output["title"])
    log.info(
        "Verdict: %s | unmet rules: %d",
        output["verdict"] or "(none)",
        len(violations),
    )


def _build_caller_chain() -> list[tuple[str, object]]:
    """Provider order: NVIDIA → Cerebras → Groq (the free-cloud chain, each gated
    on its key) → Mistral (free) → Claude (paid, policy-gated).

    The workflow passes CEREBRAS_API_KEY / GROQ_API_KEY, but this script used to
    ignore them and try NVIDIA alone — so when NVIDIA's ids went 410 the whole
    chain had nothing left. Each free link is now actually used when its key is
    present.
    """
    callers: list[tuple[str, object]] = [("NVIDIA NIM", _call_nvidia)]
    if os.environ.get("CEREBRAS_API_KEY", "").strip():
        callers.append(("Cerebras", _call_cerebras))
    if os.environ.get("GROQ_API_KEY", "").strip():
        callers.append(("Groq", _call_groq))
    if os.environ.get("MISTRAL_API_KEY", "").strip():
        callers.append(("Mistral", _call_mistral))
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from provider_policy import allow_paid

        if allow_paid():
            callers.append(("Claude", _call_claude))
        else:
            log.info("Paid providers disabled by policy — Claude fallback skipped")
    except ImportError:
        log.debug("provider_policy module not available — Claude fallback skipped")
    return callers


def _enforce_rulebook(
    result: dict,
    raw: str,
    messages: list[dict],
    source_fetched: bool,
    title: str,
    caller_name: str,
    model_label: str,
) -> tuple[dict, list, int]:
    """Validate, attempt one repair, and keep whichever result scored better.

    Returns (result, violations, repair_rounds). Never raises — a failed repair
    leaves the original result intact so the pipeline still produces a document.
    """
    violations = context_rules.validate(
        result, source_fetched=source_fetched, repo_root=REPO_ROOT, title=title
    )
    if not violations:
        log.info("Quality gate passed on the first attempt")
        return result, violations, 0

    log.warning("Quality gate found %d unmet rule(s) — repairing", len(violations))
    for violation in violations:
        log.warning("  %s", violation)

    caller = dict(_build_caller_chain()).get(caller_name)
    if caller is None:
        return result, violations, 0

    repair_messages = [
        *messages,
        {"role": "assistant", "content": raw},
        {"role": "user", "content": context_rules.repair_instruction(violations)},
    ]
    try:
        repaired, _, _ = caller(SYSTEM_PROMPT, repair_messages)  # type: ignore[operator]
    except Exception as exc:
        log.warning("Repair round failed (%s) — keeping the original result", exc)
        return result, violations, 1

    repaired_violations = context_rules.validate(
        repaired, source_fetched=source_fetched, repo_root=REPO_ROOT, title=title
    )
    # Keep the repair only if it is actually better; a model can regress.
    if len(repaired_violations) < len(violations):
        log.info(
            "Repair improved the result: %d → %d unmet rule(s)",
            len(violations),
            len(repaired_violations),
        )
        return repaired, repaired_violations, 1

    log.warning("Repair did not improve the result — keeping the original")
    return result, violations, 1


if __name__ == "__main__":
    main()
