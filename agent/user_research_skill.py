"""agent/user_research_skill.py — User research skill for the agent platform.

Implements the four core user-research capabilities adapted from the
cookiy-ai/user-research-skill reference architecture:

  1. **Plan**   — Produce a structured research plan (objectives, hypotheses,
                  methods, target sample, timeline) from a research question.
  2. **Synthesize** — Combine qualitative + quantitative findings into a
                      unified research brief with executive summary and
                      actionable recommendations.
  3. **Qual**   — Qualitative analysis of interview transcripts, open-ended
                  survey responses, or notes. Produces themes, pain points,
                  and verbatim quotes tagged by participant.
  4. **Quant**  — Quantitative analysis of survey results or numeric data.
                  Produces descriptive statistics, distributions, and
                  segment cuts.

All four capabilities are registered as agent tools via the
``ToolRegistry`` decorator pattern used elsewhere in the codebase so the
agent loop can discover and invoke them like any other tool.

The skill is designed to be deterministic and dependency-light: no LLM
calls are made inside the skill itself — the LLM is the executor that
*uses* the tool, and the tool provides the structural framework
(Pydantic contracts, sample-size math, theme extraction heuristics,
descriptive stats). This keeps the skill fast, testable, and free of
hidden costs.

Design notes:
- Pydantic v2 models use ``extra="forbid"`` so the executor can't smuggle
  unknown fields past validation.
- All methods are pure (no I/O) so the skill is trivially mockable in
  tests.
- Sample-size calculations use the standard finite-population
  adjustment for populations < 100k.
"""
from __future__ import annotations

import math
import re
import statistics
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

log = None  # populated lazily so tests that monkeypatch logging still work

# ── Pydantic models ───────────────────────────────────────────────────────────


class ResearchObjective(BaseModel):
    """A single research objective — what we want to learn."""

    model_config = {"extra": "forbid"}

    id: str = Field(..., description="Stable ID (e.g. 'OBJ-1')")
    statement: str = Field(..., min_length=10, description="The objective phrased as a question or goal")
    priority: Literal["must", "should", "could"] = "should"
    success_metric: str = Field(..., description="How we'll know this objective is met")


class ResearchHypothesis(BaseModel):
    """A falsifiable hypothesis to test."""

    model_config = {"extra": "forbid"}

    id: str = Field(..., description="Stable ID (e.g. 'HYP-1')")
    statement: str = Field(..., min_length=10)
    null_alternative: bool = Field(
        True, description="True if the hypothesis is stated in null-hypothesis form",
    )


class ResearchMethod(BaseModel):
    """A research method (interview, survey, diary study, etc.)."""

    model_config = {"extra": "forbid"}

    method: Literal[
        "interview", "survey", "diary_study", "usability_test",
        "card_sorting", "tree_testing", "field_observation", "focus_group",
    ]
    target_participants: int = Field(..., ge=1, le=10_000)
    duration_minutes: int | None = Field(None, ge=5, le=480)
    rationale: str = Field(..., min_length=10)


class ResearchPlan(BaseModel):
    """The output of the **Plan** capability.

    A structured research plan that a researcher (human or AI) can execute
    without further clarification.
    """

    model_config = {"extra": "forbid"}

    title: str = Field(..., min_length=5)
    primary_question: str = Field(..., min_length=10)
    audience: str = Field(..., min_length=5, description="Who the research is for")
    scope_in: list[str] = Field(default_factory=list)
    scope_out: list[str] = Field(default_factory=list)
    objectives: list[ResearchObjective] = Field(..., min_length=1)
    hypotheses: list[ResearchHypothesis] = Field(default_factory=list)
    methods: list[ResearchMethod] = Field(..., min_length=1)
    target_sample_size: int = Field(..., ge=1, le=10_000)
    timeline_days: int = Field(..., ge=1, le=365)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )

    @field_validator("objectives")
    @classmethod
    def _no_dup_objective_ids(cls, items: list[Any]) -> list[Any]:
        seen: set[str] = set()
        for it in items:
            _id = it.get("id") if isinstance(it, dict) else getattr(it, "id", None)
            if _id in seen:
                raise ValueError(f"Duplicate objective ID: {_id}")
            seen.add(_id)
        return items


