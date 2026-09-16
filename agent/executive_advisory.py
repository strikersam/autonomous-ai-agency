"""agent/executive_advisory.py — a C-suite business-advisory layer.

The agency's CEO (``agent/agency.py``) is an *engineering* orchestrator: it
drives the codebase to quality via dev/security/reviewer/release/scout/optimizer
runtimes. It has no notion of the *business* questions that a company the agency
manages actually faces — pricing, fundraising, GTM, hiring, contracts.

This module adds that missing layer, inspired by SenteLabsAI/OpenExecutive but
built the repo's own way: no ChromaDB, no bespoke scheduler, no Anthropic-only
prompt caching. Every model call goes through the canonical router path
(``backend.server.call_llm`` → ``packages/ai/router.py``) per rule 2, so the
C-suite runs on whatever provider the failover chain resolves — NVIDIA NIM
first, exactly like the CEO.

Shape: a small set of executive personas (CFO, CSO, COO, CMO, CPO, General
Counsel). A question is routed to the relevant executives, each answers from its
own domain, and a chief-of-staff pass synthesises one unified recommendation —
the "single executive voice" idea, minus the framework weight.

The module is self-contained and hermetic: it never reads the environment
(rule 5) and never imports the heavy company store. Callers supply company
context; ``advise`` accepts an optional injected ``llm`` so tests run without a
live provider.
"""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("qwen-proxy")

#: An LLM callable: takes an OpenAI-style message list, returns the reply text.
LLMFn = Callable[[list[dict[str, str]]], Awaitable[str]]


# ── Personas ────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Executive:
    """One C-suite persona: its identity and the domain it answers from."""

    role: str
    title: str
    focus: str
    system_prompt: str
    #: Lower-cased keywords that route a question to this executive.
    keywords: tuple[str, ...] = ()


_BASE_STYLE = (
    " Answer only from your own domain. Be concrete and decisive: state a "
    "recommendation, the one reason it is right, and the first action to take. "
    "If the question is outside your remit, say so in one line rather than "
    "guessing. Never invent figures — if you lack a number, name what you would "
    "need to get it."
)


def default_executives() -> list[Executive]:
    """Return the built-in C-suite personas."""
    return [
        Executive(
            role="cso",
            title="Chief Strategy Officer",
            focus="market positioning, competition, M&A, growth bets",
            keywords=("strategy", "market", "competitor", "competition",
                      "positioning", "moat", "acquisition", "m&a", "expand",
                      "growth", "roadmap direction"),
            system_prompt=(
                "You are the Chief Strategy Officer. You reason about where the "
                "company should compete and why it will win there." + _BASE_STYLE
            ),
        ),
        Executive(
            role="cfo",
            title="Chief Financial Officer",
            focus="unit economics, burn, runway, pricing, fundraising",
            keywords=("finance", "financial", "budget", "burn", "runway",
                      "revenue", "pricing", "price", "cost", "margin", "cash",
                      "fundrais", "invest", "valuation", "roi"),
            system_prompt=(
                "You are the Chief Financial Officer. You reason about money: "
                "unit economics, runway, pricing and capital." + _BASE_STYLE
            ),
        ),
        Executive(
            role="coo",
            title="Chief Operating Officer",
            focus="execution, process, vendors, staffing capacity",
            keywords=("operations", "operational", "process", "vendor",
                      "supplier", "hiring", "hire", "staffing", "capacity",
                      "execution", "scale operations", "logistics"),
            system_prompt=(
                "You are the Chief Operating Officer. You reason about getting "
                "things done reliably at scale: process, people and vendors."
                + _BASE_STYLE
            ),
        ),
        Executive(
            role="cmo",
            title="Chief Marketing Officer",
            focus="go-to-market, brand, demand generation, messaging",
            keywords=("marketing", "brand", "gtm", "go-to-market", "campaign",
                      "demand", "lead", "messaging", "positioning message",
                      "audience", "channel", "launch"),
            system_prompt=(
                "You are the Chief Marketing Officer. You reason about reaching "
                "and converting the right customers." + _BASE_STYLE
            ),
        ),
        Executive(
            role="cpo",
            title="Chief Product Officer",
            focus="product strategy, prioritisation, user value",
            keywords=("product", "feature", "roadmap", "prioriti", "user need",
                      "ux", "user experience", "backlog", "mvp", "adoption",
                      "retention"),
            system_prompt=(
                "You are the Chief Product Officer. You reason about what to "
                "build next and why users will care." + _BASE_STYLE
            ),
        ),
        Executive(
            role="gc",
            title="General Counsel",
            focus="contracts, IP, compliance, employment, risk",
            keywords=("legal", "contract", "compliance", "regulat", "license",
                      "licence", "ip", "intellectual property", "privacy",
                      "gdpr", "liability", "terms", "employment law"),
            system_prompt=(
                "You are the General Counsel. You reason about legal and "
                "compliance risk. Flag where formal legal advice is required; "
                "you inform decisions, you do not replace counsel." + _BASE_STYLE
            ),
        ),
    ]


_CHIEF_OF_STAFF_PROMPT = (
    "You are the Chief of Staff to the CEO. Several executives have each given "
    "their view on one question. Synthesise them into a single, decisive "
    "recommendation in the CEO's voice: lead with the decision, then the two or "
    "three reasons that carry it, then the immediate next step. Call out any "
    "genuine disagreement between executives rather than papering over it. Keep "
    "it tight — no restating each executive in turn."
)


