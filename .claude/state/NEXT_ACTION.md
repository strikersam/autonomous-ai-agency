# NEXT_ACTION — updated 2026-11-14 (daily automation)

**What shipped:** PR #1962 — Claude Fable 5.2 / Mythos 5.2 / Meta Muse Ember in model catalogue; docs
configuration-reference.md updated to reference current default model `nvidia/nemotron-3-ultra-550b-a55b`.
Auto-merge armed; will land once CI passes.

## Open items

1. **Muse Ember long-context tier** not reflected in cost_tracker: requests above 200K input tokens
   are billed at $0.30/$1.50 (3x higher). `cost_for_tokens` has no per-token-count pricing bands;
   this would need a new cost function signature. Currently the standard $0.10/$0.50 is returned
   for all request sizes — conservative under-accounting for large context calls.
2. **Claude Fable 5.2 / Mythos 5.2 versioned IDs** (e.g. `claude-fable-5-2-20261109`) not yet
   in the catalogue — add once Anthropic publishes them.
3. **NEXT_ACTION open from 2026-11-12 (task failure rate / capacity backoff):** `claude/epic-hopper-mwe63w`
   branch has work pushed but no PR yet. See that branch's last commit for details.
4. **Muse Ember priority:** currently 99 (explicit-only). Lower once catalogue-probe.yml
   sees a 200 from the OpenRouter endpoint.

## Next daily run

Start from openrouter.ai/models for the next catalogue pass. Check for:
- Versioned IDs for Fable 5.2 / Mythos 5.2 (e.g. claude-fable-5-2-20261109)
- Any Gemini 4 Hydrogen confirmation (Nov 12-13 search was inconclusive)
- GPT-6-Cyber availability beyond restricted security teams
