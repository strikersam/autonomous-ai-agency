"""tests/test_harness_sync.py — the harness spec survives throwaway task worktrees."""

from __future__ import annotations

from agent.harness_spec import SpecEntry, read_entries, write_entries
from runtimes.adapters.harness_sync import persist_spec, seed_spec


def _dirs(tmp_path):
    base, wt = tmp_path / "base", tmp_path / "wt"
    base.mkdir()
    wt.mkdir()
    return base, wt


def _sigs(root):
    return [e.signature for e in read_entries(root)]


def test_spec_refined_in_a_worktree_reaches_the_base_workspace(tmp_path):
    base, wt = _dirs(tmp_path)
    seeded = seed_spec(str(base), str(wt))
    write_entries([SpecEntry("abc", 2, "x")], wt)
    persist_spec(str(wt), str(base), seeded)
    assert _sigs(base) == ["abc"]


def test_next_worktree_is_seeded_from_the_base_spec(tmp_path):
    base, wt = _dirs(tmp_path)
    write_entries([SpecEntry("abc", 2, "x")], base)
    assert seed_spec(str(base), str(wt)) == frozenset({"abc"})
    assert _sigs(wt) == ["abc"]


def test_concurrent_worktrees_keep_each_others_promotions(tmp_path):
    base, wt1 = _dirs(tmp_path)
    wt2 = tmp_path / "wt2"
    wt2.mkdir()
    write_entries([SpecEntry("old", 2, "o")], base)
    s1, s2 = seed_spec(str(base), str(wt1)), seed_spec(str(base), str(wt2))
    write_entries([SpecEntry("old", 2, "o"), SpecEntry("a", 2, "a")], wt1)
    write_entries([SpecEntry("old", 2, "o"), SpecEntry("b", 2, "b")], wt2)
    persist_spec(str(wt1), str(base), s1)
    persist_spec(str(wt2), str(base), s2)
    assert sorted(_sigs(base)) == ["a", "b", "old"]


def test_retirement_in_a_worktree_is_applied_to_the_base(tmp_path):
    base, wt = _dirs(tmp_path)
    write_entries([SpecEntry("gone", 2, "g"), SpecEntry("keep", 2, "k")], base)
    seeded = seed_spec(str(base), str(wt))
    write_entries([SpecEntry("keep", 2, "k")], wt)
    persist_spec(str(wt), str(base), seeded)
    assert _sigs(base) == ["keep"]


def test_history_is_appended_once(tmp_path):
    base, wt = _dirs(tmp_path)
    hist = wt / ".agency" / "harness-history.jsonl"
    hist.parent.mkdir(parents=True, exist_ok=True)
    hist.write_text('{"added": ["a"]}\n')
    persist_spec(str(wt), str(base))
    persist_spec(str(wt), str(base))
    assert (base / ".agency" / "harness-history.jsonl").read_text() == '{"added": ["a"]}\n'


def test_oversized_and_symlinked_specs_are_refused(tmp_path):
    base, wt = _dirs(tmp_path)
    (wt / ".agency").mkdir()
    (wt / ".agency" / "harness.md").write_text("- [lesson:a hits=2] " + "x" * (70 * 1024) + "\n")
    persist_spec(str(wt), str(base))
    assert _sigs(base) == []
    target = tmp_path / "secret.txt"
    target.write_text("- [lesson:s hits=2] secret\n")
    (wt / ".agency" / "harness.md").unlink()
    (wt / ".agency" / "harness.md").symlink_to(target)
    persist_spec(str(wt), str(base))
    assert _sigs(base) == []


def test_same_directory_is_a_no_op(tmp_path):
    write_entries([SpecEntry("a", 2, "x")], tmp_path)
    assert seed_spec(str(tmp_path), str(tmp_path)) == frozenset()
    persist_spec(str(tmp_path), str(tmp_path))
    assert _sigs(tmp_path) == ["a"]
