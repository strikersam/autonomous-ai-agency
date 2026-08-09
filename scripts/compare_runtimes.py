"""scripts/compare_runtimes.py — head-to-head runtime comparison.

Answers the question that gates promoting a runtime out of TIER_2: does it
actually beat `internal_agent` on the same work? Runs an identical task set
through two or more runtimes and reports success rate, wall time, and tokens.

    python scripts/compare_runtimes.py --runtimes internal_agent prime_agent
    python scripts/compare_runtimes.py --tasks tasks.json --json report.json

**What this measures depends entirely on the provider behind it.** Pointed at a
real LLM it is a capability benchmark. Pointed at a stub it measures only
integration mechanics — that the adapter executes, reports usage, and classifies
success correctly. The report labels which one you got by recording the provider,
so a mechanics run cannot be mistaken later for a capability result.

Exits non-zero when a runtime is unavailable, so CI cannot record a green
comparison against a runtime that never ran.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Any

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtimes.base import TaskSpec  # noqa: E402

# Small, deliberately verifiable default set: each task's success is checkable
# without a model grading it.
DEFAULT_TASKS: list[dict[str, str]] = [
    {"id": "echo", "instruction": "Reply with the single word: ready.", "task_type": "general"},
    {"id": "explain", "instruction": "In one sentence, say what a unit test is.", "task_type": "reasoning"},
    {"id": "summarise", "instruction": "Summarise in one line why retries need backoff.", "task_type": "reasoning"},
]


@dataclass
class RunRecord:
    runtime_id: str
    task_id: str
    success: bool
    duration_s: float
    tokens: int | None = None
    cost_usd: float | None = None
    provider: str | None = None
    model: str | None = None
    error: str | None = None


@dataclass
class RuntimeSummary:
    runtime_id: str
    available: bool
    runs: int = 0
    successes: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    durations: list[float] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    error: str | None = None

    @property
    def success_rate(self) -> float:
        return (self.successes / self.runs) if self.runs else 0.0

    @property
    def median_duration_s(self) -> float:
        return statistics.median(self.durations) if self.durations else 0.0


async def _run_one(adapter: Any, task: dict[str, str], workspace: str, timeout: int) -> RunRecord:
    spec = TaskSpec(
        task_id=task["id"],
        instruction=task["instruction"],
        task_type=task.get("task_type", "general"),
        workspace_path=workspace,
        timeout_sec=timeout,
    )
    started = time.monotonic()
    try:
        result = await adapter.execute(spec)
    except Exception as exc:
        return RunRecord(
            runtime_id=adapter.RUNTIME_ID, task_id=task["id"], success=False,
            duration_s=round(time.monotonic() - started, 2), error=f"{type(exc).__name__}: {exc}",
        )
    return RunRecord(
        runtime_id=adapter.RUNTIME_ID,
        task_id=task["id"],
        success=bool(result.success),
        duration_s=round(time.monotonic() - started, 2),
        tokens=result.tokens_used,
        cost_usd=result.cost_usd,
        provider=result.provider_used,
        model=result.model_used,
        error=None if result.success else str(result.metadata.get("error") or result.output)[:200],
    )


async def compare(
    runtime_ids: list[str], tasks: list[dict[str, str]], workspace: str, timeout: int
) -> tuple[list[RunRecord], dict[str, RuntimeSummary]]:
    from runtimes.manager import get_runtime_manager

    manager = get_runtime_manager()
    records: list[RunRecord] = []
    summaries: dict[str, RuntimeSummary] = {}

    for runtime_id in runtime_ids:
        adapter = manager._registry.get(runtime_id)
        if adapter is None:
            summaries[runtime_id] = RuntimeSummary(
                runtime_id, available=False,
                error=f"not registered — set RUNTIME_{runtime_id.upper()}_ENABLED=true",
            )
            continue
        health = await adapter.health_check()
        summary = RuntimeSummary(runtime_id, available=health.available, error=health.error)
        summaries[runtime_id] = summary
        if not health.available:
            continue
        for task in tasks:
            record = await _run_one(adapter, task, workspace, timeout)
            records.append(record)
            summary.runs += 1
            summary.successes += int(record.success)
            summary.durations.append(record.duration_s)
            summary.total_tokens += record.tokens or 0
            summary.total_cost_usd += record.cost_usd or 0.0
            if record.provider:
                summary.providers.append(record.provider)
    return records, summaries


def render(summaries: dict[str, RuntimeSummary], records: list[RunRecord]) -> str:
    lines = ["", "Runtime comparison", "=" * 72]
    header = f"{'runtime':<18}{'avail':<8}{'runs':<6}{'success':<10}{'median s':<11}{'tokens':<9}provider"
    lines += [header, "-" * 72]
    for summary in summaries.values():
        if not summary.available:
            lines.append(f"{summary.runtime_id:<18}{'no':<8}{'—':<6}{'—':<10}{'—':<11}{'—':<9}{summary.error or ''}")
            continue
        provider = sorted(set(summary.providers))
        lines.append(
            f"{summary.runtime_id:<18}{'yes':<8}{summary.runs:<6}"
            f"{f'{summary.success_rate:.0%} ({summary.successes}/{summary.runs})':<10}"
            f"{summary.median_duration_s:<11.2f}{summary.total_tokens:<9}{','.join(provider) or '—'}"
        )
    failures = [r for r in records if not r.success]
    if failures:
        lines += ["", "Failures:"]
        lines += [f"  {r.runtime_id}/{r.task_id}: {r.error}" for r in failures]
    lines += ["", "Reminder: these numbers are only a capability benchmark if the provider",
              "column names a real LLM. Against a stub they measure integration mechanics only."]
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Compare agent runtimes head to head.")
    parser.add_argument("--runtimes", nargs="+", default=["internal_agent", "prime_agent"])
    parser.add_argument("--tasks", help="JSON file: [{id, instruction, task_type}]")
    parser.add_argument("--workspace", default=os.getcwd())
    parser.add_argument("--timeout", type=int, default=180)
    parser.add_argument("--json", dest="json_out", help="Write the full report to this path")
    args = parser.parse_args()

    tasks = DEFAULT_TASKS
    if args.tasks:
        with open(args.tasks) as handle:
            tasks = json.load(handle)

    records, summaries = asyncio.run(compare(args.runtimes, tasks, args.workspace, args.timeout))
    print(render(summaries, records))

    if args.json_out:
        payload = {
            "tasks": tasks,
            "records": [asdict(r) for r in records],
            "summaries": {
                k: {**asdict(v), "success_rate": v.success_rate, "median_duration_s": v.median_duration_s}
                for k, v in summaries.items()
            },
        }
        with open(args.json_out, "w") as handle:
            json.dump(payload, handle, indent=2)
        print(f"\nWrote {args.json_out}")

    unavailable = [s.runtime_id for s in summaries.values() if not s.available]
    if unavailable:
        print(f"\nUnavailable, nothing measured: {', '.join(unavailable)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
