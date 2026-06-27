# Cloudflare = the real working app

The Cloudflare Workers deployment (`autonomous-ai-agency.strikersam.workers.dev`) serves the
**real React app** connected to the live backend — not the static marketing demo.
(The pre-rebrand `local-llm-server.strikersam.workers.dev` URL now 404s.)

## How it works

```text
Browser ──► autonomous-ai-agency.strikersam.workers.dev
              ├── /                  → React SPA (frontend/build, served as static assets)
              └── /api/*, /runtimes/* → reverse-proxied to https://local-llm-server.onrender.com
```

- `worker/index.js` is the Worker entry: it proxies the backend prefixes (`/api`, `/runtimes`)
  to the Render backend and serves static assets for everything else.
- Because the app and the API share one origin, there is **no CORS** to configure and the
  `Authorization: Bearer` token (in `localStorage`, sent by `frontend/src/api.js`) passes through.
- `frontend/src/api.js` uses `window.location.origin` as the backend base when
  `REACT_APP_BACKEND_URL` is unset, so the build intentionally leaves it unset.
- SPA client-side routes are handled by `assets.not_found_handling: "single-page-application"`.

## Cloudflare dashboard settings to verify

`wrangler.jsonc` declares the build via `build.command`. If the connected Cloudflare
**Workers Builds** project doesn't pick that up, set in the dashboard
(Workers & Pages → local-llm-server → Settings → Build):

- **Build command:** `cd frontend && npm install --legacy-peer-deps && CI=false PUBLIC_URL=/ REACT_APP_BACKEND_URL= npm run build && rm -f build/_redirects`
  - `rm -f build/_redirects` — CRA's `/* /index.html 200` rule is rejected by Workers Assets; SPA fallback is handled by `not_found_handling` instead.
  - `REACT_APP_BACKEND_URL=` (empty) is **required** — it overrides any dashboard build env var so the app uses `window.location.origin` and routes API calls through the same-origin proxy. If a non-empty `REACT_APP_BACKEND_URL` gets baked in, the app calls the backend cross-origin, triggering CORS preflights that fail (`OPTIONS /api/auth/login → 400`) and breaking login.
- **Deploy command:** `npx wrangler deploy`
- **Root directory:** repository root
- **Build env vars:** leave `REACT_APP_BACKEND_URL` **unset/empty** in the dashboard (the build command forces it empty regardless, but don't rely on a stale value).

## Backend (Render)

Data APIs work through the proxy with no backend change. **OAuth/social login is the
exception:** after a successful GitHub/Google callback the backend redirects to
`FRONTEND_URL`. It MUST be the live app origin
**`FRONTEND_URL=https://autonomous-ai-agency.strikersam.workers.dev`** (set in `render.yaml`
and the Render dashboard). If it points anywhere else — e.g. the old `https://strikersam.github.io`
Pages demo — the post-callback redirect lands the session tokens on the wrong origin and both
GitHub and Google login silently fail (you bounce back to `/login` unauthenticated), even though
the OAuth handshake itself succeeds. Email/password login is unaffected. The OAuth start uses
`OAUTH_REDIRECT_BASE` (currently `https://local-llm-server.onrender.com`); its
`/api/auth/{github,google}/callback` paths must stay registered in the GitHub and Google OAuth apps.

If the backend URL changes, update `BACKEND_ORIGIN` in `worker/index.js`.

## Verify after deploy

1. Open `https://autonomous-ai-agency.strikersam.workers.dev` → the real app loads (not the demo).
2. `https://autonomous-ai-agency.strikersam.workers.dev/api/health` → returns the backend health JSON
   (confirms the proxy works).
3. Sign in with GitHub **and** Google → each returns to
   `https://autonomous-ai-agency.strikersam.workers.dev/auth/callback?...` and lands authenticated
   on the dashboard (not back on `/login`).
4. Log in and run company onboarding against a real URL → real scanner results with categories.

## Notes

- The old static marketing page (`index.html`) is no longer served at this URL. It remains in the
  repo; deploy it elsewhere (e.g. GitHub Pages) if you still want the demo.
- The Render backend may cold-start (free tier sleeps); the first `/api/*` request can be slow.