class QualQuote(BaseModel):
    """A single verbatim quote tagged with metadata."""

    model_config = {"extra": "forbid"}

    participant_id: str
    text: str = Field(..., min_length=1)
    sentiment: Literal["positive", "neutral", "negative"] = "neutral"
    source: str | None = None


class QualTheme(BaseModel):
    """A theme extracted from qualitative data."""

    model_config = {"extra": "forbid"}

    name: str = Field(..., min_length=2)
    description: str = Field(..., min_length=10)
    supporting_quote_ids: list[str] = Field(default_factory=list)
    frequency: int = Field(..., ge=1, description="How many distinct participants mentioned this theme")


class QualAnalysis(BaseModel):
    """The output of the **Qual** capability."""

    model_config = {"extra": "forbid"}

    source: str = Field(..., description="Where the qualitative data came from (e.g. '5 customer interviews')")
    participant_count: int = Field(..., ge=1)
    pain_points: list[QualTheme] = Field(default_factory=list)
    desires: list[QualTheme] = Field(default_factory=list)
    quotes: list[QualQuote] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class QuantSegment(BaseModel):
    """A segment cut (e.g. 'enterprise', 'SMB')."""

    model_config = {"extra": "forbid"}

    name: str
    count: int = Field(..., ge=0)
    mean: float
    median: float
    stdev: float


class QuantAnalysis(BaseModel):
    """The output of the **Quant** capability."""

    model_config = {"extra": "forbid"}

    source: str
    sample_size: int = Field(..., ge=1)
    metric_name: str = Field(..., min_length=2, description="What is being measured (e.g. 'NPS', 'time-on-task')")
    metric_type: Literal["rating", "count", "duration_seconds", "percentage", "binary"]
    mean: float
    median: float
    stdev: float
    min_value: float
    max_value: float
    distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Histogram-style bin → count (for rating) or category → count (for categorical)",
    )
    segments: list[QuantSegment] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


class ResearchBrief(BaseModel):
    """The output of the **Synthesize** capability.

    Combines one QualAnalysis + one QuantAnalysis (and optional context)
    into a single decision-ready brief.
    """

    model_config = {"extra": "forbid"}

    title: str
    executive_summary: str = Field(..., min_length=40, max_length=1000)
    key_findings: list[str] = Field(..., min_length=1, max_length=10)
    quant_snapshot: QuantAnalysis | None = None
    qual_snapshot: QualAnalysis | None = None
    recommendations: list[str] = Field(..., min_length=1, max_length=10)
    confidence: Literal["high", "medium", "low"] = "medium"
    next_steps: list[str] = Field(default_factory=list)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


# ── Helpers ────────────────────────────────────────────────────────────────────


def _sample_size_for_proportion(
    *,
    population_size: int | None,
    confidence_z: float = 1.96,
    margin_of_error: float = 0.05,
    p: float = 0.5,
) -> int:
    """Compute the minimum sample size for a proportion estimate.

    Uses the standard normal-approximation formula with finite-population
    correction when ``population_size`` is provided.
    """
    z2 = confidence_z * confidence_z
    n0 = (z2 * p * (1 - p)) / (margin_of_error * margin_of_error)
    if population_size is None or population_size <= 0:
        return int(math.ceil(n0))
    n = n0 / (1 + (n0 - 1) / population_size)
    return int(math.ceil(n))


