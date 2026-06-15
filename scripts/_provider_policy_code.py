# --- Provider Policy (Paid-Provider Kill Switch) ----------------------------------------
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
