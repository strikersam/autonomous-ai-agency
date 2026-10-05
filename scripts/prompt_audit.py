"""scripts/prompt_audit.py — Audit CLAUDE.md and AGENTS.md for staleness.

Checks two categories of drift:
  (a) File paths referenced in backticks that no longer exist in the repo.
  (b) Model IDs mentioned that are in neither config/models.yaml (routing) nor
      config/llm/models.yaml (the full model catalogue).

A model id immediately followed (or preceded) by "deprecated", "retired" or
"removed" is a deliberate mention and is not flagged; other ids on the same
line still are.

Non-blocking: prints findings to stdout and exits 0.  This is an informational
report, not a hard CI gate — false positives are possible (e.g. a path mentioned
as an example, not as a real file), so review findings before acting on them.

Usage:
    python scripts/prompt_audit.py
    python scripts/prompt_audit.py --files CLAUDE.md AGENTS.md
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


# ── Model ID loading ─────────────────────────────────────────────────────────

def _load_catalogue_ids() -> set[str]:
    """Model ids declared in config/llm/models.yaml (the full catalogue)."""
    path = ROOT / "config" / "llm" / "models.yaml"
    try:
        import yaml  # type: ignore[import-untyped]

        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return set()
    models = data.get("models") if isinstance(data, dict) else None
    return {str(k) for k in models} if isinstance(models, dict) else set()


def _load_model_ids() -> set[str]:
    """Model ids from config/models.yaml candidates/role_presets plus the catalogue."""
    models_yaml = ROOT / "config" / "models.yaml"
    if not models_yaml.exists():
        return set()
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        return set()
    try:
        with open(models_yaml) as fh:
            data = yaml.safe_load(fh)
    except Exception:
        return set()
    ids: set[str] = set()
    providers = (data or {}).get("providers", {}) or {}
    for prov in providers.values():
        if not isinstance(prov, dict):
            continue
        for key in ("candidates", "fallback_candidates"):
            for entry in prov.get(key) or []:
                if isinstance(entry, str):
                    ids.add(entry)
                elif isinstance(entry, dict) and "id" in entry:
                    ids.add(entry["id"])
        presets = prov.get("role_presets") or {}
        if isinstance(presets, dict):
            for v in presets.values():
                if isinstance(v, str):
                    ids.add(v)
    return ids | _load_catalogue_ids()


# ── Path extraction ──────────────────────────────────────────────────────────

# Match backtick-delimited tokens that look like file paths
# (contain a slash or a dot followed by a known extension).
_PATH_RE = re.compile(
    r"`([a-zA-Z0-9_./@-][a-zA-Z0-9_./@ -]*\.[a-zA-Z]{1,6})`"
)
_PATH_EXTS = {
    ".py", ".yaml", ".yml", ".json", ".md", ".txt", ".sh", ".toml",
    ".cfg", ".ini", ".env", ".js", ".ts", ".jsx", ".tsx", ".html",
    ".css", ".sql", ".lock", ".pem", ".crt",
}


# Files that exist only while something runs (a session lock, a pid file).
_RUNTIME_SUFFIXES = {".lock", ".pid"}


def _looks_like_path(token: str) -> bool:
    if Path(token).suffix.lower() not in _PATH_EXTS:
        return False
    # Bare filenames without a directory separator are usually example text.
    return "/" in token or token.startswith(".")


def _check_file_paths(text: str, source: str) -> list[str]:
    findings: list[str] = []
    for m in _PATH_RE.finditer(text):
        # A backticked command (`python scripts/x.py --check`) is checked token
        # by token; the whole string was being reported as one missing path.
        for token in m.group(1).split():
            if not _looks_like_path(token):
                continue
            if Path(token).suffix.lower() in _RUNTIME_SUFFIXES:
                continue
            if not (ROOT / token).exists():
                findings.append(f"  {source}: path `{token}` does not exist")
    return findings


# ── Model ID extraction ──────────────────────────────────────────────────────

# Pattern for model IDs: provider/model-id  or  bare ids with version numbers
# like `claude-sonnet-5`, `nvidia/llama-3.3-nemotron-super-49b-v1`.
_MODEL_RE = re.compile(
    r"`([a-z0-9][a-z0-9._-]*/[a-z0-9][a-z0-9._/-]+|"
    r"(?:claude|gpt|gemini|deepseek|llama|mistral|qwen|nvidia|meta|openai|groq|kimi|gemma|glm|phi)"
    r"[a-z0-9._/-]+)`",
    re.IGNORECASE,
)


_DELIBERATE_MENTION = re.compile(r"deprecat|retired|removed|sunset", re.IGNORECASE)


def _is_path_not_model(candidate: str) -> bool:
    """`handlers/v3_auth.py` and `tests/e2e/` match the provider/model shape."""
    return (
        candidate.endswith("/")
        or Path(candidate).suffix.lower() in _PATH_EXTS
        or (ROOT / candidate).exists()
    )


# How close a deprecation word must be to excuse one id, not the whole line:
# "`deepseek-r1-70b` deprecated" and "retired `x`" excuse only that id.
_MENTION_AFTER = 12
_MENTION_BEFORE = 12


def _check_model_ids(text: str, source: str, known_ids: set[str]) -> list[str]:
    if not known_ids:
        return []
    findings: list[str] = []
    for line in text.splitlines():
        findings.extend(_unknown_models_in(line, source, known_ids))
    return findings


def _deliberate(line: str, start: int, end: int) -> bool:
    window = line[max(0, start - _MENTION_BEFORE):start] + line[end:end + _MENTION_AFTER]
    return bool(_DELIBERATE_MENTION.search(window))


def _unknown_models_in(line: str, source: str, known_ids: set[str]) -> list[str]:
    findings: list[str] = []
    for m in _MODEL_RE.finditer(line):
        candidate = m.group(1).strip()
        if _is_path_not_model(candidate) or _deliberate(line, m.start(), m.end()):
            continue
        # Only flag if it looks like a real model id (has a digit somewhere).
        if not re.search(r"\d", candidate):
            continue
        # Fuzzy check: the candidate or any known id is a substring of the other.
        matched = any(
            candidate.lower() in kid.lower() or kid.lower() in candidate.lower()
            for kid in known_ids
        )
        if not matched:
            findings.append(
                f"  {source}: model `{candidate}` not in config/models.yaml or config/llm/models.yaml"
            )
    return findings


# ── Main ─────────────────────────────────────────────────────────────────────

def audit(files: list[Path]) -> int:
    known_ids = _load_model_ids()
    if not known_ids:
        print("[prompt-audit] WARNING: could not load config/models.yaml — "
              "model-id checks skipped")

    all_findings: list[str] = []
    for path in files:
        if not path.exists():
            print(f"[prompt-audit] SKIP  {path} (not found)")
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        try:
            rel = str(path.relative_to(ROOT))
        except ValueError:
            rel = str(path)
        all_findings.extend(_check_file_paths(text, rel))
        all_findings.extend(_check_model_ids(text, rel, known_ids))

    if all_findings:
        print(f"[prompt-audit] {len(all_findings)} finding(s):\n")
        for f in all_findings:
            print(f)
    else:
        print("[prompt-audit] No staleness found.")

    return 0  # non-blocking: always exit 0


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument(
        "--files", nargs="+", default=["CLAUDE.md", "AGENTS.md"],
        help="Files to audit (default: CLAUDE.md AGENTS.md)",
    )
    args = parser.parse_args()
    files = [ROOT / f for f in args.files]
    sys.exit(audit(files))


if __name__ == "__main__":
    main()
