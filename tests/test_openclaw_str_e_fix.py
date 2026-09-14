"""tests/test_openclaw_str_e_fix.py

Root-cause fix for PR #1486: the OpenClaw weekly auto-fix workflow used a
blanket regex that rewrote *every* ``HTTPException(detail=str(exc))`` call to
a generic message, regardless of status code or exception type. That turned
two deliberately-authored, safe 400/404 ``ValueError`` messages into a
nonsensical "Internal server error" with no security benefit.

These tests lock down ``.github/scripts/openclaw_str_e_fix.py``: it must only
rewrite a call site when the exception is caught by a genuinely broad handler
(bare ``except:`` / ``except Exception``) *and* the response status is a real
5xx — never a specific exception type, and never a 4xx.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_SCRIPT = _ROOT / ".github" / "scripts" / "openclaw_str_e_fix.py"

_spec = importlib.util.spec_from_file_location("openclaw_str_e_fix", _SCRIPT)
osf = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = osf
_spec.loader.exec_module(osf)  # type: ignore[union-attr]


# ── The exact PR #1486 regressions must NOT be touched ──────────────────────

def test_value_error_400_is_left_untouched():
    source = (
        "try:\n"
        "    pass\n"
        "except ValueError as exc:\n"
        '    raise HTTPException(status_code=400, detail=str(exc)) from None\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 0
    assert new_source == source


def test_value_error_404_is_left_untouched():
    source = (
        "try:\n"
        "    pass\n"
        "except ValueError as exc:\n"
        '    raise HTTPException(status_code=404, detail=str(exc)) from exc\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 0
    assert new_source == source


# ── The pattern this bot legitimately exists to fix ──────────────────────────

def test_broad_except_with_5xx_is_rewritten():
    source = (
        "try:\n"
        "    pass\n"
        "except Exception as e:\n"
        '    raise HTTPException(status_code=500, detail=str(e)) from e\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 1
    assert 'detail="Internal server error"' in new_source
    assert "str(e)" not in new_source


def test_bare_except_cannot_be_fixed_and_is_left_untouched():
    """A bare `except:` binds no name, so `str(exc)` inside one can never be
    the caught exception — there is nothing safe to match against."""
    source = (
        "try:\n"
        "    pass\n"
        "except:\n"
        '    raise HTTPException(status_code=502, detail=str(exc)) from None\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 0
    assert new_source == source


def test_base_exception_with_5xx_is_rewritten():
    source = (
        "try:\n"
        "    pass\n"
        "except BaseException as e:\n"
        '    raise HTTPException(status_code=503, detail=str(e)) from e\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 1


# ── Other reasons NOT to touch a call site ───────────────────────────────────

def test_broad_except_but_4xx_is_left_untouched():
    """Even a broad except shouldn't relabel a client error as a server fault."""
    source = (
        "try:\n"
        "    pass\n"
        "except Exception as e:\n"
        '    raise HTTPException(status_code=400, detail=str(e)) from e\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 0
    assert new_source == source


def test_specific_custom_exception_is_left_untouched():
    source = (
        "try:\n"
        "    pass\n"
        "except KeyError as e:\n"
        '    raise HTTPException(status_code=500, detail=str(e)) from e\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 0


def test_detail_not_wrapping_the_caught_exception_is_left_untouched():
    """str(other_var) that isn't the caught exception name must not be touched."""
    source = (
        "try:\n"
        "    pass\n"
        "except Exception as e:\n"
        '    raise HTTPException(status_code=500, detail=str(other_var)) from e\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 0


def test_no_op_on_source_with_no_http_exceptions():
    source = "x = 1\ny = 2\n"
    new_source, count = osf.fix_source(source)
    assert count == 0
    assert new_source == source


def test_syntax_error_returns_unchanged_source():
    source = "def f(:\n"
    new_source, count = osf.fix_source(source)
    assert count == 0
    assert new_source == source


# ── Multi-line and multi-occurrence handling ─────────────────────────────────

def test_multiline_raise_is_rewritten():
    source = (
        "try:\n"
        "    pass\n"
        "except Exception as e:\n"
        "    raise HTTPException(\n"
        "        status_code=500,\n"
        "        detail=str(e),\n"
        "    ) from e\n"
    )
    new_source, count = osf.fix_source(source)
    assert count == 1
    assert 'detail="Internal server error"' in new_source
    assert "str(e)" not in new_source
    # Surrounding structure (the multi-line call, trailing comma) survives.
    assert "status_code=500," in new_source
    assert ") from e" in new_source


def test_multiple_call_sites_in_one_file_all_rewritten():
    source = (
        "try:\n"
        "    pass\n"
        "except Exception as e:\n"
        '    raise HTTPException(status_code=500, detail=str(e)) from e\n'
        "\n"
        "try:\n"
        "    pass\n"
        "except Exception as exc:\n"
        '    raise HTTPException(status_code=503, detail=str(exc)) from exc\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 2
    assert new_source.count('detail="Internal server error"') == 2


def test_mixed_safe_and_unsafe_in_same_file():
    source = (
        "try:\n"
        "    pass\n"
        "except ValueError as exc:\n"
        '    raise HTTPException(status_code=400, detail=str(exc)) from None\n'
        "\n"
        "try:\n"
        "    pass\n"
        "except Exception as e:\n"
        '    raise HTTPException(status_code=500, detail=str(e)) from e\n'
    )
    new_source, count = osf.fix_source(source)
    assert count == 1
    # The ValueError/400 site is untouched.
    assert "detail=str(exc)) from None" in new_source
    # The broad-except/500 site is rewritten.
    assert 'detail="Internal server error") from e' in new_source


# ── File-walking / skip rules ────────────────────────────────────────────────

def test_iter_target_files_skips_tests_and_vendor_dirs(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("x = 1\n")
    (tmp_path / ".venv").mkdir()
    (tmp_path / ".venv" / "y.py").write_text("y = 1\n")
    (tmp_path / "app.py").write_text("z = 1\n")

    found = {p.relative_to(tmp_path).as_posix() for p in osf.iter_target_files(tmp_path)}
    assert found == {"app.py"}


def test_fix_file_writes_only_when_changed(tmp_path):
    target = tmp_path / "handler.py"
    target.write_text(
        "try:\n"
        "    pass\n"
        "except Exception as e:\n"
        '    raise HTTPException(status_code=500, detail=str(e)) from e\n'
    )
    count = osf.fix_file(target)
    assert count == 1
    assert 'detail="Internal server error"' in target.read_text()


def test_fix_file_no_write_when_nothing_to_fix(tmp_path):
    target = tmp_path / "handler.py"
    original = (
        "try:\n"
        "    pass\n"
        "except ValueError as exc:\n"
        '    raise HTTPException(status_code=400, detail=str(exc)) from None\n'
    )
    target.write_text(original)
    count = osf.fix_file(target)
    assert count == 0
    assert target.read_text() == original
