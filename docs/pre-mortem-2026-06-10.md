# Pre-Mortem Analysis: Agency Core autonomy story (Cloudflare deployment)

Date: 2026-06-10
Method: borghei/Claude-Skills `project-management/discovery/pre-mortem` (Tiger / Paper Tiger / Elephant)
Scenario: "It is 14 days after we market Agency Core as a self-running AI agency. It has failed. Why?"
Evidence source: live probes of https://local-llm-server.strikersam.workers.dev + repo state at `consolidate/maturation-stable`.

## Summary

Total risks identified: 9 — Tigers: 6 (Launch-Blocking: 3, Fast-Follow: 2, Track: 1), Paper Tigers: 1, Elephants: 2.

## Risk Registry

| # | Risk | Category | Urgency | Evidence | Mitigation | Owner | Decision date |
|---|------|----------|---------|----------|------------|-------|---------------|
| 1 | Doctor storage check crashes in production ("MotorCollection object is not callable") | Tiger | Launch-Blocking | Live `/api/doctor/public` response 2026-06-09 | **FIXED** in commit `1120346` (+ regression test). Needs redeploy. | strikersam | on next deploy |
| 2 | API 500s on malformed company IDs (`GET /api/company/<bad-id>`) | Tiger | Launch-Blocking | Live probe returned 500, not 404 | **FIXED** in commit `563ae93` (+ regression test). Needs redeploy. | strikersam | on next deploy |
| 3 | Committed credentials: `memory/test_credentials.md` is git-tracked and contains the live admin password and proxy admin secret; the same creds work on the public Cloudflare deployment | Tiger | Launch-Blocking | `git ls-files memory/` + successful live login with those creds | Rotate admin password & admin secret; remove file from tracking (`git rm --cached`), add to `.gitignore`; purge from history if repo is public (it is). | strikersam | before any public launch |
| 4 | 9 pre-existing test failures in `tests/test_company_graph.py` / `tests/test_company_api.py` on this branch | Tiger | Fast-Follow | `pytest` run 2026-06-10 | Triage and fix; CI "green" claim is currently false locally. | strikersam | +14 days |
| 5 | Local branch is 5+ commits ahead of origin; PR #489 unmerged; no push credentials configured locally | Tiger | Fast-Follow | `git rev-list` vs `origin/consolidate/maturation-stable` | Push branch + merge #489 once GitHub auth is available. | strikersam | +7 days |
| 6 | Ollama unreachable on the deployment (public doctor warns) | Tiger | Track | Live `/api/doctor/public` | Expected on Cloudflare (no local Ollama); provider routing falls back to nvidia-nim, which passes. Document this in the doctor explainer. | — | review cadence |
| 7 | Sidecar runtimes (hermes/goose/aider) "fail" and flip Doctor to not-ready although they are optional betas | Tiger→fixed | Launch-Blocking | Live authenticated `/api/doctor` | **FIXED** in commit `2818339` — optional runtimes now `warn`; only `internal_agent` is required. | strikersam | on next deploy |
| 8 | "A competitor copies the 34-specialist-family pitch" | Paper Tiger | — | No evidence of impact; differentiation is execution, not the list | None. | — | — |
| 9 | README autonomy claims exceed what the support matrix admits (beta/experimental features in the hot path) | Elephant | TBD | User's own audit prompt concedes this; support matrix vs README | Name it: either demote claims in README or promote features to stable with E2E evidence. Decision documented, not deferred. | strikersam | before marketing push |

## Elephants, named

1. **The README sells a product the feature matrix doesn't back.** Everyone working on the repo knows it. Either the claims come down or the features come up — keeping both is how the "stranger pastes a URL" demo fails in public.
2. **Credentials hygiene.** A tracked markdown file holds working admin credentials for a public deployment of a repo that is itself public on GitHub. This is the quiet risk most likely to become an incident, and it costs minutes to fix.

## What was already fixed during this pre-mortem

- #1 doctor storage crash (`1120346`)
- #2 malformed-ID 500 (`563ae93`)
- #7 sidecar runtimes gating (`2818339`)

Remaining launch blocker: **#3 credential rotation/removal** — requires the owner (rotation invalidates active sessions/tools).
