"""
tests/test_output_filter.py — Unit tests for output_filter.py

Verifies token reduction across all supported command types.
"""
from __future__ import annotations

import pytest
from output_filter import OutputFilter, FILTER_ENABLED, MAX_CHARS


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def _enable_filter():
    """Ensure filter is enabled for all tests."""
    OutputFilter.enable()
    yield
    OutputFilter.enable()  # Restore


# ─── Git output ───────────────────────────────────────────────────────────────

def test_git_log_large():
    """git log with 200 commits should be compressed."""
    stdout = "\n".join(
        f"commit {i:040x}\nAuthor: Dev <dev@example.com>\nDate: 2026-06-0{i % 9 + 1}\n\n    Commit message {i}\n"
        for i in range(200)
    )
    result = OutputFilter.filter("git log --oneline", stdout)
    assert len(result) < len(stdout) * 0.5
    assert "more lines" in result.lower() or "…" in result


def test_git_status_small():
    """Small git status should pass through unchanged."""
    stdout = "On branch master\nnothing to commit, working tree clean"
    result = OutputFilter.filter("git status", stdout)
    assert result == stdout


# ─── ls / dir ─────────────────────────────────────────────────────────────────

def test_ls_many_files():
    """Directory with 200 files should be summarized by extension."""
    stdout = "\n".join(
        [f"file_{i}.py" for i in range(80)]
        + [f"test_{i}.py" for i in range(60)]
        + [f"data_{i}.json" for i in range(40)]
        + [f"readme_{i}.md" for i in range(20)]
    )
    result = OutputFilter.filter("ls -la", stdout)
    assert len(result) < len(stdout) * 0.6
    assert ".py" in result


def test_ls_small():
    """Small directory listing should pass through."""
    stdout = "file1.py\nfile2.py\nreadme.md"
    result = OutputFilter.filter("ls", stdout)
    assert result == stdout


# ─── pip ──────────────────────────────────────────────────────────────────────

def test_pip_install_large():
    """pip install with many progress lines should be compressed."""
    stdout = "Collecting package\n" + "\n".join(
        f"\r  Downloading ... ({i}%)" for i in range(0, 100, 2)
    ) + "\nSuccessfully installed package-1.0"
    result = OutputFilter.filter("pip install package", stdout)
    assert len(result) < len(stdout) * 0.4
    assert "intermediate lines" in result.lower() or "Successfully" in result


# ─── npm ──────────────────────────────────────────────────────────────────────

def test_npm_install_large():
    """npm install with spinner output should be compressed."""
    stdout = "\n".join(
        ["npm install starting"]
        + [f"⠋ Loading... ({i})" for i in range(50)]
        + ["added 500 packages in 30s"]
    )
    result = OutputFilter.filter("npm install", stdout)
    assert len(result) < len(stdout) * 0.5
    # Spinner characters should be stripped
    assert "⠋" not in result


# ─── docker ───────────────────────────────────────────────────────────────────

def test_docker_build_large():
    """docker build with many layers should be compressed."""
    layers = [f"# {i} [stage 1/1] RUN echo step {i}\nsha256:{i:064x}\n" for i in range(30)]
    stdout = "Building...\n" + "\n".join(layers) + "\nSuccessfully built abc123"
    result = OutputFilter.filter("docker build .", stdout)
    assert len(result) < len(stdout) * 0.5


# ─── pytest ───────────────────────────────────────────────────────────────────

def test_pytest_many_tests():
    """pytest output with many passing tests should be compressed."""
    stdout = "============================= test session starts =============================\n" + "\n".join(
        [f"tests/test_{i}.py::test_{i} PASSED" for i in range(100)]
    ) + "\n\n100 passed in 5.00s"
    result = OutputFilter.filter("pytest tests/", stdout)
    assert len(result) < len(stdout) * 0.5
    assert "passed" in result.lower()


def test_pytest_with_failures():
    """pytest output with failures should preserve failure details."""
    stdout = (
        "test session starts\n"
        "tests/test_a.py::test_ok PASSED\n"
        "tests/test_a.py::test_fail FAILED\n"
        "FAILURES\n"
        "________ test_fail ________\n"
        "    assert 1 == 2\n"
        "E   assert 1 == 2\n"
        "short test summary info\n"
        "FAILED tests/test_a.py::test_fail\n"
        "1 failed, 1 passed in 0.10s\n"
    )
    result = OutputFilter.filter("pytest tests/", stdout)
    assert "FAILED" in result or "failed" in result.lower()


# ─── Python traceback ─────────────────────────────────────────────────────────

def test_python_deep_traceback():
    """Deep Python traceback should collapse intermediate frames."""
    stdout = "Traceback (most recent call last):\n" + "\n".join(
        [f'  File "mod_{i}.py", line {i}, in func_{i}\n    return mod_{i+1}.func_{i+1}(x)' for i in range(1, 21)]
    ) + "\nValueError: something broke"
    result = OutputFilter.filter("python script.py", stdout)
    # Should be smaller than original - compress by at least 5%
    assert len(result) < len(stdout) * 0.95
    assert "intermediate frames" in result.lower() or "ValueError" in result


# ─── curl ─────────────────────────────────────────────────────────────────────

def test_curl_large_response():
    """Large curl output should be truncated with head/tail."""
    stdout = "\n".join([f"data line {i}" for i in range(1000)])
    result = OutputFilter.filter("curl https://api.example.com", stdout)
    assert len(result) < len(stdout) * 0.5
    assert "lines" in result.lower() or "chars" in result.lower()


# ─── Disabled mode ────────────────────────────────────────────────────────────

def test_disabled_passthrough():
    """When disabled, output should pass through (truncated to max_chars)."""
    OutputFilter.disable()
    try:
        stdout = "x" * 20000
        result = OutputFilter.filter("some-command", stdout, max_chars=1000)
        assert len(result) <= 1100  # Allow some overhead for truncation message
        assert len(result) < len(stdout)
    finally:
        OutputFilter.enable()


# ─── Empty input ──────────────────────────────────────────────────────────────

def test_empty_input():
    """Empty or whitespace-only input should pass through unchanged."""
    assert OutputFilter.filter("ls", "") == ""
    assert OutputFilter.filter("git log", "   \n  ") == "   \n  "


# ─── Unknown command ──────────────────────────────────────────────────────────

def test_unknown_command_generic_filter():
    """Unrecognized commands should get generic dedup+truncation."""
    stdout = "\n".join(
        ["line " + str(i) for i in range(100)]
        + ["repeated"] * 50
    )
    result = OutputFilter.filter("unknown-tool", stdout)
    assert len(result) < len(stdout) * 0.7
