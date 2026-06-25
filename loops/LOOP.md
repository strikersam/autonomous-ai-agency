# LOOP.md — The loops that run this agency

> **Self-referential governance.** This repo is an autonomous AI agency: it is
> meant to keep *itself* up to date, learn, and self-heal without a human
> issuing each instruction. This document is the operator's-eye view of the
> machinery that does that — the **loop fleet** — and the contract that keeps it
> legible instead of a black box.
>
> Inspired by [Loop Engineering](https://github.com/cobusgreyling/loop-engineering)
> (Cobus Greyling; building on Addy Osmani and Boris Cherny). Companion specs:
> [`docs/autonomy/AUTONOMY_CHARTER.md`](../docs/autonomy/AUTONOMY_CHARTER.md) for
> the operating directive, and the machine-readable catalogue in
> [`loops/registry.yaml`](./registry.yaml).

---

## Why this exists

A loop is **not a prompt** — it is a recurring process with memory,
verification, and boundaries that discovers work, hands it to agents (often
sub-agents), verifies the result, persists state, and decides the next action
on a schedule or until a goal is met. You shouldn't be prompting the coding
agent turn-by-turn; you should be **designing the loops that prompt it**.

This repo already runs ~29 such loops — 40 GitHub Actions workflows plus
in-process daemons (`agent/self_healing.py`, `agent/log_monitor.py`,
`log_watcher.py`, `agent/improvement_loop.py`, `agent/trend_watcher.py`). Loop
Engineering's insight is that a *pile* of automations becomes an *operable
fleet* only once it has a **durable spine**: one catalogue, scored for
readiness, costed, and guarded against drift. That spine is what this directory
adds — without inventing new automations the repo doesn't need.

## The five building blocks (and how this repo realises them)

| Loop Engineering primitive | In this repo |
|----------------------------|--------------|
| **Automations / scheduling** | 19 cron workflows + event triggers (see registry) |
| **Worktrees** (isolated parallel work) | per-branch GitHub Actions runners; `claude/*` branches |
| **Skills** (persistent knowledge) | `.claude/skills/`, `CLAUDE.md`, module `CLAUDE.md` files |
| **Plugins / connectors (MCP)** | `agent/mcp_client.py`, GitHub MCP, Telegram bot |
| **Sub-agents** (maker/checker) | planner → executor → verifier → JUDGE in `agent/loop.py` |
| **Memory / state** | `.claude/state/`, `agent/persistent_memory.py`, KPIs |

## Maturity ladder

Every loop in [`registry.yaml`](./registry.yaml) declares a level. Promote a
loop only when the level below has earned trust:

- **L1 — report-only.** Observes and reports; a human acts. (digests, scans,
  ceremonies, security/regression reports.)
- **L2 — assisted / gated.** Acts, but risky or outward-facing actions stop at
  a **Telegram human-approval gate** (per the Autonomy Charter §3). Most
  self-healing and triage loops live here.
- **L3 — unattended.** Runs the full plan→execute→verify→land cycle without a
  gate. Rare by design — only `autonomous-cycle` (the 2-minute tick) is L3,
  and only because every change still passes Verifier → JUDGE → safety check →
  bounded retries before it can land.

## The three operator tools (`agent/loop_registry.py`)

Loop Engineering ships `loop-audit`, `loop-cost`, and `loop-init` as CLIs; this
repo expresses them as typed, tested code:

- **loop-audit** — `loop_readiness(registry)` scores the fleet 0–100 across
  four dimensions (maturity 40%, self-heal 25%, governance 20%, safety 15%) and
  returns a letter grade plus actionable notes.
- **loop-cost** — `LoopSpec.estimate_monthly_tokens()` models 30-day token
  spend per loop and for the whole fleet, so the cost of the cadence is visible
  *before* the bill arrives.
- **drift self-heal** — `audit_drift(registry)` fails if any cron-scheduled
  workflow is missing from the catalogue, or if a catalogued loop's source file
  has been deleted. The catalogue can therefore never silently rot.

Run it locally or in CI:

```bash
python -m agent.loop_registry audit            # human report
python -m agent.loop_registry audit --check    # exit 1 on registry/workflow drift
python -m agent.loop_registry audit --min-score 50   # exit 2 below a readiness floor
```

The [`loop-audit` workflow](../.github/workflows/loop-audit.yml) runs `--check`
on a weekly cadence and whenever a workflow changes, and files an issue if drift
is detected — a loop that keeps the loop catalogue honest. The readiness score
is also surfaced live at `GET /api/autonomy/status` under `loop_readiness`.

## How to add or change a loop

1. Add or edit the loop in [`registry.yaml`](./registry.yaml) (every
   cron-scheduled workflow **must** have an entry — CI enforces it).
2. Pick the lowest honest `level`; start at L1 and earn promotion.
3. Set a real `gate` for any loop that can take risky or outward-facing action.
4. Run `python -m agent.loop_registry audit` and confirm no drift.
5. Keep `purpose` and `source` accurate — governance scoring depends on them.

> **Comprehension debt is the real risk.** Automation amplifies judgment, good
> or bad. Read what the loops ship. This catalogue exists so the next operator
> can see the whole machine at a glance and stay the engineer — not inherit a
> black box.
