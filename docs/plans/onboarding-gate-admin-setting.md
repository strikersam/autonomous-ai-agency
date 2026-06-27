# Implementation Plan — Onboarding-Gate Admin Setting + Ephemeral Companies

> Branch: `claude/onboarding-gate-admin-setting-tv7zc5`
> Status: in progress

## Goal

Give admins a single, DB-persisted switch that **turns off the per-user
onboarding activation gate by default**, so any logged-in user can run the
setup wizard without being added to the allow-list one-by-one.

To keep the platform affordable on the **free Render backend**, agencies
created by non-admin (GitHub / Google) users are **ephemeral**: their company
and settings live for **24 hours** and are then destroyed by a reaper loop.
**Only admin-created companies persist forever.** A floating banner tells
non-admin users about the 24-hour window and why it exists.

## Requirements → design

| # | Requirement | Where |
|---|-------------|-------|
| 1 | Admin setting to turn off the onboarding gate by default, persisted in DB | `app_settings.py` (new) + `activation_api.py` settings routes + sqlite `app_settings` table |
| 2 | Gate default feeds the onboarding allow check | `activation_api.is_user_onboarding_allowed` consults the cached global default |
| 3 | GitHub/Google users' companies live 24h then are destroyed | `Company` model gets `persistent` / `expires_at` / `created_by_*`; `create_company` sets them; reaper loop deletes expired |
| 4 | Admin-created companies persist forever | `create_company` marks admin companies `persistent=True, expires_at=None` |
| 5 | Floating banner notifying the 24h limit + free-Render note | `EphemeralBanner.jsx` mounted in `AppShell`, backed by `GET /api/company/account/lifecycle` |
| 6 | Admin UI toggle for the setting | New `SectionCard` in `AdminOnboardingPanel.jsx` |

## Backend changes

### `app_settings.py` (new)
Tiny async settings layer over `db.get_store()`, collection `app_settings`
(one doc per key: `{key, value, updated_at, updated_by}`).
- `get_setting(key, default)` / `set_setting(key, value, updated_by)`
- Typed helpers + module-level cache:
  - `ONBOARDING_GATE_ENABLED_KEY` (default `True` — gate on, per-user allow).
    When an admin sets it `False`, users with no explicit record are allowed.
  - `EPHEMERAL_TTL_HOURS_KEY` (default `24`).
- `onboarding_gate_enabled_cached()` — sync read of the in-process cache so the
  existing sync gate check stays sync; cache is refreshed on set + best-effort
  at startup.

### `db/sqlite_store.py`
Add `"app_settings"` to `_COLLECTIONS` and index it on `key`. (Mongo store is
dynamic, no change needed.)

### `activation_api.py`
- `is_user_onboarding_allowed(uid)`: if the user has an explicit record, honour
  it; otherwise fall back to "allowed when the gate is disabled".
- New admin routes:
  - `GET /api/activation/settings` → current settings.
  - `PUT /api/activation/settings` → update + audit + cache refresh.

### `models/company_graph.py`
Add to `Company`:
- `persistent: bool = True`
- `expires_at: datetime | None = None`
- `created_by_role: str | None = None`
- `created_by_provider: str | None = None`

### `backend/company_api.py`
`create_company` resolves admin status + provider and passes lifecycle fields:
- admin → `persistent=True, expires_at=None`
- non-admin → `persistent=False, expires_at=now + ttl_hours`
- New `GET /api/company/account/lifecycle` → `{ ephemeral, expires_at,
  ttl_hours, persistent, note }` for the banner.

### `services/ephemeral_reaper.py` (new) + `services/background.py`
Async daemon (`EPHEMERAL_COMPANY_REAPER_ENABLED`, default on) that periodically
deletes companies with `persistent=False` and `expires_at <= now`. Registered
alongside the other autonomy loops and catalogued in `loops/registry.yaml`.

## Frontend changes
- `EphemeralBanner.jsx` — floating, dismissible banner shown to non-admin users
  with the countdown + free-Render note. Mounted in `AppShell`.
- `AdminOnboardingPanel.jsx` — "Default Onboarding Gate" `SectionCard` with the
  toggle + TTL.
- `api.js` — `getOnboardingSettings`, `updateOnboardingSettings`,
  `getAccountLifecycle`.

## Tests
- `tests/test_app_settings.py` — get/set persistence + gate-default behaviour.
- `tests/test_ephemeral_reaper.py` — reaps expired ephemeral, keeps persistent
  and unexpired.
- `tests/test_activation_api.py` — settings routes (admin-gated).
- Company-creation lifecycle assertions (admin vs social user).

## Docs / changelog
- `docs/changelog.md` under `[Unreleased]` (`Added` / `Security`).
- `docs/admin/` note on the new setting + ephemeral lifecycle.
