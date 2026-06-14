"""Regression tests for path-traversal protection in WorkspaceTools."""
from __future__ import annotations

import os

import pytest

from agent.tools import WorkspaceTools


def test_path_traversal_rejected():
    tools = WorkspaceTools(workspace_root="/tmp/safe_root")
    with pytest.raises(ValueError, match="traversal"):
        tools._safe_path("../../etc/passwd")


def test_normal_path_accepted():
    tools = WorkspaceTools(workspace_root="/tmp/safe_root")
    assert tools._safe_path("src/main.py").startswith("/tmp/safe_root")


def test_absolute_path_outside_root_rejected():
    tools = WorkspaceTools(workspace_root="/tmp/safe_root")
    with pytest.raises(ValueError, match="traversal"):
        tools._safe_path("/etc/passwd")


def test_sibling_prefix_dir_rejected():
    # /tmp/safe_root_evil shares a string prefix with the root but is outside it.
    tools = WorkspaceTools(workspace_root="/tmp/safe_root")
    with pytest.raises(ValueError, match="traversal"):
        tools._safe_path("../safe_root_evil/secret")


def test_root_itself_accepted():
    tools = WorkspaceTools(workspace_root="/tmp/safe_root")
    assert tools._safe_path(".") == os.path.realpath("/tmp/safe_root")


def test_read_file_rejects_traversal(tmp_path):
    tools = WorkspaceTools(workspace_root=str(tmp_path))
    with pytest.raises(ValueError, match="traversal"):
        tools.read_file("../../../etc/passwd")


def test_write_file_rejects_traversal(tmp_path):
    tools = WorkspaceTools(workspace_root=str(tmp_path))
    with pytest.raises(ValueError, match="traversal"):
        tools.write_file("../escape.txt", "pwned")


def test_apply_diff_rejects_traversal(tmp_path):
    tools = WorkspaceTools(workspace_root=str(tmp_path))
    with pytest.raises(ValueError, match="traversal"):
        tools.apply_diff("../../escape.txt", "pwned")
