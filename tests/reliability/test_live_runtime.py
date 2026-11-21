"""One integration test against a real runtime; skipped unless credentials are present.

Run it with ``NVIDIA_API_KEY`` set and ``-m "integration"`` (the default run excludes it).
"""
from __future__ import annotations

import os

import pytest

from packages.runs.composition import ChildJob, ChildOutcome, CompositionSpec
from tests.reliability._helpers import compose, step

pytestmark = [pytest.mark.integration, pytest.mark.live,
              pytest.mark.skipif(not os.environ.get("NVIDIA_API_KEY"),
                                 reason="needs NVIDIA_API_KEY: a real provider call")]


async def test_live_a_composition_child_calls_a_real_provider_through_the_failover_client():
    from packages.ai.failover_client import failover_chat_completion

    async def child(job: ChildJob) -> ChildOutcome:
        res = await failover_chat_completion({"model": "meta/llama-3.1-8b-instruct", "max_tokens": 16,
                                              "messages": [{"role": "user", "content": "Reply with the word OK."}]})
        return ChildOutcome(success=bool(res.text), output=res.text, tokens=res.prompt_tokens + res.completion_tokens)

    _, store, _, root, res = await compose(CompositionSpec(steps=[step("live")]), executor=child)
    assert res.state == "succeeded" and res.aggregate[0]
    assert (await store.get(root.run_id)).spent_tokens > 0
