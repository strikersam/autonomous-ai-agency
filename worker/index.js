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

// Backend path prefixes to reverse-proxy to Render. Everything else is the SPA.
// Keep this in sync with assets.run_worker_first in wrangler.jsonc.
const PROXY_PREFIXES = ["/api", "/runtimes"];

function needsProxy(pathname) {
  return PROXY_PREFIXES.some((p) => pathname === p || pathname.startsWith(p + "/"));
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (needsProxy(url.pathname)) {
      const target = BACKEND_ORIGIN + url.pathname + url.search;
      const proxied = new Request(target, request);
      proxied.headers.set("X-Forwarded-Host", url.host);
      return fetch(proxied, { redirect: "manual" });
    }

    return env.ASSETS.fetch(request);
  },

  async scheduled(event, env, ctx) {
    // Cloudflare Cron fires every minute — pings the Render backend tick endpoint
    // to keep APScheduler alive and fire overdue scheduled jobs.
    const secret = env.CRON_SECRET || "";
    ctx.waitUntil(
      fetch(BACKEND_ORIGIN + "/api/scheduler/tick", {
        method: "POST",
        headers: { "x-cron-secret": secret },
      })
        .then(r => r.ok ? console.log("tick ok") : console.warn("tick", r.status))
        .catch(e => console.error("tick error", e))
    );
  },
};
