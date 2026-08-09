"""tests/test_harness_spec.py — the Continual Harness spec.

Covers the property that separates this from prompt drift: nothing is written
that cannot be traced back to a specific recorded lesson, and nothing is written
at all unless the deployment opted in.
"""

from __future__ import annotations

import agent.harness_spec as spec_mod
from agent.harness_spec import (
    SpecEntry,
    build_block,
    propose_entries,
    read_entries,
    refine,
    spec_path,
    write_entries,
)


def _lesson(signature="abc123", hits=3, lesson="Executor produced no applicable file update.", phase="execute"):
    return {"signature": signature, "hits": hits, "lesson": lesson, "phase": phase}


class TestProposal:
    def test_repeated_lesson_is_promoted(self):
        proposals = propose_entries([_lesson(hits=2)], min_hits=2)
        assert len(proposals) == 1
        assert proposals[0].signature == "abc123"
        assert "During execute:" in proposals[0].text

    def test_one_off_failure_is_not_a_rule(self):
        assert propose_entries([_lesson(hits=1)], min_hits=2) == []

    def test_uncited_proposal_is_discarded(self):
        """The core guarantee: no citation, no entry."""
        assert propose_entries([_lesson(signature="")], min_hits=1) == []

    def test_empty_text_is_discarded(self):
        assert propose_entries([_lesson(lesson="   ")], min_hits=1) == []

    def test_malformed_lessons_do_not_raise(self):
        assert propose_entries([None, "nonsense", {}, _lesson()], min_hits=2)


class TestPersistence:
    def test_round_trip(self, tmp_path):
        entries = [SpecEntry("sig1", 4, "Do the thing"), SpecEntry("sig2", 2, "Avoid the trap")]
        write_entries(entries, tmp_path)
        assert [(e.signature, e.hits, e.text) for e in read_entries(tmp_path)] == [
            ("sig1", 4, "Do the thing"),
            ("sig2", 2, "Avoid the trap"),
        ]

    def test_file_lands_in_dot_agency(self, tmp_path):
        write_entries([SpecEntry("sig1", 2, "x")], tmp_path)
        assert spec_path(tmp_path) == tmp_path / ".agency" / "harness.md"
        assert spec_path(tmp_path).is_file()

    def test_hand_written_prose_is_preserved(self, tmp_path):
        write_entries([SpecEntry("sig1", 2, "generated")], tmp_path)
        path = spec_path(tmp_path)
        path.write_text("# Harness Spec\n\nHand note: always run pytest.\n\n"
                        "## Standing instructions\n\n- [lesson:sig1 hits=2] generated\n")
        write_entries([SpecEntry("sig1", 2, "generated"), SpecEntry("sig2", 3, "new")], tmp_path)
        text = path.read_text()
        assert "Hand note: always run pytest." in text
        assert text.count("## Standing instructions") == 1

    def test_missing_file_reads_as_empty(self, tmp_path):
        assert read_entries(tmp_path) == []

    def test_corrupt_file_reads_as_empty(self, tmp_path):
        path = spec_path(tmp_path)
        path.parent.mkdir(parents=True)
        path.write_text("not\nan\nentry\n")
        assert read_entries(tmp_path) == []


class TestRefineGate:
    def test_disabled_by_default(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HARNESS_SPEC_AUTO_REFINE", raising=False)
        assert refine(tmp_path, lessons=[_lesson()]) == []
        assert not spec_path(tmp_path).exists()

    def test_enabled_by_env(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HARNESS_SPEC_AUTO_REFINE", "true")
        added = refine(tmp_path, lessons=[_lesson()])
        assert len(added) == 1
        assert spec_path(tmp_path).is_file()

    def test_force_bypasses_the_flag(self, tmp_path, monkeypatch):
        monkeypatch.delenv("HARNESS_SPEC_AUTO_REFINE", raising=False)
        assert len(refine(tmp_path, lessons=[_lesson()], force=True)) == 1

    def test_same_lesson_is_not_written_twice(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HARNESS_SPEC_AUTO_REFINE", "true")
        assert len(refine(tmp_path, lessons=[_lesson()])) == 1
        assert refine(tmp_path, lessons=[_lesson()]) == []
        assert len(read_entries(tmp_path)) == 1

    def test_entry_count_is_capped(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HARNESS_SPEC_AUTO_REFINE", "true")
        monkeypatch.setenv("HARNESS_SPEC_MAX_ENTRIES", "3")
        refine(tmp_path, lessons=[_lesson(signature=f"sig{i}") for i in range(10)])
        assert len(read_entries(tmp_path)) == 3

    def test_never_raises_on_broken_store(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HARNESS_SPEC_AUTO_REFINE", "true")
        monkeypatch.setattr(spec_mod, "write_entries", lambda *a, **k: (_ for _ in ()).throw(OSError("disk full")))
        assert refine(tmp_path, lessons=[_lesson()]) == []


class TestPromptBlock:
    def test_absent_spec_injects_nothing(self, tmp_path):
        """Golden rule: a workspace that never opted in gets identical prompts."""
        assert build_block(tmp_path) == ""

    def test_block_lists_instructions(self, tmp_path):
        write_entries([SpecEntry("sig1", 5, "Always run pytest before committing")], tmp_path)
        block = build_block(tmp_path)
        assert "HARNESS SPEC" in block
        assert "Always run pytest before committing" in block

    def test_block_respects_char_budget(self, tmp_path):
        write_entries([SpecEntry(f"sig{i}", i, "x" * 200) for i in range(20)], tmp_path)
        assert len(build_block(tmp_path, max_chars=400)) <= 400 + 80

    def test_most_repeated_survives_truncation(self, tmp_path):
        write_entries(
            [SpecEntry("low", 1, "RARE-LESSON " + "x" * 300),
             SpecEntry("high", 99, "COMMON-LESSON")],
            tmp_path,
        )
        block = build_block(tmp_path, max_chars=200)
        assert "COMMON-LESSON" in block
        assert "RARE-LESSON" not in block

    def test_kill_switch(self, tmp_path, monkeypatch):
        write_entries([SpecEntry("sig1", 2, "something")], tmp_path)
        monkeypatch.setenv("HARNESS_SPEC_ENABLED", "false")
        assert build_block(tmp_path) == ""


class TestLessonStoreIntegration:
    def test_store_exposes_signature_for_citation(self, tmp_path, monkeypatch):
        """refine() cannot cite what the store does not return."""
        from agent.lessons import LessonStore

        store = LessonStore(db_path=tmp_path / "lessons.db")
        store.record(phase="execute", issue="Executor did not produce a file update")
        store.record(phase="execute", issue="Executor did not produce a file update")
        recent = store.recent()
        assert recent[0]["signature"]
        assert recent[0]["hits"] == 2
        added = refine(tmp_path, lessons=recent, force=True)
        assert added and added[0].signature == recent[0]["signature"]


class TestEnrichmentWiring:
    def test_spec_reaches_the_full_enrichment_block(self, tmp_path):
        from agent.harness_enrichment import HarnessEnrichment

        write_entries([SpecEntry("sig1", 3, "Always update the changelog")], tmp_path)
        enrichment = HarnessEnrichment(workspace_root=str(tmp_path))
        assert "Always update the changelog" in enrichment.build_spec_block()
        assert "Always update the changelog" in enrichment.build_full_enrichment()

    def test_no_spec_leaves_enrichment_unchanged(self, tmp_path):
        from agent.harness_enrichment import HarnessEnrichment

        enrichment = HarnessEnrichment(workspace_root=str(tmp_path))
        assert enrichment.build_spec_block() == ""
