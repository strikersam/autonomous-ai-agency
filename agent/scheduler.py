"""agent/scheduler.py — backward-compat shim.

Real implementation: ``packages/scheduler/scheduler.py`` (moved in V2.0 Phase 4).
"""
from packages.scheduler.scheduler import *  # noqa: F401, F403
import packages.scheduler.scheduler as _real

_g = globals()
for _name in dir(_real):
    if _name.startswith("__") and _name not in ("__all__",):
        continue
    _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
