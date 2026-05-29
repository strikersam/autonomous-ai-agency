# Cloudflare = the real working app

The Cloudflare Workers deployment (`local-llm-server.strikersam.workers.dev`) serves the
**real React app** connected to the live backend — not the static marketing demo.

## How it works

```
Browser ──► local-llm-server.strikersam.workers.dev
              ├── /            → React SPA  (frontend/build, served as static assets)
              └── /api/*       → reverse-proxied to https://local-llm-server.onrender.com
```

- `worker/index.js` is the Worker entry: it proxies `/api/*` to the Render backend and serves
  static assets for everything else.
- Because the app and the API share one origin, there is **no CORS** to configure and the
  `Authorization: Bearer` token (in `localStorage`, sent by `frontend/src/api.js`) passes through.
- `frontend/src/api.js` uses `window.location.origin` as the backend base when
  `REACT_APP_BACKEND_URL` is unset, so the build intentionally leaves it unset.
- SPA client-side routes are handled by `assets.not_found_handling: "single-page-application"`.

## Cloudflare dashboard settings to verify

`wrangler.jsonc` declares the build via `build.command`. If the connected Cloudflare
**Workers Builds** project doesn't pick that up, set in the dashboard
(Workers & Pages → local-llm-server → Settings → Build):

- **Build command:** `cd frontend && npm install --legacy-peer-deps && PUBLIC_URL=/ npm run build`
- **Deploy command:** `npx wrangler deploy`
- **Root directory:** repository root
- **Build env vars:** do **not** set `REACT_APP_BACKEND_URL` (same-origin proxy is used). If you
  ever want the app to hit the backend directly instead, set it to the Render URL and add the
  workers.dev origin to the backend `CORS_ORIGINS`.

## Backend (Render)

No change required — the Worker proxies to `https://local-llm-server.onrender.com`. If the
backend URL changes, update `BACKEND_ORIGIN` in `worker/index.js`.

## Verify after deploy

1. Open `https://local-llm-server.strikersam.workers.dev` → the real app loads (not the demo).
2. `https://local-llm-server.strikersam.workers.dev/api/health` → returns the backend health JSON
   (confirms the proxy works).
3. Log in and run company onboarding against a real URL → real scanner results with categories.

## Notes

- The old static marketing page (`index.html`) is no longer served at this URL. It remains in the
  repo; deploy it elsewhere (e.g. GitHub Pages) if you still want the demo.
- The Render backend may cold-start (free tier sleeps); the first `/api/*` request can be slow.
