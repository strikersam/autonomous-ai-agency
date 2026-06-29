"""Regression tests for log_watcher.LogWatcher security fixes (PR 487).

Covers the three bugs found by CodeRabbit on PR 487 in log_watcher.py:
  1. _create_github_issue() must refuse to fire when github_repo is empty
     (no upstream default; forks and test deployments cannot file against
     the wrong repo).
  2. _scan_file() first scan must read from position 0 (not EOF) so
     pre-existing ERROR lines are detected, not silently skipped.
  3. AUTO_FILE_ENABLED defaults to off; _handle_error() must skip issue
     creation when the flag is off (no network call).
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from packages.telemetry.log_watcher import AUTO_FILE_ENABLED, AUTO_FIX_ENABLED, LogWatcher, _redact_sensitive


class TestRedactSensitive:
    def test_redacts_sk_prefixed_token(self) -> None:
        assert "sk-<REDACTED>" in _redact_sensitive("key=sk-abcdefghijklmnop1234")

    def test_redacts_email(self) -> None:
        assert "<EMAIL_REDACTED>" in _redact_sensitive("contact alice@example.com today")

    def test_redacts_ip(self) -> None:
        assert "<IP_REDACTED>" in _redact_sensitive("server at 10.0.0.5:8000")


class TestCreateGithubIssueRepoRequired:
    """_create_github_issue() must not fire when no explicit repo is set."""

    def test_refuses_when_github_repo_blank(self) -> None:
        # Pass empty github_repo (constructor param) and ensure no env override
        with patch.dict(os.environ, {"GITHUB_REPOSITORY": ""}, clear=False):
            watcher = LogWatcher(
                log_files=["/tmp/does-not-matter.log"],  # nosec B106 B108 -- fake test fixture, not a real credential/path
                github_token="ghp_fake_token_for_test",  # nosec B106 B108 -- fake test fixture, not a real credential/path
                github_repo="",
            )
            entry = MagicMock()
            entry.error_type = "error"
            entry.file_path = "test.log"
            entry.message = "ERROR something went wrong"
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.assert_not_called()
                watcher._create_github_issue(entry, "fp123")
                urlopen.assert_not_called()

    def test_refuses_when_only_constructor_empty(self) -> None:
        watcher = LogWatcher(
            log_files=["/tmp/does-not-matter.log"],  # nosec B106 B108 -- fake test fixture, not a real credential/path
            github_token="ghp_fake_token_for_test",  # nosec B106 B108 -- fake test fixture, not a real credential/path
            github_repo="",
        )
        entry = MagicMock()
        entry.error_type = "error"
        entry.file_path = "test.log"
        entry.message = "ERROR something went wrong"
        with patch("urllib.request.urlopen") as urlopen:
            watcher._create_github_issue(entry, "fp456")
            urlopen.assert_not_called()

    def test_fires_when_explicit_repo_set(self) -> None:
        watcher = LogWatcher(
            log_files=["/tmp/does-not-matter.log"],  # nosec B106 B108 -- fake test fixture, not a real credential/path
            github_token="ghp_fake_token_for_test",  # nosec B106 B108 -- fake test fixture, not a real credential/path
            github_repo="my-org/my-repo",
        )
        entry = MagicMock()
        entry.error_type = "error"
        entry.file_path = "test.log"
        entry.message = "ERROR something went wrong"
        fake_response = MagicMock()
        fake_response.read.return_value = b'{"number": 42}'
        fake_response.__enter__ = MagicMock(return_value=fake_response)
        fake_response.__exit__ = MagicMock(return_value=False)
        with patch.dict(os.environ, {"LOG_WATCHER_AUTO_FILE": "1"}, clear=False):
            with patch("urllib.request.urlopen") as urlopen:
                urlopen.return_value = fake_response
                watcher._create_github_issue(entry, "fp789")
                urlopen.assert_called_once()
                req = urlopen.call_args[0][0]
                # production passes a urllib.request.Request object
                url = getattr(req, "full_url", req)
                assert "my-org/my-repo" in url


class TestFirstScanFromBeginning:
    """First scan must read from position 0, not EOF."""

    def test_first_scan_detects_existing_errors(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2026-06-09 10:00:00 INFO startup complete\n")
            f.write("2026-06-09 10:00:01 ERROR something broke\n")
            f.write("2026-06-09 10:00:02 INFO recovered\n")
            tmp_path = f.name
        try:
            watcher = LogWatcher(log_files=[tmp_path], github_token="")  # nosec B106 B108 -- fake test fixture, not a real credential/path
            entries = watcher.scan_now()
            error_entries = [e for e in entries if e.error_type != "traceback"]
            # The pre-existing ERROR line MUST be detected on first scan
            assert any("something broke" in e.message for e in error_entries), (
                f"First scan should detect pre-existing ERROR lines, "
                f"but got: {[e.message for e in error_entries]}"
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_subsequent_scan_only_reads_new_content(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2026-06-09 10:00:00 ERROR first error\n")
            tmp_path = f.name
        try:
            watcher = LogWatcher(log_files=[tmp_path], github_token="")  # nosec B106 B108 -- fake test fixture, not a real credential/path
            first = watcher.scan_now()
            assert any("first error" in e.message for e in first)

            # Append a new error after the first scan
            with open(tmp_path, "a") as f:
                f.write("2026-06-09 10:00:05 ERROR second error\n")

            second = watcher.scan_now()
            # Second scan should only see the NEW error
            assert any("second error" in e.message for e in second)
            assert not any("first error" in e.message for e in second), (
                "Second scan should not re-read already-consumed content"
            )
        finally:
            Path(tmp_path).unlink(missing_ok=True)


class TestAutoFileEnabledGate:
    """AUTO_FILE_ENABLED must default to off; _handle_error() must respect it."""

    def test_auto_file_disabled_by_default(self) -> None:
        # Re-read the module attribute to confirm the default is opt-in (off)
        assert AUTO_FILE_ENABLED is False, (
            "LOG_WATCHER_AUTO_FILE must default to off (opt-in feature flag) "
            "so forks and test deployments never file issues by accident"
        )

    def test_handle_error_skips_when_auto_file_disabled(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2026-06-09 10:00:00 ERROR something broke\n")
            tmp_path = f.name
        try:
            watcher = LogWatcher(
                log_files=[tmp_path],
                github_token="ghp_fake_token_for_test",  # nosec B106 B108 -- fake test fixture, not a real credential/path
                github_repo="my-org/my-repo",
            )
            with patch.dict(os.environ, {"LOG_WATCHER_AUTO_FILE": "0"}, clear=False):
                with patch("urllib.request.urlopen") as urlopen:
                    entries = watcher.scan_now()
                    # scan_now returns entries, but _handle_error should not
                    # attempt to create an issue when AUTO_FILE is off
                    for entry in entries:
                        watcher._handle_error(entry)
                    urlopen.assert_not_called()
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_handle_error_fires_when_auto_file_enabled(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            f.write("2026-06-09 10:00:00 ERROR something broke\n")
            tmp_path = f.name
        try:
            watcher = LogWatcher(
                log_files=[tmp_path],
                github_token="ghp_fake_token_for_test",  # nosec B106 B108 -- fake test fixture, not a real credential/path
                github_repo="my-org/my-repo",
            )
            fake_response = MagicMock()
            fake_response.read.return_value = b'{"number": 99}'
            fake_response.__enter__ = MagicMock(return_value=fake_response)
            fake_response.__exit__ = MagicMock(return_value=False)
            with patch.dict(os.environ, {"LOG_WATCHER_AUTO_FILE": "1"}, clear=False):
                with patch("urllib.request.urlopen") as urlopen:
                    urlopen.return_value = fake_response
                    entries = watcher.scan_now()
                    for entry in entries:
                        watcher._handle_error(entry)
                    urlopen.assert_called_once()
        finally:
            Path(tmp_path).unlink(missing_ok=True)