_WORD_RE = re.compile(r"\b[a-zA-Z][a-zA-Z'\-]{2,}\b")
_STOPWORDS = frozenset({
    "the", "and", "but", "for", "with", "this", "that", "from", "have", "has",
    "had", "you", "your", "our", "they", "their", "them", "were", "what",
    "when", "where", "which", "while", "who", "why", "how", "are", "was",
    "will", "would", "could", "should", "can", "cant", "cannot", "wont",
    "dont", "doesnt", "didnt", "wouldnt", "shouldnt", "couldnt", "about",
    "just", "like", "really", "very", "much", "some", "any", "all", "most",
    "more", "less", "into", "over", "under", "than", "then", "there", "here",
    "also", "only", "other", "such", "its", "it's",
})


def _extract_keywords(text: str, *, top_n: int = 20) -> list[tuple[str, int]]:
    """Tokenise text into (word, frequency) pairs, dropping stopwords."""
    lowered = text.lower()
    tokens = _WORD_RE.findall(lowered)
    counter: Counter[str] = Counter()
    for tok in tokens:
        if tok in _STOPWORDS or len(tok) < 4:
            continue
        counter[tok] += 1
    return counter.most_common(top_n)


def _classify_sentiment(text: str) -> Literal["positive", "neutral", "negative"]:
    """Tiny rule-based sentiment classifier. No LLM, deterministic, fast.

    Real production sentiment should use an LLM call; this baseline is
    good enough for skill scaffolding and tests.
    """
    positive = {
        "love", "great", "amazing", "excellent", "fantastic", "perfect",
        "easy", "fast", "helpful", "intuitive", "smooth", "delight",
        "impressed", "enjoy", "enjoyed", "saved", "efficient", "reliable",
    }
    negative = {
        "hate", "terrible", "awful", "bad", "broken", "slow", "confusing",
        "frustrated", "frustrating", "annoying", "annoyed", "difficult",
        "hard", "useless", "waste", "painful", "crash", "buggy", "missing",
    }
    lowered = text.lower()
    pos = sum(1 for w in positive if w in lowered)
    neg = sum(1 for w in negative if w in lowered)
    if pos > neg:
        return "positive"
    if neg > pos:
        return "negative"
    return "neutral"


# ── Capability: Plan ───────────────────────────────────────────────────────────


def plan_research(
    *,
    title: str,
    primary_question: str,
    audience: str,
    objectives: list[dict[str, Any]],
    methods: list[dict[str, Any]],
    population_size: int | None = None,
    margin_of_error: float = 0.05,
    timeline_days: int = 14,
    hypotheses: list[dict[str, Any]] | None = None,
    scope_in: list[str] | None = None,
    scope_out: list[str] | None = None,
) -> ResearchPlan:
    """Produce a structured research plan.

    The four Plan inputs that are typically auto-derived:
      * ``objectives[i].id`` / ``methods[i].id`` defaults to OBJ-N / METH-N.
      * ``target_sample_size`` is computed from the sum of method targets
        (capped by the sample-size math) so a researcher doesn't have to
        hand-pick it.

    Args:
        title: Short research title.
        primary_question: The single most important question.
        audience: Who the research serves.
        objectives: List of objective dicts (must contain ``statement``).
        methods: List of method dicts (must contain ``method`` and
            ``target_participants``).
        population_size: Optional finite population for sample-size
            correction. ``None`` = infinite population.
        margin_of_error: Desired margin of error for the survey portion
            (default 5%).
        timeline_days: Total research timeline in days.
        hypotheses: Optional list of hypothesis dicts.
        scope_in: Optional list of in-scope topics.
        scope_out: Optional list of out-of-scope topics.

    Returns:
        A validated :class:`ResearchPlan` ready to execute.
    """
    # Auto-assign IDs to objectives and methods if missing
    obj_models: list[ResearchObjective] = []
    for i, obj in enumerate(objectives, start=1):
        data = dict(obj)
        data.setdefault("id", f"OBJ-{i}")
        data.setdefault("priority", "should")
        data.setdefault("success_metric", "Achieves the stated objective with measurable evidence")
        obj_models.append(ResearchObjective.model_validate(data))

    method_models: list[ResearchMethod] = []
    method_participant_sum = 0
    for i, m in enumerate(methods, start=1):
        data = dict(m)
        data.setdefault("rationale", f"Selected to address the research question via {data.get('method', 'this method')}")
        model = ResearchMethod.model_validate(data)
        method_models.append(model)
        method_participant_sum += model.target_participants

    hyp_models: list[ResearchHypothesis] = []
    for i, h in enumerate(hypotheses or [], start=1):
        data = dict(h)
        data.setdefault("id", f"HYP-{i}")
        data.setdefault("null_alternative", True)
        hyp_models.append(ResearchHypothesis.model_validate(data))

    # Compute target sample size: the larger of (a) sum of method targets
    # and (b) the proportion-formula sample size with finite correction.
    stats_sample = _sample_size_for_proportion(
        population_size=population_size,
        margin_of_error=margin_of_error,
    )
    target = max(method_participant_sum, stats_sample)

    return ResearchPlan(
        title=title,
        primary_question=primary_question,
        audience=audience,
        scope_in=scope_in or [],
        scope_out=scope_out or [],
        objectives=obj_models,
        hypotheses=hyp_models,
        methods=method_models,
        target_sample_size=target,
        timeline_days=timeline_days,
    )


