"""tests/test_monitor_lib.py — unit tests for scripts/monitor_lib.py.

Covers the four deterministic responsibilities:

1. ``download_status()`` — in-progress / stalled / done / missing-dir / no-log.
2. ``await_ready()`` — success on first try / retries / timeout / model-id-missing.
3. ``read_pid_file`` + ``is_process_alive`` (latter is mocked).
4. ``supervise_tick`` — heartbeat / crash-restart / manual-stop / adopted.
   Plus ``write_supervisor_state`` atomic-write contract and the
   ``supervise_loop`` give-up-after-max-crashes path.

All filesystem state lives in ``tmp_path`` and all env vars are scoped per
test so the suite is hermetic and parallel-safe.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Iterator
from unittest import mock

import pytest

_HERE = Path(__file__).resolve().parent
_REPO = _HERE.parent
sys.path.insert(0, str(_REPO / "scripts"))

import monitor_lib as ml  # noqa: E402


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Pin all env-overridable paths to tmp_path for hermetic tests."""
    monkeypatch.setenv("COLIBRI_DIR", str(tmp_path / "colibri"))
    monkeypatch.setenv("COLIBRI_MODEL_DIR", str(tmp_path / "glm-5.2"))
    monkeypatch.setenv("COLIBRI_DOWNLOAD_LOG", str(tmp_path / "glm-5.2.download.log"))
    monkeypatch.setenv("COLIBRI_URL", "http://localhost:8081/v1")
    monkeypatch.setenv("COLIBRI_MODEL_ID", "glm-5.2")
    yield


# ── download_status() ───────────────────────────────────────────────────────


def _write_log(path: Path, body: str, mtime: float) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    # mtime is in epoch seconds; ignore "future" platform restrictions.
    import os as _os
    _os.utime(path, (mtime, mtime))


class TestDownloadStatus:
    def test_missing_model_dir_returns_missing_dir_detail(self, tmp_path: Path) -> None:
        status = ml.download_status()
        assert status.detail == "missing-dir"
        assert status.complete is False
        assert status.on_disk_bytes == 0

    def test_no_log_returns_no_log_detail(self, tmp_path: Path) -> None:
        (tmp_path / "glm-5.2").mkdir()
        status = ml.download_status()
        assert status.detail == "no-log"
        assert status.complete is False

    def test_in_progress_with_no_done_signal(self, tmp_path: Path) -> None:
        mdir = tmp_path / "glm-5.2"
        mdir.mkdir()
        (mdir / "shard-00001.safetensors").write_bytes(b"x" * 1024)
        _write_log(tmp_path / "glm-5.2.download.log", "fetching shard 50/150\n", time.time())
        status = ml.download_status()
        assert status.detail == "in-progress"
        assert status.complete is False
        assert status.on_disk_bytes == 1024
        assert status.log_tail_has_done_signal is False

    def test_in_progress_with_incomplete_present(self, tmp_path: Path) -> None:
        mdir = tmp_path / "glm-5.2"
        mdir.mkdir()
        (mdir / "shard-00001.safetensors").write_bytes(b"x" * 2048)
        (mdir / "shard-00002.safetensors.incomplete").write_bytes(b"y" * 512)
        _write_log(tmp_path / "glm-5.2.download.log", "fetching shard 2/150\n", time.time())
        status = ml.download_status()
        assert status.detail == "in-progress"
        assert status.incomplete_count == 1
        assert status.complete is False

    def test_complete_when_done_signal_and_no_incomplete(self, tmp_path: Path) -> None:
        mdir = tmp_path / "glm-5.2"
        mdir.mkdir()
        (mdir / "shard-00001.safetensors").write_bytes(b"x" * 4096)
        _write_log(tmp_path / "glm-5.2.download.log", "\nDone. Fetched 150 files. Total 380 GB.\n", time.time())
        status = ml.download_status()
        assert status.detail == "done"
        assert status.complete is True
        assert status.log_tail_has_done_signal is True
        assert status.on_disk_bytes == 4096

    def test_stalled_when_log_old_and_no_done_signal(self, tmp_path: Path) -> None:
        mdir = tmp_path / "glm-5.2"
        mdir.mkdir()
        (mdir / "shard-00001.safetensors").write_bytes(b"x" * 1024)
        # 30 minutes ago, well past 15 minute stall threshold.
        _write_log(tmp_path / "glm-5.2.download.log", "fetching shard 7/150\n", time.time() - 30 * 60)
        status = ml.download_status()
        assert status.detail == "stalled"
        assert status.complete is False
        assert status.log_mtime_age_seconds > 15 * 60

    def test_old_log_but_has_done_signal_is_still_done(self, tmp_path: Path) -> None:
        """Old log + done signal + no .incomplete = complete (caller can
        cleanup the log themselves)."""
        mdir = tmp_path / "glm-5.2"
        mdir.mkdir()
        (mdir / "final.safetensors").write_bytes(b"z" * 256)
        _write_log(tmp_path / "glm-5.2.download.log", "Done. 100%\n", time.time() - 60 * 60)
        status = ml.download_status()
        assert status.complete is True
        assert status.detail == "done"


