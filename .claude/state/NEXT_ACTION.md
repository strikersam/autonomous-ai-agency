# Next Action
# NEXT_ACTION — updated 2026-10-30 (daily automation, branch `claude/intelligent-gates-hfu9ql`)

Daily automation complete. PR #1861 open. CI green → auto-merge to master.

Three models added: GPT-6.1 Terra ($1/$5), Kimi K3.1 Pro ($2/$10), Inception Mercury 3 ($0.10/$0.35).

## Next daily run suggestions (2026-10-31)
- Check PR #1861 merged; if not, investigate CI failure.
- Look for any new model releases: GPT-6.1 Terra Pro if it surfaces, Kimi K3.1 Pro Highspeed (mentioned in search results but pricing unconfirmed), any new Anthropic or Google releases.
- Monitor Inception Mercury 3 for a standalone API ID (currently only OpenRouter confirmed).

---
# Previous NEXT_ACTION — 2026-10-29 (security audit, branch `security/cloudflare-audit-fixes`)
# NEXT_ACTION — updated 2026-10-31 (security audit remaining findings, branch `security/audit-remaining`)

All leads left open by #1858/#1860 are fixed in one PR: DNS-pinned fetches (`agent/web_reach.py` `pinned_transport`), SEO browser SSRF guard, logout revocation (`tokens_valid_after`), login-CSRF nonce on `/auth/callback`, GitHub repo-connect claim code, Google `verified_email`, self-repo shipping limited to system/admin tasks, anonymous heartbeat redaction, E2B write-back containment, literal company search, quick-note CI author gate + credential isolation, diag/seed hardening.

## Open items

1. **Operator check** — bare `/api/auth/<provider>/login` links (no login-page nonce) now end on the callback error screen; use the login page.
2. **Product check** — regular users' tasks now run report-only (no platform GitHub token / auto-commit); quick notes and portfolio board changes are admin-only. Reverse in `tasks/service.py::_owner_may_ship_code` if users should ship code.
3. ~~Unaudited surfaces~~ — reviewed 2026-10-31 (branch `security/bandit-tmp-fix`): Hermes `/tasks` fails closed with a render-generated `HERMES_API_KEY`; spec approve/reject and sprint changes admin-only; `direct_chat` no longer falls back to the host GitHub token; ceo and code-mode routers already admin-gate their mutations. Operator: confirm `agency-hermes` picked up the generated `HERMES_API_KEY` after the blueprint sync.

---

# NEXT_ACTION — updated 2026-10-29 (security audit, branch `security/cloudflare-audit-fixes`)

Ran the cloudflare/security-audit-skill workflow (standard profile, sandboxed source-and-local only). The run is **incomplete**: coverage critics, a second hunter wave, 7 Phase-3 validations and Phase-5 record verification were not run (user asked to finish; agent limit hit). Fixed 9 independently confirmed findings plus 2 parent-verified ones (task purge scope, cron issue-intake label gate), each with a regression test. Audit artifacts live outside the repo (`~/security-audit-skill/autonomous-ai-agency/run-1/`).

## Open items

1. **JWT revocation** (confirmed, low) — logout/password rotation do not revoke access or refresh tokens; needs a per-user `token_version` claim checked in `get_optional_user`, `JWTUserStateMiddleware` and `/api/auth/refresh`.
2. **Needs validation, then fix** — Google login links by email without `verified_email` (`packages/auth/oauth.py`, risky module: rule 15 review first); GitHub repo-connect callback state not bound to the browser (check registered callback URL); `/auth/callback` accepts any URL token (login CSRF); quick-note CI pipeline has no author trust gate and gives an unrestricted shell with persisted `GH_PAT` (check repo issue visibility); Mongo `$regex` search unescaped.
3. **Unvalidated candidates** — anonymous `/api/autonomy/tick` and `/status` echo other users' task titles; DNS-rebinding gap in `unsafe_target_reason`; E2B `extract_changes_to_worktree` writes sandbox-reported paths without containment; SEO browser fetch has no SSRF route guard; self-registered users can queue self-repo-ship agent work.
4. **Unaudited surfaces** — agile/ceo/spec/code-mode routers, `services/hermes_server.py`, `direct_chat.py` host GH token fallback.

