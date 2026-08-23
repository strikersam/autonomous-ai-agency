"""packages/governance/authoring.py — validate and propose policy edits.

In-product policy authoring, done the safe way. The governance API deliberately
has no endpoint that rewrites ``config/agent_policy.yaml`` in place (see
``backend/governance_router.py``): a live-editable policy would make the audit
trail's "who changed the rules" question unanswerable and would let anyone who
compromised an admin session silently disable the controls.

This module keeps that invariant while still giving operators an in-product
authoring experience. A proposed policy is:

1. **Validated** — parsed, compiled through the real :class:`PolicyEngine`, and
   checked against the org baseline, so bad YAML or a loosened guardrail is
   rejected before anything leaves the process.
2. **Proposed as a pull request** — the change lands on a new branch and opens a
   PR against the policy file. It reaches production the same way every other
   change does: review, CI, merge. The live file is never written from HTTP.

The one hard rule the UI cannot bend: the organization baseline
(``baseline.*.deny`` and ``baseline.*.require_approval``) can only be *tightened*
from here, never loosened. Removing a baseline guardrail is exactly the "silently
disable the controls" move this design exists to prevent, so a proposal that
drops one is refused rather than sent for review.
"""
from __future__ import annotations

import difflib
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Protocol

from packages.governance.policy import PolicyEngine, Surface

log = logging.getLogger("governance.authoring")

# Baseline effects that a dashboard proposal may add to but never remove. These
# are the "organization-wide guardrails that can't be overridden" — a group can
# tighten on top, and this module lets an operator tighten the baseline itself,
# but neither may loosen it.
_LOCKED_EFFECTS = ("deny", "require_approval")

POLICY_PATH = "config/agent_policy.yaml"


@dataclass
class ValidationResult:
    """Outcome of validating a proposed policy document."""

    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {"ok": self.ok, "errors": self.errors, "warnings": self.warnings}


class _GitHub(Protocol):
    """The subset of ``agent.github_tools.GitHubTools`` this module calls.

    Declared as a Protocol so the propose path can be tested with a fake that
    never touches the network.
    """

    async def create_branch(self, owner: str, repo: str, branch_name: str, base_branch: str = ...) -> dict[str, Any]: ...
    async def commit_file(self, owner: str, repo: str, path: str, content: str, message: str, branch: str = ...) -> dict[str, Any]: ...
    async def open_pull_request(self, owner: str, repo: str, title: str, head: str, base: str = ..., body: str = ...) -> dict[str, Any]: ...


