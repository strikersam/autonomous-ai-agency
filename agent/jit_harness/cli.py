"""agent/jit_harness/cli.py — CLI for JIT harness pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from agent.jit_harness.pipeline import JITHarnessPipeline, PipelineResult

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="JIT Harness Pipeline")
    parser.add_argument("task", nargs="?", help="Task description (or --task)")
    parser.add_argument("--task", "-t", dest="task_opt", help="Task description")
    parser.add_argument(
        "--num-candidates", "-n", type=int, default=3, help="Number of harness candidates"
    )
    parser.add_argument(
        "--output", "-o", help="Output JSON file for results"
    )
    parser.add_argument(
        "--meta-model", default=os.environ.get("JIT_META_MODEL", "gpt-4o"),
        help="Meta-model for harness generation"
    )
    parser.add_argument(
        "--meta-base", default=os.environ.get("JIT_META_BASE", "https://api.openai.com/v1"),
        help="Meta-model API base URL"
    )
    parser.add_argument(
        "--meta-key", default=os.environ.get("JIT_META_API_KEY"),
        help="Meta-model API key"
    )
    parser.add_argument(
        "--meta-temp", type=float, default=0.7, help="Meta-model temperature"
    )
    parser.add_argument(
        "--exec-model", default=os.environ.get("JIT_EXEC_MODEL", "gpt-4o"),
        help="Execution model"
    )
    parser.add_argument(
        "--exec-base", default=os.environ.get("JIT_EXEC_BASE", "https://api.openai.com/v1"),
        help="Execution model API base URL"
    )
    parser.add_argument(
        "--exec-key", default=os.environ.get("JIT_EXEC_API_KEY"),
        help="Execution model API key"
    )
    parser.add_argument(
        "--judge-model", default=os.environ.get("JIT_JUDGE_MODEL", "gpt-4o-mini"),
        help="Judge model for selection"
    )
    parser.add_argument(
        "--judge-base", default=os.environ.get("JIT_JUDGE_BASE", "https://api.openai.com/v1"),
        help="Judge model API base URL"
    )
    parser.add_argument(
        "--judge-key", default=os.environ.get("JIT_JUDGE_API_KEY"),
        help="Judge model API key"
    )
    parser.add_argument(
        "--selector", choices=["judge", "logprob"], default="judge",
        help="Selector type"
    )
    parser.add_argument(
        "--ref-mode", choices=["desc", "code"], default="desc",
        help="Reference mode for meta-model"
    )
    parser.add_argument(
        "--ref-k", type=int, default=3, help="Number of reference harnesses"
    )
    parser.add_argument(
        "--max-steps", type=int, default=40, help="Max steps for execution"
    )
    parser.add_argument(
        "--trace-dir", help="Directory for execution traces"
    )
    parser.add_argument(
        "--workspace", help="Workspace root directory"
    )
    parser.add_argument(
        "--health-check", action="store_true", help="Run health check and exit"
    )

    return parser.parse_args()


async def main() -> int:
    args = parse_args()

    task = args.task or args.task_opt
    if not task and not args.health_check:
        log.error("Task is required (positional or --task)")
        return 1

    pipeline = JITHarnessPipeline(
        meta_model=args.meta_model,
        meta_base_url=args.meta_base,
        meta_api_key=args.meta_key,
        meta_temperature=args.meta_temp,
        num_candidates=args.num_candidates,
        reference_mode=args.ref_mode,
        reference_k=args.ref_k,
        selector_type=args.selector,
        judge_model=args.judge_model,
        judge_base_url=args.judge_base,
        judge_api_key=args.judge_key,
        execution_model=args.exec_model,
        execution_base_url=args.exec_base,
        execution_api_key=args.exec_key,
        max_steps=args.max_steps,
        trace_dir=args.trace_dir,
        workspace_root=args.workspace,
    )

    if args.health_check:
        health = await pipeline.health_check()
        print(json.dumps(health, indent=2))
        await pipeline.cleanup()
        return 0 if all(health.values()) else 1

    result: PipelineResult = await pipeline.run(task, num_candidates=args.num_candidates)

    # Print summary
    print("\n" + "=" * 60)
    print("JIT PIPELINE RESULT")
    print("=" * 60)
    print(f"Task: {task[:100]}...")
    print(f"Candidates generated: {len(result.generated_candidates)}")
    if result.selection_result:
        print(f"Selected: {result.selection_result.selected_harness.name}")
        print(f"Selector: {result.selection_result.selector_type}")
        print(f"Scores: {result.selection_result.scores}")
    if result.execution_result:
        print(f"Execution: {'SUCCESS' if result.execution_result.success else 'FAILED'}")
        print(f"Score: {result.execution_result.score:.3f}")
        print(f"Duration: {result.execution_result.duration_s:.1f}s")
        if result.execution_result.error:
            print(f"Error: {result.execution_result.error}")
    print(f"Total duration: {result.total_duration_s:.1f}s")
    print("=" * 60)

    # Save output
    if args.output:
        Path(args.output).write_text(json.dumps(result.to_dict(), indent=2))
        log.info("Results saved to %s", args.output)

    await pipeline.cleanup()
    return 0 if (result.execution_result and result.execution_result.success) else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))