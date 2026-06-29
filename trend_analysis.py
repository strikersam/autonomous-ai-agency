"""trend_analysis.py — backward-compat shim.

Real implementation: ``packages.telemetry.trend_analysis`` (moved in reorg PR).
"""
from packages.telemetry.trend_analysis import *  # noqa: F401, F403
import packages.telemetry.trend_analysis as _real

_g = globals()
for _name in dir(_real):
    if not _name.startswith("__") or _name == "__all__":
        _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
