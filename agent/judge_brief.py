"""agent/judge_brief.py — what the run judge is told when a run changed no files.

Production 2026-10-15: research tasks (trend scoping: "research … no code
change; surface a recommendation only") were judged by the code-review judge,
which saw "Diff: (unavailable)" and rejected every one, so no research task
could ever pass. A run that changed no files is now judged on its findings: it
passes only when the goal asked for analysis rather than a change and the
findings answer it. A goal that needed a code change still fails, as before.
"""

from __future__ import annotations

import json
from typing import Any

CODE_JUDGE_SYSTEM = (
    "You are a code-review judge. Review the diff against the goal and the "
    "plan. REJECT when the diff does not accomplish the goal, removes or "
    "rewrites working code the goal did not ask to change, touches files the "
    "plan did not name, or adds URLs, names, contacts or identifiers that do "
    "not appear elsewhere in the repository. REJECT placeholder work: stub "
    "or empty files, files named after a task id, code that only exists to "
    "make an error go away, or notes and logs when the goal asks for a code "
    "change. Respond with ONLY a JSON object "
    "with keys: verdict (APPROVED, APPROVED_WITH_CONDITIONS, or REJECTED), "
    "security (PASS, WARN, or FAIL), correctness (PASS, WARN, or FAIL), "
    "notes (string)."
)

NO_CHANGE_JUDGE_SYSTEM = (
    "You are a code-review judge. This run changed no files, so there is no diff; "
    "judge the findings instead. APPROVE only when the goal asks for research, "
    "analysis, an evaluation or a recommendation (not a code, config or docs change) "
    "AND the findings below substantively answer it with a concrete conclusion. "
    "REJECT when the goal required changing files, when the findings are empty, "
    "generic or off-topic, or when they rest on files or facts the findings do not "
    "show. Respond with ONLY a JSON object with keys: verdict (APPROVED, "
    "APPROVED_WITH_CONDITIONS, or REJECTED), security (PASS, WARN, or FAIL), "
    "correctness (PASS, WARN, or FAIL), notes (string: state the recommendation "
    "the findings support)."
)

_PER_RESULT_CHARS = 800
_FINDINGS_CHARS = 9000


def planned_a_change(plan: Any) -> bool:
    """True when the plan has an edit or create step: the goal needs files changed."""
    return any(getattr(s, "type", "") in ("edit", "create") for s in getattr(plan, "steps", None) or [])


def changed_nothing(step_results: list[dict[str, Any]], plan: Any = None) -> bool:
    """True for a research run: steps ran, none changed a file, and none was meant to.

    A plan with an edit or create step stays with the code judge, so a code
    goal whose edits were skipped or failed is never judged as research.
    """
    if plan is not None and planned_a_change(plan):
        return False
    return bool(step_results) and not any(s.get("changed_files") for s in step_results)


def judge_system(step_results: list[dict[str, Any]], plan: Any = None) -> str:
    """The judge's system prompt for this run."""
    return NO_CHANGE_JUDGE_SYSTEM if changed_nothing(step_results, plan) else CODE_JUDGE_SYSTEM


def _text(value: Any) -> str:
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value, default=str)
    except (TypeError, ValueError):
        return str(value)


def findings(step_results: list[dict[str, Any]]) -> str:
    """The run's observations, newest last, bounded so the judge prompt stays small.

    Each result is clipped with an explicit marker, so the judge never mistakes
    a clipped observation for an incomplete answer.
    """
    parts: list[str] = []
    for step in step_results:
        parts.append(f"Step {step.get('step_id')} ({step.get('status')}): {step.get('description', '')}")
        for obs in step.get("observations") or []:
            if not isinstance(obs, dict):
                continue
            body = _text(obs.get("result"))
            if len(body) > _PER_RESULT_CHARS:
                body = body[:_PER_RESULT_CHARS] + f" … [clipped, {len(body)} chars in total]"
            parts.append(f"- {obs.get('tool', '?')}: {body}")
    text = "\n".join(parts)
    if len(text) > _FINDINGS_CHARS:
        text = f"[earlier findings clipped, {len(text)} chars in total]\n" + text[-_FINDINGS_CHARS:]
    return text or "(no findings recorded)"


def clip_content(path: str, text: str, limit: int) -> str:
    """A changed file's content for the judge, marked when it is clipped."""
    if len(text) <= limit:
        return f"--- {path} (current content; no git baseline to diff against)\n{text}"
    return (f"--- {path} (current content, first {limit} of {len(text)} chars; "
            f"the file continues past this point)\n{text[:limit]}")
