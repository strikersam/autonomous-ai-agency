"""agents/persona_library.py — role personas for auto-provisioned specialists.

Every specialist a company onboarding provisions is registered in AgentStore by
``services/company_agency.py``, and task execution hands the agent's
``system_prompt`` to the runtime. That prompt was always empty: a provisioned
"security" specialist worked a task with no security method, no rules and no
definition of done — only the family name in its tag.

The personas come from `msitarzewski/agency-agents
<https://github.com/msitarzewski/agency-agents>`_ (MIT, quick note #1570), a
curated catalogue of specialist agents. A reviewed subset is vendored
unchanged under ``agents/personas/agency_agents/`` with its LICENSE; see the
README there for the source commit. Only families with a genuine counterpart
are mapped — a family with no good match (merchandising, PIM, OMS, DAM,
trading) keeps an empty prompt rather than a misleading one.

``distill`` keeps the parts of a persona that change how the agent works —
identity, mission, critical rules, workflow, success criteria — and drops code
examples, communication-style flavour and memory boilerplate, so the prompt
costs about a third of the source file.
"""
from __future__ import annotations

import functools
import logging
import re
from pathlib import Path

log = logging.getLogger("qwen-proxy")

PERSONA_DIR = Path(__file__).resolve().parent / "personas" / "agency_agents"
SOURCE_REPO = "https://github.com/msitarzewski/agency-agents"
MAX_PERSONA_CHARS = 7000

#: SpecialistFamily (models/company_graph.py) → vendored persona file stem.
FAMILY_PERSONAS: dict[str, str] = {
    "engineering": "engineering-senior-developer",
    "fullstack": "engineering-senior-developer",
    "frontend": "engineering-frontend-developer",
    "backend": "engineering-backend-architect",
    "architecture": "engineering-software-architect",
    "mobile": "engineering-mobile-app-builder",
    "devops": "engineering-devops-automator",
    "infra": "engineering-sre",
    "cloud": "engineering-platform-engineer",
    "platform": "engineering-platform-engineer",
    "data": "engineering-data-engineer",
    "ml": "engineering-ai-engineer",
    "docs": "engineering-technical-writer",
    "qa": "testing-test-automation-engineer",
    "security": "security-appsec-engineer",
    "analytics": "support-analytics-reporter",
    "support": "support-support-responder",
    "operations": "operations-manager",
    "agile": "product-sprint-prioritizer",
    "portfolio": "project-manager-senior",
    "delivery": "project-management-project-shepherd",
    "product": "product-manager",
    "design": "design-ui-designer",
    "ux": "design-ux-researcher",
    "seo": "marketing-seo-specialist",
    "content": "marketing-content-creator",
    "marketing": "marketing-growth-hacker",
    "crm": "specialized-salesforce-architect",
    "research": "research-synthesist",
}

# Section headings (emoji stripped, lowercased) that define how the agent
# works. Everything else — deliverable code samples, voice, memory — is cut.
_KEEP = ("identity", "mission", "critical rules", "rules", "workflow",
         "process", "success", "philosophy")
_FRONTMATTER = re.compile(r"\A---\n.*?\n---\n", re.S)
_CODE_BLOCK = re.compile(r"```.*?```", re.S)
_HEADING = re.compile(r"^## +(.*)$", re.M)
_BLANK_RUN = re.compile(r"\n{3,}")


def _heading_key(heading: str) -> str:
    return re.sub(r"[^a-z &]", "", heading.lower()).strip()


def distill(markdown: str, max_chars: int = MAX_PERSONA_CHARS) -> str:
    """Reduce a persona file to its role-defining sections, capped at a
    section boundary so the prompt never ends mid-rule."""
    body = _CODE_BLOCK.sub("", _FRONTMATTER.sub("", markdown))
    parts = _HEADING.split(body)
    preamble, sections = parts[0].strip(), list(zip(parts[1::2], parts[2::2]))
    out = preamble
    for heading, text in sections:
        if not any(k in _heading_key(heading) for k in _KEEP):
            continue
        text = _BLANK_RUN.sub("\n\n", text.strip())
        block = f"\n\n## {heading.strip()}\n{text}"
        if len(out) + len(block) > max_chars:
            break
        out += block
    return out.strip()


@functools.lru_cache(maxsize=64)
def _load(stem: str) -> str:
    path = PERSONA_DIR / f"{stem}.md"
    try:
        return distill(path.read_text(encoding="utf-8"))
    except OSError:
        log.warning("persona_library: missing persona file %s", path)
        return ""


def persona_for_family(family: str, company_name: str = "") -> str:
    """System prompt for a provisioned specialist of ``family`` ('' if none).

    The attribution line is part of the prompt on purpose: it tells whoever
    reads a run log where the persona came from and that it is a template.
    """
    stem = FAMILY_PERSONAS.get(family)
    if not stem:
        return ""
    persona = _load(stem)
    if not persona:
        return ""
    scope = f" You work for {company_name}." if company_name else ""
    return (
        f"You are this agency's {family} specialist.{scope} Adopt the role below; "
        f"the agency's own rules and the task instructions take precedence over it.\n\n"
        f"{persona}\n\n"
        f"_(Role template: {SOURCE_REPO} — {stem}, MIT.)_"
    )
