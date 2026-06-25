"""Apply Phase 1 paid-provider kill switch changes to backend/server.py and workflow_orchestrator.py."""
import sys, os

def apply_backend_change():
    """Insert provider policy endpoints before @app.get('/api/models/catalog')."""
    path = "backend/server.py"
    data = open(path, 'rb').read()
    
    # Find @app.get("/api/models/catalog") - the first endpoint after provider routes
    needle = b'@app.get("/api/models/catalog")'
    idx = data.find(needle)
    if idx == -1:
        print("ERROR: Cannot find @app.get('/api/models/catalog') in backend/server.py")
        return False
    
    new_code = b'''# --- Provider Policy (Paid-Provider Kill Switch) ----------------------------------------
# Durable singleton controlling whether paid LLM providers (Anthropic) are
# allowed. Stored in the providers collection with provider_id="provider_policy".
# Edited from the Providers screen; read by every LLM call site and CI.


class ProviderPolicyUpdate(BaseModel):
    """Editable subset of the provider policy."""
    allow_paid: bool = Field(
        default=False,
        description="When false, paid providers (Anthropic) are NEVER auto-selected",
    )


async def _get_provider_policy() -> dict:
    """Read the durable provider policy, falling back to a safe default.

    Returns a dict with at least {'allow_paid': bool}. Never raises.
    Failsafe: returns allow_paid=False when the DB is unreachable.
    """
    try:
        doc = await get_db().providers.find_one({"provider_id": "provider_policy"})
        if doc:
            return {"allow_paid": bool(doc.get("allow_paid", False))}
    except Exception:
        pass
    return {"allow_paid": False}


async def _set_provider_policy(update: ProviderPolicyUpdate) -> dict:
    """Persist the provider policy and return the new state."""
    now = datetime.now(timezone.utc).isoformat()
    await get_db().providers.update_one(
        {"provider_id": "provider_policy"},
        {"$set": {"allow_paid": update.allow_paid, "updated_at": now}},
        upsert=True,
    )
    return {"allow_paid": update.allow_paid}


@app.get("/api/providers/policy")
async def get_provider_policy(user: dict = Depends(get_current_user)):
    """Return the durable provider policy (single source of truth for paid-provider gating)."""
    return await _get_provider_policy()


@app.put("/api/providers/policy")
async def update_provider_policy(
    body: ProviderPolicyUpdate,
    user: dict = Depends(get_current_user),
):
    """Update the provider policy. Admin-only - the UI enforces this."""
    result = await _set_provider_policy(body)
    await log_activity(
        "provider",
        f"Provider policy updated: allow_paid={body.allow_paid}",
        user_id=user["_id"],
    )
    return result


'''
    new_data = data[:idx] + new_code + data[idx:]
    
    assert b"ProviderPolicyUpdate" in new_data, "ProviderPolicyUpdate not in result"
    assert b"/api/providers/policy" in new_data, "/api/providers/policy not in result"
    
    open(path, 'wb').write(new_data)
    print("OK: backend/server.py - inserted provider policy endpoints")
    return True


def apply_workflow_change():
    """Modify _resolve_brain_provider to read allow_paid from the durable policy."""
    path = "services/workflow_orchestrator.py"
    data = open(path, 'rb').read()
    
    # Find and replace the hardcoded fallback logic
    old = (
        b"        # First pass: prefer free cloud providers (NVIDIA NIM, Google Gemini,\r\n"
        b"        # OpenRouter, etc.) \xe2\x80\x94 never auto-select paid Anthropic.\r\n"
        b"        picked = _pick(allow_paid=False)\r\n"
        b"        if picked is None and not _has_usable_free_provider():\r\n"
        b"            # No free provider is configured at all \xe2\x80\x94 only then allow paid\r\n"
        b"            # (Anthropic) as a manual-only last-resort fallback. The operator\r\n"
        b"            # can still disable it by setting AGENT_LLM_BASE_URL to another\r\n"
        b"            # provider or by removing the ANTHROPIC_API_KEY env var.\r\n"
        b"            picked = _pick(allow_paid=True)"
    )
    new = (
        b"        # Read the durable provider policy (default: allow_paid=False).\r\n"
        b"        # This is the single source of truth \xe2\x80\x94 edited from the Providers\r\n"
        b"        # screen. Paid providers (Anthropic) are NEVER auto-selected unless\r\n"
        b"        # the operator explicitly flips the switch.\r\n"
        b"        try:\r\n"
        b"            from backend.server import _get_provider_policy\r\n"
        b"            policy = await _get_provider_policy()\r\n"
        b"            allow_paid = bool(policy.get(\"allow_paid\", False))\r\n"
        b"        except Exception:\r\n"
        b"            allow_paid = False  # failsafe: never allow paid\r\n"
        b"\r\n"
        b"        # First pass: prefer free cloud providers (NVIDIA NIM, Google Gemini,\r\n"
        b"        # OpenRouter, etc.) \xe2\x80\x94 never auto-select paid Anthropic.\r\n"
        b"        picked = _pick(allow_paid=False)\r\n"
        b"        if picked is None and allow_paid:\r\n"
        b"            # allow_paid=True in the policy \xe2\x80\x94 only then fall through to paid\r\n"
        b"            # (Anthropic) as a last-resort. This gate stops silent credit burn\r\n"
        b"            # when ANTHROPIC_API_KEY is set but the policy switch is OFF.\r\n"
        b"            picked = _pick(allow_paid=True)"
    )
    
    if old in data:
        data = data.replace(old, new, 1)
        open(path, 'wb').write(data)
        print("OK: workflow_orchestrator.py - wired allow_paid from durable policy")
        return True
    else:
        # Try without the em-dash characters (using -- instead)
        old2 = (
            b"        # First pass: prefer free cloud providers (NVIDIA NIM, Google Gemini,\r\n"
            b"        # OpenRouter, etc.) -- never auto-select paid Anthropic.\r\n"
            b"        picked = _pick(allow_paid=False)\r\n"
            b"        if picked is None and not _has_usable_free_provider():\r\n"
            b"            # No free provider is configured at all -- only then allow paid\r\n"
            b"            # (Anthropic) as a manual-only last-resort fallback. The operator\r\n"
            b"            # can still disable it by setting AGENT_LLM_BASE_URL to another\r\n"
            b"            # provider or by removing the ANTHROPIC_API_KEY env var.\r\n"
            b"            picked = _pick(allow_paid=True)"
        )
        if old2 in data:
            data = data.replace(old2, new, 1)
            open(path, 'wb').write(data)
            print("OK: workflow_orchestrator.py - wired allow_paid from durable policy (alt match)")
            return True
        else:
            print("ERROR: Cannot find the old string in workflow_orchestrator.py")
            # Show context around line 270
            lines = data.split(b'\r\n')
            for i, line in enumerate(lines):
                if b'First pass: prefer free cloud' in line:
                    print(f"  Found at line {i+1}: {line[:100]}")
            return False


if __name__ == "__main__":
    ok1 = apply_backend_change()
    ok2 = apply_workflow_change()
    if ok1 and ok2:
        print("\nSUCCESS: Both changes applied")
        sys.exit(0)
    else:
        print("\nFAILED: Some changes could not be applied")
        sys.exit(1)
