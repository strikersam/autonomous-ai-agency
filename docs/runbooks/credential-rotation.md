# Credential Rotation Runbook

The 2026-06-10 pre-mortem (docs/pre-mortem-2026-06-10.md, risk #3) found the
admin password, proxy admin secret, and later a GitHub PAT in
`memory/test_credentials.md`, which was git-tracked in this public repo.
The file is now untracked + gitignored, but **the values remain in git
history and must be rotated**.

## What to rotate (owner action, ~10 minutes)

1. **Admin password** — set a new `ADMIN_PASSWORD` in the Render dashboard
   (single source of truth; nothing else hardcodes it — verified by repo scan).
   Active JWT sessions expire naturally (24h access / 7d refresh).
2. **Proxy admin secret** — regenerate and update the env var; update any
   Telegram/remote-admin clients using it.
3. **GitHub PAT** — revoke the exposed token at github.com/settings/tokens
   and mint a fine-grained replacement (repo scope only). Update
   `GH_TOKEN`/`GITHUB_TOKEN` in Render + GitHub Actions secrets.
4. **History purge (optional but recommended)** — `git filter-repo
   --path memory/test_credentials.md --invert-paths` + force-push, or use
   GitHub Support to invalidate cached views.

## Guardrails already in place

- `memory/test_credentials.md` is gitignored.
- CI "Secret / Credential Scan" check blocks new leaks on PRs.
- `docker-compose.e2e.yml` and tests read `ADMIN_PASSWORD` from env only.
