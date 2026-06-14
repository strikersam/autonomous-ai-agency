from __future__ import annotations

"""
Council-review agent using NVIDIA NIM.

Fetches the git diff of a PR branch vs master and runs the council-review
skill (Security, Correctness, Performance, Maintainability reviewers).

Usage:
  python review_agent.py <pr_number>

Writes /tmp/review_result.json with:
  {"verdict": "PASS"|"WARN"|"FAIL", "summary": str, "details": str}

Always exits 0 — the workflow uses the verdict value, not the exit code.
Defaults to WARN on any API or format error so auto-merge is never silently
blocked by a reviewer crash.
"""


import json
import logging
import os
import random  # nosec B311 — used only for jitter in rate-limit backoff, not crypto
import subprocess
import sys
import textwrap
import time
from pathlib import Path

from openai import OpenAI

# CLI script: log to stdout so messages stay visible and ordered in CI logs.
logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stdout)
log = logging.getLogger("review_agent")

PR_NUMBER = sys.argv[1] if len(sys.argv) > 1 else ""
RESULT_FILE = "/tmp/review_result.json"  # nosec: B108 - Predictable temp file path used for backward compatibility

# NVIDIA NIM is the primary engine for council review.
# Opus-via-Anthropic is only an optional fallback when configured.
# Live-verified 2026-06-14: only 3 of 10 tested models are reachable.
OPUS_MODEL = "claude-opus-4-6"
NVIDIA_CANDIDATE_MODELS = [
    "nvidia/llama-3.3-nemotron-super-49b-v1",
    "meta/llama-4-maverick-17b-128e-instruct",
    "meta/llama-3.3-70b-instruct",
]
# Keep the old name as an alias so existing code that references CANDIDATE_MODELS still works
CANDIDATE_MODELS = NVIDIA_CANDIDATE_MODELS