# ── await_ready() ───────────────────────────────────────────────────────────


class TestAwaitReady:
    def test_success_first_try_with_model_id(self) -> None:
        body = json.dumps({"data": [{"id": "glm-5.2"}]}).encode("utf-8")
        sleeper = mock.MagicMock()
        with mock.patch.object(ml.urllib.request, "urlopen") as fake_open:
            fake_open.return_value.__enter__.return_value.status = 200
            fake_open.return_value.__enter__.return_value.read.return_value = body
            ok = ml.await_ready(
                "http://localhost:8081/v1",
                "glm-5.2",
                timeout_s=10,
                sleeper=sleeper,
            )
        assert ok is True
        assert sleeper.call_count == 0  # never needed to sleep

    def test_success_after_two_retries(self) -> None:
        body = json.dumps({"data": [{"id": "GLM-5.2"}]}).encode("utf-8")
        # First two attempts raise ConnectionError, third succeeds.
        sleeper = mock.MagicMock()
        success_mock = mock.MagicMock()
        success_mock.__enter__.return_value.status = 200
        success_mock.__enter__.return_value.read.return_value = body
        with mock.patch.object(ml.urllib.request, "urlopen") as fake_open:
            fake_open.side_effect = [ConnectionError("refused"), ConnectionError("refused"), success_mock]
            ok = ml.await_ready(
                "http://localhost:8081/v1",
                "glm-5.2",
                timeout_s=30,
                poll_s=2,
                sleeper=sleeper,
            )
        assert ok is True
        assert sleeper.call_count == 2

    def test_timeout_when_endpoint_always_fails(self) -> None:
        import itertools as _it
        sleeper = mock.MagicMock()
        # Virtual clock advances 1 sec per call. With deadline=10 and poll_s=1,
        # the loop sleeps ~10 times before exiting.
        fake_now = _it.count(0.0, 1.0)
        with mock.patch.object(ml.urllib.request, "urlopen") as fake_open:
            fake_open.side_effect = ConnectionError("nope")
            ok = ml.await_ready(
                "http://localhost:8081/v1",
                "glm-5.2",
                timeout_s=10,
                poll_s=1,
                now_fn=lambda: next(fake_now),
                sleeper=sleeper,
            )
        assert ok is False
        assert sleeper.call_count >= 5

    def test_success_without_model_id_requirement(self) -> None:
        body = json.dumps({"data": [{"id": "anything"}]}).encode("utf-8")
        sleeper = mock.MagicMock()
        with mock.patch.object(ml.urllib.request, "urlopen") as fake_open:
            fake_open.return_value.__enter__.return_value.status = 200
            fake_open.return_value.__enter__.return_value.read.return_value = body
            ok = ml.await_ready(
                "http://localhost:8081/v1",
                model_id=None,  # any 200 is enough
                sleeper=sleeper,
            )
        assert ok is True

    def test_status_500_keeps_polling(self) -> None:
        sleeper = mock.MagicMock()
        success_mock = mock.MagicMock()
        success_mock.__enter__.return_value.status = 200
        success_mock.__enter__.return_value.read.return_value = json.dumps({"data": [{"id": "glm-5.2"}]}).encode("utf-8")
        # First call returns non-200, second call succeeds.
        bad_mock = mock.MagicMock()
        bad_mock.__enter__.return_value.status = 503
        bad_mock.__enter__.return_value.read.return_value = b""
        with mock.patch.object(ml.urllib.request, "urlopen") as fake_open:
            fake_open.side_effect = [bad_mock, success_mock]
            ok = ml.await_ready("http://localhost:8081/v1", "glm-5.2", sleeper=sleeper)
        assert ok is True
        assert sleeper.call_count == 1


