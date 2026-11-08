"""Map a detected framework name to the system type it implies.

The scanner reports frameworks with display names ("FastAPI", "Vue.js",
"Next.js"); onboarding used to compare them against a short lowercase list
("django", "flask", ...), so a FastAPI backend or a "Vue.js" frontend was
never recognised and the company got generic specialists instead of the right
technical ones. One normaliser, used everywhere a framework becomes a family.
"""
from __future__ import annotations

_FRONTEND = frozenset({
    "react", "vue", "angular", "svelte", "next", "nuxt", "vite", "remix",
    "astro", "gatsby", "solid", "preact", "ember",
})
_BACKEND = frozenset({
    "django", "flask", "fastapi", "starlette", "rails", "laravel", "express",
    "nestjs", "nest", "spring", "springboot", "aiohttp", "tornado", "sanic", "koa", "hapi",
    "phoenix", "gin", "fiber", "aspnet", "symfony",
})


def _normalise(name: str) -> str:
    low = (name or "").strip().lower()
    for suffix in (".js", "js"):
        if low.endswith(suffix) and low not in {"js"}:
            low = low[: -len(suffix)]
            break
    return low.replace(" ", "").replace(".", "").replace("-", "")


def system_type_for_framework(name: str) -> str | None:
    """``"frontend"``, ``"backend"`` or ``None`` for a scanner framework name."""
    key = _normalise(name)
    if key in _FRONTEND:
        return "frontend"
    if key in _BACKEND:
        return "backend"
    return None
