"""agent/code_graph.py — structural code queries for agents (opt-in).

Wraps the `codebase-memory-mcp <https://github.com/DeusData/codebase-memory-mcp>`_
CLI (MIT, native binary, tree-sitter over 162 languages). It indexes the agent
workspace into a call graph and answers the three questions ``search_code``
and ``repowise`` cannot:

  * ``code_trace``  — who calls this function / what does it call (any language);
  * ``code_impact`` — which functions a branch's diff can break (blast radius);
  * ``code_search`` — find a symbol by name pattern and kind, with its file.

``agent/repowise.py`` is Python-only (it walks ``ast``); client repositories
are JavaScript, Go, Java and the rest as often as Python, and for those the
agent was left grepping. The graph fills that gap without replacing repowise.

Opt-in (``CODE_GRAPH_ENABLED``): the binary is not in the default image, and
indexing a large repository is too heavy for the 512MB Render free tier.
Self-hosted installs enable it with ``pip install codebase-memory-mcp``.

Every call is a list-form subprocess (rule 12) run in a worker thread (rule
25). Arguments are validated before they reach argv so a model-chosen value
can never be read as a CLI flag.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import re
import shutil
import threading
import subprocess  # nosec B404 - list-form argv only, fixed binary
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger("qwen-proxy")

LABELS = frozenset({"Function", "Method", "Class", "Module", "File", "Route"})
DIRECTIONS = frozenset({"inbound", "outbound", "both"})
_SYMBOL_RE = re.compile(r"^[^\s-][^\s]{0,199}$")          # no leading '-', no spaces
_REF_RE = re.compile(r"^[A-Za-z0-9._/][A-Za-z0-9._/~^-]{0,199}$")
_QUERY_TIMEOUT = 60

Runner = Callable[..., "subprocess.CompletedProcess[str]"]


class CodeGraphError(RuntimeError):
    """The graph could not answer — binary missing, index failed, bad input."""


class CodeGraph:
    """One workspace's code graph, indexed lazily and re-indexed on change."""

    def __init__(
        self,
        root: str | Path,
        binary: str = "codebase-memory-mcp",
        index_timeout: int = 180,
        runner: Runner = subprocess.run,
    ) -> None:
        self.root = Path(root).resolve()
        self.binary = binary
        self.index_timeout = index_timeout
        self._run = runner
        self._project: str | None = None
        self._fingerprint: str | None = None
        # Two queries in flight must not start two index runs of one repo.
        self._lock = threading.Lock()

    # ── plumbing ─────────────────────────────────────────────────────────────

    def available(self) -> bool:
        return shutil.which(self.binary) is not None

    def _exec(self, argv: list[str], timeout: int) -> str:
        try:
            proc = self._run(  # nosec B603 - list-form argv, validated values
                [self.binary, "cli", "--quiet", *argv],
                cwd=str(self.root), capture_output=True, text=True,
                timeout=timeout, check=False,
            )
        except FileNotFoundError as exc:
            raise CodeGraphError(f"{self.binary} is not installed") from exc
        except subprocess.TimeoutExpired as exc:
            raise CodeGraphError(f"{argv[0]} timed out after {timeout}s") from exc
        if proc.returncode != 0:
            detail = (proc.stderr or proc.stdout or "").strip().splitlines()
            raise CodeGraphError(detail[-1][:300] if detail else f"{argv[0]} failed")
        return proc.stdout

    def _json(self, argv: list[str], timeout: int = _QUERY_TIMEOUT) -> dict[str, Any]:
        out = self._exec(argv, timeout)
        try:
            data = json.loads(out)
        except json.JSONDecodeError as exc:
            raise CodeGraphError(f"{argv[0]} returned non-JSON output") from exc
        if not isinstance(data, dict):
            raise CodeGraphError(f"{argv[0]} returned an unexpected shape")
        return data

    def _git(self, *args: str) -> str | None:
        try:
            proc = self._run(  # nosec B603 B607 - fixed git argv
                ["git", *args], cwd=str(self.root), capture_output=True,
                text=True, timeout=30, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            return None
        return proc.stdout if proc.returncode == 0 else None

    def _workspace_fingerprint(self) -> str | None:
        """Content of every change since HEAD — the index is stale when it moves.

        ``git status`` alone is not enough: a second edit to an already-dirty
        file leaves it unchanged. So this hashes HEAD, the full diff against
        HEAD, and each untracked file's size and mtime. ``None`` (not a git
        repo) means "cannot tell", which always re-indexes.
        """
        head = self._git("rev-parse", "HEAD")
        if head is None:
            return None
        digest = hashlib.sha256(head.encode())
        digest.update((self._git("diff", "HEAD", "--no-color") or "").encode())
        for rel in (self._git("ls-files", "--others", "--exclude-standard") or "").splitlines():
            try:
                st = (self.root / rel).stat()
                digest.update(f"{rel}\x00{st.st_size}\x00{st.st_mtime_ns}".encode())
            except OSError:
                digest.update(rel.encode())
        return digest.hexdigest()

    def default_base(self) -> str:
        """The remote's default branch (origin/HEAD), else main/master, else HEAD~1."""
        ref = (self._git("symbolic-ref", "--quiet", "--short", "refs/remotes/origin/HEAD") or "").strip()
        if ref:
            return ref
        for candidate in ("main", "master"):
            if self._git("rev-parse", "--verify", "--quiet", candidate) is not None:
                return candidate
        return "HEAD~1"

    def ensure_indexed(self) -> str:
        """Index (incrementally) when the workspace changed; return the project."""
        with self._lock:
            fingerprint = self._workspace_fingerprint()
            if self._project and fingerprint is not None and fingerprint == self._fingerprint:
                return self._project
            result = self._json(
                ["index_repository", "--repo-path", str(self.root)], self.index_timeout
            )
            project = result.get("project")
            if not isinstance(project, str) or not project:
                raise CodeGraphError("index_repository did not name a project")
            self._project, self._fingerprint = project, fingerprint
            return project

    # ── queries (sync; the async wrappers below run them in a thread) ────────

    def trace(self, function_name: str, direction: str = "both", depth: int = 3) -> dict:
        _check_symbol(function_name, "function_name")
        if direction not in DIRECTIONS:
            raise CodeGraphError(f"direction must be one of {sorted(DIRECTIONS)}")
        project = self.ensure_indexed()
        return self._json([
            "trace_path", "--project", project, "--function-name", function_name,
            "--direction", direction, "--depth", str(_clamp(depth, 1, 5)),
            "--format", "json",
        ])

    def search(self, name_pattern: str, label: str | None = None, limit: int = 20) -> dict:
        _check_symbol(name_pattern, "name_pattern")
        argv = ["search_graph", "--project", self.ensure_indexed(),
                "--name-pattern", name_pattern, "--limit", str(_clamp(limit, 1, 100))]
        if label:
            if label not in LABELS:
                raise CodeGraphError(f"label must be one of {sorted(LABELS)}")
            argv += ["--label", label]
        return self._json([*argv, "--format", "json"])

    def impact(self, base_branch: str | None = None) -> dict:
        base_branch = base_branch or self.default_base()
        if not _REF_RE.match(base_branch) or ".." in base_branch:
            raise CodeGraphError("base_branch is not a valid git ref")
        project = self.ensure_indexed()
        return self._json([
            "detect_changes", "--project", project, "--base-branch", base_branch,
            "--format", "json",
        ])


def _check_symbol(value: str, field: str) -> None:
    if not isinstance(value, str) or not _SYMBOL_RE.match(value):
        raise CodeGraphError(f"{field} must be 1-200 non-space chars, not starting with '-'")


def _clamp(value: int, low: int, high: int) -> int:
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError):
        return low


async def run_query(fn: Callable[..., dict], *args: Any, **kwargs: Any) -> dict:
    """Run a graph query off the event loop; errors come back as data."""
    try:
        return await asyncio.to_thread(fn, *args, **kwargs)
    except CodeGraphError as exc:
        return {"error": str(exc)}


_graphs: dict[str, CodeGraph] = {}


def get_code_graph(root: str | Path) -> CodeGraph:
    """Per-workspace singleton, configured from settings (rule 5)."""
    from packages.config import settings

    key = str(Path(root).resolve())
    if key not in _graphs:
        _graphs[key] = CodeGraph(
            key, binary=settings.code_graph_bin,
            index_timeout=settings.code_graph_timeout_seconds,
        )
    return _graphs[key]


def code_graph_enabled() -> bool:
    """True when the operator opted in AND the binary is actually installed."""
    from packages.config import settings

    return settings.code_graph_enabled and shutil.which(settings.code_graph_bin) is not None