# ── Capability: Qual ───────────────────────────────────────────────────────────


def analyze_qualitative(
    *,
    source: str,
    transcripts: list[str],
    participant_ids: list[str] | None = None,
    pain_point_keywords: list[str] | None = None,
    desire_keywords: list[str] | None = None,
    min_theme_frequency: int = 2,
) -> QualAnalysis:
    """Extract themes, pain points, and desires from qualitative data.

    Args:
        source: Human-readable description of the data source
            (e.g. ``"5 customer interviews"``).
        transcripts: One string per participant. If ``participant_ids`` is
            omitted, IDs are auto-assigned P1..Pn.
        participant_ids: Optional list of IDs matching ``transcripts``.
        pain_point_keywords: Optional custom keywords to flag as pain points.
        desire_keywords: Optional custom keywords to flag as desires.
        min_theme_frequency: Minimum number of distinct participants needed
            for a theme to be reported (default 2).

    Returns:
        A validated :class:`QualAnalysis` with extracted themes and quotes.
    """
    if not transcripts:
        raise ValueError("transcripts must contain at least one entry")

    n = len(transcripts)
    if participant_ids is None:
        participant_ids = [f"P{i+1}" for i in range(n)]
    if len(participant_ids) != n:
        raise ValueError("participant_ids length must match transcripts length")

    default_pain = {"problem", "issue", "frustrat", "annoy", "broken", "bug", "fail", "stuck", "hate", "terrible", "slow", "confus", "difficult"}
    default_desire = {"want", "wish", "hope", "love", "need", "would", "should", "improve", "better"}

    pain_kw = {k.lower() for k in (pain_point_keywords or default_pain)}
    desire_kw = {k.lower() for k in (desire_keywords or default_desire)}

    quotes: list[QualQuote] = []
    pain_kw_hits: Counter[str] = Counter()
    desire_kw_hits: Counter[str] = Counter()
    participant_pain_kw: dict[str, set[str]] = {pid: set() for pid in participant_ids}
    participant_desire_kw: dict[str, set[str] | None] = {pid: set() for pid in participant_ids}

    for pid, text in zip(participant_ids, transcripts):
        sentiment = _classify_sentiment(text)
        # Take the first sentence as the canonical quote
        first_sentence = re.split(r"(?<=[.!?])\s+", text.strip(), maxsplit=1)[0]
        quotes.append(QualQuote(
            participant_id=pid,
            text=first_sentence[:500],
            sentiment=sentiment,
            source=source,
        ))
        lowered = text.lower()
        for kw in pain_kw:
            if kw in lowered:
                pain_kw_hits[kw] += 1
                participant_pain_kw[pid].add(kw)
        for kw in desire_kw:
            if kw in lowered:
                desire_kw_hits[kw] += 1
                participant_desire_kw[pid].add(kw)

    # Build pain themes: each keyword becomes a theme, frequency = number of
    # distinct participants who mentioned it.
    pain_themes: list[QualTheme] = []
    for kw, _hits in pain_kw_hits.most_common():
        participants = [pid for pid, kws in participant_pain_kw.items() if kw in kws]
        if len(participants) < min_theme_frequency:
            continue
        pain_themes.append(QualTheme(
            name=kw,
            description=f"Participants expressed frustration related to '{kw}'.",
            supporting_quote_ids=participants,
            frequency=len(participants),
        ))

    desire_themes: list[QualTheme] = []
    for kw, _hits in desire_kw_hits.most_common():
        participants = [pid for pid, kws in participant_desire_kw.items() if kws and kw in kws]
        if len(participants) < min_theme_frequency:
            continue
        desire_themes.append(QualTheme(
            name=kw,
            description=f"Participants expressed desire / improvement requests related to '{kw}'.",
            supporting_quote_ids=participants,
            frequency=len(participants),
        ))

    return QualAnalysis(
        source=source,
        participant_count=n,
        pain_points=pain_themes,
        desires=desire_themes,
        quotes=quotes,
    )


