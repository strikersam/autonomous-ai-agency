# Review instructions

How every pull request in this repository is reviewed — by humans, by review bots,
and by the agency's own judge (`agent/loop.py` reads this file into the judge prompt).
The rules being checked are `CLAUDE.md` §1–§2; this file says how to review against them.

## Passes

Run three passes and tag each finding with its pass:

- **Bugs**: logic errors, broken edge cases, regressions, a test that no longer tests
  what it claims, behaviour changed that the PR did not ask for (rule 1).
- **Security**: unauthenticated endpoints (rule 10), unvalidated input (rule 11),
  `shell=True` with interpolation (rule 12), writes outside the workspace (rule 13),
  unscreened external URLs (rule 14), secrets in code, logs or tests (rule 6).
- **Compliance**: the diff does what the intent and plan say (`docs/intent/`,
  `docs/plans/`, or the plan in the PR body) and touches only the files the plan names;
  changelog entries in both files (rule 34); provider calls through the router (rule 2);
  env vars read only in config modules (rule 5); a regression test that fails before
  the fix (rule 31).

## What Important means here

Important is reserved for findings that would break behaviour, leak data, breach a
CLAUDE.md rule, or ship a claim that is not true (an invented URL, contact, customer,
metric or model id). Everything else — naming, style, wording — is a nit.

## Cap the nits

Report at most five nits per review; summarise the rest as a count.

## Do not report

- Generated files: `graphify-out/`, `frontend/build/`, lockfiles.
- Anything CI already enforces: formatting, byte-compilation, changelog parity,
  loop-registry drift.
- The size of `backend/server.py` or `proxy.py` (on record in `AGENTS.md`), unless the
  PR makes them larger.
