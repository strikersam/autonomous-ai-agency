# Autonomy Uplift — Living Roadmap & Detailed Implementation Specs

> **Purpose.** Single source of truth for the "make the agency self-maintaining,
> with a Telegram gate I can act from" effort. This PR stays **open** as a
> tracker — updated as each item lands.
>
> **Audience note (important).** The implementation specs in §3 are written to be
> executed by a **low-powered LLM** (e.g. the NIM/Cerebras auto-PR agent). They
> are deliberately prescriptive: exact files, signatures, steps, tests, and
> explicit **DO-NOT** guardrails. An item is "done" only when its **Acceptance**
> checks pass. When in doubt, an agent should make the **smallest additive
> change** and never delete or empty an existing file (the slop-gate enforces this).
>
> Status legend: ✅ done & merged · 🟡 in flight · ⬜ pending · 🔭 deferred.
> Last updated: 2026-06-26.

---

## 0. The goal (operator's words)

> "Consider you are replacing me to run the autonomous AI agency repo — keep it
> up to date, learn, self-heal on errors/bugs/failure logs, and let me rest,
> acting only through a Telegram gate."

North star: **trustworthy self-maintenance** (auto-PRs that aren't slop) +
**observe & act from Telegram** + a brain that's **free, fast, always-on,
swappable from the UI** + the agency's **own** runtime servers (Hermes), not
external dependencies.

---

## 1. Shipped ✅

| Item | PR |
|------|----|
| Brain liveness-probe `NameError` fixed | [#831](https://github.com/strikersam/autonomous-ai-agency/pull/831) |
| Brain auto-selects **Cerebras → Groq → NIM** by key | [#831](https://github.com/strikersam/autonomous-ai-agency/pull/831) |
| Loop Engineering **UI screen** + `GET /api/loops` | [#834](https://github.com/strikersam/autonomous-ai-agency/pull/834) |
| README truth-up | [#834](https://github.com/strikersam/autonomous-ai-agency/pull/834) |
| Brain card Ollama note + crash guard | [#834](https://github.com/strikersam/autonomous-ai-agency/pull/834) |
| Telegram **observe**: `/autonomy` + `/loops` | [#835](https://github.com/strikersam/autonomous-ai-agency/pull/835) |
| **Ollama brain base URL via Provider UI** (no Render env) | [#836](https://github.com/strikersam/autonomous-ai-agency/pull/836) |

## 2. In flight 🟡

| Item | PR |
|------|----|
| **Slop-gate for auto-PRs** + auto-PR scripts use the upgraded brain (root-cause of #833) | [#837](https://github.com/strikersam/autonomous-ai-agency/pull/837) |

---

## 3. Pending ⬜ — detailed implementation specs

> Conventions: run `pytest -x` before and after. Update `docs/changelog.md`
> **and** `CHANGELOG.md` identically (parity gate). Branch off `master`. Never
> touch `admin_auth.py` / `key_store.py` / `agent/tools.py` without the
> `risky-module-review` skill. Suppress any new `subprocess.run([...])` Bandit
> finding with a **bare** `# nosec` on that line (a specific-id nosec mis-parses).

### 3a. Apply the slop-gate to the sibling auto-PR scripts ✅  (size: S)

**Goal.** `#837` gates `.github/scripts/autonomous_agent.py`. Three siblings
write model output to disk the same blind way. Make them import the shared gate.

**Files to modify (surgical edits only — do NOT rewrite them):**
1. `.github/scripts/implement_agent.py`
2. `.github/scripts/apply_review.py`
3. `scripts/agency_fix.py`

**Steps (apply the same pattern to each):**
1. After the existing imports, add (for files in `.github/scripts/`):
   ```python
   import sys, os
   sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
   from slop_gate import is_destructive_overwrite, python_parses, diff_is_sloppy
   ```
   For `scripts/agency_fix.py` (a different dir) point the insert at the repo's
   `.github/scripts` dir instead.
2. Find every `Path(path).write_text(content)` of **model-derived** content.
   Immediately **before** each, insert:
   ```python
   if Path(path).exists():
       _bad, _why = is_destructive_overwrite(Path(path).read_text(), content)
       if _bad:
           print(f"SLOP-GATE: refusing {path} — {_why}"); sys.exit(0)
   if path.endswith(".py") and not python_parses(content):
       print(f"SLOP-GATE: {path} does not parse"); sys.exit(0)
   ```
3. If the script computes a pre-commit git diff, add the aggregate guard
   (copy from `autonomous_agent.py` §7), with a bare `# nosec` on the numstat line.
4. In each owning workflow yml, add `CEREBRAS_API_KEY` + `GROQ_API_KEY` to the
   step `env:` and route any hardcoded model through a `_select_brain()` helper
   copied from `autonomous_agent.py`.

**DO NOT:** change control flow; remove functionality; add dependencies.

**Acceptance:**
- [ ] Each of the 3 scripts imports `slop_gate` and guards every model-driven write.
- [ ] `python -m py_compile` passes for all three.
- [ ] Security Gate delta is 0.
- [ ] Changelog updated in both files.

---

### 3b. Hermes — **our own** Hermes server (in-repo), UI-wired ⬜  (size: M)

**Decision (corrected per operator): we run our OWN Hermes server inside this
repo's stack — NOT an external NousResearch deployment.** It is a thin FastAPI
service that speaks the API `runtimes/adapters/hermes.py` already calls
(`GET /health`, `POST /tasks`) and executes via our existing
`InternalAgentAdapter` (i.e. on our brain). This makes Hermes genuinely ours and
running, with zero external dependency.

**Files to CREATE:**
1. `services/hermes_server.py` — standalone FastAPI app (sketch — verify the real
   `TaskSpec`/`TaskResult` field names in `runtimes/base.py` and match exactly;
   DO NOT invent fields):
   ```python
   """Our own Hermes-compatible runtime server. Speaks the API the
   HermesAdapter calls; executes via InternalAgentAdapter (our brain)."""
   from __future__ import annotations
   import uuid
   from fastapi import FastAPI
   from pydantic import BaseModel
   app = FastAPI(title="Agency Hermes")

   class TaskIn(BaseModel):
       task_id: str | None = None
       instruction: str
       task_type: str = "code_review"
       timeout_sec: int = 600
       context: dict | None = None
       workspace_path: str | None = None
       model: str | None = None

   @app.get("/health")
   async def health():
       return {"status": "ok", "runtime": "hermes", "ours": True}

   @app.post("/tasks")
   async def tasks(t: TaskIn):
       from runtimes.adapters.internal_agent import InternalAgentAdapter
       from runtimes.base import TaskSpec
       spec = TaskSpec(
           task_id=t.task_id or str(uuid.uuid4()),
           instruction=t.instruction, task_type=t.task_type,
           workspace_path=t.workspace_path, model_preference=t.model,
           timeout_sec=t.timeout_sec, context=t.context or {},
       )
       res = await InternalAgentAdapter().execute(spec)
       return {"task_id": spec.task_id,
               "status": "done" if res.success else "failed",
               "success": res.success, "output": res.output,
               "artifacts": getattr(res, "artifacts", [])}
   ```
2. `Dockerfile.hermes` — minimal, mirror `Dockerfile.backend`;
   `CMD ["uvicorn", "services.hermes_server:app", "--host", "0.0.0.0", "--port", "8100"]`.
3. Add a `hermes` service to `docker-compose.yml` (port 8100, same env as the
   backend so it can reach the brain) and inject `HERMES_BASE_URL=http://hermes:8100`
   into the backend service env.

**Files to MODIFY (surgical):**
4. `services/brain_config_store.py` — add `resolve_hermes_base_url()` mirroring
   `resolve_ollama_base_url()` (DB-persisted value → `HERMES_BASE_URL` env →
   `http://localhost:8100`).
5. `runtimes/adapters/hermes.py` — resolve `self._base_url` via
   `resolve_hermes_base_url()` first, keep env fallback (~3 lines).
6. (Optional this pass) Runtimes-screen "Hermes base URL" field, mirroring the
   BrainCard Ollama field.

**Tests:**
- `tests/test_hermes_server.py` — TestClient `/health` (200, `ours:true`);
  `/tasks` with `InternalAgentAdapter.execute` monkeypatched to a fake result;
  assert response shape.
- `tests/test_hermes_base_url.py` — `resolve_hermes_base_url()` precedence.

**DO NOT:** depend on external `NousResearch/hermes-agent`; add heavy deps; change
`InternalAgentAdapter`'s signature.

**Acceptance:**
- [ ] `uvicorn services.hermes_server:app` serves `/health` + `/tasks`.
- [ ] With `HERMES_BASE_URL` pointed at it, Doctor/Runtimes shows Hermes **online**.
- [ ] `docker-compose up` starts a `hermes` service the backend reaches.
- [ ] Tests pass; changelog updated (both files).

---

### 3c. CRISPY — harden, then re-enable ⬜  (size: L, risky-module-review)

**Why demoted (#467):** `workflow/engine.py` "does not enforce its own phase
sequence" + lacks isolation. We must *fix*, not flip.

**Steps:**
1. Read `workflow/engine.py` + `agents/profiles.py` + `agents/swarm.py` fully.
2. Add **phase-sequence enforcement**: run architect → scout → coder → reviewer →
   verifier **in order**; refuse to advance until the prior phase returns a valid
   result; add a typed `PhaseSequenceError`.
3. Add **per-task worktree isolation** (reuse
   `agent/job_manager.make_isolated_workspace`).
4. Tests `tests/test_crispy_workflow.py`: phases run in order; a skipped/failed
   phase aborts cleanly; two concurrent tasks get isolated workspaces.
5. Only after green, set the `crispy_workflow` entry live in `features/matrix.py`
   and document `FEATURE_CRISPY_WORKFLOW=enabled`.

**DO NOT:** flip the flag before enforcement + isolation + tests exist.

**Acceptance:**
- [ ] Phase-ordering + isolation tests pass.
- [ ] `FEATURE_CRISPY_WORKFLOW=enabled` runs a real 5-role task end-to-end on the brain.
- [ ] `risky-module-review` recorded in the PR.

---

### 3d. Phase 3 — auto-PR *quality* beyond the slop-gate ⬜  (size: M)

1. **Codebase grounding**: before the model call, attach the relevant files
   (`graphify query` output or `read_file` on paths named in the issue) to the
   prompt so the model edits real code, not guesses.
2. **Verifier routing**: after applying changes and before opening the PR, run the
   `agent/loop.py` verifier (or at minimum `pytest -x` on touched modules); abort
   the PR (`sys.exit(0)`) on failure.
3. **Auto-merge gate**: only enable auto-merge on an auto-PR when CI is green **and**
   the verifier passed.

**Acceptance:** an auto-PR that breaks tests never opens; a passing one opens with a "verified" note.

---

### 3e. Phase 4 — reliability spine ⬜  (size: M)

1. **Brain health-watchdog** (`services/brain_watchdog.py` + a `loops/registry.yaml`
   entry): on N consecutive provider failures, auto-fail-over to the next provider
   in `RECOMMENDED_PROVIDER_PRIORITY` (persist via the brain store) + Telegram page.
2. **Weekly readiness digest** to Telegram via `NotificationDispatcher`: loop
   readiness score, drift, monthly cost, open auto-PR count.
3. Document the stable Cloudflare-tunnel setup for the Ollama fallback.

**Acceptance:** killing the active provider in a test triggers a logged fail-over to the next; the weekly digest renders.

---

## 4. Deferred 🔭

| Item | Why |
|------|-----|
| **Mutating Telegram control** (switch brain / merge PR from the phone) | Needs a backend **service-token** — an auth-surface change warranting its own `risky-module-review` PR. |

---

## 5. Operating notes

- **Recommended brain:** set `CEREBRAS_API_KEY` in Render → the in-app brain *and*
  the auto-PR scripts use Cerebras automatically. NIM 49B is the always-on floor.
- **Local GPU as brain:** Providers → Brain → Ollama → paste tunnel URL → Test → Apply.
- **Watch the fleet:** the **Loops** screen, or `/loops` / `/autonomy` on Telegram.
- **Auto-PRs** are now slop-gated — but always eyeball the +/- before merging.
