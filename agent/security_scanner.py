"""agent/security_scanner.py — Security & Vulnerability Scanner

Runs static analysis and dependency audits on the codebase, returning
structured findings that ImprovementLoop registers as SECURITY-category
DetectedIssue entries.

Scanners:
  bandit   — Python SAST (common insecure patterns, hardcoded secrets)
  safety   — Known CVEs in requirements.txt / installed packages
  secrets  — grep-based search for accidentally committed credentials

All runners are optional: if the tool is not installed, that scan is skipped
and a WARNING is logged.  Results are always returned as a list of dicts
suitable for the improvement loop.
"""
from __future__ import annotations

import json
import logging
import os
import re
import secrets as _sec
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger("qwen-proxy")

_REPO_ROOT = Path(__file__).parent.parent

# Patterns that suggest a committed secret or credential.
_SECRET_PATTERNS: list[tuple[str, str]] = [
    (r"(?i)(api_key|apikey|api-key)\s*=\s*['\"][A-Za-z0-9_\-]{20,}['\"]", "Potential hardcoded API key"),
    (r"(?i)(secret|password|passwd|pwd)\s*=\s*['\"][^'\"]{8,}['\"]", "Potential hardcoded secret/password"),
    (r"(?i)bearer\s+[A-Za-z0-9_\-\.]{20,}", "Potential hardcoded Bearer token"),
    (r"(?i)(private_key|privatekey)\s*=", "Potential private key reference"),
    (r"sk-[A-Za-z0-9]{32,}", "Possible OpenAI/Anthropic API key pattern"),
]

# Files and directories to exclude from scanning.
_EXCLUDE_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
_EXCLUDE_FILES = {"generate_api_key.py"}


@dataclass
class SecurityFinding:
    scanner: str          # "bandit" | "safety" | "secrets"
    severity: str         # "high" | "medium" | "low"
    title: str
    description: str
    file_path: str | None = None
    line_number: int | None = None
    cve: str | None = None
    finding_id: str = field(default_factory=lambda: "sec_" + _sec.token_hex(4))

    def as_dict(self) -> dict[str, Any]:
        return {
            "finding_id": self.finding_id,
            "scanner": self.scanner,
            "severity": self.severity,
            "title": self.title,
            "description": self.description,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "cve": self.cve,
        }

    def to_issue_instruction(self) -> str:
        parts = [
            f"Fix the following security finding detected by `{self.scanner}`.",
            f"\n**Finding:** {self.title}",
            f"**Severity:** {self.severity}",
            f"**Description:** {self.description}",
        ]
        if self.file_path:
            parts.append(f"**File:** {self.file_path}")
        if self.line_number:
            parts.append(f"**Line:** {self.line_number}")
        if self.cve:
            parts.append(f"**CVE:** {self.cve}")
        parts += [
            "\nPlease:",
            "1. Understand the security risk thoroughly.",
            "2. Apply the minimum correct fix — do not introduce regressions.",
            "3. Add a test that verifies the fix (or documents why one isn't needed).",
            "4. Update docs/changelog.md under `### Security`.",
        ]
        return "\n".join(parts)


