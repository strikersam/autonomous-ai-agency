"""Rule 49 (independent verification before "done") must read the same in every
agent instruction file, and every CRISPY role prompt must carry it."""
from __future__ import annotations

import importlib.util
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent


def _checker():
    spec = importlib.util.spec_from_file_location(
        "check_verification_rule", ROOT / "scripts" / "check_verification_rule.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_every_mirror_matches_claude_md() -> None:
    assert _checker().main() == 0


def test_a_drifted_mirror_is_caught(tmp_path, monkeypatch) -> None:
    mod = _checker()
    (tmp_path / "CLAUDE.md").write_text(f"{mod.START}\nrule\n{mod.END}\n")
    for m in mod.MIRRORS:
        (tmp_path / m).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / m).write_text(f"{mod.START}\nrule\n{mod.END}\n")
    (tmp_path / "GEMINI.md").write_text(f"{mod.START}\nedited rule\n{mod.END}\n")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    assert mod.main() == 1


def test_role_prompts_carry_rule_49() -> None:
    from agents.profiles import STANDING_INSTRUCTIONS_NOTICE

    assert "Rule 49" in STANDING_INSTRUCTIONS_NOTICE
    assert "PASS" in STANDING_INSTRUCTIONS_NOTICE
