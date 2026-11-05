from __future__ import annotations

import pytest

from agent.truncation_guard import TruncatedResponseError, is_truncated, require_complete


@pytest.mark.parametrize("reason", ["length", "max_tokens", "MAX_TOKENS", " Length "])
def test_limit_reasons_are_truncated(reason: str) -> None:
    assert is_truncated(reason)
    with pytest.raises(TruncatedResponseError):
        require_complete(reason)


@pytest.mark.parametrize("reason", ["stop", "tool_calls", "end_turn", "", None, 3])
def test_other_reasons_are_complete(reason: object) -> None:
    assert not is_truncated(reason)
    require_complete(reason)