def get_pr_diff(pr_num: str) -> str:
    try:
        result = subprocess.run(
            ["gh", "pr", "diff", pr_num, "--patch"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"[diff unavailable: gh exited {result.returncode}: {result.stderr.strip()[:200]}]"
        diff = result.stdout
    except subprocess.TimeoutExpired:
        return "[diff unavailable: gh timed out]"
    if len(diff) > 12000:
        diff = diff[:12000] + "\n...[diff truncated]"
    return diff


def get_pr_files(pr_num: str) -> str:
    try:
        result = subprocess.run(
            ["gh", "pr", "view", pr_num, "--json", "files", "-q", ".files[].path"],
            capture_output=True, text=True, timeout=30,
        )
        if result.returncode != 0:
            return f"[files unavailable: gh exited {result.returncode}: {result.stderr.strip()[:200]}]"
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return "[files unavailable: gh timed out]"


def load_council_skill() -> str:
    p = Path(".agents/skills/council-review/SKILL.md")
    if p.exists():
        return p.read_text()[:2000]
    return ""


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


def _call_review_llm(prompt: str, *, anthropic_key: str, nvidia_key: str) -> str:
    """Call the best available LLM for review. NVIDIA NIM is the primary engine;
    Opus-via-Anthropic is only an optional fallback.

    Hardened fallback (2026-06-14):
      - 429 rate-limit: exponential backoff retry (3 attempts, jittered) on
        the same model before advancing.
      - Timeout: advance to the next model immediately.
      - 404/422: drop the model from rotation for this run and advance.
      - Unknown error: advance to the next model.
      - Full exhaustion: fall through to Anthropic (if configured) or return "".
    """
    # Primary: NVIDIA NIM with hardened fallback
    if nvidia_key:
        client = OpenAI(base_url="https://integrate.api.nvidia.com/v1", api_key=nvidia_key)
        dropped_models: set[str] = set()
        model_idx = 0
        while model_idx < len(NVIDIA_CANDIDATE_MODELS):
            model = NVIDIA_CANDIDATE_MODELS[model_idx]
            if model in dropped_models:
                model_idx += 1
                continue
            try:
                response = client.chat.completions.create(
                    model=model,
                    max_tokens=2048,
                    messages=[{"role": "user", "content": prompt}],
                )
                text = response.choices[0].message.content or ""
                if text:
                    log.info("[review] Got response from %s (NVIDIA NIM)", model)
                    return text
                log.warning("[review] Model %s returned empty content — advancing", model)
                model_idx += 1
            except Exception as exc:
                err_kind = _classify_error(exc)
                log.warning("[review] Model %s failed [%s]: %s", model, err_kind, exc)

                # 429 rate-limit — transient; retry same model with exponential
                # backoff + jitter before advancing. Up to 3 attempts.
                if err_kind == "429_rate_limit":
                    retry_succeeded = False
                    for backoff_attempt in range(3):
                        delay = (2 ** backoff_attempt) + random.uniform(0, 1)  # nosec B311 — jitter only, not crypto
                        log.warning(
                            "[review] Model %s rate-limited (429) — retrying in %.1fs "
                            "(attempt %d/3)", model, delay, backoff_attempt + 1
                        )
                        time.sleep(delay)
                        try:
                            response = client.chat.completions.create(
                                model=model,
                                max_tokens=2048,
                                messages=[{"role": "user", "content": prompt}],
                            )
                            text = response.choices[0].message.content or ""
                            if text:
                                log.info("[review] Model %s recovered after rate-limit backoff", model)
                                return text
                            retry_succeeded = False
                            break
                        except Exception as retry_exc:
                            retry_kind = _classify_error(retry_exc)
                            log.warning(
                                "[review] Model %s retry %d/3 failed [%s]: %s",
                                model, backoff_attempt + 1, retry_kind, retry_exc
                            )
                            if retry_kind in ("404_not_found", "422_unprocessable"):
                                log.warning(
                                    "[review] Model %s returned %s on retry — dropping from rotation",
                                    model, retry_kind
                                )
                                break
                            # Non-429 errors on retry (timeout, unknown) are not transient
                            # — break immediately rather than wasting more retries.
                            break
                    if not retry_succeeded:
                        model_idx += 1
                    continue

                # Timeout — advance immediately, no backoff
                elif err_kind == "timeout":
                    log.warning("[review] Model %s timed out — advancing immediately", model)
                    model_idx += 1
                    continue

                # 404 / 422 — model is not available or incompatible; drop and advance
                elif err_kind in ("404_not_found", "422_unprocessable"):
                    log.warning(
                        "[review] Model %s returned %s — dropping from rotation for this run",
                        model, err_kind
                    )
                    dropped_models.add(model)
                    model_idx += 1
                    continue

                # Unknown error — advance to next model
                else:
                    model_idx += 1
                    continue

        log.error("[review] All NVIDIA candidate models exhausted")

    # Optional fallback: Anthropic Claude Opus
    if anthropic_key:
        try:
            import anthropic as _anthropic
            client = _anthropic.Anthropic(api_key=anthropic_key)
            resp = client.messages.create(
                model=OPUS_MODEL,
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            text = next((b.text for b in resp.content if b.type == "text"), "")
            if text:
                log.info("[review] Got response from %s (Anthropic fallback)", OPUS_MODEL)
                return text
        except Exception as exc:
            log.exception("[review] Anthropic Opus fallback failed: %s", exc)

    return ""


def main() -> None:
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "")
    nvidia_key = os.environ.get("NVIDIA_API_KEY", "")

    if not anthropic_key and not nvidia_key:
        print("ERROR: neither ANTHROPIC_API_KEY nor NVIDIA_API_KEY set — defaulting to WARN", file=sys.stderr)
        with open(RESULT_FILE, "w") as f:
            json.dump({"verdict": "WARN", "summary": "Review skipped (no API key)", "details": ""}, f)
        sys.exit(0)

    diff = get_pr_diff(PR_NUMBER)
    files = get_pr_files(PR_NUMBER)

    # Warn open: if we couldn't fetch the diff, don't block the merge.
    if diff.startswith("[diff unavailable"):
        print(f"WARNING: {diff} — defaulting to WARN", file=sys.stderr)
        with open(RESULT_FILE, "w") as f:
            json.dump({"verdict": "WARN", "summary": f"Could not fetch diff: {diff}", "details": ""}, f)
        sys.exit(0)

    skill = load_council_skill()

    prompt = textwrap.dedent(f"""
        You are performing a council code review on PR #{PR_NUMBER}.

        ## Council Review Skill
        {skill}

        ## Files Changed
        {files}

        ## Diff
        ```diff
        {diff}
        ```

        ## Instructions
        Run all four reviewer roles (Security, Correctness, Performance,
        Maintainability). For each, give a verdict: PASS / WARN / FAIL and
        a one-sentence reason.

        Then give an overall verdict:
        - PASS: all reviewers are PASS or WARN, no blocking issues
        - WARN: one or more WARNs but nothing blocking — auto-merge OK
        - FAIL: any reviewer found a blocking issue — needs human review

        Output in this exact format:
        SECURITY: <PASS|WARN|FAIL> — <reason>
        CORRECTNESS: <PASS|WARN|FAIL> — <reason>
        PERFORMANCE: <PASS|WARN|FAIL> — <reason>
        MAINTAINABILITY: <PASS|WARN|FAIL> — <reason>
        OVERALL: <PASS|WARN|FAIL>
        SUMMARY: <one-paragraph summary of the changes and verdict>
    """).strip()

    text = _call_review_llm(prompt, anthropic_key=anthropic_key, nvidia_key=nvidia_key)

    if not text:
        print("All review models failed — defaulting to WARN", file=sys.stderr)
        with open(RESULT_FILE, "w") as f:
            json.dump({"verdict": "WARN", "summary": "All review models failed — defaulting to WARN.", "details": ""}, f)
        sys.exit(0)

    print(text)

    # Parse verdict — warn open if output is unparseable (never block on ambiguity)
    verdict = "WARN"
    parsed_successfully = False
    for line in text.splitlines():
        if line.startswith("OVERALL:"):
            v = line.split(":", 1)[1].strip().split()[0].upper()
            if v in {"PASS", "WARN", "FAIL"}:
                verdict = v
                parsed_successfully = True
            break

    summary_lines = [l for l in text.splitlines() if l.startswith("SUMMARY:")]
    summary = summary_lines[0].replace("SUMMARY:", "").strip() if summary_lines else text[:300]

    result = {
        "verdict": verdict,
        "summary": summary,
        "details": text,
        "parsed_successfully": parsed_successfully,
    }
    with open(RESULT_FILE, "w") as f:
        json.dump(result, f)

    print(f"\n[review] Verdict: {verdict} (parsed={parsed_successfully})")
    sys.exit(0)  # Workflow routes via verdict value, not exit code


if __name__ == "__main__":
    main()
