# Next Action

_Updated 2026-08-29._

## Nothing is blocked on an agent. Three things need a human.

### 0. NVIDIA models — resolved, with one measurement still missing

Every NVIDIA id this repo carried was probed against the production key on
2026-08-28. All but one answered 410 or 404, including `z-ai/glm-5.2` (the
default brain for all four agent roles) and `nvidia/nemotron-3-ultra-550b-a55b`
(briefly installed as the default on the strength of a catalogue listing alone).

The rotation now holds only ids that returned HTTP 200 to a real completion,
and all three tool-call correctly:
`nvidia/nemotron-3-super-120b-a12b`, `openai/gpt-oss-120b`, `openai/gpt-oss-20b`.
`mistralai/mistral-nemotron` answers but is slow — it timed out on one of two runs.

**Still missing, and not guessable:** real `context_window` / `max_output_tokens`
for these models. NVIDIA's `/v1/models` returns only `id`, `object`, `created`
and `owned_by` — no capability fields at all, so an earlier note here claiming
"anyone with the key can get them from `GET /v1/models`" was wrong. The entries
in `config/llm/models.yaml` and `packages/ai/registry.py` therefore carry
conservative floors (32768 / 4096), which prune prompts rather than overflow
them. Raise them when someone measures the real limits.

Model ids live in six places (`config/models.yaml`, `config/llm/models.yaml`,
`config/llm/providers.yaml`, `packages/ai/brain_config.py`,
`packages/ai/registry.py`, `services/brain_failover.py::_MODEL_ALIASES`).
`tests/test_one_model_catalogue.py` freezes the divergence and blocks retired
ids from becoming routable, but the consolidation itself is not done.

Re-check anything above with:
`gh workflow run catalogue-probe.yml -f provider=nvidia -f chat=nvidia -f tools=true`

### 0b. `nvidia/nemotron-3-ultra-550b-a55b` is NOT dead — I retired it on bad evidence

Correction to the note above. That id was retired on 2026-08-28 on the strength
of a `404` from probe runs 33192841180 / 33193061913 (17:02 and 17:05 UTC), and
it is on the `RETIRED` list in `tests/test_nvidia_default_model.py`, which now
actively blocks a model that works.

Two later observations contradict the 404:

- The council-review step of run 33204279915, at **20:10 UTC**, logged
  `[review] Got response from nvidia/nemotron-3-ultra-550b-a55b (NVIDIA NIM)`
  after an `HTTP/1.1 200 OK`.
- A direct re-probe at **23:25 UTC** (run 33220369591, dispatched against the
  production key) returned:
  `nvidia/nemotron-3-ultra-550b-a55b: HTTP 200` and
  `tools nvidia/nemotron-3-ultra-550b-a55b: YES ['get_weather']`.

So it serves *and* tool-calls. `nvidia/nemotron-3-super-120b-a12b` answered 200
with tool calls in the same run, so the current default is fine either way.

What this does **not** establish is that the ultra is reliable: a model that
answers 404 at 17:00 and 200 at 20:10 and 23:25 is intermittent, and
intermittent is not the same as retired. The honest fix is to take it off the
`RETIRED` list — that list means "gone", and it is not gone — while leaving
`nvidia/nemotron-3-super-120b-a12b` as the default, since that one has answered
on every probe. Do not promote the ultra back to default on this evidence.

Not done here to avoid widening a green, unrelated PR. It costs one edit to
`tests/test_nvidia_default_model.py` plus a rotation entry.

### 1. Render is suspended for billing — this is the big one

Service `srv-d7cb43beo5us73e1leug` (`local-llm-server`) is `suspended`,
`suspenders: ["billing"]`. Everything below is dark until that is resolved, and
none of it is fixable from a session:

- `PR_APPROVAL_GATE_ENABLED=true` cannot be set (`400 cannot deploy suspended
  service`), so there is no Telegram gate on PR approval.
- The in-process agency is down: CEO loop, self-healing, dispatcher, Telegram
  bot, `services/pr_approval_gate.py`.
- **Langfuse tracing is already wired** across `proxy.py`, `agent/loop.py`,
  `agent/agency.py`, `tasks/service.py`, `packages/ai/self_heal.py`,
  `services/otel_tracing.py`, `handlers/anthropic_compat.py`,
  `agent/trend_watcher.py`, `agent/sam.py`, `packages/config/settings.py`, with
  keys in `render.yaml` as `sync: false`. It emits nothing because the service
  is not running. No code change is needed — only billing.