def parse_policy_text(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """Parse YAML policy text into a mapping. Returns ``(document, error)``."""
    import yaml  # imported lazily: policy is optional configuration

    try:
        document = yaml.safe_load(text)
    except yaml.YAMLError as exc:  # malformed YAML — the operator's typo
        return None, f"invalid YAML: {exc}"
    if document is None:
        return None, "policy document is empty"
    if not isinstance(document, dict):
        return None, f"policy root must be a mapping, got {type(document).__name__}"
    return document, None


def _baseline_patterns(document: dict[str, Any]) -> dict[str, set[str]]:
    """Extract locked baseline patterns as ``{"<surface>:<effect>": {patterns}}``."""
    out: dict[str, set[str]] = {}
    baseline = document.get("baseline") or {}
    if not isinstance(baseline, dict):
        return out
    for surface in Surface:
        section = baseline.get(surface.value)
        if not isinstance(section, dict):
            continue
        for effect in _LOCKED_EFFECTS:
            values = section.get(effect)
            if isinstance(values, list):
                out[f"{surface.value}:{effect}"] = {str(v) for v in values}
    return out


def _baseline_loosened(current: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    """Return baseline guardrails present in *current* but missing from *proposed*."""
    cur = _baseline_patterns(current)
    new = _baseline_patterns(proposed)
    removed: list[str] = []
    for key, patterns in cur.items():
        missing = patterns - new.get(key, set())
        for pattern in sorted(missing):
            surface, effect = key.split(":", 1)
            removed.append(f"baseline.{surface}.{effect} drops {pattern!r}")
    return removed


def validate_policy_text(text: str, *, current_document: dict[str, Any] | None = None) -> ValidationResult:
    """Validate proposed policy text without applying it.

    Rejects malformed YAML, a non-mapping root, a document the engine cannot
    compile, and — the load-bearing check — any proposal that loosens the org
    baseline relative to *current_document*. Mode changes and group edits are
    allowed; a mode flip is surfaced as a warning so review sees it.
    """
    errors: list[str] = []
    warnings: list[str] = []

    document, parse_error = parse_policy_text(text)
    if parse_error or document is None:
        return ValidationResult(ok=False, errors=[parse_error or "unparseable policy"])

    raw_mode = str(document.get("mode", "observe")).strip().lower()
    if raw_mode not in ("observe", "enforce"):
        warnings.append(f"unknown mode {raw_mode!r}; the engine will treat it as observe")

    # Compile through the real engine: this is the same code the enforcer runs,
    # so anything it cannot turn into a usable policy is caught here rather than
    # at load time in production.
    try:
        PolicyEngine(document)
    except Exception as exc:  # noqa: BLE001 - report, never leak a traceback to the caller
        errors.append(f"policy does not compile: {exc}")

    if current_document is not None:
        loosened = _baseline_loosened(current_document, document)
        if loosened:
            errors.append(
                "the organization baseline can only be tightened from the dashboard, "
                "never loosened — remove these changes or make them in git: "
                + "; ".join(loosened)
            )
        if raw_mode != str(current_document.get("mode", "observe")).strip().lower():
            warnings.append(
                f"mode change: {current_document.get('mode', 'observe')} -> {raw_mode}"
            )

    return ValidationResult(ok=not errors, errors=errors, warnings=warnings)


def diff_policy(current_text: str, proposed_text: str) -> str:
    """Return a unified diff from *current_text* to *proposed_text*."""
    diff = difflib.unified_diff(
        current_text.splitlines(),
        proposed_text.splitlines(),
        fromfile="config/agent_policy.yaml (current)",
        tofile="config/agent_policy.yaml (proposed)",
        lineterm="",
    )
    return "\n".join(diff)


def _proposal_branch_name() -> str:
    return f"governance/policy-proposal-{int(time.time())}"


async def propose_policy_change(
    proposed_text: str,
    *,
    actor: str,
    reason: str,
    gh: _GitHub,
    repo: str,
    current_text: str,
    base: str = "master",
    path: str = POLICY_PATH,
) -> dict[str, Any]:
    """Validate a proposed policy and open a PR that carries it.

    Never writes the live policy file. On success the change exists only on a
    new branch and in an open pull request; a human merges it like any other
    change. Raises :class:`ValueError` if validation fails (the caller maps that
    to a 400) — no branch or PR is created for an invalid proposal.
    """
    current_document, _ = parse_policy_text(current_text)
    result = validate_policy_text(proposed_text, current_document=current_document)
    if not result.ok:
        raise ValueError("; ".join(result.errors))

    if "/" not in repo:
        raise ValueError(f"repo must be 'owner/name', got {repo!r}")
    owner, name = repo.split("/", 1)
    branch = _proposal_branch_name()

    await gh.create_branch(owner, name, branch, base_branch=base)
    commit_message = f"chore(governance): propose policy update ({actor})\n\n{reason}".strip()
    await gh.commit_file(owner, name, path, proposed_text, commit_message, branch=branch)

    title = f"chore(governance): policy update proposed by {actor}"
    body = _pr_body(actor=actor, reason=reason, result=result, diff=diff_policy(current_text, proposed_text))
    pr = await gh.open_pull_request(owner, name, title, head=branch, base=base, body=body)
    pr_url = str(pr.get("html_url") or pr.get("url") or "")

    _audit_proposal(actor=actor, reason=reason, repo=repo, branch=branch, pr_url=pr_url)
    log.info("Governance policy change proposed by %s: %s", actor, pr_url or branch)
    return {
        "proposed": True,
        "pr_url": pr_url,
        "pr_number": pr.get("number"),
        "branch": branch,
        "validation": result.to_dict(),
    }


def _pr_body(*, actor: str, reason: str, result: ValidationResult, diff: str) -> str:
    warn = ("\n\n**Validation warnings:**\n" + "\n".join(f"- {w}" for w in result.warnings)) if result.warnings else ""
    diff_block = f"\n\n<details><summary>Diff</summary>\n\n```diff\n{diff}\n```\n</details>" if diff else ""
    return (
        f"Proposed from the governance dashboard by **{actor}**.\n\n"
        f"**Reason:** {reason or '(none given)'}\n\n"
        "Validated against the live policy engine and the org baseline before this PR "
        "was opened; the baseline was not loosened. Review, let CI run, and merge to "
        "apply — the live policy file is never written from the dashboard."
        f"{warn}{diff_block}"
    )


def _audit_proposal(*, actor: str, reason: str, repo: str, branch: str, pr_url: str) -> None:
    """Record the proposal in the governance audit trail.

    This is what keeps "who changed the rules" answerable: every dashboard
    proposal is attributed to an operator here, and the change itself still goes
    through PR review before it can take effect.
    """
    try:
        from packages.governance.audit import record_event

        record_event(
            agent_id=f"operator:{actor}",
            display_name=actor,
            owner=actor,
            surface="tool",
            action="governance.policy.propose",
            decision="allow",
            effective="allow",
            result_status="proposed",
            reason=(f"opened {pr_url}" if pr_url else "opened policy proposal PR") + (f" — {reason}" if reason else ""),
            repo=repo,
            branch=branch,
        )
    except Exception as exc:  # noqa: BLE001 - auditing must never break the proposal
        log.warning("Failed to audit policy proposal by %s: %s", actor, exc)
