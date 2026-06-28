"""services/brain_watchdog.py — backward-compat shim.

Real implementation: ``packages/ai/watchdog.py`` (moved in V2.0 Phase 2).
"""
from packages.ai.watchdog import *  # noqa: F401, F403
import packages.ai.watchdog as _real

_g = globals()
for _name in dir(_real):
    if _name.startswith("__") and _name not in ("__all__",):
        continue
    _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