class SecurityScanner:
    """Run security scans and return structured findings.

    Usage::

        scanner = SecurityScanner()
        findings = scanner.run_all()
        for f in findings:
            print(f.severity, f.title)
    """

    def __init__(self, repo_root: Path = _REPO_ROOT) -> None:
        self._root = repo_root

    def run_all(self) -> list[SecurityFinding]:
        """Run all available scanners and aggregate results."""
        findings: list[SecurityFinding] = []
        findings.extend(self._run_bandit())
        findings.extend(self._run_safety())
        findings.extend(self._run_secret_grep())
        log.info("SecurityScanner: %d findings total", len(findings))
        return findings

    def run_harness_audit(self) -> dict[str, Any]:
        """Run a cross-harness security audit.

        Checks that the agent harness configuration follows security best
        practices for Claude Code, Cursor, Codex, OpenCode, and other
        supported harnesses. Returns a structured audit report.
        """
        report: dict[str, Any] = {
            "audit_id": "harness_" + _sec.token_hex(4),
            "timestamp": _now(),
            "harnesses": {},
            "overall_score": 0,
            "findings": [],
        }

        harnesses = {
            "claude_code": self._root / ".claude",
            "cursor": self._root / ".cursor",
            "codex": self._root,
            "opencode": self._root / ".opencode",
        }

        checks_passed = 0
        checks_total = 0

        for harness_name, harness_dir in harnesses.items():
            harness_result: dict[str, Any] = {
                "configured": harness_dir.exists(),
                "checks": [],
                "score": 0,
            }
            h_checks = 0
            h_passed = 0

            # Check: Skills directory
            skills_dir = self._root / ".claude" / "skills"
            if harness_name == "claude_code":
                h_checks += 1
                if skills_dir.exists() and list(skills_dir.rglob("SKILL.md")):
                    h_passed += 1
                    harness_result["checks"].append({
                        "check": "skills_directory",
                        "passed": True,
                        "message": f"Found {len(list(skills_dir.rglob('SKILL.md')))} skills",
                    })
                else:
                    harness_result["checks"].append({
                        "check": "skills_directory",
                        "passed": False,
                        "message": "No skills directory or SKILL.md files",
                    })

            # Check: State directory
            state_dir = self._root / ".claude" / "state"
            if harness_name == "claude_code":
                h_checks += 1
                if state_dir.exists():
                    h_passed += 1
                    harness_result["checks"].append({
                        "check": "state_directory",
                        "passed": True,
                        "message": "State directory present",
                    })
                else:
                    harness_result["checks"].append({
                        "check": "state_directory",
                        "passed": False,
                        "message": "State directory missing",
                    })

            # Check: No hardcoded secrets
            h_checks += 1
            if harness_dir.exists():
                secret_count = 0
                for env_file in harness_dir.rglob("*.env"):
                    try:
                        content = env_file.read_text(errors="replace")
                        if any(p in content for p in ("API_KEY=", "SECRET=", "TOKEN=")):
                            secret_count += 1
                    except OSError:
                        pass
                if secret_count == 0:
                    h_passed += 1
                    harness_result["checks"].append({
                        "check": "no_hardcoded_secrets",
                        "passed": True,
                        "message": "No hardcoded secrets in config",
                    })
                else:
                    harness_result["checks"].append({
                        "check": "no_hardcoded_secrets",
                        "passed": False,
                        "message": f"Found {secret_count} files with potential secrets",
                    })
            else:
                h_passed += 1
                harness_result["checks"].append({
                    "check": "no_hardcoded_secrets",
                    "passed": True,
                    "message": "Harness not configured",
                })

            # Check: AGENTS.md exists
            if harness_name == "claude_code":
                agents_md = self._root / "AGENTS.md"
                h_checks += 1
                if agents_md.exists():
                    try:
                        content = agents_md.read_text(errors="replace")
                        if len(content) > 500:
                            h_passed += 1
                            harness_result["checks"].append({
                                "check": "agents_md",
                                "passed": True,
                                "message": f"AGENTS.md present ({len(content)} chars)",
                            })
                        else:
                            harness_result["checks"].append({
                                "check": "agents_md",
                                "passed": False,
                                "message": "AGENTS.md too short",
                            })
                    except OSError:
                        harness_result["checks"].append({
                            "check": "agents_md",
                            "passed": False,
                            "message": "AGENTS.md unreadable",
                        })
                else:
                    harness_result["checks"].append({
                        "check": "agents_md",
                        "passed": False,
                        "message": "AGENTS.md missing",
                    })
            else:
                h_passed += 1
                h_checks += 1
                harness_result["checks"].append({
                    "check": "agents_md",
                    "passed": True,
                    "message": "N/A for non-Claude harness",
                })

            harness_result["score"] = round(h_passed / max(1, h_checks) * 100, 1)
            report["harnesses"][harness_name] = harness_result
            checks_passed += h_passed
            checks_total += h_checks

        report["overall_score"] = round(checks_passed / max(1, checks_total) * 100, 1)
        security_findings = self.run_all()
        report["findings"] = [f.as_dict() for f in security_findings]
        report["security_findings_count"] = len(security_findings)

        log.info(
            "SecurityScanner/harness_audit: overall=%.1f%% findings=%d",
            report["overall_score"], len(security_findings),
        )
        return report

    # ── Bandit (SAST) ─────────────────────────────────────────────────────────

    def _run_bandit(self) -> list[SecurityFinding]:
        if not _tool_available("bandit"):
            log.debug("SecurityScanner: bandit not installed — skipping SAST")
            return []
        try:
            result = subprocess.run(
                [
                    "bandit", "-r", ".",
                    "--format", "json",
                    "--quiet",
                    "--exclude", ".git,.venv,venv,node_modules,tests",
                    "-ll",  # report medium and high severity only
                ],
                capture_output=True,
                text=True,
                cwd=str(self._root),
                timeout=120,
            )
            raw = result.stdout.strip()
            if not raw:
                return []
            data = json.loads(raw)
            findings = []
            for issue in data.get("results", [])[:20]:  # cap at 20
                sev_map = {"HIGH": "high", "MEDIUM": "medium", "LOW": "low"}
                sev = sev_map.get(issue.get("issue_severity", "MEDIUM"), "medium")
                findings.append(SecurityFinding(
                    scanner="bandit",
                    severity=sev,
                    title=f"[{issue.get('test_id')}] {issue.get('issue_text', '')[:80]}",
                    description=(
                        f"{issue.get('issue_text', '')}\n\n"
                        f"Confidence: {issue.get('issue_confidence', 'UNKNOWN')}\n"
                        f"Test: `{issue.get('test_id')}` — {issue.get('test_name', '')}"
                    ),
                    file_path=issue.get("filename"),
                    line_number=issue.get("line_number"),
                ))
            log.info("SecurityScanner/bandit: %d findings", len(findings))
            return findings
        except json.JSONDecodeError:
            log.debug("SecurityScanner: bandit produced no JSON output")
        except subprocess.TimeoutExpired:
            log.warning("SecurityScanner: bandit timed out")
        except Exception as exc:
            log.warning("SecurityScanner: bandit error: %s", exc)
        return []

    # ── Safety (dependency CVEs) ──────────────────────────────────────────────

    def _run_safety(self) -> list[SecurityFinding]:
        if not _tool_available("safety"):
            log.debug("SecurityScanner: safety not installed — skipping dependency audit")
            return []
        req_file = self._root / "requirements.txt"
        if not req_file.exists():
            return []
        try:
            result = subprocess.run(
                ["safety", "check", "--file", str(req_file), "--json"],
                capture_output=True,
                text=True,
                cwd=str(self._root),
                timeout=60,
            )
            raw = result.stdout.strip()
            if not raw:
                return []
            data = json.loads(raw)
            # Safety v3 format: list of vulnerability dicts
            vulns = data if isinstance(data, list) else data.get("vulnerabilities", [])
            findings = []
            for v in vulns[:15]:
                pkg = v.get("package_name") or v.get("name") or "unknown"
                installed = v.get("analyzed_version") or v.get("installed_version") or "?"
                cve = v.get("cve") or ""
                advisory = v.get("advisory") or v.get("description") or ""
                findings.append(SecurityFinding(
                    scanner="safety",
                    severity="high",
                    title=f"CVE in {pkg} {installed}: {(advisory[:60] + '…') if len(advisory) > 60 else advisory}",
                    description=(
                        f"Package `{pkg}` version `{installed}` has a known vulnerability.\n\n"
                        f"Advisory: {advisory[:400]}\n"
                        f"Fix: upgrade to `{v.get('fixed_versions', ['latest'])[0] if v.get('fixed_versions') else 'latest'}`"
                    ),
                    cve=cve,
                ))
            log.info("SecurityScanner/safety: %d CVEs found", len(findings))
            return findings
        except json.JSONDecodeError:
            log.debug("SecurityScanner: safety produced no JSON output")
        except subprocess.TimeoutExpired:
            log.warning("SecurityScanner: safety timed out")
        except Exception as exc:
            log.warning("SecurityScanner: safety error: %s", exc)
        return []

    # ── Secret grep ───────────────────────────────────────────────────────────

    def _run_secret_grep(self) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        py_files = [
            f for f in self._root.rglob("*.py")
            if not any(part in _EXCLUDE_DIRS for part in f.parts)
            and f.name not in _EXCLUDE_FILES
        ]
        for src_file in py_files[:200]:  # cap file set
            try:
                text = src_file.read_text(errors="replace")
            except OSError:
                continue
            for pattern, label in _SECRET_PATTERNS:
                for m in re.finditer(pattern, text):
                    line_no = text[: m.start()].count("\n") + 1
                    # Skip lines that are clearly commented out or test fixtures
                    line = text.splitlines()[line_no - 1] if line_no <= len(text.splitlines()) else ""
                    if line.lstrip().startswith("#"):
                        continue
                    if "test" in str(src_file).lower() and "example" in line.lower():
                        continue
                    findings.append(SecurityFinding(
                        scanner="secrets",
                        severity="high",
                        title=f"{label} in {src_file.relative_to(self._root)}:{line_no}",
                        description=(
                            f"A pattern matching `{label}` was found in "
                            f"`{src_file.relative_to(self._root)}` at line {line_no}.\n\n"
                            f"Snippet: `{line.strip()[:120]}`\n\n"
                            "If this is a real credential, rotate it immediately and move it to an env var."
                        ),
                        file_path=str(src_file.relative_to(self._root)),
                        line_number=line_no,
                    ))
                    if len(findings) >= 10:
                        return findings  # cap early to avoid flooding
        log.info("SecurityScanner/secrets: %d potential secrets found", len(findings))
        return findings


def _tool_available(name: str) -> bool:
    """Return True if *name* is on PATH."""
    import shutil
    return shutil.which(name) is not None


def _now() -> str:
    """Return current UTC timestamp as ISO string."""
    import time as _time
    return _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