---

# NEXT_ACTION — updated 2026-10-25 (daily automation, branch `claude/intelligent-gates-xd0rsk`)

Gemini 4 Argon (`gemini-4-argon` / `google/gemini-4-argon`, GA 2026-10-13) declared at priority 99. $2/$10 intro pricing with 5% cache read override. PR #1830 open; 31 tests pass; catalogue 100 ids; PARITY OK.

## Open items for next daily run

1. **Gemini 4 Argon live probe** — declared priority 99 (explicit-only). Once PR merges and account is probed, lower priority and set as candidate.

2. **Anthropic API version 2026-10-21** — New API version with breaking changes (document blocks in assistant messages → 400; citations on text blocks → 400). Multiple files currently hardcode `"2023-06-01"`. Needs explicit human decision (rule 40 — breaking API change) before update. Not skipped for capability reasons; needs authorization.

3. **Gemini 4 Argon pricing update** — introductory $2/$10 ends 2026-11-30; standard $4/$20 from 2026-12-01. Update `_DEFAULT_COST_TABLE` entries before that date.

4. **Kimi K3.1 Pro** — search found mention but no confirmed API model ID or pricing. Re-check when official Moonshot docs publish it.

---

# NEXT_ACTION — updated 2026-10-23 (daily automation, branch `claude/intelligent-gates-pc2vqv`)

Qwen3.6 27B (`qwen/qwen3.6-27b`, Groq, $0.60/$3.00/MTok) and MiniMax M3.1 Flash cost entry (`MiniMax-M3.1-Flash`, $0.15/$0.60/MTok) added. 23 tests pass; compileall clean; changelog parity OK; catalogue 98 ids no drift.

## Open items for next daily run

1. **Qwen3.6 27B live probe** — declared at priority 99 (explicit-only). Once the PR merges and the Groq account is probed, lower priority and add to routing candidates.

2. **MiniMax M3.1 Flash TokenIn ID** — confirm `myt/MiniMax-M3.1-Flash-free` is a real TokenIn candidate ID. Add to the `myt/` free section of cost_tracker when confirmed.

3. **DeepSeek V4 Pro tool-call probe** — declared `supports_tools: false` conservatively. Once the NIM account proves the model answers completions, raise a follow-up to set `supports_tools: true` and lower priority from 99.

4. **Groq Llama 4 Scout probe** (`meta-llama/llama-4-scout-17b-16e-instruct`, priority 99) — still pending.

5. **Qwen3.6 27B non-reasoning variant** — research suggests a `qwen/qwen3.6-27b-non-reasoning` variant; confirm model ID format from Groq console before adding.

---

# NEXT_ACTION — updated 2026-10-20 (daily automation, branch `claude/intelligent-gates-x2astt`)

**Updated:** 2026-10-22

## Immediate

- **PR #1815** (`feat(models): MiniMax M3.1 Flash`) — CI running. 29 checks (in_progress/queued, none failed at push time). Merge when green.

## Background context

- Daily automation (2026-10-22) completed: added `minimax/minimax-m3.1-flash:free` to model catalogue. Ecosystem scan reviewed Claude Code v2.1.305, Codex CLI v0.163.0, NVIDIA NIM, OpenRouter. No other changes warranted today.
- `deepseek-ai/deepseek-v4.1-flash` remains blocked by the 2026-09-27 note: re-add only after a live completion probe confirms it answers on this NIM account.
- Task 50 (central provider/model source of truth): P1-P4 still pending — needs real pytest suite (fastapi/motor unavailable in remote sandbox).
- Task 34 (TokenIn): blocked on Render billing.
