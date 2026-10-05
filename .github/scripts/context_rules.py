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

import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

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

#: R13 — trees never counted as prior art. Generated plans and graph snapshots
#: quote URLs without implementing anything; tests quote them as fixtures. Hidden
#: directories (caches, session state) are skipped too, except ``.github``.
PRIOR_ART_EXCLUDED_DIRS = frozenset({
    ".git", "node_modules", "graphify-out", "build", "dist", "__pycache__",
})
PRIOR_ART_EXCLUDED_PREFIXES = ("docs/context/", "tests/", "frontend/build/")
PRIOR_ART_MAX_FILES = 10
PRIOR_ART_MAX_BYTES = 1_000_000

#: R14 — a repo-path-shaped token in prose: segments joined by "/" ending in a
#: source or config extension. Only checked when its first segment is a
#: top-level entry of this repo, so a path inside the *linked* project
#: (``references/hig/x.md``) is not mistaken for one of ours.
_PROSE_PATH = re.compile(
    r"(?<![\w./:-])((?:[\w.-]+/)+[\w.-]+\.(?:py|ya?ml|md|jsx?|tsx?|json|toml|sh))\b"
)
_URL = re.compile(r"https?://\S+")

#: Rules whose failure means a ``reject`` contradicts what is in the repo, so the
#: reject must go to a human instead of being filed (#1634 rejected a source the
#: repo already vendors, citing a file that does not exist).
CONTESTED_REJECT_RULES = frozenset({"R13", "R14"})


@dataclass(frozen=True)
class PriorArt:
    """A tracked file that already references the linked source."""

    path: str
    line: str


def source_slug(url: str) -> str:
    """Reduce a URL to the token a reference to it would contain.

    ``https://github.com/owner/repo/tree/main/x`` → ``owner/repo``; any other
    URL → host plus path, without scheme, ``www.`` or a trailing slash.
    """
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower().removeprefix("www.")
    parts = [p for p in parsed.path.split("/") if p]
    if host == "github.com" and len(parts) >= 2:
        return f"{parts[0]}/{parts[1].removesuffix('.git')}".lower()
    path = "/".join(parts)
    return f"{host}/{path}".rstrip("/").lower() if path else host


def find_prior_art(url: str | None, repo_root: Path) -> list[PriorArt]:
    """Return tracked files that already mention the linked source (R13).

    A quick note can re-submit something the repo already uses: #1634 linked
    the agency-agents repo that #1570 had already vendored, and the reviewer,
    never told, rejected it as "not compatible".
    """
    slug = source_slug(url) if url else ""
    if "/" not in slug:
        return []
    found: list[PriorArt] = []
    for dirpath, dirnames, filenames in os.walk(repo_root):
        dirnames[:] = sorted(
            d for d in dirnames
            if d not in PRIOR_ART_EXCLUDED_DIRS and (d == ".github" or not d.startswith("."))
        )
        for name in sorted(filenames):
            path = Path(dirpath) / name
            rel = path.relative_to(repo_root).as_posix()
            if rel.startswith(PRIOR_ART_EXCLUDED_PREFIXES):
                continue
            line = _first_mention(path, slug)
            if line is not None:
                found.append(PriorArt(rel, line))
                if len(found) >= PRIOR_ART_MAX_FILES:
                    return found
    return found


def _first_mention(path: Path, slug: str) -> str | None:
    """The first line of ``path`` containing ``slug``, or None."""
    try:
        if path.stat().st_size > PRIOR_ART_MAX_BYTES:
            return None
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    for line in text.splitlines():
        if slug in line.lower():
            return line.strip()[:160]
    return None


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


def _check_prior_art(result: dict, prior_art: list[PriorArt]) -> list[Violation]:
    """R13 — when the repo already references the source, say what it has."""
    if not prior_art:
        return []
    haystack = _text_of(result, "verdict_reason", "notes", "prompt")
    if any(item.path.lower() in haystack for item in prior_art):
        return []
    return [
        Violation(
            "R13",
            "the repository already references this source, and the plan names "
            "none of it: " + ", ".join(item.path for item in prior_art),
        )
    ]


