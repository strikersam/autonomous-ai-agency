"""A sandbox is seeded even when the workspace is not a git repository.

Production agents saw an empty workspace (``list_files`` and ``search_code``
returned ``[]``): seeding relied on ``git ls-files``, the deployed app directory
is not a git repo, and the caller carried on with an empty sandbox.
"""
from __future__ import annotations

import io
import os
import subprocess
import tarfile
from pathlib import Path

from services import sandbox_seed as seed


def _names(tar_bytes: bytes) -> set[str]:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        return set(tar.getnames())


def _workspace(tmp_path: Path) -> Path:
    ws = tmp_path / "ws"
    (ws / "pkg").mkdir(parents=True)
    (ws / "pkg" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    (ws / "README.md").write_text("hi\n", encoding="utf-8")
    (ws / "node_modules" / "dep").mkdir(parents=True)
    (ws / "node_modules" / "dep" / "index.js").write_text("//\n", encoding="utf-8")
    (ws / "__pycache__").mkdir()
    (ws / "__pycache__" / "mod.pyc").write_bytes(b"\x00")
    return ws


def test_a_non_git_workspace_is_still_seeded(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    tar_bytes, count = seed.pack_seed(str(ws))
    names = _names(tar_bytes)
    assert {"pkg/mod.py", "README.md"} <= names
    assert count == len(names)
    assert not any(n.startswith(("node_modules", "__pycache__")) for n in names)


def test_a_git_workspace_seeds_tracked_files_only(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True, env=env)
    subprocess.run(["git", "add", "README.md"], cwd=ws, check=True, env=env)
    tar_bytes, count = seed.pack_seed(str(ws))
    assert _names(tar_bytes) == {"README.md"} and count == 1


def test_an_empty_workspace_yields_no_seed(tmp_path: Path) -> None:
    ws = tmp_path / "empty"
    ws.mkdir()
    assert seed.pack_seed(str(ws)) == (b"", 0)


def test_links_are_packed_as_links_and_outside_content_is_not_read(tmp_path: Path) -> None:
    outside = tmp_path / "secret.txt"
    outside.write_text("OUTSIDE", encoding="utf-8")
    ws = _workspace(tmp_path)
    os.symlink(str(outside), str(ws / "leak.txt"))
    os.symlink(str(ws / "missing"), str(ws / "dangling.txt"))
    tar_bytes, _ = seed.pack_seed(str(ws))
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r:gz") as tar:
        leak = tar.getmember("leak.txt")
        assert leak.issym(), "a link must be stored as a link, not as its target's content"
        assert tar.getmember("dangling.txt").issym()
    assert b"OUTSIDE" not in tar_bytes


def test_oversized_files_are_skipped(tmp_path: Path, monkeypatch) -> None:
    ws = _workspace(tmp_path)
    (ws / "big.bin").write_bytes(b"0" * 2048)
    monkeypatch.setattr(seed, "_MAX_FILE_BYTES", 1024)
    assert "big.bin" not in _names(seed.pack_seed(str(ws))[0])


def test_the_walk_is_bounded(tmp_path: Path, monkeypatch) -> None:
    ws = tmp_path / "many"
    ws.mkdir()
    for i in range(12):
        (ws / f"f{i:02d}.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(seed, "_MAX_FILES", 5)
    assert len(seed.list_seed_files(str(ws))) == 5


async def test_seed_from_worktree_packs_off_the_event_loop(tmp_path: Path, monkeypatch) -> None:
    import asyncio
    import threading

    from services.e2b_sandbox import E2BSandboxSession

    ws = _workspace(tmp_path)
    loop_thread = threading.get_ident()
    seen: dict[str, object] = {}

    def fake_pack(path: str) -> tuple[bytes, int]:
        seen["thread"] = threading.get_ident()
        return b"", 0

    monkeypatch.setattr(seed, "pack_seed", fake_pack)
    session = E2BSandboxSession.__new__(E2BSandboxSession)
    monkeypatch.setattr(E2BSandboxSession, "is_open", property(lambda self: True))
    assert await session.seed_from_worktree(str(ws)) is False
    assert seen["thread"] != loop_thread, "packing must not run on the event loop thread"
    await asyncio.sleep(0)
