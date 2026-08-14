from pathlib import Path

from agent.tools import WorkspaceTools


def test_workspace_tools_list_read_search_and_apply_diff(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    sample = root / "app.py"
    sample.write_text("print('hello')\n", encoding="utf-8")

    tools = WorkspaceTools(root)

    listed = tools.list_files(limit=10)
    assert "app.py" in listed

    content = tools.read_file("app.py")
    assert "hello" in content

    hits = tools.search_code("hello", limit=5)
    assert hits
    assert hits[0]["path"] == "app.py"

    diff_result = tools.apply_diff("app.py", "print('updated')\n")
    assert "updated" in tools.read_file("app.py")
    assert "app.py" in diff_result["path"]


# ---------------------------------------------------------------------------
# JIT retrieval tools  (head_file + file_index)
# ---------------------------------------------------------------------------

def test_head_file_returns_first_n_lines(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    lines = [f"line {i}" for i in range(100)]
    (root / "big.py").write_text("\n".join(lines) + "\n", encoding="utf-8")

    tools = WorkspaceTools(root)
    head = tools.head_file("big.py", lines=10)

    assert "line 0" in head
    assert "line 9" in head
    assert "line 10" not in head
    assert "90 more lines" in head


def test_head_file_full_small_file(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "small.py").write_text("a\nb\nc\n", encoding="utf-8")

    tools = WorkspaceTools(root)
    head = tools.head_file("small.py", lines=50)
    assert "a" in head
    assert "more lines" not in head


def test_head_file_rejects_path_escape(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    tools = WorkspaceTools(root)
    try:
        tools.head_file("../../etc/passwd", lines=5)
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_file_index_returns_line_and_byte_counts(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "a.py").write_text("x\ny\nz\n", encoding="utf-8")
    (root / "b.py").write_text("hello world\n", encoding="utf-8")

    tools = WorkspaceTools(root)
    index = tools.file_index()

    paths = [e["path"] for e in index]
    assert "a.py" in paths
    assert "b.py" in paths

    for entry in index:
        assert "lines" in entry
        assert "bytes" in entry
        assert isinstance(entry["lines"], int)
        assert isinstance(entry["bytes"], int)


def test_file_index_respects_max_entries(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    for i in range(20):
        (root / f"file_{i}.py").write_text(f"# file {i}\n", encoding="utf-8")

    tools = WorkspaceTools(root)
    index = tools.file_index(max_entries=5)
    assert len(index) == 5


# ---------------------------------------------------------------------------
# F1 — Precise Diff Application  (edit_file)
# ---------------------------------------------------------------------------

def test_edit_file_exact_match(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    (root / "main.py").write_text("def foo():\n    return 1\n", encoding="utf-8")

    tools = WorkspaceTools(root)
    result = tools.edit_file("main.py", "return 1", "return 42")

    assert result["error"] == ""
    assert "return 42" in (root / "main.py").read_text(encoding="utf-8")
    assert "-    return 1" in result["diff"]
    assert "+    return 42" in result["diff"]


def test_edit_file_old_string_not_found_returns_error(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    original = "def foo():\n    return 1\n"
    (root / "main.py").write_text(original, encoding="utf-8")

    tools = WorkspaceTools(root)
    result = tools.edit_file("main.py", "return 999", "return 0")

    assert result["error"] != ""
    # File must be unchanged
    assert (root / "main.py").read_text(encoding="utf-8") == original


def test_edit_file_whitespace_normalised_fallback(tmp_path: Path):
    """Trailing spaces on lines must not block the edit."""
    root = tmp_path / "repo"
    root.mkdir()
    # File has trailing spaces on the function-body line
    (root / "a.py").write_text("def bar():  \n    x = 1  \n", encoding="utf-8")

    tools = WorkspaceTools(root)
    # old_string has no trailing spaces
    result = tools.edit_file("a.py", "def bar():\n    x = 1", "def bar():\n    x = 2")

    assert result["error"] == "", f"unexpected error: {result['error']}"
    assert "x = 2" in (root / "a.py").read_text(encoding="utf-8")


def test_edit_file_missing_file_returns_error(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    tools = WorkspaceTools(root)
    result = tools.edit_file("nonexistent.py", "old", "new")
    assert "not found" in result["error"]


def test_edit_file_delete_old_string(tmp_path: Path):
    """Replacing with empty string removes the matched text."""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "cfg.py").write_text("DEBUG = True\nPROD = False\n", encoding="utf-8")

    tools = WorkspaceTools(root)
    result = tools.edit_file("cfg.py", "DEBUG = True\n", "")

    assert result["error"] == ""
    content = (root / "cfg.py").read_text(encoding="utf-8")
    assert "DEBUG" not in content
    assert "PROD" in content


def test_edit_file_rejects_path_traversal(tmp_path: Path):
    root = tmp_path / "repo"
    root.mkdir()
    tools = WorkspaceTools(root)
    try:
        tools.edit_file("../../etc/passwd", "old", "new")
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_edit_file_registered_in_capability_registry(tmp_path: Path):
    """edit_file must be discoverable via the capability registry."""
    from agent.capability_registry import ToolRegistry, _register_builtin_tools

    registry = ToolRegistry()
    _register_builtin_tools(registry, workspace_root=str(tmp_path))

    tool_names = {t.name for t in registry._tools.values()}
    assert "edit_file" in tool_names
