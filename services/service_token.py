"""services/service_token.py — backward-compat shim.

Real implementation: ``packages/auth/service_token.py`` (moved in V2.0 Phase 3).
"""
from packages.auth.service_token import *  # noqa: F401, F403
import packages.auth.service_token as _real

_g = globals()
for _name in dir(_real):
    if _name.startswith("__") and _name not in ("__all__",):
        continue
    _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
