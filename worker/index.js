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
 *
 * CRITICAL: API responses MUST NOT be cached by Cloudflare's CDN. The SPA's
 * `not_found_handling: "single-page-application"` setting serves index.html for
 * any unmatched path — including /api/* paths if the worker somehow doesn't run
 * first. If Cloudflare caches that HTML response at an /api/* URL, every subsequent
 * browser request to that API endpoint gets the cached HTML instead of the real
 * API response (307 redirect, 401 JSON, etc.). This was the root cause of the
 * "social login button click does nothing" bug: /api/auth/github/login was cached
 * as SPA HTML, so clicking the button navigated to the cached HTML page instead
 * of following the 307 redirect to GitHub. Fix: set `Cache-Control: no-store` on
 * every proxied API response so the CDN never caches it.
 */
const BACKEND_ORIGIN = "https://local-llm-server.onrender.com";

// Backend path prefixes to reverse-proxy to Render. Everything else is the SPA.
// Keep this in sync with assets.run_worker_first in wrangler.jsonc.
// Keep in sync with assets.run_worker_first in wrangler.jsonc.
// "/admin/api" is proxied (not "/admin") so admin-gated JSON endpoints like
// /admin/api/policy/brain reach the Render backend (the Brain card needs this),
// while the "/admin" HTML portal path is left to normal asset/SPA handling.
const PROXY_PREFIXES = ["/api", "/v1", "/v4", "/runtimes", "/admin/api", "/agent"];

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
      const response = await fetch(proxied, { redirect: "manual" });
      // CRITICAL: Prevent Cloudflare's CDN from caching API responses.
      const headers = new Headers(response.headers);
      headers.set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
      headers.set("Pragma", "no-cache");
      headers.set("Expires", "0");
      return new Response(response.body, {
        status: response.status,
        statusText: response.statusText,
        headers,
      });
    }

    // For non-API paths, try to serve a static asset first.
    const assetResponse = await env.ASSETS.fetch(request);
    // If the asset exists (200), serve it. If not (404), serve index.html
    // for SPA client-side routing — BUT only for non-API paths (API paths
    // are handled by needsProxy above and should NEVER reach here).
    if (assetResponse.status === 200) {
      return assetResponse;
    }
    // SPA fallback: serve index.html for client-side routes like /login,
    // /dashboard, etc. This replaces the "single-page-application"
    // not_found_handling setting (which was causing the CDN to cache
    // index.html at /api/* URLs for navigation requests).
    const indexRequest = new Request(new URL("/", url.origin), request);
    const indexResponse = await env.ASSETS.fetch(indexRequest);
    // Clone + set no-cache so the SPA shell itself isn't cached at
    // random paths (only at "/" where it belongs).
    const spaHeaders = new Headers(indexResponse.headers);
    spaHeaders.set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
    return new Response(indexResponse.body, {
      status: 200,
      statusText: "OK",
      headers: spaHeaders,
    });
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
