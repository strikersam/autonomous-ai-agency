# Autonomy Platform — Remaining Implementation Plan

> **Scope:** This is the agent-ready follow-through plan for PR #652
> (`claude/autonomous-platform-telegram-gates-jf6mrc`). It covers (A) the open
> CodeRabbit review fixes on this PR and (B) the four remaining Autonomy Charter
> integration gaps **G2–G5** (`docs/autonomy/AUTONOMY_CHARTER.md` §6).
>
> **Status of this PR:** G1 (proactive Telegram approval-gate push +
> `TELEGRAM_CHAT_ID` single-operator convention) is **implemented, tested, and
> green** (full suite 2898 passed). G2–G5 are **specified here, not yet built**.
>
> **How to use this doc:** Each part is self-contained. Pick a part, read its
> *Objective → Tech stack → Files → To-dos → Acceptance criteria → Tests*, and
> implement. Every part follows the repo conventions in `CLAUDE.md`
> (type annotations + `from __future__ import annotations`, async I/O, `logging`
> not `print`, Pydantic models for API I/O, changelog entry per meaningful
> commit, `pytest -x` before/after, `risky-module-review` skill for any
> auth/key/`agent/tools.py` change). Honour the repo's **"wired-or-coming-soon,
> nothing in between"** docs-consistency rule (`tests/test_docs_consistency.py`):
> never document a capability as live until it is wired + tested.

---

## Part 0 — P0 production unblockers (issue #656) ✅ landed in this PR

Live agents were stuck and could not act. Root causes + fixes (all tested):

- **Brain hard-blocked on paid-Anthropic `400` →** every task failed 10 retries
  with `"All runtimes failed and policy prevents paid escalation"`. When no free
  provider is configured, `_resolve_brain_provider()` used to silently fall
  through to paid Anthropic; a stale Anthropic model id then returned `400` and
  blocked everything. **Fix:** the brain never silently escalates to paid —
  gated behind `ALLOW_PAID_BRAIN=true` (default off); otherwise it falls to
  local Ollama and logs *“set `NVIDIA_API_KEY` for a free cloud brain.”* This
  makes the **free NVIDIA NIM model the brain** the moment `NVIDIA_API_KEY` is
  set (it is already auto-synthesised as a provider record), with no other
  config. (`services/workflow_orchestrator.py`, `tests/test_brain_priority_scanner.py`.)
- **Telegram `getUpdates` 409/429/502 storm + dual-poller →** the embedded web
  bot and the dedicated worker both polled the same token. **Fix:** honour
  `retry_after` on 429, exponential backoff (5→60s) on conflict/5xx/network, and
  a `TELEGRAM_POLLER_DISABLED=true` single-poller guard (set on the worker in
  `render.yaml` so the web service — which runs the orchestrator in-process for
  G1 callbacks — is the sole poller). (`telegram_bot.py`,
  `tests/test_telegram_freebuff.py`.)
- **Stale `NVIDIA_DEFAULT_MODEL`** example corrected to the live
  `nvidia/llama-3.3-nemotron-super-49b-v1`; `.env.example` documents the
  free-first brain policy.

**Operator action to fully unblock #656:** set `NVIDIA_API_KEY` (free, from
https://build.nvidia.com) in Render on the web service. The brain then resolves
to the free NVIDIA model and never touches Anthropic. A larger free NIM model
(e.g. `nemotron`-class) can be selected via `NVIDIA_DEFAULT_MODEL` once its exact
model id is confirmed on build.nvidia.com.

**Not yet addressed from #656 (lower priority, deferred):** the
`Process Quick Note` auto-implement pipeline's baseline `pytest` times out at
120s in CI (`.github/scripts/implement_agent.py`) — a CI-infra timeout, not a
runtime agent blocker; track separately.

---

## Part A — CodeRabbit review fixes for this PR (do first, small)

These are the actionable review findings on PR #652. They are low-risk and
should land before merge. Order is roughly cheapest-first.

### A1 — `docs/changelog.md`: add the two autonomy docs under `### Added` ✅ trivial
- **Why:** Keep-a-Changelog completeness — the feature entry exists but the doc
  artifacts (`AUTONOMY_CHARTER.md`, `MASTER_PROMPT.md`, and now this plan) are
  not listed.
