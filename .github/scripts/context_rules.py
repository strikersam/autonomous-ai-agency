"""Quality gate for generated quick-note context documents.

Implements the machine-checkable subset of `docs/QUICK_NOTE_CONTEXT_RULEBOOK.md`.
Every rule ID below (R1, R2, ...) must be documented in that file; the reverse is
asserted by `tests/test_context_rulebook.py`.

Used by `.github/scripts/generate_context.py`:

    violations = validate(result, source_fetched=True, repo_root=Path("."))
    if violations:
        repair = repair_instruction(violations)   # one more LLM attempt
    ...
    doc += format_violations(violations)          # never ship slop silently
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

# --------------------------------------------------------------------------
# Rule vocabulary
# --------------------------------------------------------------------------

VALID_VERDICTS = ("adopt", "adapt", "reject")

MIN_SOURCE_SUMMARY_CHARS = 120
MIN_DONE_WHEN_CHARS = 20

#: R5 — verbs that describe reading, not doing. Reading the source is the
#: generator's job and has already happened by the time a plan is written.
FILLER_OPENERS = (
    "review", "investigate", "explore", "research", "understand",
    "consider", "look into", "analyze", "analyse", "study",
    "familiarize", "familiarise", "determine", "identify",
)

#: R6 — hedges that read like facts. Each one is a claim the writer did not check.
BANNED_HEDGES = (
    "such as", "e.g.", "if necessary", "if applicable", "may need to",
    "might need", "potentially", "as appropriate", "various", "and so on",
    "etc.",
)

#: R9 — rules every agent already loads from CLAUDE.md. Repeating them pads a
#: thin plan until it looks thorough.
CONSTITUTION_ECHOES = (
    "pytest -x",
    "type annotations on all",
    "type hints on all",
    "pydantic models for all",
    "use `logging`",
    "logging module instead of print",
    "instead of print statements",
    "update docs/changelog.md",
    "update the docs/changelog.md",
    "no secrets in source",
    "not hardcoded in the source",
    "all config via env",
    "configuration is done via environment variables",
)

#: R10 — the repository's former name.
STALE_PROJECT_NAME = "local-llm-server"

#: R8/R11 — marker exempting a path that the plan intends to create.
NEW_FILE_MARKER = "(new)"


@dataclass(frozen=True)
class Violation:
    """A single unmet rule, reportable to both an LLM and a human."""

    rule: str
    detail: str

    def __str__(self) -> str:
        return f"{self.rule}: {self.detail}"


# --------------------------------------------------------------------------
# Individual rule checks
# --------------------------------------------------------------------------

def _text_of(result: dict, *fields: str) -> str:
    """Concatenate the named string fields into one lowercase haystack."""
    return "\n".join(str(result.get(f, "") or "") for f in fields).lower()


def _check_grounding(result: dict, source_fetched: bool) -> list[Violation]:
    """R1 — the plan must be grounded in retrieved source content."""
    if source_fetched:
        return []
    return [
        Violation(
            "R1",
            "the linked source was not retrieved, so every claim about it is "
            "unverified; the document must be reviewed before implementation",
        )
    ]


def _check_source_summary(result: dict, title: str) -> list[Violation]:
    """R2 — state what the artifact actually is."""
    summary = str(result.get("source_summary", "") or "").strip()
    if len(summary) < MIN_SOURCE_SUMMARY_CHARS:
        return [
            Violation(
                "R2",
                f"source_summary is {len(summary)} chars; at least "
                f"{MIN_SOURCE_SUMMARY_CHARS} are needed to establish what the "
                "source is and what it does",
            )
        ]
    # Direction matters: the summary is already >=120 chars here, so asking
    # whether it fits inside the (short) title can never be true. The defect to
    # catch is the reverse — a model padding the issue title with filler until
    # it clears the length gate. An empty title would match everything, so it is
    # excluded rather than allowed to flag every result.
    normalised_summary = re.sub(r"\s+", " ", summary.lower())
    normalised_title = re.sub(r"\s+", " ", title.lower()).strip()
    if normalised_title and normalised_title in normalised_summary:
        return [Violation("R2", "source_summary merely echoes the issue title")]
    return []


def _check_verdict(result: dict) -> list[Violation]:
    """R3 — reach an explicit adopt/adapt/reject verdict, with a reason."""
    out: list[Violation] = []
    verdict = str(result.get("verdict", "") or "").strip().lower()
    if verdict not in VALID_VERDICTS:
        out.append(
            Violation(
                "R3",
                f"verdict must be one of {', '.join(VALID_VERDICTS)}; got "
                f"{verdict or '(missing)'!r}",
            )
        )
    if not str(result.get("verdict_reason", "") or "").strip():
        out.append(Violation("R3", "verdict_reason is empty"))
    return out


def _check_todos(result: dict) -> list[Violation]:
    """R4 and R5 — done-conditions, and no exploration dressed up as work."""
    out: list[Violation] = []
    todos = result.get("todos") or []
    if not todos:
        return [Violation("R4", "no TODOs were produced for a non-reject verdict")]

    for index, todo in enumerate(todos, start=1):
        task = str(todo.get("task", "") or "").strip()
        done_when = str(todo.get("done_when", "") or "").strip()
        file_ref = str(todo.get("file", "") or "").strip()
        label = f"TODO {index} ({task[:50] or 'untitled'})"

        if len(done_when) < MIN_DONE_WHEN_CHARS:
            out.append(
                Violation(
                    "R4",
                    f"{label} has no checkable done_when "
                    f"({len(done_when)} chars, need {MIN_DONE_WHEN_CHARS})",
                )
            )

        opener = _matched_filler_opener(task)
        if opener and (not file_ref or opener in done_when.lower()):
            out.append(
                Violation(
                    "R5",
                    f"{label} opens with {opener!r} and "
                    + (
                        "names no target file"
                        if not file_ref
                        else "its done_when just repeats the same verb"
                    ),
                )
            )
    return out


def _matched_filler_opener(task: str) -> str | None:
    """Return the filler verb a task opens with, if any."""
    lowered = task.strip().lower()
    for verb in FILLER_OPENERS:
        if lowered.startswith(verb):
            return verb
    return None


def _check_hedges(result: dict) -> list[Violation]:
    """R6 — no hedged guesses in the prompt or notes."""
    haystack = _text_of(result, "prompt", "notes")
    found = [hedge for hedge in BANNED_HEDGES if hedge in haystack]
    if not found:
        return []
    return [
        Violation(
            "R6",
            "hedged language instead of a checked claim: "
            + ", ".join(repr(f) for f in sorted(found)),
        )
    ]


def _check_risk_flags(result: dict) -> list[Violation]:
    """R7 — a module is risky only if a TODO actually modifies it."""
    touched = {
        str(t.get("file", "") or "").strip()
        for t in (result.get("todos") or [])
        if str(t.get("file", "") or "").strip()
    }
    unearned = [
        flag
        for flag in (result.get("risk_flags") or [])
        if str(flag).strip() and str(flag).strip() not in touched
    ]
    if not unearned:
        return []
    return [
        Violation(
            "R7",
            "risk flags for modules no TODO modifies: "
            + ", ".join(sorted(str(f) for f in unearned)),
        )
    ]


def _check_files_exist(result: dict, repo_root: Path) -> list[Violation]:
    """R8 and R11 — named files resolve, and at least one already exists."""
    out: list[Violation] = []
    entries = [str(f).strip() for f in (result.get("relevant_files") or []) if str(f).strip()]

    missing: list[str] = []
    existing: list[str] = []
    for entry in entries:
        if NEW_FILE_MARKER in entry.lower():
            continue
        if (repo_root / entry).exists():
            existing.append(entry)
        else:
            missing.append(entry)

    if missing:
        out.append(
            Violation(
                "R8",
                "relevant_files names paths that do not exist (mark intended new "
                "files with '(new)'): " + ", ".join(sorted(missing)),
            )
        )
    if not existing:
        out.append(
            Violation(
                "R11",
                "the plan names no existing module it hooks into",
            )
        )
    return out


def _check_constitution_echo(result: dict) -> list[Violation]:
    """R9 — do not re-teach rules every agent already loads from CLAUDE.md."""
    haystack = _text_of(result, "prompt")
    found = [phrase for phrase in CONSTITUTION_ECHOES if phrase in haystack]
    if not found:
        return []
    return [
        Violation(
            "R9",
            "prompt restates CLAUDE.md rules the implementing agent already has: "
            + ", ".join(repr(f) for f in sorted(found)),
        )
    ]


def _check_project_identity(result: dict) -> list[Violation]:
    """R10 — the project is autonomous-ai-agency."""
    haystack = _text_of(result, "prompt", "notes", "source_summary")
    if STALE_PROJECT_NAME not in haystack:
        return []
    return [
        Violation(
            "R10",
            f"uses the former project name {STALE_PROJECT_NAME!r}; "
            "this repository is 'autonomous-ai-agency'",
        )
    ]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

#: Rules that only apply when there is a plan to check. A `reject` verdict is a
#: complete, valid outcome with no TODOs, files, or risks to validate.
PLAN_ONLY_RULES = frozenset({"R4", "R5", "R7", "R8", "R11"})


def validate(result: dict, *, source_fetched: bool, repo_root: Path, title: str = "") -> list[Violation]:
    """Return every unmet rule for a generated context result.

    `source_fetched` reports whether the linked URL yielded real content.
    `repo_root` anchors the filesystem checks for R8/R11.
    """
    violations: list[Violation] = []
    violations += _check_grounding(result, source_fetched)
    violations += _check_source_summary(result, title)
    violations += _check_verdict(result)
    violations += _check_hedges(result)
    violations += _check_constitution_echo(result)
    violations += _check_project_identity(result)
    violations += _check_todos(result)
    violations += _check_risk_flags(result)
    violations += _check_files_exist(result, repo_root)

    # A `reject` verdict is a complete outcome with no plan to validate, so the
    # plan-only rules are dropped rather than skipped upstream — PLAN_ONLY_RULES
    # stays the single place that decides which rules those are.
    if str(result.get("verdict", "") or "").strip().lower() == "reject":
        return [v for v in violations if v.rule not in PLAN_ONLY_RULES]
    return violations


def repair_instruction(violations: list[Violation]) -> str:
    """Build the follow-up message asking the model to fix its own output."""
    listed = "\n".join(f"- {v}" for v in violations)
    return (
        "Your previous response violated the context rulebook. Fix every item "
        "below and return the corrected JSON object only — same schema, no "
        "commentary, no markdown fences.\n\n"
        f"{listed}\n\n"
        "If the source genuinely has nothing applicable to this repository, set "
        '"verdict": "reject" with a specific verdict_reason rather than inventing '
        "a plan to satisfy these rules."
    )


def format_violations(violations: list[Violation]) -> str:
    """Render the Quality Gate section appended to a shipped document."""
    # Plain paths, not markdown links: this text is rendered both as a file in
    # docs/context/ and as a PR body, and GitHub resolves relative links
    # differently in those two places, so any relative link breaks in one of them.
    if not violations:
        return (
            "## Quality Gate\n\n"
            "✅ Passed every machine-checked rule in "
            "`docs/QUICK_NOTE_CONTEXT_RULEBOOK.md`.\n"
        )
    lines = "\n".join(f"- **{v.rule}** — {v.detail}" for v in violations)
    return (
        "## Quality Gate\n\n"
        f"⚠️ **{len(violations)} unmet rule(s)** from "
        "`docs/QUICK_NOTE_CONTEXT_RULEBOOK.md`. "
        "This plan was shipped anyway so a reviewer can see exactly where it is thin — "
        "treat the items below as unresolved before implementing.\n\n"
        f"{lines}\n"
    )
