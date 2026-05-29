/**
 * Cloudflare Worker entry for the production app.
 *
 * Serves the built React SPA (frontend/build, bound as ASSETS) and reverse-proxies
 * every /api/* request to the Render backend. Proxying keeps the app and API on the
 * SAME origin, so there are no CORS requirements and the Authorization: Bearer token
 * (stored client-side and sent by frontend/src/api.js) passes straight through.
 *
 * Non-/api paths fall through to static assets; SPA client-side routes are handled by
 * the `not_found_handling: "single-page-application"` setting in wrangler.jsonc.
 */
const BACKEND_ORIGIN = "https://local-llm-server.onrender.com";

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (url.pathname === "/api" || url.pathname.startsWith("/api/")) {
      const target = BACKEND_ORIGIN + url.pathname + url.search;
      // Preserve method, headers (incl. Authorization), and body.
      const proxied = new Request(target, request);
      proxied.headers.set("X-Forwarded-Host", url.host);
      // redirect: "manual" so backend 3xx responses (e.g. OAuth login) are handed
      // back to the browser instead of being followed server-side.
      return fetch(proxied, { redirect: "manual" });
    }

    return env.ASSETS.fetch(request);
  },
};
