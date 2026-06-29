"""packages/resilience/__init__.py — Provider Resilience.

Graceful failover, task checkpointing, state preservation, and
transparent recovery when providers become unavailable.
"""
from packages.resilience.checkpoint import (
    Checkpoint, CheckpointManager, get_checkpoint_manager,
)

__all__ = [
    "Checkpoint", "CheckpointManager", "get_checkpoint_manager",
]
