"""tests/test_harness_sync.py — the harness spec survives throwaway task worktrees."""

from __future__ import annotations

from runtimes.adapters.harness_sync import persist_spec, seed_spec


def _write(root, text):
    path = root / ".agency" / "harness.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_spec_refined_in_a_worktree_reaches_the_base_workspace(tmp_path):
    base, wt = tmp_path / "base", tmp_path / "wt"
    base.mkdir(), wt.mkdir()
    _write(wt, "- [lesson:abc hits=2] x\n")
    assert persist_spec(str(wt), str(base)) is True
    assert (base / ".agency" / "harness.md").read_text() == "- [lesson:abc hits=2] x\n"


def test_next_worktree_is_seeded_from_the_base_spec(tmp_path):
    base, wt = tmp_path / "base", tmp_path / "wt"
    base.mkdir(), wt.mkdir()
    _write(base, "- [lesson:abc hits=2] x\n")
    assert seed_spec(str(base), str(wt)) is True
    assert (wt / ".agency" / "harness.md").is_file()


def test_unchanged_oversized_and_symlinked_specs_are_not_copied(tmp_path):
    base, wt = tmp_path / "base", tmp_path / "wt"
    base.mkdir(), wt.mkdir()
    assert persist_spec(str(wt), str(base)) is False  # nothing to copy
    _write(wt, "same")
    _write(base, "same")
    assert persist_spec(str(wt), str(base)) is False  # identical
    _write(wt, "x" * (70 * 1024))
    assert persist_spec(str(wt), str(base)) is False  # over the cap
    target = tmp_path / "secret.txt"
    target.write_text("secret")
    link = wt / ".agency" / "harness.md"
    link.unlink()
    link.symlink_to(target)
    assert persist_spec(str(wt), str(base)) is False  # symlink refused


def test_same_directory_is_a_no_op(tmp_path):
    _write(tmp_path, "x")
    assert seed_spec(str(tmp_path), str(tmp_path)) is False
    assert persist_spec(str(tmp_path), str(tmp_path)) is False