# ── Capability: Quant ──────────────────────────────────────────────────────────


def analyze_quantitative(
    *,
    source: str,
    values: list[float],
    metric_name: str,
    metric_type: Literal["rating", "count", "duration_seconds", "percentage", "binary"] = "rating",
    segments: list[dict[str, Any]] | None = None,
    bins: int = 5,
) -> QuantAnalysis:
    """Compute descriptive statistics for a numeric series.

    Args:
        source: Where the numbers came from.
        values: The numeric samples.
        metric_name: What is being measured (e.g. ``"NPS"``).
        metric_type: One of ``rating``, ``count``, ``duration_seconds``,
            ``percentage``, ``binary``.
        segments: Optional pre-computed segment cuts. Each dict must have
            ``name``, ``count``, ``mean``, ``median``, ``stdev``.
        bins: Number of histogram bins for rating data (default 5).

    Returns:
        A validated :class:`QuantAnalysis` with mean, median, stdev, min,
        max, distribution, and optional segments.
    """
    if not values:
        raise ValueError("values must contain at least one sample")
    if bins < 2 or bins > 20:
        raise ValueError("bins must be between 2 and 20")

    sample = [float(v) for v in values]
    mean = statistics.fmean(sample)
    median = statistics.median(sample)
    stdev = statistics.pstdev(sample) if len(sample) < 2 else statistics.stdev(sample)
    min_v = min(sample)
    max_v = max(sample)

    distribution: dict[str, int] = {}
    if metric_type == "rating":
        lo = math.floor(min_v)
        hi = math.ceil(max_v)
        if hi == lo:
            hi = lo + 1
        width = max(1.0, (hi - lo) / bins)
        for i in range(bins):
            bin_lo = lo + i * width
            bin_hi = lo + (i + 1) * width
            label = f"{bin_lo:g}-{bin_hi:g}"
            count = sum(1 for v in sample if bin_lo <= v < bin_hi or (i == bins - 1 and v == bin_hi))
            distribution[label] = count
    else:
        # Round to int and count
        counter: Counter[str] = Counter(str(int(round(v))) for v in sample)
        distribution = dict(sorted(counter.items()))

    seg_models: list[QuantSegment] = []
    for seg in segments or []:
        seg_models.append(QuantSegment.model_validate(seg))

    return QuantAnalysis(
        source=source,
        sample_size=len(sample),
        metric_name=metric_name,
        metric_type=metric_type,
        mean=round(mean, 3),
        median=round(median, 3),
        stdev=round(stdev, 3),
        min_value=round(min_v, 3),
        max_value=round(max_v, 3),
        distribution=distribution,
        segments=seg_models,
    )


