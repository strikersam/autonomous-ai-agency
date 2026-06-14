"""tools.py — WorkspaceTools: read/write/search and diff application (risky module)."""
from __future__ import annotations

import difflib
import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from agent.user_memory import UserMemoryStore

from agent.repowise import RepowiseIntelligence


TEXT_EXTENSIONS = {
    ".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".ps1",
    ".sh", ".bat", ".js", ".ts", ".tsx", ".jsx", ".html", ".css", ".scss", ".sql",
    ".xml", ".env",
}


class WorkspaceTools:
    def __init__(
        self,
        root: str | Path | None = None,
        *,
        workspace_root: str | Path | None = None,
    ) -> None:
        # ``workspace_root`` is an alias for ``root`` kept for API/test clarity.
        chosen = workspace_root if workspace_root is not None else root
        self.root = Path(chosen or os.environ.get("AGENT_WORKSPACE_ROOT") or ".").resolve()
        self.workspace_root = str(self.root)
        self.repowise = RepowiseIntelligence(root=self.root)

    def get_answer(self, question: str) -> str:
        """Delegate to RepowiseIntelligence for a natural-language codebase question."""
        return self.repowise.get_answer(question)

    def search_codebase(self, query: str) -> str:
        """Delegate to RepowiseIntelligence for a semantic/text codebase search."""
        return self.repowise.search_codebase(query)

    def get_decision_flownodes(self) -> str:
        """Delegate to RepowiseIntelligence to list architectural decision nodes."""
        return self.repowise.get_decision_flownodes()

    def get_overview(self) -> dict:
        """Return a high-level repository map and hotspot summary."""
        return self.repowise.get_overview()

    def get_context(self, targets: list[str], include: list[str] | None = None) -> str:
        """Return a formatted context block for the given file paths."""
        kwargs = {"include": include} if include is not None else {}
        return self.repowise.get_context(targets, **kwargs)

    def get_risk(self, targets: list[str] | None = None, changed_files: list[str] | None = None) -> dict:
        """Return a risk summary for the workspace or a subset of files."""
        return self.repowise.get_risk(targets=targets, changed_files=changed_files)

    def get_why(self, target: str) -> str:
        """Return git-blame / decision rationale for a file."""
        return self.repowise.get_why(target)

    def _safe_path(self, filepath: str) -> str:
        """Resolve filepath relative to workspace_root, rejecting traversal attempts.

        Uses a strict realpath prefix comparison so that ``..`` segments,
        absolute paths, and sibling-prefix directories (e.g. ``/tmp/root_evil``
        for root ``/tmp/root``) are all rejected.
        """
        root = os.path.realpath(self.workspace_root)
        target = os.path.realpath(os.path.join(root, filepath))
        if not target.startswith(root + os.sep) and target != root:
            raise ValueError(f"Security: path traversal attempt rejected: {filepath!r}")
        return target

    def _resolve_path(self, path: str) -> Path:
        cleaned = path.strip().replace("/", os.sep)
        # Delegate to _safe_path for the security boundary check.
        return Path(self._safe_path(cleaned))

    def list_files(self, path: str = ".", limit: int = 200) -> list[str]:
        target = self._resolve_path(path)
        if target.is_file():
            return [str(target.relative_to(self.root))]
        output: list[str] = []
        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".venv", "node_modules"}]
            for filename in filenames:
                rel = str((Path(dirpath) / filename).relative_to(self.root))
                output.append(rel)
                if len(output) >= limit:
                    return output
        return output

    def read_file(self, path: str, max_chars: int = 12000) -> str:
        target = self._resolve_path(path)
        return target.read_text(encoding="utf-8")[:max_chars]

    def write_file(self, path: str, content: str) -> dict[str, str | int]:
        target = self._resolve_path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return {"path": str(target.relative_to(self.root)), "bytes": len(content.encode("utf-8"))}

    def apply_diff(self, path: str, new_content: str) -> dict[str, str]:
        target = self._resolve_path(path)
        old_content = target.read_text(encoding="utf-8") if target.exists() else ""
        diff = "\n".join(
            difflib.unified_diff(
                old_content.splitlines(),
                new_content.splitlines(),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
                lineterm="",
            )
        )
        self.write_file(path, new_content)
        return {"path": str(target.relative_to(self.root)), "diff": diff}

    def recall_memory(
        self,
        key: str,
        *,
        user_id: str,
        memory_store: UserMemoryStore,
    ) -> str:
        """Return a previously saved memory value, or an empty string if absent."""
        value = memory_store.recall(user_id, key)
        return value if value is not None else ""

    def save_memory(
        self,
        key: str,
        value: str,
        *,
        user_id: str,
        memory_store: UserMemoryStore,
    ) -> str:
        """Persist a key/value pair to the user's profile store."""
        memory_store.save(user_id, key, value)
        return f"Saved '{key}' for {user_id}."

    def head_file(self, path: str, lines: int = 50) -> str:
        """Return the first *lines* lines of a file.

        Just-in-time retrieval: the executor uses this to quickly inspect a
        file's structure without loading the entire content into the context
        window.  If the full file is needed the executor can follow up with
        ``read_file``.

        Recommended by Anthropic's managed-agents article: prefer targeted
        head/search queries over full-file reads during the inspection phase.
        """
        target = self._resolve_path(path)
        text = target.read_text(encoding="utf-8")
        head = "\n".join(text.splitlines()[:lines])
        total = len(text.splitlines())
        suffix = f"\n… ({total - lines} more lines)" if total > lines else ""
        return head + suffix

    def file_index(self, path: str = ".", max_entries: int = 100) -> list[dict[str, str | int]]:
        """Return a lightweight index of files with line counts and sizes.

        This is the 'always-loaded lightweight index' tier from the
        three-tier JIT retrieval hierarchy (Anthropic managed-agents article):
        ~150 chars per entry, always in context, detailed content loaded
        on demand.
        """
        target = self._resolve_path(path)
        entries: list[dict[str, str | int]] = []
        if target.is_file():
            lines = len(target.read_text(encoding="utf-8", errors="ignore").splitlines())
            return [{"path": str(target.relative_to(self.root)), "lines": lines, "bytes": target.stat().st_size}]

        for dirpath, dirnames, filenames in os.walk(target):
            dirnames[:] = [d for d in dirnames if d not in {".git", "__pycache__", ".venv", "node_modules"}]
            for filename in filenames:
                full = Path(dirpath) / filename
                if full.suffix.lower() not in TEXT_EXTENSIONS and full.name not in {".env", ".gitignore"}:
                    continue
                try:
                    content = full.read_text(encoding="utf-8", errors="ignore")
                    line_count = len(content.splitlines())
                    byte_size = full.stat().st_size
                except OSError:
                    continue
                rel = str(full.relative_to(self.root))
                entries.append({"path": rel, "lines": line_count, "bytes": byte_size})
                if len(entries) >= max_entries:
                    return entries
        return entries

    def search_code(self, query: str, limit: int = 20) -> list[dict[str, str | int]]:
        matches: list[dict[str, str | int]] = []
        lowered = query.lower()
        for rel_path in self.list_files(limit=1000):
            p = self.root / rel_path
            if p.suffix.lower() not in TEXT_EXTENSIONS and p.name not in {".env", ".gitignore"}:
                continue
            try:
                text = p.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            for idx, line in enumerate(text.splitlines(), start=1):
                if lowered in line.lower():
                    matches.append({"path": rel_path, "line": idx, "snippet": line.strip()[:240]})
                    if len(matches) >= limit:
                        return matches
        return matches
