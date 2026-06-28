"""services/brain_config_store.py — backward-compat shim.

Real implementation: ``packages/ai/brain_config.py`` (moved in V2.0 Phase 2).

NOTE: Tests that mutate the module-level ``_store`` singleton should now
import the real module: ``import packages.ai.brain_config as mod``.
The shim re-exports the SYMBOLS but module-level writes here do NOT
propagate to the real singleton.
"""
from packages.ai.brain_config import *  # noqa: F401, F403
import packages.ai.brain_config as _real

_g = globals()
for _name in dir(_real):
    if _name.startswith("__") and _name not in ("__all__",):
        continue
    _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