# ── Capability: Synthesize ─────────────────────────────────────────────────────


def synthesize_research(
    *,
    title: str,
    quant: QuantAnalysis | None = None,
    qual: QualAnalysis | None = None,
    key_findings: list[str] | None = None,
    recommendations: list[str] | None = None,
    next_steps: list[str] | None = None,
    confidence: Literal["high", "medium", "low"] = "medium",
) -> ResearchBrief:
    """Combine qualitative + quantitative findings into a decision-ready brief.

    If ``key_findings`` or ``recommendations`` are not supplied, sensible
    defaults are derived from the quant and qual data so the brief is
    never empty.

    Args:
        title: Brief title.
        quant: Optional quantitative analysis.
        qual: Optional qualitative analysis.
        key_findings: List of one-line findings. Auto-derived if omitted.
        recommendations: List of one-line recommendations. Auto-derived if omitted.
        next_steps: Optional list of concrete next steps.
        confidence: Overall confidence in the findings (high/medium/low).

    Returns:
        A validated :class:`ResearchBrief`.
    """
    derived_findings: list[str] = []
    derived_recommendations: list[str] = []

    if quant is not None:
        if quant.metric_type == "rating":
            derived_findings.append(
                f"{quant.metric_name}: mean {quant.mean}, median {quant.median}, "
                f"σ {quant.stdev} across n={quant.sample_size}."
            )
            if quant.mean >= 4.0:
                derived_recommendations.append(
                    f"Leverage the strong {quant.metric_name} score ({quant.mean}) in launch messaging."
                )
            elif quant.mean <= 2.5:
                derived_recommendations.append(
                    f"Investigate drivers of low {quant.metric_name} ({quant.mean}) before scaling."
                )
        else:
            derived_findings.append(
                f"{quant.metric_name} (n={quant.sample_size}): mean {quant.mean}, "
                f"range {quant.min_value}–{quant.max_value}."
            )
        if quant.segments:
            best = max(quant.segments, key=lambda s: s.mean)
            worst = min(quant.segments, key=lambda s: s.mean)
            derived_findings.append(
                f"Segment gap: '{best.name}' scores {best.mean} vs '{worst.name}' at {worst.mean}."
            )

    if qual is not None:
        for theme in qual.pain_points[:3]:
            derived_findings.append(
                f"{theme.frequency}/{qual.participant_count} participants raised pain point: '{theme.name}'."
            )
        for theme in qual.desires[:3]:
            derived_recommendations.append(
                f"Prioritise improvement on the '{theme.name}' desire ({theme.frequency}/{qual.participant_count} participants)."
            )

    # Auto-summarise into an exec summary if user didn't supply one
    exec_summary = (
        f"Research brief '{title}' synthesises "
        f"{'quantitative ' if quant else ''}{'and ' if quant and qual else ''}"
        f"{'qualitative ' if qual else ''}data"
        f"{f' (n={quant.sample_size})' if quant else ''}"
        f"{f' across {qual.participant_count} participants' if qual else ''}. "
        f"{len(derived_findings or key_findings or [])} key finding(s) inform "
        f"{len(derived_recommendations or recommendations or [])} recommendation(s)."
    )

    return ResearchBrief(
        title=title,
        executive_summary=exec_summary,
        key_findings=key_findings or derived_findings or ["No findings supplied."],
        recommendations=recommendations or derived_recommendations or ["Collect more data before recommending action."],
        quant_snapshot=quant,
        qual_snapshot=qual,
        next_steps=next_steps or [],
        confidence=confidence,
    )


# ── Tool registration ─────────────────────────────────────────────────────────


