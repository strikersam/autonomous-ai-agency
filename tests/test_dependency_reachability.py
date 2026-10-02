"""Tests for agent/dependency_reachability.py and reachability-aware safety findings."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from unittest.mock import patch

from agent.dependency_reachability import first_party_imports, import_names, is_directly_imported
from agent.security_scanner import SecurityScanner


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "app.py").write_text("import yaml\nfrom requests.adapters import HTTPAdapter\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "x.py").write_text("import urllib3\n")
    (tmp_path / "requirements.txt").write_text("requests\npyyaml\n")
    return tmp_path


def test_first_party_imports_skips_vendored_dirs(tmp_path):
    imports = first_party_imports(_repo(tmp_path))
    assert {"yaml", "requests"} <= imports
    assert "urllib3" not in imports


def test_alias_maps_distribution_to_import_name():
    assert "yaml" in import_names("PyYAML")
    assert "jose" in import_names("python_jose")


def test_is_directly_imported(tmp_path):
    imports = first_party_imports(_repo(tmp_path))
    assert is_directly_imported("PyYAML", imports)
    assert is_directly_imported("requests", imports)
    assert not is_directly_imported("urllib3", imports)


def _run_safety_with(root: Path, vulns: list[dict]) -> list:
    done = subprocess.CompletedProcess(args=[], returncode=0, stdout=json.dumps(vulns), stderr="")
    with patch("agent.security_scanner._tool_available", return_value=True), \
         patch("agent.security_scanner.subprocess.run", return_value=done):
        return SecurityScanner(repo_root=root)._run_safety()


def test_transitive_cve_is_medium_and_kept(tmp_path):
    findings = _run_safety_with(_repo(tmp_path), [
        {"package_name": "urllib3", "analyzed_version": "1.0", "advisory": "bad", "cve": "CVE-1"},
        {"package_name": "requests", "analyzed_version": "2.0", "advisory": "worse", "cve": "CVE-2"},
    ])
    by_pkg = {f.cve: f for f in findings}
    assert by_pkg["CVE-2"].severity == "high"
    assert "imported directly" in by_pkg["CVE-2"].description
    assert by_pkg["CVE-1"].severity == "medium"
    assert "likely transitive" in by_pkg["CVE-1"].description


def test_cap_keeps_reachable_cves_first(tmp_path):
    transitive = [{"package_name": f"dep{i}", "advisory": "x", "cve": f"T{i}"} for i in range(20)]
    reachable = {"package_name": "pyyaml", "advisory": "y", "cve": "R1"}
    findings = _run_safety_with(_repo(tmp_path), transitive + [reachable])
    assert len(findings) == 15
    assert findings[0].cve == "R1"