`/api/ping` returns 000; Hermes 404s. The GitHub-Actions half of the agency
(37 loops) is unaffected and running.

### 2. `anthropic >=1.0.0` — resolved, and the premise was wrong

An earlier note here held this back under rule 40 as a breaking dependency
upgrade. It is not one, and the reason matters: **`anthropic>=0.122.0` already
resolves to 1.0.0**, so CI, Render and every developer install have been running
1.0.0 since it was published. Dependabot's PR raises the *floor*; it does not
change a single byte of what gets installed. The risk it appeared to carry had
already been taken, silently, weeks earlier — which is the same shape as every
other defect on this branch.

Verified rather than assumed. The SDK has exactly two call sites, both in
`agent/loop.py` (not `packages/ai/router.py` or `handlers/anthropic_compat.py`,
as the earlier note said): they construct `AsyncAnthropic` and
`AsyncAnthropicBedrock` and call
`messages.create(model=, max_tokens=, system=, messages=)`. All four names are
present in 1.0.0's signature; neither site passes `temperature`, which 1.0.0
dropped. The pin is applied and #1336 is closed.

### 3. The loop overrode its own recorded REJECT, inside a single pull request

The first fully successful autonomous run (run 33204279915, 39 min, issue #1356)
worked end to end — implement, pytest, PR, review bots, apply review, council,
draft→ready, squash-merge, close issue — and produced `b368f9e7` on master:
~1,200 lines of SEO-to-portfolio bridging (`agents/seo_portfolio_bridge.py`,
three new endpoints in `backend/seo_api.py`, 13 tests).

**PR #1357 is that PR** — not, as an earlier draft of this note said, a separate
earlier one. Verified: `merged_at 2026-08-28T20:10:59Z` (the second `b368f9e7`
was authored), base `8b448842` (its parent), and `1199 additions / 7 deletions /
7 changed files`, matching the commit exactly. Its title is still
*"docs: reject: SEO backlog-to-roadmap is out of scope for autonomous-ai-agenc"*
and its body still reads **"🛑 REJECT — nothing here belongs in this
repository."** The context step wrote that verdict; the implement step ran on the
same branch and merged 1,199 lines under it. Nothing in the pipeline reads its
own planning decision.

The REJECT was not authoritative either, and should not be treated as the
correct answer that got overridden. The same PR body records
*"Fetch status: ⚠️ NOT FETCHED — the plan below is unverified against the
source"* and a Quality Gate failure: *"R1 — the linked source was not retrieved,
so every claim about it is unverified; the document must be reviewed before
implementation."* It was generated by `mistral-small-latest`. So the planner
rejected an article it never read, and the implementer then built 1,200 lines
for an article it never read. Neither half of that run was grounded.

The bad squash subject is what hid the contradiction: with a correct subject the
merge commit would have read *"implement quick-note issue #1356"* while its own
PR was titled *"reject: … out of scope"* — visible in one line of `git log`.

**The review bots did not review it.** CodeRabbit posted
*"This repository does not receive automatic reviews because it has fewer than
10 stars"*, and Codex posted *"You have reached your Codex usage limits for code
reviews."* The `.coderabbit.yml` the loop created in this very commit sets
`auto_review.drafts: true`, which does not address the actual blocker (star
count). The pipeline's "Wait for review bots → Apply review comments" steps ran
11m03s and reported success against no bot review.

What *did* review it was the repo's own council step, and its verdict was
**WARN** with: *"SECURITY: WARN — New API endpoints added … but diff is
truncated; cannot verify authentication/authorization guards on these routes"*
and *"These are non-blocking but require human verification before merge."*
`process-quick-note.yml` treats `WARN` as mergeable, so a review that asked for
human verification before merge was auto-merged without it.

Both council WARNs have now been resolved by hand:

- **Security — resolved, no defect.** All three endpoints take
  `Depends(_get_current_user_thunk)` *and then* `get_company_access(company_id,
  user)`, so another company's audit answers 404. Rule 10 holds; rule 11 holds
  too (Pydantic v2 request models with `Field` constraints, `response_model` on
  every route).
- **Correctness — one real defect, still open.** `Initiative.wsjf` is a
  `@property`, so `init.wsjf` is correct, and `source` is a real field. But
  `estimated_monthly_value` **is not a field on `Initiative`**, and
  `delegation_task_to_initiative` never carries it across — it interpolates
  `task.estimated_monthly_value` into the free-text `rationale` string and drops
  the number. Every consumer then reads it as
  `getattr(init, 'estimated_monthly_value', 0)` — 8 call sites in
  `backend/seo_api.py`, 2 in the bridge — so **all three new endpoints return
  `"estimated_monthly_value": 0` for every initiative, and the roadmap markdown
  prints `$0` in the value column for every row.** Confirmed by construction: a
  task carrying `12345.0` yields an initiative whose call sites all read `0`,
  with the real figure surviving only as prose inside `rationale`. The
  `getattr(..., 0)` default is what makes it silent — without it the first call
  would have raised `AttributeError`. Fixing it changes user-visible output, so
  it is rule 1 work and is left for a decision: either add
  `estimated_monthly_value` to `Initiative` and set it in the conversion, or
  drop the field from the API responses rather than reporting a fabricated zero.

**The override itself is fixed** — see §4. `scripts/context_plan_gate.py` now
reads the plan before the implementer runs, and fails closed on all three of the
signals this plan carried (REJECT, unfetched source, unmet rules).

Still unmet and not fixed:

- **Rule 28 in `b368f9e7`.** `build_seo_roadmap` (74 lines), `plan_seo_sprint`
  (83), `run_seo_pipeline` (114), and three functions in
  `agents/seo_portfolio_bridge.py` (52/57/78) all exceed the 50-line limit, and
  `backend/seo_api.py` went from 381 to 756 lines against the 800-line cap.
  Refactoring merged code is behaviour-touching work under rule 1 and needs its
  own change, not a rider on a workflow fix.

### 4. The backlog is at zero, and the gates that let bad work through are closed

**6 open issues → 0. 11 open PRs → 0.** Details in tracker row 43.

Five gates in `process-quick-note.yml` resolved an unknown into an approval,
and all five are now closed with tests that fail against the pre-fix workflows:

1. **The plan is read before anything is built.** `scripts/context_plan_gate.py`
   parses the committed context plan and fails **closed** — a REJECT verdict, an
   unfetched source, unmet rulebook rules, or a verdict it does not recognise
   all block the implement step, label the issue `quick-note:rejected`, and
   comment. The old defence was a label written best-effort by a different
   workflow on one code path; when it did not happen, nothing said so.
2. **Only `PASS` auto-merges.** `WARN` used to, including the one on #1357
   reading *"cannot verify authentication/authorization guards"* and *"require
   human verification before merge"*.
3. **A council that did not run is `NONE`, not `WARN`.** The step is
   `continue-on-error: true`, so a crashed reviewer previously merged exactly
   like an approving one. Every non-`PASS` outcome now comments; before, only
   `FAIL` did.
4. **Review bots are counted.** Zero reviews raises a warning instead of an
   11-minute "apply review comments" step reporting success against nothing.
5. **The queue holds work, not paperwork.** `agency-escalation`,
   `trend-digest` and `crispy-burn-in` labels are excluded from selection.

Two upstream loops fed the same pattern and are fixed: `agency-cycle.yml` no
longer escalates failures its own classifier calls unfixable, and
`crispy-burn-in-check.yml` fails loudly instead of filing a verdict computed
from an empty evaluation.

**What this changes for you:** the loop will now open PRs and leave them for a
human whenever the council does not return `PASS`. That is deliberate — it
trades throughput for the property that a merged change was actually reviewed.
If the volume of waiting PRs becomes the problem, the lever is the council's
own strictness, not the merge gate.

## Running unattended, no action needed

- **Dependabot backlog: 12 open, draining ~1/hour.** `dependabot-auto-merge.yml`
  runs hourly, updates one stale branch per run (branch protection means only one
  PR can merge per run regardless), classifies each up-to-date PR with
  `scripts/classify_dependabot_update.py`, and arms auto-merge only for
  `group`/`minor`/`patch`. `major` and `unknown` go to a human. #1346 and #1345
  merged this way.
- **The plan→implement loop converged.** `agency-cycle` run 380 ran on `50b04aa7`
  (contains the parser fix `cfea9ff`) and filed no new failure issue — the first
  clean tick since the ghost-node-ID bug. #1331 and #1317 closed themselves;
  #1312 is on `retry:1`. Open issues 10 → 8.
- `process-quick-note.yml` picks the oldest open non-exhausted issue every 4h.
- `orphaned-pr-sweep.yml` runs daily at 06:00 UTC.

## If you pick this up next

Check that the Dependabot count keeps falling (12 → 0 over ~12 hours). If it
stalls, read the sweep log first — the exit code has been misleading three
separate times on this workflow, and every real defect was found by comparing
the log against the PRs' actual state.