def _check_prose_paths(result: dict, repo_root: Path) -> list[Violation]:
    """R14 — every repo path cited in prose exists, whatever the verdict."""
    missing: set[str] = set()
    for field in ("verdict_reason", "notes", "prompt"):
        text = _URL.sub(" ", str(result.get(field, "") or ""))
        for match in _PROSE_PATH.finditer(text):
            cited = match.group(1)
            if text[match.end():match.end() + 7].lower().lstrip().startswith(NEW_FILE_MARKER):
                continue
            top = cited.split("/", 1)[0]
            if (repo_root / top).is_dir() and not (repo_root / cited).exists():
                missing.add(cited)
    if not missing:
        return []
    return [
        Violation(
            "R14",
            "prose cites repository paths that do not exist: " + ", ".join(sorted(missing)),
        )
    ]


# --------------------------------------------------------------------------
# Public API
# --------------------------------------------------------------------------

#: Rules that only apply when there is a plan to check. A `reject` verdict is a
#: complete, valid outcome with no TODOs, files, or risks to validate.
PLAN_ONLY_RULES = frozenset({"R4", "R5", "R7", "R8", "R11"})


def validate(
    result: dict,
    *,
    source_fetched: bool,
    repo_root: Path,
    title: str = "",
    prior_art: list[PriorArt] | None = None,
) -> list[Violation]:
    """Return every unmet rule for a generated context result.

    `source_fetched` reports whether the linked URL yielded real content.
    `repo_root` anchors the filesystem checks for R8/R11/R14.
    `prior_art` is what `find_prior_art` found for the linked URL (R13).
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
    violations += _check_prior_art(result, prior_art or [])
    violations += _check_prose_paths(result, repo_root)

    # A `reject` verdict is a complete outcome with no plan to validate, so the
    # plan-only rules are dropped rather than skipped upstream — PLAN_ONLY_RULES
    # stays the single place that decides which rules those are.
    if str(result.get("verdict", "") or "").strip().lower() == "reject":
        return [v for v in violations if v.rule not in PLAN_ONLY_RULES]
    return violations


NEEDS_REVIEW_REASON = (
    "The model's verdict was `reject`, but the gate found it at odds with the "
    "repository ({rules}), so a human decides. #1634 was rejected as \"not "
    "compatible\" with a source the repo already vendors, citing a file that does "
    "not exist. The model's reason is kept below for reference only.\n\n"
    "> {reason}"
)


def apply_review_gate(result: dict, violations: list[Violation]) -> dict:
    """Route a reject that contradicts the repository to a human.

    A reject is filed and forgotten. When it ignores prior art (R13) or cites a
    path that does not exist (R14), filing it buries a note whose analysis is
    demonstrably wrong, so the verdict becomes ``needs-review``.
    """
    if str(result.get("verdict", "") or "").strip().lower() != "reject":
        return result
    rules = sorted({v.rule for v in violations} & CONTESTED_REJECT_RULES)
    if not rules:
        return result
    gated = dict(result)
    gated["verdict"] = "needs-review"
    reason = str(result.get("verdict_reason", "") or "").strip() or "(none given)"
    gated["verdict_reason"] = NEEDS_REVIEW_REASON.format(rules=", ".join(rules), reason=reason)
    return gated


def prior_art_section(prior_art: list[PriorArt]) -> str:
    """Tell the model what the repo already has from this source — R13."""
    if not prior_art:
        return ""
    rows = "\n".join(f"- `{item.path}`: {item.line}" for item in prior_art)
    return (
        "---\n## Prior art in this repository\n\n"
        "These tracked files already reference the linked source. This note may "
        "be a re-submission: say what it adds beyond them (R13).\n\n"
        f"{rows}\n\n"
    )


def prior_art_cell(paths: list[str]) -> str:
    """Render the prior-art row of the grounding table — rulebook R13."""
    if not paths:
        return "none found"
    return f"{len(paths)} file(s): " + ", ".join(f"`{p}`" for p in paths)


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
