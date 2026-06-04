"""tests/test_skills_route_order.py — /api/company/skills must not be shadowed.

The static `GET /skills` catalog route is registered on the same router as the
dynamic `GET /{company_id}` route. If `/{company_id}` is registered first,
Starlette matches `/api/company/skills` as `company_id="skills"` and the skill
catalog becomes unreachable. This locks the correct ordering.
"""
from __future__ import annotations

from backend.company_api import router


def _route_index(path: str) -> int:
    for i, r in enumerate(router.routes):
        if getattr(r, "path", None) == path:
            return i
    raise AssertionError(f"route {path} not registered")


def test_static_skills_routes_precede_dynamic_company_id_route():
    company_id_idx = _route_index("/api/company/{company_id}")
    for static_path in (
        "/api/company/skills",
        "/api/company/skills/recommend/auto",
        "/api/company/skills/recommend",
    ):
        assert _route_index(static_path) < company_id_idx, (
            f"{static_path} is registered AFTER /{{company_id}} and will be "
            f"shadowed (matched as company_id='skills')."
        )
