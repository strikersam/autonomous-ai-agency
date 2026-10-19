# Workflows: the autonomous loops

A loop is a recurring process that finds work, hands it to an agent, verifies the
result, records state and decides the next step, on a schedule and without a person
prompting each turn. The agency runs its loops as GitHub Actions plus a few in-process
daemons.

## The pattern

1. **One catalogue.** Every loop is listed in a registry
   ([`loops/registry.yaml`](../../loops/registry.yaml)) with its trigger, cadence, cost
   tier, maturity level and approval gate.
2. **Maturity levels.** `L1` reports only, `L2` proposes and waits for a person, `L3`
   runs unattended inside a gate. Promote a loop one level at a time.
3. **Gates.** Anything outward-facing (merge, deploy, message, payment) stops at a human
   gate (`telegram` or `human` in the registry).
4. **Drift check.** A CI job (`python agent/loop_registry.py audit --check`) fails when a
   scheduled workflow exists on disk but not in the registry.
5. **Independent verification.** A loop's output counts only after a verifier that did
   not write it passes it (rule 49 in [`../rules/AGENT_RULES.md`](../rules/AGENT_RULES.md)).

## Where the real ones live

GitHub only runs workflows from `.github/workflows/`, so they can't move here. Read them
as worked examples:

| Loop | Workflow | What it does |
|---|---|---|
| Autonomous cycle | `autonomous-cycle.yml` | Runs one plan → execute → verify tick of the agency unattended |
| CI autofix | `ci-failure-autofix.yml` | Diagnoses a red CI run and pushes a fix |
| Quick note | `process-quick-note.yml` | Turns quick-note issues into implementation PRs |
| Nightly regression | `nightly-regression.yml` | Runs the full regression suite and files an issue on failure |
| Feature scout | `feature-scout.yml` | Reads competitor releases weekly and files at most two small feature issues |
| Security scan | `security-scan.yml` | Weekly dependency, secret and security scan that files CVE issues |

The governance narrative is in [`loops/LOOP.md`](../../loops/LOOP.md). To adopt the
pattern elsewhere: copy a workflow, replace the repo-specific script it calls, and add a
registry entry before you schedule it.
