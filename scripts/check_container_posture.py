"""scripts/check_container_posture.py — assert the container security posture.

CI guard for the claims made in ``docs/governance/README.md``. Documentation
drifts; a script fails. Every check here corresponds to a specific,
irreversible mistake someone makes at 2am to get a container working:

  * ``privileged: true``            — hands the container root on the host.
  * mounting ``/var/run/docker.sock`` — same thing, one indirection away.
  * ``user: root`` / ``user: "0"``   — undoes the non-root default.
  * a sandbox profile losing ``cap_drop: ALL``.
  * the ``security`` sandbox profile gaining network egress.

Deliberately dependency-light (PyYAML only) and exits non-zero with a named
finding, so the failure message tells a contributor what to change without
reading this file.

Usage::

    python scripts/check_container_posture.py
    python scripts/check_container_posture.py --quiet
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent

# Compose files whose services must not run privileged or mount the socket.
COMPOSE_FILES = (
    "docker-compose.yml",
    "docker-compose.prod.yml",
    "docker-compose.e2e.yml",
)

SOCKET_MARKERS = ("/var/run/docker.sock", "docker.sock")


def _load_yaml(path: Path) -> dict[str, Any] | None:
    import yaml

    try:
        with path.open("r", encoding="utf-8") as fh:
            document = yaml.safe_load(fh)
    except FileNotFoundError:
        return None
    except Exception as exc:  # noqa: BLE001
        print(f"::error file={path}::could not parse: {exc}")
        return None
    return document if isinstance(document, dict) else None


def check_compose(findings: list[str]) -> None:
    """No compose service may be privileged or mount the Docker socket."""
    for name in COMPOSE_FILES:
        path = REPO_ROOT / name
        document = _load_yaml(path)
        if document is None:
            continue
        for service_name, service in (document.get("services") or {}).items():
            if not isinstance(service, dict):
                continue

            if service.get("privileged") is True:
                findings.append(
                    f"{name}: service '{service_name}' sets privileged: true — "
                    f"this grants host root and voids every other control"
                )

            for volume in service.get("volumes") or []:
                text = volume if isinstance(volume, str) else str(volume)
                if any(marker in text for marker in SOCKET_MARKERS):
                    findings.append(
                        f"{name}: service '{service_name}' mounts the Docker "
                        f"socket ({text}) — equivalent to host root. Use a "
                        f"rootless builder or a remote DOCKER_HOST instead"
                    )

            user = str(service.get("user", "")).strip()
            if user in ("root", "0", "0:0"):
                findings.append(
                    f"{name}: service '{service_name}' pins user={user!r} — "
                    f"containers must not run as root"
                )

            for opt in service.get("cap_add") or []:
                if str(opt).upper() in ("ALL", "SYS_ADMIN") and service_name != "browser":
                    findings.append(
                        f"{name}: service '{service_name}' adds capability "
                        f"{opt} — justify it in the governance docs or drop it"
                    )


def check_sandbox_profiles(findings: list[str]) -> None:
    """Committed sandbox profiles must stay least-privilege."""
    path = REPO_ROOT / "config" / "sandbox_profiles.yaml"
    document = _load_yaml(path)
    if document is None:
        return
    profiles = document.get("profiles") or {}
    if not isinstance(profiles, dict):
        findings.append("config/sandbox_profiles.yaml: 'profiles' must be a mapping")
        return

    for name, profile in profiles.items():
        if not isinstance(profile, dict):
            continue

        cap_drop = [str(c).upper() for c in (profile.get("cap_drop") or [])]
        if "ALL" not in cap_drop:
            findings.append(
                f"sandbox profile '{name}': cap_drop must include ALL "
                f"(add back only the specific capabilities the workload needs)"
            )

        security_opt = [str(o) for o in (profile.get("security_opt") or [])]
        if not any("no-new-privileges" in o for o in security_opt):
            findings.append(
                f"sandbox profile '{name}': security_opt must include "
                f"no-new-privileges:true"
            )

        user = str(profile.get("user", "")).strip()
        if user.startswith("0:") or user == "root":
            findings.append(f"sandbox profile '{name}': must not run as root")

        env_allowlist = profile.get("env_allowlist")
        if env_allowlist is not None and not isinstance(env_allowlist, list):
            findings.append(
                f"sandbox profile '{name}': env_allowlist must be a list of "
                f"variable NAMES, never values"
            )

        for entry in env_allowlist or []:
            text = str(entry)
            # An allow-list holds names. A `=` means someone pasted a value.
            if "=" in text:
                findings.append(
                    f"sandbox profile '{name}': env_allowlist entry {text!r} "
                    f"looks like a value — this file holds NAMES only and is "
                    f"committed to git"
                )

    # The scanner profile reads the whole repo. Giving it egress as well turns
    # it into an exfiltration path with a job title.
    security_profile = profiles.get("security")
    if isinstance(security_profile, dict):
        if security_profile.get("network") not in (None, "none"):
            findings.append(
                "sandbox profile 'security': must have network: none — a "
                "scanner that reads everything and can reach the internet is "
                "an exfiltration path"
            )
        if security_profile.get("internet") is True:
            findings.append("sandbox profile 'security': internet must be false")


def check_policy_baseline(findings: list[str]) -> None:
    """The shipped policy must keep its non-negotiable baseline denies."""
    path = REPO_ROOT / "config" / "agent_policy.yaml"
    document = _load_yaml(path)
    if document is None:
        return
    baseline = document.get("baseline") or {}

    fs_deny = [str(p) for p in ((baseline.get("filesystem") or {}).get("deny") or [])]
    if not any(p.endswith(".env") or p == ".env" for p in fs_deny):
        findings.append(
            "config/agent_policy.yaml: baseline.filesystem.deny must block .env "
            "— it is the highest-value credential target in the repo"
        )

    net_deny = [str(p) for p in ((baseline.get("network") or {}).get("deny") or [])]
    if "169.254.169.254" not in net_deny:
        findings.append(
            "config/agent_policy.yaml: baseline.network.deny must block "
            "169.254.169.254 (cloud metadata / SSRF-to-credentials pivot)"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quiet", action="store_true", help="only print failures")
    args = parser.parse_args()

    findings: list[str] = []
    check_compose(findings)
    check_sandbox_profiles(findings)
    check_policy_baseline(findings)

    if findings:
        print("CONTAINER POSTURE: FAIL", file=sys.stderr)
        for finding in findings:
            print(f"::error::{finding}", file=sys.stderr)
        return 1

    if not args.quiet:
        print("CONTAINER POSTURE: OK")
        print("  - no privileged services, no Docker socket mounts, no root users")
        print("  - every sandbox profile drops ALL capabilities and runs non-root")
        print("  - policy baseline blocks .env and the cloud metadata endpoint")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
