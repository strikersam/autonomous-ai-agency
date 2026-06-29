"""packages.config — single source of truth for all configuration.

Every module imports `from packages.config import settings`.
No module reads `os.environ` directly (except this one).
"""
from packages.config.settings import settings

__all__ = ["settings"]
