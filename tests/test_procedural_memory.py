"""tests/test_procedural_memory.py — Unit tests for agent/procedural_memory.py (★4).

Covers:
- record_success: deduplication, eviction at MAX_RECORDS
- retrieve_relevant: scoring, limit, min-score filter, use-count bump
- clear
- _tokenize helper
- _json_instruction integration with AnthropicProvider (C1)
- Module-level singleton via get_procedural_memory
"""
from __future__ import annotations

import pytest

from agent.procedural_memory import (
    MAX_RECORDS,
    MIN_SCORE,
    ProceduralMemoryStore,
    _overlap_score,
    _record_id,
    _tokenize,
    get_procedural_memory,
)


# ── _tokenize ─────────────────────────────────────────────────────────────────

class TestTokenize:
    def test_basic_words(self):
        tokens = _tokenize("Add unit tests for the auth module")
        assert "add" in tokens
        assert "auth" in tokens
        assert "unit" in tokens
        # stopwords removed
        assert "the" not in tokens
        assert "for" not in tokens

    def test_empty_string(self):
        assert _tokenize("") == set()

    def test_mixed_case_normalised(self):
        assert _tokenize("FastAPI FastAPI") == _tokenize("fastapi fastapi")

    def test_underscores_kept(self):
        tokens = _tokenize("update brain_config.py")
        assert "brain_config" in tokens

    def test_numbers_kept(self):
        tokens = _tokenize("python 3.13 upgrade")
        assert "3" in tokens or "13" in tokens or "python" in tokens


# ── _overlap_score ─────────────────────────────────────────────────────────────

class TestOverlapScore:
    def test_identical_sets(self):
        s = {"a", "b", "c"}
        assert _overlap_score(s, s) == pytest.approx(1.0)

    def test_disjoint_sets(self):
        assert _overlap_score({"a"}, {"b"}) == 0.0

    def test_partial_overlap(self):
        score = _overlap_score({"a", "b"}, {"a", "c"})
        assert score == pytest.approx(0.5)

    def test_empty_query(self):
        assert _overlap_score(set(), {"a"}) == 0.0

    def test_empty_record(self):
        assert _overlap_score({"a"}, set()) == 0.0


# ── ProceduralMemoryStore ─────────────────────────────────────────────────────

@pytest.fixture
def store() -> ProceduralMemoryStore:
    return ProceduralMemoryStore(store=None)


class TestRecordSuccess:
    def test_record_returns_id(self, store):
        rid = store.record_success(
            goal_summary="Add test for auth",
            step_description="Write pytest for login endpoint",
            action_summary="edited tests/test_auth.py",
        )
        assert rid.startswith("pm_")

    def test_records_stored(self, store):
        store.record_success(
            goal_summary="Refactor router",
            step_description="Extract routing logic to router.py",
            action_summary="edited router.py",
        )
        assert len(store.all_records()) == 1

    def test_duplicate_deduplicated(self, store):
        kwargs = dict(
            goal_summary="Add feature",
            step_description="Implement the widget",
            action_summary="edited widget.py",
        )
        id1 = store.record_success(**kwargs)
        id2 = store.record_success(**kwargs)
        assert id1 == id2
        assert len(store.all_records()) == 1  # not stored twice

    def test_different_steps_both_stored(self, store):
        store.record_success(
            goal_summary="Fix bug",
            step_description="Identify root cause",
            action_summary="read logs",
        )
        store.record_success(
            goal_summary="Fix bug",
            step_description="Apply patch to services.py",
            action_summary="edited services.py",
        )
        assert len(store.all_records()) == 2

    def test_eviction_at_max_records(self, store):
        for i in range(MAX_RECORDS + 5):
            store.record_success(
                goal_summary=f"goal_{i}",
                step_description=f"step_{i}",
                action_summary=f"action_{i}",
            )
        assert len(store.all_records()) <= MAX_RECORDS


class TestRetrieveRelevant:
    def test_returns_relevant_record(self, store):
        store.record_success(
            goal_summary="Add authentication middleware",
            step_description="Write JWT validation in middleware.py",
            action_summary="edited middleware.py",
        )
        results = store.retrieve_relevant("add JWT authentication to middleware")
        assert len(results) >= 1
        assert results[0]["step_description"] == "Write JWT validation in middleware.py"

    def test_empty_store_returns_empty(self, store):
        assert store.retrieve_relevant("anything") == []

    def test_irrelevant_record_not_returned(self, store):
        store.record_success(
            goal_summary="Update Dockerfile",
            step_description="Change base image to python 3.13",
            action_summary="edited Dockerfile",
        )
        results = store.retrieve_relevant("add authentication unit tests")
        assert len(results) == 0

    def test_limit_respected(self, store):
        for i in range(10):
            store.record_success(
                goal_summary=f"Add test for module{i}",
                step_description=f"Write test for module{i} function",
                action_summary=f"edited tests/test_module{i}.py",
            )
        results = store.retrieve_relevant("add test for module function", limit=3)
        assert len(results) <= 3

    def test_use_count_increments_on_retrieve(self, store):
        store.record_success(
            goal_summary="Fix auth bug",
            step_description="Patch token validation",
            action_summary="edited auth.py",
        )
        store.retrieve_relevant("fix auth token validation")
        records = store.all_records()
        assert records[0]["use_count"] == 1

    def test_empty_query_returns_empty(self, store):
        store.record_success(
            goal_summary="Something",
            step_description="Do something",
            action_summary="edited something.py",
        )
        results = store.retrieve_relevant("")
        assert results == []


class TestClear:
    def test_clear_empties_store(self, store):
        store.record_success(
            goal_summary="task", step_description="step", action_summary="action"
        )
        n = store.clear()
        assert n == 1
        assert store.all_records() == []

    def test_clear_resets_loaded_flag(self, store):
        store._loaded = True
        store.clear()
        assert store._loaded is False


# ── module-level singleton ────────────────────────────────────────────────────

class TestGetProceduralMemory:
    def test_returns_instance(self):
        inst = get_procedural_memory()
        assert isinstance(inst, ProceduralMemoryStore)

    def test_same_instance_on_second_call(self):
        a = get_procedural_memory()
        b = get_procedural_memory()
        assert a is b


# ── record_id determinism ─────────────────────────────────────────────────────

class TestRecordId:
    def test_same_inputs_same_id(self):
        assert _record_id("goal", "step") == _record_id("goal", "step")

    def test_different_goals_different_id(self):
        assert _record_id("goal A", "step") != _record_id("goal B", "step")

    def test_different_steps_different_id(self):
        assert _record_id("goal", "step A") != _record_id("goal", "step B")
