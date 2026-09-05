"""The three autonomous agent scripts must share one NVIDIA model list.

``.github/scripts/nvidia_models.py`` opens by calling itself the "single source
of truth for all autonomous agent scripts". It was not: nothing imported it.
``implement_agent.py``, ``review_agent.py`` and ``apply_review.py`` each carried
their own divergent copy — six, five and four ids, overlapping but not equal,
one of them listing the same model twice.

That is how the 2026-08-27 outage stayed invisible after being fixed once. Every
id in all three copies was dead by then (four ``410 Gone``, two of them retired
the previous morning), so fixing one script left the other two pointed at
models NVIDIA had already retired, and there was no single place to correct.

These tests do not assert any model is *live* — that cannot be known from here
without a provider key. They assert there is exactly one list to fix.
"""
from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = REPO_ROOT / ".github" / "scripts"

# Every id observed returning 410/404 in the 2026-08-27 implementer logs.
RETIRED_MODEL_IDS = [
    "qwen/qwen3-coder-480b-a35b-instruct",
    "nvidia/llama-3.1-nemotron-ultra-253b-v1",
    "qwen/qwen2.5-coder-32b-instruct",
]

CONSUMERS = [
    "review_agent.py", "apply_review.py", "implement_agent.py",
    # generate_context.py used to carry its own NVIDIA list (all ids dead by
    # 2026-09), which is exactly why quick-note context generation produced
    # nothing on open issues. It now uses the shared module like the others.
    "generate_context.py",
]


def _source(name: str) -> str:
    return (SCRIPTS / name).read_text(encoding="utf-8")


def _assigned_names(source: str) -> set[str]:
    """Top-level names this module assigns, so an *import* is not miscounted."""
    tree = ast.parse(source)
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    names.add(target.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


class TestOneListToFix:
    @pytest.mark.parametrize("script", CONSUMERS)
    def test_script_does_not_define_its_own_list(self, script: str) -> None:
        assigned = _assigned_names(_source(script))
        assert "NVIDIA_CANDIDATE_MODELS" not in assigned, (
            f"{script} defines its own model list; three divergent copies is "
            "what made the outage survive its first fix"
        )
        assert "NVIDIA_MODEL_IDS" not in assigned

    @pytest.mark.parametrize(
        "script", ["review_agent.py", "apply_review.py", "generate_context.py"]
    )
    def test_script_imports_the_shared_list(self, script: str) -> None:
        assert "nvidia_models" in _source(script)

    @pytest.mark.parametrize("script", CONSUMERS)
    @pytest.mark.parametrize("model_id", RETIRED_MODEL_IDS)
    def test_no_retired_id_is_hardcoded(self, script: str, model_id: str) -> None:
        assert model_id not in _source(script), (
            f"{model_id} returned 410/404 on 2026-08-27; it must not be pinned "
            f"in {script}"
        )


@pytest.fixture(scope="module")
def models():
    sys.path.insert(0, str(SCRIPTS))
    import nvidia_models

    yield nvidia_models
    if str(SCRIPTS) in sys.path:
        sys.path.remove(str(SCRIPTS))


class TestTheSharedListFitsBothCallers:
    """The two consumers iterate different shapes; both must keep working."""

    def test_ids_are_plain_strings_for_review_agent(self, models) -> None:
        """`review_agent.py` does `for model in ...` and passes it as `model=`."""
        assert models.NVIDIA_MODEL_IDS
        assert all(isinstance(m, str) for m in models.NVIDIA_MODEL_IDS)

    def test_pairs_are_two_tuples_for_apply_review(self, models) -> None:
        """`apply_review.py` does `for model, desc in ...`."""
        assert models.NVIDIA_CANDIDATE_MODELS
        for entry in models.NVIDIA_CANDIDATE_MODELS:
            assert isinstance(entry, tuple) and len(entry) == 2

    def test_the_two_shapes_agree(self, models) -> None:
        assert models.NVIDIA_MODEL_IDS == [
            model_id for model_id, _label in models.NVIDIA_CANDIDATE_MODELS
        ]

    def test_the_static_floor_is_only_a_floor(self, models) -> None:
        """Breadth now comes from discovery, not from this list.

        The old list held three ids and two were dead; padding it with more
        unverified ids would only have made the turn-1 exhaustion slower. The
        floor is deliberately short, and `resolve_model_ids()` is what supplies
        real breadth by asking the provider.
        """
        assert models.NVIDIA_MODEL_IDS, "a floor of nothing is not a floor"
        assert callable(models.resolve_model_ids)

    def test_no_duplicate_candidates(self, models) -> None:
        """apply_review.py listed the same model twice, wasting a retry."""
        ids = models.NVIDIA_MODEL_IDS
        assert len(ids) == len(set(ids))


class TestTheNamesActuallyResolve:
    """Source-text assertions cannot catch a NameError.

    Every test above reads the scripts as text. Swapping ``review_agent.py`` to
    import ``NVIDIA_MODEL_IDS`` while line 95 still said
    ``NVIDIA_CANDIDATE_MODELS`` passed all of them and would have raised
    ``NameError`` on every council review. Importing the module is the only
    check that would have caught it, so it is the check that lives here.
    """

    @pytest.mark.parametrize("module_name", ["review_agent", "apply_review"])
    def test_module_imports_cleanly(self, module_name: str) -> None:
        """Runs only where `openai` is installed.

        It is not in requirements.txt — `process-quick-note.yml` pip-installs it
        at run time — so this skips in CI rather than failing. The AST check
        below is the guard that runs everywhere; this one is the stronger
        version of it for anyone who has the runtime deps.
        """
        pytest.importorskip("openai")
        import importlib

        sys.path.insert(0, str(SCRIPTS))
        sys.modules.pop(module_name, None)
        try:
            importlib.import_module(module_name)
        finally:
            if str(SCRIPTS) in sys.path:
                sys.path.remove(str(SCRIPTS))

    @pytest.mark.parametrize(
        "script,expected",
        [("review_agent.py", "resolve_model_ids"),
         ("apply_review.py", "resolve_candidates")],
    )
    def test_every_nvidia_name_used_is_bound(self, script: str, expected: str) -> None:
        """Catches a rename that updates the import but misses a use site."""
        tree = ast.parse(_source(script))
        bound = _assigned_names(_source(script))
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                for alias in node.names:
                    bound.add(alias.asname or alias.name)
        used = {
            n.id for n in ast.walk(tree)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)
            and ("CANDIDATE_MODELS" in n.id or "MODEL_IDS" in n.id
                 or n.id.startswith("resolve_"))
        }
        assert used == {expected}, (
            f"{script} reads {used or 'nothing'}; it should read {expected}"
        )
        assert used <= bound, (
            f"{script} reads {used - bound}, which nothing binds — a rename that "
            "updated the import but missed a use site raises NameError at run time"
        )
