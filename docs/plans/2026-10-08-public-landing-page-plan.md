# Plan: a page search engines and AI crawlers can actually read

From [`docs/intent/2026-10-08-public-landing-page.md`](../intent/2026-10-08-public-landing-page.md).

## Files that change

- `frontend/public/home.html` (new): static landing page, inline CSS, JSON-LD.
- `frontend/public/og.jpg` (new): social preview, copied from `brag-output/brag.jpg`.
- `frontend/public/sitemap.xml` (new); `robots.txt` gains the sitemap and `Disallow: /v5/`.
- `frontend/public/_redirects`: `/` rewrites to `home.html` on Netlify.
- `frontend/public/index.html`: `noindex` on the app shell.
- `frontend/public/llms.txt`: links the home page.
- `worker/index.js`: serve the `/home` asset for `GET`/`HEAD /`, fall back to the SPA if it is missing.
- `wrangler.jsonc`: add `/` to `run_worker_first`; without it Cloudflare serves `index.html` and never runs the Worker.
- Tests: `frontend/src/__tests__/worker_landing.test.js`, `tests/test_landing_page.py`.

## Order of work

1. Write the page from facts in `README.md` and `proof/README.md` only.
2. Wire the Worker and Netlify; mark the app shell `noindex`; sitemap and robots.
3. Tests, then run the real Worker with `wrangler dev` and a browser before merging.

## Risks

- Signed-in users landing on `/` now see the landing page for one script tick before
  `location.replace("/v5")`. Accepted; the redirect runs before first paint in practice.
- A broken `home.html` deploy would take `/` with it; the Worker falls back to the SPA
  when the asset is missing.

## Proof

Jest drives the Worker's real `fetch` (fails without the change). `tests/test_landing_page.py`
checks head tags, landmarks, JSON-LD, every link and quoted number. `wrangler dev`: `/`
returns the landing page, `/login`, `/v5/*` and deep links return the app.
