"""task_runner.py — backward-compat shim.

Real implementation: ``packages.orchestration.task_runner`` (moved in reorg PR).
"""
from packages.orchestration.task_runner import *  # noqa: F401, F403
import packages.orchestration.task_runner as _real

_g = globals()
for _name in dir(_real):
    if not _name.startswith("__") or _name == "__all__":
        _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
