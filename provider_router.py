"""provider_router.py — backward-compat shim.

Real implementation: ``packages/ai/router.py`` (moved in V2.0 Phase 2).
This shim re-exports EVERY symbol (public + private) so existing
`from provider_router import X` calls keep working.
"""
from packages.ai.router import *  # noqa: F401, F403
import packages.ai.router as _real

# Re-export every name the real module exposes (including private ones —
# tests import `_release_provider_probe`, `_record_429_failure`, etc.).
_g = globals()
for _name in dir(_real):
    if _name.startswith("__") and _name not in ("__all__",):
        continue
    _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
