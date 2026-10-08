# Intent: a page search engines and AI crawlers can actually read

Author: repository owner, written up by Claude Code. Status: accepted 2026-10-08.

## Problem

The agency has no visibility. Every host (Cloudflare Worker, Netlify, GitHub Pages)
serves only the React app, so `/` is a JavaScript shell that redirects to a login
form. Crawlers that do not run JavaScript, which includes most AI crawlers, see an
empty page. The 1,500-line root `index.html` was never deployed anywhere, and its
demo invents a scan of a real retail brand, so it cannot be used as it stands.
Agent SEO tasks kept "fixing" a login wall (#1694, #1696).

## Proposed outcome

`/` on the production Worker serves a static, crawlable landing page that says what
the project does, how it works and where the evidence is. Signed-in visitors go
straight to the dashboard. The app shell is `noindex`, so only the landing page is
indexed. Search engines get a sitemap; AI crawlers get `llms.txt`.

## Affected users and systems

First-time visitors, search and AI crawlers. `worker/index.js`, `wrangler.jsonc`,
`frontend/public/` (`home.html`, `_redirects`, `robots.txt`, `sitemap.xml`,
`llms.txt`, `index.html` meta).

## Constraints

- Every claim on the page is checkable in the repository; no invented customers,
  metrics, contacts or testimonials.
- No change to the app's routes, auth or API proxying.
- No external fonts or scripts: the page must render fast and without JavaScript.

## Open questions

- GitHub Pages cannot rewrite `/`, so the Pages mirror keeps serving the app there
  (now `noindex`). The Worker is the canonical host.
