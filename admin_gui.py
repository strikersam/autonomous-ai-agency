"""admin_gui.py — backward-compat shim.

Real implementation: ``packages.ui.admin_gui`` (moved in reorg PR).
"""
from packages.ui.admin_gui import *  # noqa: F401, F403
import packages.ui.admin_gui as _real

_g = globals()
for _name in dir(_real):
    if not _name.startswith("__") or _name == "__all__":
        _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
