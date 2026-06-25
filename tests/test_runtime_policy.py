import os
import importlib


def test_runtime_manager_default_prefers_internal(monkeypatch):
    # Ensure AGENT_MODE_DOCKER is not set
    monkeypatch.delenv("AGENT_MODE_DOCKER", raising=False)
    # Reset manager singleton and reload
    import runtimes.manager as mgr_mod
    mgr_mod._runtime_manager = None
    rm = mgr_mod.get_runtime_manager()
    assert rm._router.policy.preferred_runtime_id == "internal_agent"
