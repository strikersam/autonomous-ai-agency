"""Tests for the C-suite business-advisory layer (agent/executive_advisory.py).

Hermetic: the LLM is injected, so no provider is called.
"""
from __future__ import annotations

import pytest

from agent.executive_advisory import (
    AdviceResult,
    ExecutiveAdvisory,
    _format_company_context,
    default_executives,
    get_executive_advisory,
    reset_executive_advisory,
)


def _recording_llm(replies: list[str]):
    """Return an async llm that yields queued replies and records calls."""
    calls: list[list[dict[str, str]]] = []
    seq = iter(replies)

    async def llm(messages):
        calls.append(messages)
        try:
            return next(seq)
        except StopIteration:
            return "default reply"

    llm.calls = calls  # type: ignore[attr-defined]
    return llm


def test_select_routes_by_domain_keyword():
    adv = ExecutiveAdvisory()
    assert "cfo" in adv.select("What pricing and runway do we need?")
    assert "gc" in adv.select("Review this vendor contract for IP risk")
    assert "cmo" in adv.select("Plan our go-to-market launch campaign")


def test_select_falls_back_when_nothing_matches():
    adv = ExecutiveAdvisory()
    chosen = adv.select("xyzzy plugh")
    assert chosen == ["cso", "cfo", "cpo"]


@pytest.mark.asyncio
async def test_advise_consults_selected_execs_and_synthesizes():
    llm = _recording_llm(["CFO view", "CSO view", "SYNTHESIS"])
    adv = ExecutiveAdvisory(llm=llm)
    result = await adv.advise("What is our pricing strategy vs competitors?")
    assert isinstance(result, AdviceResult)
    # pricing → cfo, strategy/competitors → cso
    assert set(result.consulted) >= {"cfo", "cso"}
    assert result.answer == "SYNTHESIS"
    # one call per consulted exec + one synthesis call
    assert len(llm.calls) == len(result.consulted) + 1


@pytest.mark.asyncio
async def test_advise_explicit_roles_override_routing():
    llm = _recording_llm(["only-gc"])
    adv = ExecutiveAdvisory(llm=llm)
    result = await adv.advise("anything", roles=["gc"], synthesize=False)
    assert result.consulted == ["gc"]
    # single usable opinion → returned as the answer without a synthesis call
    assert result.answer == "only-gc"
    assert len(llm.calls) == 1


@pytest.mark.asyncio
async def test_advise_is_fail_soft_when_a_voice_errors():
    async def flaky_llm(messages):
        # First (executive) call raises; synthesis never reached with 1 exec.
        raise RuntimeError("provider down")

    adv = ExecutiveAdvisory(llm=flaky_llm)
    result = await adv.advise("legal contract question", roles=["gc"])
    assert result.consulted == ["gc"]
    assert result.opinions[0].error
    assert result.opinions[0].text == ""
    assert result.answer == ""  # nothing usable, but no exception


@pytest.mark.asyncio
async def test_advise_unknown_role_is_dropped():
    llm = _recording_llm(["x"])
    adv = ExecutiveAdvisory(llm=llm)
    result = await adv.advise("q", roles=["not-a-real-exec"])
    assert result.consulted == []
    assert result.opinions == []
    assert len(llm.calls) == 0


def test_format_company_context_variants():
    assert _format_company_context(None) == ""
    assert _format_company_context("  hi  ") == "hi"
    out = _format_company_context({"name": "Acme", "stage": "seed", "empty": ""})
    assert "name: Acme" in out and "stage: seed" in out
    assert "empty" not in out


def test_default_executives_have_unique_roles():
    execs = default_executives()
    roles = [e.role for e in execs]
    assert len(roles) == len(set(roles))
    assert {"cso", "cfo", "coo", "cmo", "cpo", "gc"} == set(roles)


def test_singleton_reset():
    reset_executive_advisory()
    a = get_executive_advisory()
    b = get_executive_advisory()
    assert a is b
    reset_executive_advisory()
    assert get_executive_advisory() is not a


def test_result_as_dict_shape():
    r = AdviceResult(question="q", consulted=["cfo"])
    d = r.as_dict()
    assert d["question"] == "q"
    assert d["consulted"] == ["cfo"]
    assert d["opinions"] == []
    assert d["answer"] == ""
