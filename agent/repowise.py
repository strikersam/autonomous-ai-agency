from __future__ import annotations
import os
import subprocess
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

class RepowiseIntelligence:
    def __init__(self, root: Path):
        self.root = Path(root)

    def get_overview(self) -> Dict[str, Any]:
        """Provides an architecture summary, module map, and git health."""
        return {
            "repository_map": self.get_repository_map(max_depth=2),
            "hotspots": self.get_hotspots(limit=5),
            "entry_points": self.find_entry_points(),
            "git_health": self.get_git_health(),
            "architecture": self.get_architecture_summary()
        }

    def get_repository_map(self, max_depth: int = 3) -> str:
        """Returns a structural overview of the repository."""
        try:
            cmd = ["git", "ls-files"]
            result = subprocess.run(cmd, cwd=self.root, capture_output=True, text=True, check=True)
            files = result.stdout.splitlines()
        except Exception:
            files = []
            for p in self.root.rglob("*"):
                if any(x in p.parts for x in [".git", "__pycache__", ".venv", "node_modules"]):
                    continue
                if p.is_file():
                    files.append(str(p.relative_to(self.root)))

        tree = {}
        for f in files:
            parts = Path(f).parts
            if len(parts) > max_depth + 1:
                continue
            curr = tree
            for part in parts:
                if part not in curr:
                    curr[part] = {}
                curr = curr[part]

        def _render(node: dict, indent: str = "") -> str:
            lines = []
            for name in sorted(node.keys()):
                lines.append(f"{indent}- {name}")
                lines.append(_render(node[name], indent + "  "))
            return "\n".join([l for l in lines if l])

        return _render(tree)

    def get_hotspots(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Identifies frequently changed files using git history."""
        try:
            cmd = "git log --format='' --name-only | sort | uniq -c | sort -rn | head -n " + str(limit)
            result = subprocess.run(cmd, shell=True, cwd=self.root, capture_output=True, text=True)
            hotspots = []
            for line in result.stdout.splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    count, path = parts
                    hotspots.append({"path": path, "changes": int(count)})
            return hotspots
        except Exception:
            return []

    def find_entry_points(self) -> List[str]:
        """Guesses entry points based on file names and common patterns."""
        entry_patterns = ["main.py", "app.py", "server.py", "proxy.py", "index.js", "index.ts", "run.sh", "Makefile"]
        found = []
        for pattern in entry_patterns:
            matches = list(self.root.glob(pattern)) + list(self.root.glob(f"*/{pattern}"))
            for m in matches:
                found.append(str(m.relative_to(self.root)))
        return list(set(found))

    def get_git_health(self) -> Dict[str, Any]:
        """Basic git health metrics."""
        try:
            commit_count = subprocess.run(["git", "rev-list", "--count", "HEAD"],
                                       cwd=self.root, capture_output=True, text=True).stdout.strip()
            author_count = subprocess.run(["git", "log", "--format='%aE'", "|", "sort", "|", "uniq", "|", "wc", "-l"],
                                        shell=True, cwd=self.root, capture_output=True, text=True).stdout.strip()
            return {
                "total_commits": int(commit_count) if commit_count else 0,
                "total_authors": int(author_count) if author_count else 0
            }
        except Exception:
            return {"total_commits": 0, "total_authors": 0}

    def get_architecture_summary(self) -> Dict[str, Any]:
        """Identifies key modules and design patterns."""
        summary = {
            "key_modules": [],
            "patterns": []
        }

        # Look for directories with many files as key modules
        dirs = [d for d in self.root.iterdir() if d.is_dir() and not d.name.startswith((".", "_"))]
        for d in dirs:
            file_count = len(list(d.glob("**/*.py"))) + len(list(d.glob("**/*.js"))) + len(list(d.glob("**/*.ts")))
            if file_count > 2:
                summary["key_modules"].append({"name": d.name, "files": file_count})

        # Look for common patterns
        pattern_indicators = {
            "FastAPI/REST": ["FastAPI", "router", "endpoint"],
            "React/Frontend": ["react", "component", "useState"],
            "Docker": ["Dockerfile", "docker-compose"],
            "Agentic": ["agent", "loop", "tool", "prompt"]
        }

        for name, keywords in pattern_indicators.items():
            for kw in keywords:
                cmd = f"grep -ri '{kw}' . --include='*.py' --include='*.js' --include='*.ts' --include='Dockerfile' --include='*.yaml' --exclude-dir={{.git,__pycache__,.venv,node_modules}} | head -n 1"
                result = subprocess.run(cmd, shell=True, cwd=self.root, capture_output=True, text=True)
                if result.stdout.strip():
                    summary["patterns"].append(name)
                    break

        return summary

    def get_context(self, targets: List[str], include: List[str] = ["source"]) -> str:
        """Workhorse tool for packing content and metrics of target files."""
        output = []
        total_estimated_tokens = 0

        for target in targets:
            # Handle potential symbol:file format
            if ":" in target and not Path(target).exists():
                symbol, file_path = target.split(":", 1)
                path = self.root / file_path
                if path.exists():
                    symbol_content = self._extract_symbol(path, symbol, include)
                    total_estimated_tokens += len(symbol_content) // 4
                    output.append(symbol_content)
                    continue

            path = self.root / target
            if not path.exists():
                # Try as glob
                matches = list(self.root.glob(target))
                for match in matches:
                    file_content = self._pack_file(match, include)
                    total_estimated_tokens += len(file_content) // 4
                    output.append(file_content)
            else:
                file_content = self._pack_file(path, include)
                total_estimated_tokens += len(file_content) // 4
                output.append(file_content)

        prefix = f"<!-- Estimated total tokens: {total_estimated_tokens} -->\n\n"
        return prefix + "\n\n".join([o for o in output if o])

    def _pack_file(self, path: Path, include: List[str]) -> str:
        if not path.is_file():
            return ""

        rel_path = str(path.relative_to(self.root))
        result = [f"<file path=\"{rel_path}\">"]

        if "metrics" in include:
            stats = path.stat()
            result.append(f"<metrics size=\"{stats.st_size}\" />")

        if "callers" in include or "callees" in include:
            result.append(f"<dependencies>\n{self._get_dependencies(path, include)}\n</dependencies>")

        if "source" in include:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                result.append(content)
            except Exception as e:
                result.append(f"Error reading file: {e}")

        result.append("</file>")
        return "\n".join(result)

    def _get_dependencies(self, path: Path, include: List[str]) -> str:
        """Naive dependency extraction."""
        deps = []
        rel_path = str(path.relative_to(self.root))

        if "callees" in include:
            try:
                content = path.read_text(encoding="utf-8", errors="replace")
                imports = re.findall(r"^(?:from|import)\s+([a-zA-Z0-9._-]+)", content, re.MULTILINE)
                for imp in imports:
                    deps.append(f"  - callee: {imp}")
            except Exception:
                pass

        if "callers" in include:
            try:
                module_name = path.stem
                if "__init__" in module_name:
                    module_name = path.parent.name

                cmd = f"grep -lE '(import|from).*\b{module_name}\b' -r . --exclude-dir={{.git,__pycache__,.venv,node_modules}}"
                result = subprocess.run(cmd, shell=True, cwd=self.root, capture_output=True, text=True)
                for caller in result.stdout.splitlines():
                    if caller.strip() and caller != rel_path:
                        deps.append(f"  - caller: {caller}")
            except Exception:
                pass

        return "\n".join(deps)

    def _extract_symbol(self, path: Path, symbol: str, include: List[str]) -> str:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            # Improved regex patterns
            patterns = [
                rf"^class\s+{symbol}\b",
                rf"^def\s+{symbol}\b",
                rf"^\s*async\s+def\s+{symbol}\b",
                rf"function\s+{symbol}\b",
                rf"const\s+{symbol}\s*=",
                rf"let\s+{symbol}\s*=",
                rf"var\s+{symbol}\s*="
            ]

            lines = content.splitlines()
            start_line = -1
            for i, line in enumerate(lines):
                if any(re.search(p, line) for p in patterns):
                    start_line = i
                    break

            if start_line == -1:
                return f"<symbol name=\"{symbol}\" path=\"{path.relative_to(self.root)}\" status=\"not_found\" />"

            # Extract block based on indentation
            indent = len(lines[start_line]) - len(lines[start_line].lstrip())
            block = [lines[start_line]]
            for line in lines[start_line+1:]:
                if not line.strip():
                    block.append(line)
                    continue
                current_indent = len(line) - len(line.lstrip())
                if current_indent <= indent:
                    break
                block.append(line)

            # Trim trailing empty lines
            while block and not block[-1].strip():
                block.pop()

            rel_path = str(path.relative_to(self.root))
            return f"<symbol name=\"{symbol}\" path=\"{rel_path}\">\n" + "\n".join(block) + "\n</symbol>"
        except Exception as e:
            return f"<symbol name=\"{symbol}\" path=\"{path.relative_to(self.root)}\" error=\"{e}\" />"

    def get_risk(self, targets: Optional[List[str]] = None, changed_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Hotspot scores and potential impact analysis."""
        hotspots = {h["path"]: h["changes"] for h in self.get_hotspots(limit=100)}

        relevant_hotspots = []
        if changed_files:
            for f in changed_files:
                if f in hotspots:
                    relevant_hotspots.append({"path": f, "changes": hotspots[f], "risk": "high"})

        return {
            "overall_hotspots": self.get_hotspots(limit=10),
            "impact_analysis": relevant_hotspots
        }

    def get_why(self, target: str) -> str:
        """Extracts architectural decisions related to target from git history."""
        try:
            cmd = f"git log --grep='WHY' --grep='DECISION' --grep='TRADEOFF' -i -- '{target}'"
            result = subprocess.run(cmd, shell=True, cwd=self.root, capture_output=True, text=True)
            if not result.stdout.strip():
                return f"No documented decisions found for {target}"
            return result.stdout
        except Exception as e:
            return f"Error retrieving decisions: {e}"
