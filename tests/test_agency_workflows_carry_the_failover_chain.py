"""Every workflow that runs an agent script must carry the whole brain chain.

`CLAUDE.md` §4 documents the failover chain as Cerebras → Groq → NVIDIA NIM →
Ollama, and `autonomous-agent.yml` / `autonomous-fix.yml` have always passed all
three cloud keys. Three later workflows — including `process-quick-note.yml`,
the one that actually implements issues — passed `NVIDIA_API_KEY` alone. The
agency running in GitHub Actions therefore had no first or second link at all,
and nothing said so: a chain with two missing links looks exactly like a healthy
one until the third link dies.

Which it did. On 2026-08-28 every model NVIDIA served for this key except one
answered 410 or 404, so the agency's only remaining brain was a single model on
its only remaining provider.

This test is deliberately not a list of workflow names — a new workflow added
tomorrow is caught by the same rule, because the rule is derived from what the
workflow *does*, not from an inventory somebody has to remember to update.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = REPO_ROOT / ".github/workflows"

# Scripts that drive an LLM through the provider chain.
AGENT_SCRIPTS = (
    "implement_agent",
    "review_agent",
    "apply_review",
    "autonomous_agent",
    "autonomous_fix",
    "generate_context",
)

# The free-cloud chain, in the order CLAUDE.md documents it. Anthropic is
# deliberately absent: it is paid, and the routing work excludes it on purpose.
FREE_CHAIN = ("CEREBRAS_API_KEY", "GROQ_API_KEY", "NVIDIA_API_KEY")


def _agency_workflows() -> list[Path]:
    found = []
    for path in sorted(WORKFLOWS.glob("*.yml")):
        text = path.read_text(encoding="utf-8")
        if any(f"scripts/{name}" in text for name in AGENT_SCRIPTS):
            found.append(path)
    return found


def test_the_scan_finds_agency_workflows() -> None:
    """A selector that matched nothing would make every assertion vacuous."""
    found = _agency_workflows()
    assert len(found) >= 3, f"expected several agency workflows, found {found}"


@pytest.mark.parametrize("workflow", _agency_workflows(), ids=lambda p: p.name)
def test_agency_workflow_passes_the_whole_free_chain(workflow: Path) -> None:
    text = workflow.read_text(encoding="utf-8")
    missing = [key for key in FREE_CHAIN if f"{key}: " not in text]
    assert not missing, (
        f"{workflow.name} runs an agent script but does not pass {missing}. "
        f"A missing link is invisible until the ones below it die."
    )


@pytest.mark.parametrize("workflow", _agency_workflows(), ids=lambda p: p.name)
def test_keys_are_read_from_secrets_not_inlined(workflow: Path) -> None:
    """Rule 6: secrets are environment-only, never written into a file."""
    text = workflow.read_text(encoding="utf-8")
    for key in FREE_CHAIN:
        for match in re.finditer(rf"{key}:\s*(\S+)", text):
            value = match.group(1)
            assert value.startswith("${{"), (
                f"{workflow.name} sets {key} to a literal; it must come from secrets"
            )


class TestRenderDeclaresTheChain:
    """`render.yaml` is the infrastructure declaration for the backend.

    A key that exists only in the dashboard is a key that disappears the first
    time the service is recreated from this file — and its absence would look
    identical to a provider that was never wanted.
    """

    def _render(self) -> str:
        return (REPO_ROOT / "render.yaml").read_text(encoding="utf-8")

    @pytest.mark.parametrize("key", FREE_CHAIN)
    def test_render_declares_each_free_provider_key(self, key: str) -> None:
        assert f"- key: {key}" in self._render(), (
            f"render.yaml does not declare {key}; a dashboard-only key is "
            f"invisible to this repo and lost on a rebuild"
        )

    def test_provider_keys_are_never_given_a_literal_value(self) -> None:
        """Rule 6 again, on the deploy side: `sync: false`, never `value:`."""
        lines = self._render().splitlines()
        for i, line in enumerate(lines):
            for key in FREE_CHAIN:
                if line.strip() == f"- key: {key}":
                    following = lines[i + 1].strip()
                    assert following == "sync: false", (
                        f"{key} must be `sync: false` in render.yaml, got {following!r}"
                    )
