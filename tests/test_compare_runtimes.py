"""tests/test_compare_runtimes.py — the runtime comparison harness.

The point of these tests is that the report cannot quietly overstate itself: an
unavailable runtime must never read as a passing comparison, and the provider
behind the numbers must always be visible in the output.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SPEC = importlib.util.spec_from_file_location(
    "compare_runtimes", Path(__file__).parent.parent / "scripts" / "compare_runtimes.py"
)
compare_runtimes = importlib.util.module_from_spec(_SPEC)
# Must be registered before exec_module: @dataclass resolves cls.__module__
# through sys.modules, and a module loaded by path alone is not there yet.
sys.modules["compare_runtimes"] = compare_runtimes
_SPEC.loader.exec_module(compare_runtimes)

RunRecord = compare_runtimes.RunRecord
RuntimeSummary = compare_runtimes.RuntimeSummary


class TestSummaryMath:
    def test_success_rate(self):
        summary = RuntimeSummary("x", available=True, runs=4, successes=3)
        assert summary.success_rate == 0.75

    def test_empty_summary_does_not_divide_by_zero(self):
        assert RuntimeSummary("x", available=False).success_rate == 0.0
        assert RuntimeSummary("x", available=False).median_duration_s == 0.0

    def test_median_duration(self):
        summary = RuntimeSummary("x", available=True, durations=[1.0, 9.0, 3.0])
        assert summary.median_duration_s == 3.0


class TestReportHonesty:
    def test_unavailable_runtime_is_not_rendered_as_a_score(self):
        summaries = {"a": RuntimeSummary("a", available=False, error="binary missing")}
        output = compare_runtimes.render(summaries, [])
        assert "binary missing" in output
        assert "100%" not in output
        assert "0%" not in output

    def test_provider_is_always_visible(self):
        """A stub run must be distinguishable from a real benchmark afterwards."""
        summaries = {
            "a": RuntimeSummary("a", available=True, runs=1, successes=1,
                                durations=[1.0], providers=["agency"]),
        }
        output = compare_runtimes.render(summaries, [])
        assert "agency" in output
        assert "capability benchmark" in output

    def test_failures_are_listed_with_reasons(self):
        records = [RunRecord("a", "t1", success=False, duration_s=0.5, error="Connection error.")]
        output = compare_runtimes.render({"a": RuntimeSummary("a", available=True, runs=1)}, records)
        assert "a/t1: Connection error." in output


class TestExecution:
    @pytest.mark.asyncio
    async def test_adapter_exception_becomes_a_failed_record(self, tmp_path):
        class Exploding:
            RUNTIME_ID = "boom"

            async def execute(self, spec):
                raise RuntimeError("adapter blew up")

        record = await compare_runtimes._run_one(
            Exploding(), {"id": "t1", "instruction": "x"}, str(tmp_path), 5
        )
        assert record.success is False
        assert "adapter blew up" in record.error

    @pytest.mark.asyncio
    async def test_unsuccessful_result_records_the_error_not_the_exit_code(self, tmp_path):
        class Failing:
            RUNTIME_ID = "failing"

            async def execute(self, spec):
                class Result:
                    success = False
                    output = "ignored"
                    tokens_used = None
                    cost_usd = None
                    provider_used = "agency"
                    model_used = "m"
                    metadata = {"error": "Connection error."}
                return Result()

        record = await compare_runtimes._run_one(
            Failing(), {"id": "t1", "instruction": "x"}, str(tmp_path), 5
        )
        assert record.success is False
        assert record.error == "Connection error."
