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


_SENSITIVE = (
    ".env", ".env.production", "prod.env", "server.pem", "tls.key", "id_rsa", "credentials.json",
    ".data/agency.db", ".data/providers.json", "chat_history.db", "state.sqlite3", ".instance_id",
)


def _sensitive_workspace(tmp_path: Path) -> Path:
    ws = _workspace(tmp_path)
    for rel in _SENSITIVE:
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("SECRET", encoding="utf-8")
    return ws


def test_a_walk_never_packs_secrets_or_runtime_state(tmp_path: Path) -> None:
    """A sandbox is a third-party service: these files must not leave the host."""
    ws = _sensitive_workspace(tmp_path)
    tar_bytes, _ = seed.pack_seed(str(ws))
    names = _names(tar_bytes)
    assert {"pkg/mod.py", "README.md"} <= names
    leaked = sorted(n for n in names if n in _SENSITIVE or n.startswith(".data"))
    assert leaked == [], f"sensitive files packed for the sandbox: {leaked}"
    assert b"SECRET" not in tar_bytes


def test_tracked_secrets_are_dropped_too(tmp_path: Path) -> None:
    ws = _sensitive_workspace(tmp_path)
    env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
           "GIT_COMMITTER_EMAIL": "t@t"}
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True, env=env)
    subprocess.run(["git", "add", "-A", "-f"], cwd=ws, check=True, env=env)
    names = _names(seed.pack_seed(str(ws))[0])
    assert "README.md" in names
    assert not [n for n in names if n in _SENSITIVE or n.startswith(".data")]


def test_a_git_repo_with_nothing_tracked_seeds_nothing(tmp_path: Path) -> None:
    ws = _sensitive_workspace(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    assert seed.pack_seed(str(ws)) == (b"", 0)


def test_odd_filenames_survive_git_listing(tmp_path: Path) -> None:
    ws = tmp_path / "odd"
    ws.mkdir()
    (ws / "caf\u00e9 notes.txt").write_text("x", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "add", "-A"], cwd=ws, check=True)
    assert "caf\u00e9 notes.txt" in _names(seed.pack_seed(str(ws))[0])


def test_the_task_copy_and_its_baseline_leave_secrets_behind(tmp_path: Path) -> None:
    from runtimes.adapters.internal_agent import InternalAgentAdapter

    ws = _sensitive_workspace(tmp_path)
    path, tmp = InternalAgentAdapter._create_worktree(str(ws), "task-secret")
    try:
        assert path != str(ws)
        copied = {str(p.relative_to(path)) for p in Path(path).rglob("*") if p.is_file() and ".git" not in p.parts}
        assert "README.md" in copied
        assert not [n for n in copied if n in _SENSITIVE or n.startswith(".data")], copied
        assert b"SECRET" not in seed.pack_seed(path)[0]
    finally:
        InternalAgentAdapter._remove_worktree(str(ws), path, tmp)


def test_is_excluded_matches_any_path_component() -> None:
    from runtimes.adapters.workspace_baseline import is_excluded

    assert is_excluded(".data/checkpoints/x.json")
    assert is_excluded("sub/dir/.env.local")
    assert is_excluded("a/b/app.db-wal")
    assert not is_excluded("pkg/database.py")
    assert not is_excluded("docs/environment.md")
    assert not is_excluded(".agency/harness-history.jsonl")


_MORE_SECRETS = (
    ".ssh/id_ed25519", "id_ecdsa", ".aws/credentials", ".netrc", ".npmrc", ".pypirc",
    ".git-credentials", "cert.pfx", "keystore.jks", "service-account.json", "token.json",
    "config/secrets.yaml", ".ENV", "Server.PEM", "v.db3", "w.sqlite-journal", "z.DB",
)


def test_more_secret_formats_and_any_letter_case_are_dropped(tmp_path: Path) -> None:
    ws = _workspace(tmp_path)
    for rel in _MORE_SECRETS:
        target = ws / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("SECRET", encoding="utf-8")
    tar_bytes, _ = seed.pack_seed(str(ws))
    assert b"SECRET" not in tar_bytes
    assert not [n for n in _names(tar_bytes) if n in _MORE_SECRETS]


def test_tracked_env_templates_are_still_seeded(tmp_path: Path) -> None:
    """Dropping .env.example made an agent's new copy overwrite the real one."""
    ws = _workspace(tmp_path)
    (ws / ".env.example").write_text("VAR=\n", encoding="utf-8")
    (ws / ".env.backend-secrets.example").write_text("X=\n", encoding="utf-8")
    (ws / ".env").write_text("SECRET", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=ws, check=True)
    subprocess.run(["git", "add", "-A", "-f"], cwd=ws, check=True)
    names = _names(seed.pack_seed(str(ws))[0])
    assert {".env.example", ".env.backend-secrets.example"} <= names
    assert ".env" not in names


def test_the_task_copy_keeps_env_templates_and_tracks_them(tmp_path: Path) -> None:
    from runtimes.adapters.internal_agent import InternalAgentAdapter

    ws = _workspace(tmp_path)
    (ws / ".env.example").write_text("VAR=\n", encoding="utf-8")
    (ws / ".env").write_text("SECRET", encoding="utf-8")
    path, tmp = InternalAgentAdapter._create_worktree(str(ws), "task-template")
    try:
        assert (Path(path) / ".env.example").is_file()
        assert not (Path(path) / ".env").exists()
        tracked = subprocess.run(["git", "ls-files"], cwd=path, capture_output=True, text=True).stdout.split()
        assert ".env.example" in tracked and ".env" not in tracked
    finally:
        InternalAgentAdapter._remove_worktree(str(ws), path, tmp)
