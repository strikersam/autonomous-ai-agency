"""tests/test_autonomous_fix.py — the autonomous CI-fix bot's safety gates.

Regression coverage for the incident on PR #1285: the previous (inline,
ungated) version of this script wrote an LLM's raw JSON output straight to
disk, which invented two new duplicate/broken GitHub Actions workflow files
and shrank tests/conftest.py from 354 lines to 10 — because it was fed 3000
characters of MongoDB service-container log noise instead of the actual
pytest failure, and had no path restrictions or destructive-overwrite check.

Covers the two new pure functions (``_is_denied_path``, ``_extract_pytest_
failure``) directly against that exact incident shape.
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".github", "scripts"))

# autonomous_fix.py reads GH_TOKEN/REPO at import time (fail-fast when run for
# real without them configured) — the pure functions under test here don't use
# either, so a placeholder value is enough to import the module in isolation.
os.environ.setdefault("GH_TOKEN", "test-token")
os.environ.setdefault("REPO", "test-owner/test-repo")

from autonomous_fix import _is_denied_path, _extract_pytest_failure  # noqa: E402


# ── _is_denied_path — the exact incident shape ────────────────────────────────


class TestIsDeniedPath:
    def test_workflow_files_are_denied(self):
        assert _is_denied_path(".github/workflows/daily-automation.yml")
        assert _is_denied_path(".github/workflows/main.yml")
        assert _is_denied_path(".github/workflows/new-anything.yml")

    def test_own_script_directory_is_denied(self):
        assert _is_denied_path(".github/scripts/slop_gate.py")
        assert _is_denied_path(".github/scripts/autonomous_fix.py")

    def test_shared_conftest_is_denied(self):
        assert _is_denied_path("tests/conftest.py")

    def test_risky_modules_are_denied(self):
        for path in (
            "packages/auth/admin.py", "packages/auth/rbac.py",
            "packages/auth/oauth.py", "packages/auth/service_token.py",
            "key_store.py", "agent/tools.py", "handlers/v3_auth.py",
        ):
            assert _is_denied_path(path), f"{path} should be denied"

    def test_path_traversal_is_denied(self):
        assert _is_denied_path("../../etc/passwd")
        assert _is_denied_path("tests/../.github/workflows/ci.yml")

    def test_ordinary_source_file_is_allowed(self):
        assert _is_denied_path("chat_handlers.py") == ""
        assert _is_denied_path("router/model_router.py") == ""
        assert _is_denied_path("tests/test_model_router.py") == ""

    def test_other_conftest_like_names_are_not_over_blocked(self):
        # Only the shared root tests/conftest.py is protected — a per-package
        # conftest (if one existed) isn't the same shared bootstrap.
        assert _is_denied_path("tests/unit/conftest.py") == ""


# ── _extract_pytest_failure — pulling signal out of MongoDB noise ────────────


class TestExtractPytestFailure:
    def _mongo_noise(self, n: int = 50) -> str:
        return "\n".join(
            f'2026-08-16T07:25:02.{i:07d}Z  {{"t":{{"$date":"2026-08-16T07:24:53.510+00:00"}},'
            f'"s":"I","c":"NETWORK","id":22944,"ctx":"conn{i}","msg":"Connection ended"}}'
            for i in range(n)
        )

    def test_finds_short_test_summary_through_noise(self):
        log = self._mongo_noise(200) + "\n" + (
            "=========================== short test summary info ============================\n"
            "FAILED tests/test_vision_routing.py::TestLangfuseSessionId::"
            "test_emit_chat_observation_accepts_session_id - assert 'session_id' in "
            "mappingproxy(...)\n"
        ) + self._mongo_noise(200)
        result = _extract_pytest_failure(log)
        assert "FAILED tests/test_vision_routing.py" in result
        assert "session_id" in result

    def test_finds_failures_marker(self):
        log = self._mongo_noise(100) + "\n=== FAILURES ===\nAssertionError: boom\n"
        result = _extract_pytest_failure(log)
        assert "AssertionError: boom" in result

    def test_strips_json_noise_lines(self):
        log = self._mongo_noise(20)
        result = _extract_pytest_failure(log)
        assert '"c":"NETWORK"' not in result

    def test_falls_back_to_tail_when_no_marker_found(self):
        log = "plain build log\nwith no pytest markers\nfinal line"
        result = _extract_pytest_failure(log)
        assert "final line" in result

    def test_empty_log_does_not_raise(self):
        assert _extract_pytest_failure("") == ""
