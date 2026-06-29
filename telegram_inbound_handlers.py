"""telegram_inbound_handlers.py — backward-compat shim.

Real implementation: ``packages/notifications/inbound.py`` (moved in cleanup PR).
"""
from packages.notifications.inbound import *  # noqa: F401, F403
import packages.notifications.inbound as _real

_g = globals()
for _name in dir(_real):
    if not _name.startswith("__") or _name == "__all__":
        _g[_name] = getattr(_real, _name)

__all__ = [n for n in dir(_real) if not n.startswith("__") or n == "__all__"]