- **Change:** Add one bullet under `## [Unreleased] → ### Added`:
  > **Autonomy Charter, Master Prompt & Implementation Plan reference docs**
  > (`docs/autonomy/AUTONOMY_CHARTER.md`, `docs/autonomy/MASTER_PROMPT.md`,
  > `docs/autonomy/IMPLEMENTATION_PLAN.md`). Operational spec for the
  > human-in-the-loop approval gate (G1) and the G2–G5 follow-up roadmap.
- **Acceptance:** changelog lists all three files; `pytest -x` still green.

### A2 — `docs/telegram-bot.md`: fix broken charter links (MD + path)
- **Why:** `../autonomy/AUTONOMY_CHARTER.md` resolves *outside* `docs/`. The
  charter lives at `docs/autonomy/`, so from `docs/telegram-bot.md` the correct
  relative path is `autonomy/AUTONOMY_CHARTER.md`.
- **Change:** Line ~93 and lines ~271–272: replace `../autonomy/AUTONOMY_CHARTER.md`
  → `autonomy/AUTONOMY_CHARTER.md` (3 occurrences total).
- **Acceptance:** `grep -n "\.\./autonomy" docs/telegram-bot.md` returns nothing.

### A3 — `docs/telegram-bot.md`: add language to fenced block (MD040)
- **Why:** markdownlint MD040 — the approval-message example fence at line ~276
  has no language identifier.
- **Change:** opening ` ``` ` → ` ```text ` for the "Approval needed — run …"
  block.
- **Acceptance:** markdownlint MD040 no longer fires on this file.

### A4 — `.env.example`: use exact var name in the shortcut comment
- **Why:** The comment block (~line 230) abbreviates to `NOTIFY_CHAT_IDS`; the
  real key is `TELEGRAM_NOTIFY_CHAT_IDS`. A literal copy would not work.
- **Change:** In the comment prose, spell the three fallback targets in full:
  `TELEGRAM_ALLOWED_USER_IDS` / `TELEGRAM_ADMIN_USER_IDS` /
  `TELEGRAM_NOTIFY_CHAT_IDS`.
- **Acceptance:** no bare `NOTIFY_CHAT_IDS`/`ADMIN_USER_IDS` (without the
  `TELEGRAM_` prefix) remain in the comment.

### A5 — `services/workflow_orchestrator.py`: surface notify failures at WARNING
- **Why (coding guideline):** `_notify_approval_gate`'s `except` logs at DEBUG,
  hiding a degraded alert channel. If Telegram delivery is misconfigured, the
  run still pauses but the operator gets no ping and no visible warning.
- **Change:** in `_notify_approval_gate`'s `except Exception as exc:` block,
  change `log.debug(...)` → `log.warning("Approval-gate notify failed for run
  %s (non-fatal): %s", run.run_id, exc)`. Keep it non-fatal (do not re-raise).
  Optionally narrow `except Exception` to satisfy Ruff BLE001, or add
  `# noqa: BLE001` with a one-line reason (best-effort cross-cutting notify).
- **Acceptance:** unit test asserts a warning is logged when the dispatcher
  raises; `_notify_approval_gate` still does not propagate
  (existing `test_notify_approval_gate_is_non_fatal` must stay green).

### A6 — `telegram_bot.py`: avoid double-approve in the `wfo_approve` path ⚠️ behavioural
- **Why:** Current handler calls `orchestrator.approve(run_id, …)` synchronously
  (for fast validation) **and then** `asyncio.create_task(approve_async(run_id,
  …))`. `approve_async` approves again internally → duplicate state transition /
  race if the async step later fails after the success message was edited.
- **Decision required (pick one, document choice in the PR):**
  - **Option 1 (recommended):** Keep the synchronous `approve()` for validation
    (it raises `KeyError`/`ValueError` immediately for not-found/already-resolved
    so the user gets correct inline feedback), but make `approve_async` **resume
    an already-approved run idempotently** — i.e. `approve_async` should detect
    `run.approved is True` and skip the re-approve, only kicking the queue/execute
    resume. This preserves fast validation + non-blocking resume with a single
    logical approval.
  - **Option 2:** Drop the synchronous `approve()`; rely solely on
    `approve_async()`. Then replicate the not-found/already-resolved checks by
    inspecting the returned run/exception from `approve_async` *before* editing
    the message to "Approved". Downside: `approve_async`'s queue-unavailable
    fallback calls `execute()` inline (potentially long), so you must still fire
    it via `create_task` and cannot synchronously know the validation result —
    making correct inline feedback harder. **This is why Option 1 is preferred.**
