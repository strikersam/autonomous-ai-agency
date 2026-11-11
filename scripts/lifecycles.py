#!/usr/bin/env python3
"""scripts/lifecycles.py — inspect, export and check the app's lifecycles.

Examples::

    python scripts/lifecycles.py list
    python scripts/lifecycles.py show task
    python scripts/lifecycles.py show task --json
    python scripts/lifecycles.py mermaid task
    python scripts/lifecycles.py docs --write
    python scripts/lifecycles.py check

``check`` fails when the generated ``docs/lifecycles.md`` no longer matches the
declarations, so the map cannot go stale between commits.  It also compares
every bound status type (an enum or a ``Literal`` alias) with its declared
states, so a member added on one side and forgotten on the other is an error
rather than a state nobody can read.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from packages.lifecycle.catalogue import CATALOGUE_FINDINGS  # noqa: E402
from packages.lifecycle.registry import all_machines, get_machine  # noqa: E402
from packages.lifecycle.render import mermaid, render_markdown  # noqa: E402
from packages.lifecycle.status_types import inspect as inspect_status_type  # noqa: E402
from packages.lifecycle.status_types import reports as status_type_reports  # noqa: E402

DOC_PATH = ROOT / "docs" / "lifecycles.md"


def _json_requested(args: argparse.Namespace) -> bool:
    """Accept ``--json`` before or after the subcommand (both read naturally)."""
    return bool(getattr(args, "json_output", False) or getattr(args, "json_top", False))


def _list(as_json: bool) -> int:
    machines = all_machines()
    if as_json:
        print(json.dumps([machine.as_dict() for machine in machines], indent=2))
        return 0
    width = max(len(machine.name) for machine in machines)
    print(f"{len(machines)} lifecycles (owner -> initial, states, resting)")
    for machine in machines:
        resting = ", ".join(sorted(machine.terminal)) or "-"
        print(
            f"{machine.name:<{width}}  {machine.owner}\n"
            f"{'':<{width}}  {len(machine.states)} states, initial {machine.initial}, resting {resting}"
        )
    return 0


def _show(name: str, as_json: bool) -> int:
    machine = get_machine(name)
    if as_json:
        print(json.dumps(machine.as_dict(), indent=2))
        return 0
    print(f"{machine.name}\n{machine.description}\n")
    print(f"owner:   {machine.owner}")
    if machine.status_type:
        report = inspect_status_type(machine)
        verdict = report.describe() if report is not None and not report.ok else "matches"
        print(f"status:  {machine.status_type} ({verdict})")
    print(f"initial: {machine.initial}")
    print(f"resting: {', '.join(sorted(machine.terminal)) or '-'}")
    print("\nmoves:")
    for source in sorted(machine.states):
        targets = ", ".join(machine.allowed(source)) or "- (resting)"
        marker = " (resting)" if machine.is_terminal(source) else ""
        print(f"  {source}{marker}: {targets}")
    if machine.notes:
        print("\nnotes:")
        for note in machine.notes:
            print(f"  - {note}")
    return 0


def _rendered_doc() -> str:
    return render_markdown(all_machines(), CATALOGUE_FINDINGS)


def _docs(write: bool) -> int:
    rendered = _rendered_doc()
    if write:
        DOC_PATH.parent.mkdir(parents=True, exist_ok=True)
        DOC_PATH.write_text(rendered, encoding="utf-8")
        print(f"wrote {DOC_PATH.relative_to(ROOT)} ({len(all_machines())} lifecycles)")
        return 0
    print(rendered, end="")
    return 0


def _check() -> int:
    if not DOC_PATH.exists():
        print(
            f"STALE: {DOC_PATH.relative_to(ROOT)} is missing; "
            "run python scripts/lifecycles.py docs --write",
            file=sys.stderr,
        )
        return 1
    current = DOC_PATH.read_text(encoding="utf-8")
    rendered = _rendered_doc()
    if current != rendered:
        print(
            f"STALE: {DOC_PATH.relative_to(ROOT)} does not match the declarations; "
            "run python scripts/lifecycles.py docs --write",
            file=sys.stderr,
        )
        return 1
    reports = status_type_reports(all_machines())
    drifted = [report for report in reports if not report.ok]
    if drifted:
        for report in drifted:
            print(f"MISMATCH: {report.describe()}", file=sys.stderr)
        return 1
    print(
        f"OK: {len(all_machines())} lifecycles, {DOC_PATH.relative_to(ROOT)} is current, "
        f"{len(reports)} status types match"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", dest="json_top", help="machine-readable output")
    sub = parser.add_subparsers(dest="command")

    list_parser = sub.add_parser("list", help="one summary per lifecycle")
    list_parser.add_argument("--json", action="store_true", dest="json_output", help="machine-readable output")
    show = sub.add_parser("show", help="states and legal moves for one lifecycle")
    show.add_argument("name")
    show.add_argument("--json", action="store_true", dest="json_output", help="machine-readable output")
    diagram = sub.add_parser("mermaid", help="Mermaid state diagram for one lifecycle")
    diagram.add_argument("name")
    docs = sub.add_parser("docs", help="print the generated Markdown map")
    docs.add_argument("--write", action="store_true", help="write docs/lifecycles.md")
    sub.add_parser("check", help="fail when docs/lifecycles.md is stale")

    args = parser.parse_args(argv)
    try:
        if args.command in (None, "list"):
            return _list(_json_requested(args))
        if args.command == "show":
            return _show(args.name, _json_requested(args))
        if args.command == "mermaid":
            print(mermaid(get_machine(args.name)))
            return 0
        if args.command == "docs":
            return _docs(args.write)
        if args.command == "check":
            return _check()
    except KeyError as exc:
        print(f"error: {exc.args[0] if exc.args else exc}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