def register_user_research_tools(registry: Any) -> int:
    """Register the four user-research tools with a ``ToolRegistry``.

    Each tool wraps the corresponding function and exposes a JSON schema
    derived from the function signature. The agent loop can discover
    them via ``registry.find_by_capability("user_research")``.

    Returns the number of newly registered tools.
    """
    before = len(registry.list_all())

    @registry.agent_tool(
        name="user_research_plan",
        description=(
            "Produce a structured user-research plan (objectives, hypotheses, "
            "methods, target sample size, timeline) from a research question."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Short research title"},
                "primary_question": {"type": "string", "description": "The single most important question"},
                "audience": {"type": "string", "description": "Who the research is for"},
                "objectives": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "statement": {"type": "string"},
                            "priority": {"type": "string", "enum": ["must", "should", "could"]},
                            "success_metric": {"type": "string"},
                        },
                        "required": ["statement"],
                    },
                    "description": "Research objectives (questions or goals)",
                },
                "methods": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "method": {
                                "type": "string",
                                "enum": [
                                    "interview", "survey", "diary_study",
                                    "usability_test", "card_sorting", "tree_testing",
                                    "field_observation", "focus_group",
                                ],
                            },
                            "target_participants": {"type": "integer"},
                            "duration_minutes": {"type": "integer"},
                            "rationale": {"type": "string"},
                        },
                        "required": ["method", "target_participants"],
                    },
                    "description": "Research methods to use",
                },
                "population_size": {"type": "integer", "description": "Optional finite population size"},
                "margin_of_error": {"type": "number", "default": 0.05},
                "timeline_days": {"type": "integer", "default": 14},
                "hypotheses": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "statement": {"type": "string"},
                            "null_alternative": {"type": "boolean"},
                        },
                        "required": ["statement"],
                    },
                },
                "scope_in": {"type": "array", "items": {"type": "string"}},
                "scope_out": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["title", "primary_question", "audience", "objectives", "methods"],
        },
        capabilities=["user_research", "plan"],
        cost_tier=1,
    )
    def user_research_plan_tool(
        *,
        title: str,
        primary_question: str,
        audience: str,
        objectives: list[dict[str, Any]],
        methods: list[dict[str, Any]],
        population_size: int | None = None,
        margin_of_error: float = 0.05,
        timeline_days: int = 14,
        hypotheses: list[dict[str, Any]] | None = None,
        scope_in: list[str] | None = None,
        scope_out: list[str] | None = None,
    ) -> dict[str, Any]:
        plan = plan_research(
            title=title,
            primary_question=primary_question,
            audience=audience,
            objectives=objectives,
            methods=methods,
            population_size=population_size,
            margin_of_error=margin_of_error,
            timeline_days=timeline_days,
            hypotheses=hypotheses,
            scope_in=scope_in,
            scope_out=scope_out,
        )
        return plan.model_dump()

    @registry.agent_tool(
        name="user_research_qual",
        description=(
            "Analyse qualitative data (interview transcripts, open-ended survey "
            "responses, notes) to extract pain points, desires, and themes with "
            "supporting verbatim quotes."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Description of the data source"},
                "transcripts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "One transcript string per participant",
                },
                "participant_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional participant IDs (P1..Pn default)",
                },
                "pain_point_keywords": {"type": "array", "items": {"type": "string"}},
                "desire_keywords": {"type": "array", "items": {"type": "string"}},
                "min_theme_frequency": {"type": "integer", "default": 2},
            },
            "required": ["source", "transcripts"],
        },
        capabilities=["user_research", "qualitative"],
        cost_tier=1,
    )
    def user_research_qual_tool(
        *,
        source: str,
        transcripts: list[str],
        participant_ids: list[str] | None = None,
        pain_point_keywords: list[str] | None = None,
        desire_keywords: list[str] | None = None,
        min_theme_frequency: int = 2,
    ) -> dict[str, Any]:
        analysis = analyze_qualitative(
            source=source,
            transcripts=transcripts,
            participant_ids=participant_ids,
            pain_point_keywords=pain_point_keywords,
            desire_keywords=desire_keywords,
            min_theme_frequency=min_theme_frequency,
        )
        return analysis.model_dump()

    @registry.agent_tool(
        name="user_research_quant",
        description=(
            "Compute descriptive statistics (mean, median, stdev, distribution, "
            "segment cuts) for a numeric series from a survey or experiment."
        ),
        parameters={
            "type": "object",
            "properties": {
                "source": {"type": "string"},
                "values": {"type": "array", "items": {"type": "number"}},
                "metric_name": {"type": "string"},
                "metric_type": {
                    "type": "string",
                    "enum": ["rating", "count", "duration_seconds", "percentage", "binary"],
                    "default": "rating",
                },
                "bins": {"type": "integer", "default": 5},
                "segments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {"type": "string"},
                            "count": {"type": "integer"},
                            "mean": {"type": "number"},
                            "median": {"type": "number"},
                            "stdev": {"type": "number"},
                        },
                        "required": ["name", "count", "mean", "median", "stdev"],
                    },
                },
            },
            "required": ["source", "values", "metric_name"],
        },
        capabilities=["user_research", "quantitative"],
        cost_tier=1,
    )
    def user_research_quant_tool(
        *,
        source: str,
        values: list[float],
        metric_name: str,
        metric_type: str = "rating",
        bins: int = 5,
        segments: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        analysis = analyze_quantitative(
            source=source,
            values=values,
            metric_name=metric_name,
            metric_type=metric_type,  # type: ignore[arg-type]
            bins=bins,
            segments=segments,
        )
        return analysis.model_dump()

    @registry.agent_tool(
        name="user_research_synthesize",
        description=(
            "Combine a quantitative analysis and/or a qualitative analysis into "
            "a single decision-ready research brief with executive summary, key "
            "findings, and recommendations."
        ),
        parameters={
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "quant": {
                    "type": "object",
                    "description": "Optional QuantAnalysis dict (from user_research_quant)",
                },
                "qual": {
                    "type": "object",
                    "description": "Optional QualAnalysis dict (from user_research_qual)",
                },
                "key_findings": {"type": "array", "items": {"type": "string"}},
                "recommendations": {"type": "array", "items": {"type": "string"}},
                "next_steps": {"type": "array", "items": {"type": "string"}},
                "confidence": {
                    "type": "string",
                    "enum": ["high", "medium", "low"],
                    "default": "medium",
                },
            },
            "required": ["title"],
        },
        capabilities=["user_research", "synthesis"],
        cost_tier=1,
    )
    def user_research_synthesize_tool(
        *,
        title: str,
        quant: dict[str, Any] | None = None,
        qual: dict[str, Any] | None = None,
        key_findings: list[str] | None = None,
        recommendations: list[str] | None = None,
        next_steps: list[str] | None = None,
        confidence: str = "medium",
    ) -> dict[str, Any]:
        quant_model = QuantAnalysis.model_validate(quant) if quant else None
        qual_model = QualAnalysis.model_validate(qual) if qual else None
        brief = synthesize_research(
            title=title,
            quant=quant_model,
            qual=qual_model,
            key_findings=key_findings,
            recommendations=recommendations,
            next_steps=next_steps,
            confidence=confidence,  # type: ignore[arg-type]
        )
        return brief.model_dump()

    return len(registry.list_all()) - before


def auto_register() -> int:
    """Register the user research tools into the module-level singleton registry.

    Returns the number of newly registered tools, or 0 if registration
    has already happened.
    """
    from agent.capability_registry import get_tool_registry
    registry = get_tool_registry()
    if any(t.name == "user_research_plan" for t in registry.list_all()):
        return 0
    return register_user_research_tools(registry)