- **Also (Ruff nits flagged):**
  - RUF006: store the `asyncio.create_task(...)` return value in a variable held
    for the task's lifetime (e.g. module-level `set` of background tasks with a
    `.add`/`.discard(done_callback)`), so the task isn't GC'd mid-flight.
  - RUF001: the `ℹ` (INFORMATION SOURCE) glyph in the "already resolved" edit —
    leave as-is (intentional UX), or `# noqa: RUF001`.
- **Acceptance:** a run is approved exactly once (assert orchestrator records a
  single approval transition); existing `wfo:` callback tests stay green; add a
  regression test proving no double-approve.
- **Risk note:** touches the approval/resume control flow → run the
  `risky-module-review` skill mindset (not auth/keys, but state-mutating).

### A7 — `telegram_service.py`: escape Markdown-v1 reserved chars in approval text ⚠️ correctness
- **Why:** `goal`, `risk_reason`, and plan-step text are interpolated into a
  `parse_mode="Markdown"` payload. Unescaped `_ * \` [` cause Telegram to reject
  the message ("can't parse entities") → the approval-gate push is **silently
  dropped** (the exception is caught/logged, operator never sees the gate).
- **Change:** add a small helper and apply it to every user-derived field before
  interpolation in `send_approval_gate` (lines ~324–335 and the plan-step loop
  ~359–360):
  ```python
  def _escape_md_v1(text: str) -> str:
      """Escape Telegram Markdown-v1 reserved chars: _ * ` [ ."""
      for ch in ("_", "*", "`", "["):
          text = text.replace(ch, "\\" + ch)
      return text
  ```
  Apply **after** `_redact_for_notification(...)` (escape the redacted output).
  Do **not** escape the static label text ("*Approval needed*", "*Plan:*") —
  only the dynamic fields, so intended bold still renders.
- **Acceptance:** new test: a goal containing `_`, `*`, `` ` ``, `[` produces a
  payload where those chars are backslash-escaped; existing redaction test stays
  green. (Optional hardening: consider switching this one message to
  `parse_mode="HTML"` with `html.escape` in a later pass — out of scope here.)

### A8 — `render.yaml`: propagate Telegram vars to the worker service
- **Why:** The file documents switching `RUN_BACKGROUND_IN_WEB=false` so the
  `*-worker` service runs the orchestrator. In that mode the worker is what hits
  the `ApprovalGate`, but the worker service block currently lacks the Telegram
  env vars → no proactive push when the worker pauses a run.
- **Change:** add to the worker service's `envVars` the same Telegram keys the
  web service has: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`,
  `TELEGRAM_NOTIFY_CHAT_IDS` (and `TELEGRAM_ALLOWED_USER_IDS` /
  `TELEGRAM_ADMIN_USER_IDS` if the worker should also run the bot), all
  `sync: false`. Mirror the comment explaining the `TELEGRAM_CHAT_ID` fallback.
- **Acceptance:** worker and web service expose identical Telegram notification
  config; a note in the worker block explains it only matters when
  `RUN_BACKGROUND_IN_WEB=false`.
- **Note:** Today `RUN_BACKGROUND_IN_WEB=true` (web runs background), so this is
  forward-looking correctness, not an active bug.

### A9 — (optional) Docstring coverage warning
- CodeRabbit's pre-merge "Docstring Coverage 24.64% < 80%" is a repo-wide
  advisory, **not** a blocking CI gate here. Do **not** chase 80% in this PR.
  New public functions added by G1 already have docstrings; keep that standard
  for G2–G5. Skip unless the maintainer makes it a required check.

---

## Part B — G2: Closed-loop self-heal feedback

### Objective
Make the log-driven self-heal loop **closed**: after a fix is generated and
landed for a detected error signature, the system must **confirm the error
signature stops recurring** before marking the heal `resolved`. Today the chain
`log_monitor → self_healing → improvement_loop` can generate a fix but does not
verify the error is actually gone, so the same error can re-trigger new heals
(thrash) or a heal can be marked done while still firing.

### Tech stack / touch points
- `agent/log_monitor.py` — error detection + signature extraction.
- `agent/self_healing.py` — heal record lifecycle (the state machine to extend).
- `agent/improvement_loop.py` — orchestrates heal → SDLC → PR.
- `services/workflow_orchestrator.py` — the golden path that lands the fix
  (heals route through it so risky fixes hit the G1 gate).
- Persistence: wherever heal records live today (check `agent/self_healing.py`
  for an existing store; reuse it — do **not** invent a new DB).

### Design
1. **Error signature:** ensure `log_monitor` produces a stable signature
   (e.g. normalized exception type + message template + top frame), so "same
   error" is decidable. If one exists, reuse it; if not, add
   `def error_signature(event) -> str`.
2. **Heal record states:** extend the heal lifecycle to:
   `detected → fixing → landed → **verifying** → resolved | regressed`.
   - `landed` = fix merged/PR-open per the repo's `DeliveryPolicy` (see G5).
   - `verifying` = a monitoring window opens (config: `HEAL_VERIFY_WINDOW_SEC`,
     default e.g. 1800s) during which `log_monitor` watches for the same
     signature.
   - `resolved` = window elapsed with **zero** recurrences of the signature.
   - `regressed` = signature recurred during the window → re-open / escalate
     (and **do not** spawn a brand-new duplicate heal for the same signature
     while one is in `verifying`).
3. **Dedup guard:** `self_healing` must not create a new heal for a signature
   that already has an active (`fixing`/`landed`/`verifying`) record.
4. **Escalation:** N consecutive `regressed` cycles (config
   `HEAL_MAX_ATTEMPTS`, default 3) → mark `awaiting_human` and fire the G1
   Telegram gate with the signature + attempt history (reuse
   `NotificationDispatcher`).

### To-dos (checklist)
- [ ] Confirm/define `error_signature()` in `agent/log_monitor.py` (+ unit test).
- [ ] Add `verifying`/`regressed`/`awaiting_human` states to the heal record
      model in `agent/self_healing.py`.
- [ ] Implement the verification window watcher (subscribe to `log_monitor`
      events for the signature; resolve or regress on timeout/recurrence).
- [ ] Implement the active-heal dedup guard.
- [ ] Implement escalation to the G1 Telegram gate after `HEAL_MAX_ATTEMPTS`.
- [ ] Wire heal landing through `WorkflowOrchestrator` (so risky fixes gate).
- [ ] Config knobs (`HEAL_VERIFY_WINDOW_SEC`, `HEAL_MAX_ATTEMPTS`) via env,
      documented in `.env.example` + `docs/configuration-reference.md`.
- [ ] Changelog entry; charter §6 G2 → ✅ wired.

### Acceptance criteria
- A simulated recurring error produces exactly **one** active heal (no thrash).
- A heal is only `resolved` after the verification window passes with no
  recurrence of its signature.
- A recurrence during the window flips the heal to `regressed` and triggers a
  retry, not a silent success.
- After `HEAL_MAX_ATTEMPTS`, the heal lands in `awaiting_human` and a Telegram
  gate message is sent.
- Zero dropped work: every heal ends in a terminal/typed paused state.

### Tests
- `tests/test_self_healing.py` (extend): signature stability, state transitions,
  dedup guard, resolve-on-quiet-window, regress-on-recurrence, escalation push
  (monkeypatch `NotificationDispatcher`). Use fake clocks — no real sleeps.

---

## Part C — G3: Auto issue → task intake

### Objective
Turn external signals — **GitHub issues** (and scanner/monitor findings) — into
typed `Task` records automatically, so the autonomous loop has a real intake
queue instead of only manually-created work.

### Tech stack / touch points
- `tasks/dispatcher.py` — Task creation/dispatch (target sink).
- GitHub webhook receiver — add a FastAPI route in `backend/server.py`
  (e.g. `POST /api/webhooks/github`) **or** a poll loop if inbound webhooks
  aren't reachable in the deploy. Decide based on Render networking; default to
  webhook with an HMAC-verified secret (`GITHUB_WEBHOOK_SECRET`).
- `services/scanner.py` / monitors — emit task-worthy findings.
- Dedup/idempotency: key tasks by source id (`github:issue:<repo>#<number>`).

### Design
1. **Webhook route:** verify `X-Hub-Signature-256` against
   `GITHUB_WEBHOOK_SECRET` (constant-time compare; never log the secret —
   `risky-module-review` mindset). Handle `issues` (opened/labeled/reopened) and
   optionally `issue_comment` for commands.
2. **Mapping:** issue → `Task` with title/body/labels → capability tags;
   `company_id` resolved from the repo (via G5 `RepoConnection`, or platform
   self if it's this repo). Treat untrusted issue text as data, not
   instructions (the charter's safety invariant).
3. **Idempotency:** skip if a task already exists for the source id; update on
   reopen.
4. **Label gating:** only intake issues with an opt-in label (e.g.
   `autonomy:intake`) to avoid hoovering every issue — configurable.

### To-dos (checklist)
- [ ] `POST /api/webhooks/github` with HMAC-256 verification (Pydantic models
      for payloads; reject unverified).
- [ ] `GITHUB_WEBHOOK_SECRET` env + docs.
- [ ] Issue→Task mapper with capability tagging + `company_id` resolution.
- [ ] Source-id idempotency (no duplicate tasks).
- [ ] Opt-in label gate (`autonomy:intake`, configurable).
- [ ] Treat issue/comment text as untrusted data (no prompt-injection path).
- [ ] (If webhooks unreachable) fallback poll loop behind a feature flag.
- [ ] Changelog; charter §6 G3 → ✅ wired.

### Acceptance criteria
- A labeled GitHub issue creates exactly one `Task` (verified via dispatcher),
  with correct company + capability tags.
- Replaying the same webhook is a no-op (idempotent).
- Unsigned/invalid-signature payloads are rejected with 401/403 and logged
  (without leaking the secret).
- Unlabeled issues are ignored (when the gate is on).

### Tests
- `tests/test_issue_intake.py` (new): signature verify pass/fail, mapping,
  idempotency, label gate, untrusted-text handling. Use a captured sample
  payload fixture; monkeypatch the dispatcher.

---

## Part D — G4: Per-company trend scoping

### Objective
Today `agent/trend_watcher.py` applies trends at the **platform** level. Scope
each trend finding to **each onboarded company's detected stack** so a React
trend goes to React companies, a Stripe advisory to companies using Stripe,
etc. — then route through the Gate Matrix (🟢 autonomous research vs 🔴 gated
change).

### Tech stack / touch points
- `agent/trend_watcher.py` — trend findings + current ≥0.75 auto-dispatch.
- `models/company_graph.py` — per-company detected systems/stack.
- `services/scanner.py` — where stack/systems are detected.
- `tasks/dispatcher.py` — emit scoped tasks (ties into G3).

### Design
1. **Stack vocabulary:** normalize detected systems (CMS, framework, payment
   gateway, analytics, language) into tags on the Company graph (reuse what the
   Systems tab already surfaces).
2. **Relevance scoring:** for each trend finding, compute relevance per company
   = match between the trend's `stack_tags` and the company's detected tags,
   combined with the existing trend confidence. Threshold (config
   `TREND_COMPANY_MIN_SCORE`, default 0.5) gates whether a company gets a task.
3. **Routing:** research/ingestion = 🟢 (notify-only); any code/infra change
   suggested = 🔴 (Telegram gate via G1). Per-company budget cap respected.
4. **Fan-out:** one trend → 0..N scoped tasks (one per relevant company),
   deduped by `(trend_id, company_id)`.

### To-dos (checklist)
- [ ] Ensure trend findings carry `stack_tags` (extend `trend_watcher` source
      parsing if needed).
- [ ] Company stack-tag accessor on `models/company_graph.py`.
- [ ] `score_trend_for_company(trend, company) -> float` (+ unit tests).
- [ ] Fan-out + dedup `(trend_id, company_id)`.
- [ ] Gate routing per Gate Matrix; budget-cap check.
- [ ] Config `TREND_COMPANY_MIN_SCORE`; docs.
- [ ] Changelog; charter §6 G4 → ✅ wired.

### Acceptance criteria
- A trend tagged with a stack present in company A but not company B creates a
  task for A only.
- Code-change trends route to the 🔴 gate; research trends are 🟢 notify-only.
- No duplicate task for the same `(trend_id, company_id)`.
- Platform-level behavior preserved (platform is just another company).

### Tests
- `tests/test_trend_scoping.py` (new): scoring matrix, fan-out, dedup, gate
  routing. Fixtures for 2–3 companies with different stacks; monkeypatch
  dispatcher + notifier.

---

## Part E — G5: `RepoConnection` + `DeliveryPolicy` (GitHub-only scope)

### Objective
Give each Company a typed **`RepoConnection`** (which repo + how code lands) and
a detected **`DeliveryPolicy`**, so the agentic SDLC (Loop 3) can land changes
correctly per repo. **Scope this pass to GitHub only**; GitLab/Bitbucket are
explicitly **"coming soon"** (do not claim them done — docs-consistency rule).

### Tech stack / touch points
- `models/company_graph.py` — add `RepoConnection` + `DeliveryPolicy`
  dataclasses/Pydantic models + persistence on Company.
- `services/onboarding.py` — detect + attach during onboarding.
- GitHub REST (existing token plumbing: `GITHUB_TOKEN`/`GH_TOKEN`) — read
  default branch + branch-protection to infer policy.
- `services/workflow_orchestrator.py` — respect `DeliveryPolicy` when landing;
  gate the **first unattended merge on a newly onboarded repo** via G1.

### Design
1. **`RepoConnection`:** `{ provider: "github", owner, repo, default_branch,
   token_ref, connected_at }`. URL-only companies have `None` →
   code work pauses `awaiting_repo_connection` (Loop 5).
2. **`DeliveryPolicy`:** `detect_delivery_policy(repo) -> DeliveryPolicy` via
   GitHub REST:
   - default branch name;
   - branch protection on default (required reviews / status checks);
   - infer `mode`: `direct_push` (no protection, explicitly allowed) vs
     `pr_required` (protection or unknown → safe default = PR).
   - **Safe default is `pr_required`** when detection is uncertain.
3. **First-merge gate:** the first time the loop would merge unattended on a
   newly onboarded repo, force the 🔴 Telegram gate (charter Gate Matrix),
   regardless of policy, then record consent so subsequent merges follow policy.
4. **Coming-soon honesty:** `provider` is a `Literal["github"]` now; add a clear
   "GitLab/Bitbucket coming soon" note in docs and raise `NotImplementedError`
   (or skip with a typed reason) for non-GitHub URLs — never fabricate.

### To-dos (checklist)
- [ ] `RepoConnection` + `DeliveryPolicy` models on `models/company_graph.py`
      (+ persistence + migration of existing companies to `None`).
- [ ] `detect_delivery_policy()` via GitHub REST (default branch + protection),
      safe `pr_required` default on uncertainty.
- [ ] Wire detection into `services/onboarding.py` (attach to Company).
- [ ] `WorkflowOrchestrator` respects `DeliveryPolicy` at land time.
- [ ] First-unattended-merge-on-new-repo → G1 Telegram gate; persist consent.
- [ ] URL-only companies → `awaiting_repo_connection` (no fabrication).
- [ ] GitLab/Bitbucket explicitly "coming soon" (docs + typed skip).
- [ ] Changelog; charter §6 G5 → ✅ wired (GitHub-only).

### Acceptance criteria
- An onboarded GitHub repo gets a `RepoConnection` + detected `DeliveryPolicy`.
- Protected default branch → `pr_required`; unprotected + allowed → `direct_push`;
  uncertain → `pr_required`.
- The first unattended merge on a new repo pauses for Telegram approval; later
  merges follow the recorded policy.
- A URL-only company never attempts code work — it sits in
  `awaiting_repo_connection`.
- Non-GitHub providers are surfaced as "coming soon", not silently mis-handled.

### Tests
- `tests/test_repo_connection.py` (new): policy detection (mocked GitHub REST
  for protected/unprotected/uncertain), onboarding attach, first-merge gate,
  URL-only pause, non-GitHub skip. No live network — mock the REST client.

---

## Sequencing recommendation

1. **Part A** (review fixes) — unblock PR #652; A6/A7 are the only behavioural
   ones and both have tests.
2. **G5** then **G3** — `RepoConnection` (G5) gives G3's issue→task the
   `company_id` resolution and lets the SDLC land fixes; together they make the
   loop able to *receive* and *ship* work.
3. **G2** — closed-loop self-heal builds naturally on the SDLC landing + gate.
4. **G4** — per-company trend scoping, last, as it fans out across companies and
   benefits from G5's stack data.

Each part is its own PR off `master` (small, reviewable), updates
`docs/changelog.md`, flips the matching charter §6 row to ✅, and updates
`.claude/state/active-tasks.md` (rows 17–20).

## Definition of done (whole programme)
Matches `AUTONOMY_CHARTER.md` §7 acceptance criteria: closed-loop self-heal,
gated merges, per-company trend application, zero dropped work, free-brain-only
spend, and full observability of every autonomous decision.
