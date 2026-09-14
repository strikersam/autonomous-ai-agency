"""openclaw_str_e_fix.py — safe auto-fix for `HTTPException(detail=str(exc))`.

Root-cause fix for the OpenClaw weekly auto-fix workflow, which used a naive
regex (`raise HTTPException(status_code=\\d+, detail=str(\\w+))`) to rewrite
*every* such call to `detail="Internal server error"`, regardless of status
code or exception type. That produced PR #1486: it rewrote two 400/404
handlers whose `except ValueError` blocks raise deliberately-authored, safe
validation messages (e.g. `"'{key}' is not an operator-controllable
setting"` — `packages/config/control_overrides.py`), turning an actionable
client error into a nonsensical "Internal server error" on a 400 response,
for no security benefit (the message was never attacker-influenced or
internals-bearing).

This module only rewrites a call site when *both* hold:

1. The exception is caught by a genuinely broad handler — ``except Exception
   as e`` or ``except BaseException as e`` — never a specific type like
   ``ValueError`` or a custom exception, which is what a codebase author
   reaches for when the message is meant to be safe and shown to the client.
   (A bare ``except:`` binds no name at all, so ``str(<name>)`` inside one
   can never actually be the caught exception — there is nothing safe to
   match against, so those sites are always left alone too.)
2. The response status code is a real 5xx server fault. A 4xx is a client
   error by definition; relabelling it "Internal server error" is wrong
   regardless of the exception type.

Uses the AST (not a regex over the whole file) to find the exact `str(exc)`
sub-expression to replace, so only that one call is touched and everything
else in the line — indentation, surrounding code, comments — survives
untouched.
"""
from __future__ import annotations

import ast
from pathlib import Path

_BROAD_EXCEPT_NAMES = {"Exception", "BaseException"}
_REPLACEMENT = '"Internal server error"'

_SKIP_DIR_PARTS = {".venv", "node_modules", ".git"}
_SKIP_PATH_PREFIXES = ("tests/",)


def _is_broad_except(handler: ast.ExceptHandler) -> bool:
    """True for a bare ``except:`` or ``except Exception`` / ``except BaseException``.

    A bare ``except:`` is included here for completeness, but it can never
    actually yield a rewrite: the caller also requires a bound exception
    name (``except ... as e``) to know which ``str(...)`` argument is the
    caught exception, and a bare except binds none.
    """
    if handler.type is None:
        return True
    if isinstance(handler.type, ast.Name):
        return handler.type.id in _BROAD_EXCEPT_NAMES
    return False


def _is_http_exception_call(call: ast.Call) -> bool:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id == "HTTPException"
    if isinstance(func, ast.Attribute):
        return func.attr == "HTTPException"
    return False


def _status_code_is_server_fault(call: ast.Call) -> bool:
    for kw in call.keywords:
        if kw.arg == "status_code" and isinstance(kw.value, ast.Constant):
            value = kw.value.value
            return isinstance(value, int) and 500 <= value <= 599
    return False


def _find_unsafe_str_call(call: ast.Call, exc_name: str) -> ast.Call | None:
    """Return the ``str(exc_name)`` node passed as ``detail=`` on this HTTPException call, if any."""
    for kw in call.keywords:
        if kw.arg != "detail" or not isinstance(kw.value, ast.Call):
            continue
        inner = kw.value
        if (
            isinstance(inner.func, ast.Name)
            and inner.func.id == "str"
            and len(inner.args) == 1
            and isinstance(inner.args[0], ast.Name)
            and inner.args[0].id == exc_name
        ):
            return inner
    return None


def find_unsafe_str_calls(source: str) -> list[ast.Call]:
    """Find every ``str(exc)`` call safe to rewrite, per the two rules above.

    Returns the ``ast.Call`` nodes for the ``str(...)`` sub-expressions
    themselves (with position info), not the enclosing raise/HTTPException
    call — that keeps the eventual text replacement minimal.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []

    found: list[ast.Call] = []

    class Visitor(ast.NodeVisitor):
        def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
            if _is_broad_except(node) and node.name:
                exc_name = node.name
                for child in ast.walk(node):
                    if (
                        isinstance(child, ast.Call)
                        and _is_http_exception_call(child)
                        and _status_code_is_server_fault(child)
                    ):
                        str_call = _find_unsafe_str_call(child, exc_name)
                        if str_call is not None:
                            found.append(str_call)
            self.generic_visit(node)

    Visitor().visit(tree)
    return found


def _replace_span(
    lines: list[str], start_line: int, start_col: int, end_line: int, end_col: int, text: str
) -> None:
    """Replace the 0-indexed [start_line:start_col, end_line:end_col) span in-place."""
    if start_line == end_line:
        line = lines[start_line]
        lines[start_line] = line[:start_col] + text + line[end_col:]
    else:
        first = lines[start_line][:start_col]
        last = lines[end_line][end_col:]
        lines[start_line : end_line + 1] = [first + text + last]


def fix_source(source: str) -> tuple[str, int]:
    """Rewrite every safe ``str(exc)`` call found; return (new_source, count)."""
    calls = find_unsafe_str_calls(source)
    if not calls:
        return source, 0

    # Apply from the bottom of the file up so earlier spans stay valid even
    # when a multi-line span collapses to fewer lines.
    calls.sort(key=lambda c: (c.lineno, c.col_offset), reverse=True)

    lines = source.splitlines(keepends=True)
    for call in calls:
        assert call.end_lineno is not None and call.end_col_offset is not None
        _replace_span(
            lines,
            call.lineno - 1,
            call.col_offset,
            call.end_lineno - 1,
            call.end_col_offset,
            _REPLACEMENT,
        )
    return "".join(lines), len(calls)


def fix_file(path: Path) -> int:
    """Fix one file in place; return how many call sites were rewritten."""
    source = path.read_text(encoding="utf-8")
    new_source, count = fix_source(source)
    if count:
        path.write_text(new_source, encoding="utf-8")
    return count


def _should_skip(rel_path: str, path: Path) -> bool:
    if any(part in _SKIP_DIR_PARTS for part in path.parts):
        return True
    return rel_path.startswith(_SKIP_PATH_PREFIXES)


def iter_target_files(root: Path):
    for py_file in sorted(root.rglob("*.py")):
        rel = py_file.relative_to(root).as_posix()
        if not _should_skip(rel, py_file):
            yield py_file


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    fixed_files: list[str] = []
    for py_file in iter_target_files(root):
        try:
            count = fix_file(py_file)
        except (SyntaxError, UnicodeDecodeError):
            continue
        if count:
            fixed_files.append(py_file.relative_to(root).as_posix())

    if fixed_files:
        for f in fixed_files:
            print(f"Fixed: {f}")
    else:
        print("No auto-fixable patterns found")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