# ── Results ─────────────────────────────────────────────────────────────────


@dataclass
class ExecOpinion:
    """One executive's answer to the question."""

    role: str
    title: str
    text: str = ""
    error: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {"role": self.role, "title": self.title,
                "text": self.text, "error": self.error}


@dataclass
class AdviceResult:
    """The full advisory response: per-executive opinions plus the synthesis."""

    question: str
    consulted: list[str] = field(default_factory=list)
    opinions: list[ExecOpinion] = field(default_factory=list)
    answer: str = ""

    def as_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "consulted": list(self.consulted),
            "opinions": [o.as_dict() for o in self.opinions],
            "answer": self.answer,
        }


# ── Advisory engine ─────────────────────────────────────────────────────────


class ExecutiveAdvisory:
    """Routes a business question to the right executives and synthesises them."""

    def __init__(
        self,
        executives: Iterable[Executive] | None = None,
        *,
        llm: LLMFn | None = None,
        model: str | None = None,
    ) -> None:
        self._execs: dict[str, Executive] = {
            e.role: e for e in (executives or default_executives())
        }
        self._llm = llm
        self._model = model

    @property
    def roles(self) -> list[str]:
        return list(self._execs)

    def select(self, question: str) -> list[str]:
        """Return the roles whose keywords match *question*.

        Falls back to a sensible default trio (CSO/CFO/CPO) when nothing
        matches, so a vague question still gets a strategic answer rather than
        silence.
        """
        q = (question or "").lower()
        hits = [role for role, e in self._execs.items()
                if any(kw in q for kw in e.keywords)]
        if hits:
            return hits
        return [r for r in ("cso", "cfo", "cpo") if r in self._execs]

    async def _default_llm(self, messages: list[dict[str, str]]) -> str:
        # Lazy import: backend.server imports large modules and would create an
        # import cycle at module load. Mirrors agent/agency.py's pattern.
        from backend.server import call_llm

        return await call_llm(messages, model=self._model, temperature=0.4)

    async def _consult(
        self, exec_: Executive, question: str, company_context: str,
    ) -> ExecOpinion:
        llm = self._llm or self._default_llm
        user = question if not company_context else (
            f"Company context:\n{company_context}\n\nQuestion: {question}"
        )
        try:
            text = await llm([
                {"role": "system", "content": exec_.system_prompt},
                {"role": "user", "content": user},
            ])
            return ExecOpinion(role=exec_.role, title=exec_.title,
                               text=(text or "").strip())
        except Exception as exc:  # noqa: BLE001 — fail soft, one voice down
            log.warning("Executive %s consult failed: %s", exec_.role, exc)
            return ExecOpinion(role=exec_.role, title=exec_.title,
                               error=str(exc)[:200])

    async def advise(
        self,
        question: str,
        *,
        company_context: Any = None,
        roles: Sequence[str] | None = None,
        synthesize: bool = True,
    ) -> AdviceResult:
        """Consult the relevant executives and return a unified recommendation.

        *roles* overrides keyword routing. *company_context* may be a string or
        any object with a readable ``str()`` (e.g. a company profile dict).
        """
        chosen = [r for r in (roles or self.select(question)) if r in self._execs]
        result = AdviceResult(question=question, consulted=chosen)
        if not chosen:
            return result
        ctx = _format_company_context(company_context)
        result.opinions = list(await asyncio.gather(
            *(self._consult(self._execs[r], question, ctx) for r in chosen)
        ))
        usable = [o for o in result.opinions if o.text]
        if not synthesize or not usable:
            # One usable voice needs no synthesis; none means nothing to say.
            result.answer = usable[0].text if len(usable) == 1 else ""
            return result
        result.answer = await self._synthesize(question, usable)
        return result

    async def _synthesize(
        self, question: str, opinions: list[ExecOpinion],
    ) -> str:
        llm = self._llm or self._default_llm
        board = "\n\n".join(f"### {o.title}\n{o.text}" for o in opinions)
        try:
            text = await llm([
                {"role": "system", "content": _CHIEF_OF_STAFF_PROMPT},
                {"role": "user",
                 "content": f"Question: {question}\n\nExecutive views:\n{board}"},
            ])
            return (text or "").strip()
        except Exception as exc:  # noqa: BLE001 — fall back to raw opinions
            log.warning("Executive synthesis failed: %s", exc)
            return board


def _format_company_context(company_context: Any) -> str:
    """Coerce supplied company context to a compact string, or empty."""
    if not company_context:
        return ""
    if isinstance(company_context, str):
        return company_context.strip()[:4000]
    if isinstance(company_context, dict):
        parts = [f"{k}: {v}" for k, v in company_context.items() if v]
        return "\n".join(parts)[:4000]
    return str(company_context)[:4000]


# ── Singleton ───────────────────────────────────────────────────────────────

_advisory: ExecutiveAdvisory | None = None


def get_executive_advisory() -> ExecutiveAdvisory:
    """Return the shared :class:`ExecutiveAdvisory`, built on first use."""
    global _advisory
    if _advisory is None:
        _advisory = ExecutiveAdvisory()
    return _advisory


def reset_executive_advisory() -> None:
    """Drop the singleton (test helper)."""
    global _advisory
    _advisory = None