# ── read_pid_file + is_process_alive ─────────────────────────────────────────


class TestReadPidFile:
    def test_missing_returns_none(self, tmp_path: Path) -> None:
        assert ml.read_pid_file(tmp_path / ".colibri.pid") is None

    def test_valid_int(self, tmp_path: Path) -> None:
        p = tmp_path / ".colibri.pid"
        p.write_text("12345")
        assert ml.read_pid_file(p) == 12345

    def test_int_with_trailing_newline(self, tmp_path: Path) -> None:
        p = tmp_path / ".colibri.pid"
        p.write_text("67890\n")
        assert ml.read_pid_file(p) == 67890

    def test_empty_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / ".colibri.pid"
        p.write_text("")
        assert ml.read_pid_file(p) is None

    def test_malformed_returns_none(self, tmp_path: Path) -> None:
        p = tmp_path / ".colibri.pid"
        p.write_text("not-a-number")
        assert ml.read_pid_file(p) is None


class TestIsProcessAlive:
    def test_zero_pid_dead(self) -> None:
        assert ml.is_process_alive(0) is False

    def test_negative_pid_dead(self) -> None:
        assert ml.is_process_alive(-1) is False

    def test_alive_via_tasklist(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_out = mock.MagicMock()
        fake_out.stdout = '"coli.exe","12345","Console","1","123,456 K"\n'
        fake_out.stderr = ""
        monkeypatch.setattr(ml.platform, "system", lambda: "Windows")
        monkeypatch.setattr(ml.subprocess, "run", mock.MagicMock(return_value=fake_out))
        assert ml.is_process_alive(12345) is True

    def test_dead_via_tasklist_no_tasks(self, monkeypatch: pytest.MonkeyPatch) -> None:
        fake_out = mock.MagicMock()
        fake_out.stdout = "INFO: No tasks are running which match the specified criteria.\n"
        fake_out.stderr = ""
        monkeypatch.setattr(ml.platform, "system", lambda: "Windows")
        monkeypatch.setattr(ml.subprocess, "run", mock.MagicMock(return_value=fake_out))
        assert ml.is_process_alive(99999) is False


# ── supervise_tick ──────────────────────────────────────────────────────────


class TestSupervisorTick:
    def test_manual_stop_when_no_pid_file(self, tmp_path: Path) -> None:
        pid_path = tmp_path / ".colibri.pid"
        state = ml.SupervisorState(consecutive_crashes=0)
        action, new_state = ml.supervise_tick(pid_path, state)
        assert action == "manual-stop"
        assert new_state is state  # unchanged

    def test_heartbeat_when_alive(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pid_path = tmp_path / ".colibri.pid"
        pid_path.write_text("555")
        monkeypatch.setattr(ml, "is_process_alive", lambda pid: pid == 555)
        state = ml.SupervisorState(consecutive_crashes=0)
        action, new_state = ml.supervise_tick(pid_path, state)
        assert action == "heartbeat"
        assert new_state.consecutive_crashes == 0

    def test_crash_count_increments(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pid_path = tmp_path / ".colibri.pid"
        pid_path.write_text("777")
        monkeypatch.setattr(ml, "is_process_alive", lambda pid: False)
        state = ml.SupervisorState(consecutive_crashes=2)
        action, new_state = ml.supervise_tick(pid_path, state)
        assert action == "crash-restart"
        assert new_state.consecutive_crashes == 3
        assert new_state.total_crashes == 1
        assert new_state.last_crash_at > 0

    def test_adopted_resets_counter(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pid_path = tmp_path / ".colibri.pid"
        pid_path.write_text("888")
        monkeypatch.setattr(ml, "is_process_alive", lambda pid: True)
        state = ml.SupervisorState(consecutive_crashes=4, total_crashes=4)
        action, new_state = ml.supervise_tick(pid_path, state)
        assert action == "adopted"
        assert new_state.consecutive_crashes == 0


# ── write_supervisor_state atomicity ────────────────────────────────────────


class TestSupervisorStateAtomic:
    def test_write_does_not_leak_tmp_file(self, tmp_path: Path) -> None:
        p = tmp_path / ".colibri.supervisor.state"
        ml.write_supervisor_state(p, ml.SupervisorState(consecutive_crashes=3))
        assert p.exists()
        assert not p.with_suffix(p.suffix + ".tmp").exists()

    def test_overwrite_replaces_content(self, tmp_path: Path) -> None:
        p = tmp_path / ".colibri.supervisor.state"
        ml.write_supervisor_state(p, ml.SupervisorState(consecutive_crashes=1))
        ml.write_supervisor_state(p, ml.SupervisorState(consecutive_crashes=9, total_crashes=12))
        loaded = ml.read_supervisor_state(p)
        assert loaded.consecutive_crashes == 9
        assert loaded.total_crashes == 12

    def test_read_handles_missing_file(self, tmp_path: Path) -> None:
        loaded = ml.read_supervisor_state(tmp_path / "nope.json")
        assert loaded.consecutive_crashes == 0
        assert loaded.total_crashes == 0

    def test_read_recovers_from_corrupt_json(self, tmp_path: Path) -> None:
        p = tmp_path / "corrupt.json"
        p.write_text("{not valid json")
        loaded = ml.read_supervisor_state(p)
        assert loaded.consecutive_crashes == 0

    def test_read_ignores_unknown_keys(self, tmp_path: Path) -> None:
        p = tmp_path / "future.json"
        p.write_text(json.dumps({"consecutive_crashes": 2, "future_field": True, "total_crashes": 5}))
        loaded = ml.read_supervisor_state(p)
        assert loaded.consecutive_crashes == 2
        assert loaded.total_crashes == 5


# ── supervise_loop give-up ─────────────────────────────────────────────────


class TestSuperviseLoopGiveUp:
    def test_returns_false_after_max_consecutive_crashes(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        pid_path = tmp_path / ".colibri.pid"
        state_path = tmp_path / ".colibri.supervisor.state"
        # Always-dead pid => crash-restart every tick.
        pid_path.write_text("111")
        monkeypatch.setattr(ml, "is_process_alive", lambda pid: False)
        # No sleeps
        monkeypatch.setattr(ml.time, "sleep", lambda s: None)
        state_path.parent.mkdir(parents=True, exist_ok=True)
        start_calls: list[int] = []

        def fake_start() -> None:
            start_calls.append(1)

        ok = ml.supervise_loop(
            fake_start,
            pid_path=pid_path,
            state_path=state_path,
            max_consecutive_crashes=3,
            base_backoff_s=0,
            max_backoff_s=0,
            tick_s=0,
            heartbeat_s=0,
        )
        assert ok is False
        # 4 crashes (3+1 to exceed threshold) should have fired start_fn() 3 times
        # before giving up on the 4th tick.
        assert len(start_calls) == 3
        loaded = ml.read_supervisor_state(state_path)
        assert loaded.note == "exceeded-max-crashes" or loaded.consecutive_crashes > 3
