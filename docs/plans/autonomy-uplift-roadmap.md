# Autonomy Uplift — Living Roadmap & Checklist

> **Purpose.** Single source of truth for the "make the agency self-maintaining,
> with a Telegram gate I can act from" effort. This PR stays **open** as a
> tracker — it's updated as each work item lands. Each checklist item links to
> the PR that delivered it.
>
> **How to read this:** ✅ done & merged · 🟡 in flight (PR open) · ⬜ pending ·
> 🔭 deferred (needs a decision or external dependency).

Last updated: 2026-06-26.

---

## 0. The goal (operator's words)

> "Consider you are replacing me to run the autonomous AI agency repo — keep it
> up to date, learn, self-heal on errors/bugs/failure logs, and let me rest,
> acting only through a Telegram gate."

So the north star is: **trustworthy self-maintenance** (auto-PRs that aren't
slop) + **observability & control from Telegram** + **a brain that's free,
fast, always-on, and swappable from the UI**.

---

## 1. Shipped ✅

| Item | PR | Notes |
|------|----|-------|
| Brain liveness-probe `NameError` fixed (cloud providers couldn't be saved) | [#831](https://github.com/strikersam/autonomous-ai-agency/pull/831) | `services/brain_liveness.py` |
| Brain auto-selects recommended free chain **Cerebras → Groq → NIM** by key | [#831](https://github.com/strikersam/autonomous-ai-agency/pull/831) | `recommended_brain_config()` |
| Loop Engineering **UI screen** (`/v5/loops`) + `GET /api/loops` | [#834](https://github.com/strikersam/autonomous-ai-agency/pull/834) | readiness score/grade, drift, cost, per-loop table |
| README truth-up (brain, Cerebras/Groq, dormant sidecars) | [#834](https://github.com/strikersam/autonomous-ai-agency/pull/834) | |
| Brain card Ollama note + crash guard | [#834](https://github.com/strikersam/autonomous-ai-agency/pull/834) | |
| Telegram **observe**: `/autonomy` + `/loops` | [#835](https://github.com/strikersam/autonomous-ai-agency/pull/835) | read-only, no auth bridge |
| **Ollama brain base URL via Provider UI** (no Render env) | [#836](https://github.com/strikersam/autonomous-ai-agency/pull/836) | DB-persisted, drives the real run |

---

## 2. In flight 🟡

| Item | PR | Status |
|------|----|--------|
| **Slop-gate for auto-PRs** + auto-PR scripts use the upgraded brain (root-cause of the destructive #833) | [#837](https://github.com/strikersam/autonomous-ai-agency/pull/837) | auto-merge armed |

---

## 3. Pending ⬜ — implementation plan

### 3a. Apply the slop-gate to the sibling auto-PR scripts ⬜
**Why:** `#837` gates `autonomous_agent.py` (the proven #833 culprit), but three
siblings share the same blind-`write_text` + hardcoded-NIM pattern.
**Plan:**
- [ ] `implement_agent.py` — import `slop_gate`; guard every model-driven write; use `_select_brain()`.
- [ ] `apply_review.py` — same guards at its `write_text` (line ~170).
- [ ] `scripts/agency_fix.py` — same guards at its `write_text` (line ~253).
- [ ] Pass `CEREBRAS_API_KEY`/`GROQ_API_KEY` in each owning workflow.
- [ ] Extend `tests/test_slop_gate.py` if new edge cases surface.

### 3b. Hermes: URL-configurable from the UI + a deploy recipe 🟡→⬜ (operator chose "option 1, both eventually")
**Why:** the Hermes adapter works but is inert — no server deployed, and its URL
is env-only. Operator wants it to "work well."
**Plan:**
- [ ] Make `HERMES_BASE_URL` (and other sidecar URLs) **UI-settable + DB-persisted** (Runtimes screen), mirroring the Ollama pattern.
- [ ] Add a `docker-compose` recipe + docs to run a Hermes server you can tunnel.
- [ ] Surface honest live/offline status in the Runtimes UI.
- [ ] (External dependency: operator deploys/hosts the Hermes server.)

### 3c. CRISPY: harden then re-enable ⬜ (operator wants it to "work well")
**Why:** demoted (#467) because `workflow/engine.py` doesn't enforce its phase
sequence + lacks isolation. Re-enabling as-is = flaky. Must *fix*, not flip.
**Plan:**
- [ ] Implement phase-sequence enforcement in `workflow/engine.py` (planner→executor→reviewer→verifier ordering, no skips).
- [ ] Add per-task worktree isolation (or reuse `internal_agent`'s).
- [ ] Tests for phase ordering + isolation.
- [ ] Flip `FEATURE_CRISPY_WORKFLOW=enabled` only once green. (Risky module → `risky-module-review`.)

### 3d. Phase 3 — auto-PR quality beyond the slop-gate ⬜
**Why:** the slop-gate stops *destructive* PRs; this raises *positive* quality.
**Plan:**
- [ ] **Codebase grounding**: feed the auto-PR model the relevant files/graph context (not just the issue text).
- [ ] **Verifier routing**: run generated changes through the `agent/loop.py` verifier before opening the PR.
- [ ] **Auto-merge gate**: only auto-merge an auto-PR when CI is green **and** the verifier passed.

### 3e. Phase 4 — reliability spine ⬜
**Plan:**
- [ ] **Brain health-watchdog**: when the active provider starts failing, auto-fail-over to the next in the chain (Cerebras→Groq→NIM→Ollama) and page Telegram.
- [ ] **Weekly readiness digest** pushed to Telegram (loop readiness score, drift, cost, open auto-PRs).
- [ ] Stable Cloudflare tunnel guidance for the Ollama fallback.

---

## 4. Deferred 🔭 (need a decision / external input)

| Item | Why deferred |
|------|--------------|
| **Mutating Telegram control** (switch brain, merge PR from the phone) | Needs a backend **service-token** — an auth-surface change warranting its own `risky-module-review` PR. |
| Hosting a real **Hermes server** | External service; operator must deploy/host it. We make connecting it a UI field + recipe. |

---

## 5. Operating notes for whoever runs this next

- **Recommended brain:** set `CEREBRAS_API_KEY` in Render → the in-app brain *and*
  the auto-PR scripts use Cerebras automatically. NIM 49B is the always-on floor.
- **Local GPU as brain:** Providers → Brain → Ollama → paste your tunnel URL → Test → Apply. No env edit.
- **Watch the fleet:** the **Loops** screen, or `/loops` / `/autonomy` on Telegram.
- **If an auto-PR looks destructive:** it shouldn't get opened anymore (slop-gate), but always eyeball the +/- before merging.
