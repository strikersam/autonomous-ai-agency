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
 *
 * RENDER FREE TIER: Render free tier cold-starts take 50+ seconds. The Worker's
 * default fetch timeout is ~30s which causes 502 errors. We use AbortController
 * with a 90s timeout to give Render enough time to wake up.
 */
const BACKEND_ORIGIN = "https://local-llm-server.onrender.com";

// Render free tier cold start can take 50+ seconds. Cloudflare Workers have a
// 30s default CPU time but wall-clock time is higher. Use 90s to cover cold starts.
const BACKEND_TIMEOUT_MS = 90000;

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

      // Cloudflare Workers have a 30s wall-clock CPU limit. We can't extend
      // that. But we CAN do multiple fetch attempts with shorter timeouts.
      // Strategy: try 3 times with 10s timeout each. If Render is cold,
      // the first attempt wakes it up, the second or third gets through.
      let lastError = null;
      for (let attempt = 1; attempt <= 3; attempt++) {
        try {
          const controller = new AbortController();
          const timeoutId = setTimeout(() => controller.abort(), 10000);
          const response = await fetch(proxied, {
            redirect: "manual",
            signal: controller.signal,
          });
          clearTimeout(timeoutId);

          // Got a response! Pass it through.
          const headers = new Headers(response.headers);
          headers.set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
          headers.set("Pragma", "no-cache");
          headers.set("Expires", "0");
          return new Response(response.body, {
            status: response.status,
            statusText: response.statusText,
            headers,
          });
        } catch (err) {
          clearTimeout(timeoutId);
          lastError = err;
          // Wait 2s before retrying (gives Render time to wake up)
          if (attempt < 3) {
            await new Promise(resolve => setTimeout(resolve, 2000));
          }
        }
      }

      // All 3 attempts failed — return 503 with retry hint
      return new Response(
        JSON.stringify({
          detail: "Backend is starting up. Please retry in a few seconds.",
          retry_after: 3,
        }),
        {
          status: 503,
          headers: {
            "Content-Type": "application/json",
            "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
            "Retry-After": "3",
          },
        }
      );
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
    // Cloudflare Cron fires every minute — pings Render to keep it warm
    // (free tier sleeps after 15 min inactivity) + fires scheduled jobs.
    const secret = env.CRON_SECRET || "";
    ctx.waitUntil(
      Promise.all([
        // Health ping — keeps Render warm so login doesn't 502
        fetch(BACKEND_ORIGIN + "/api/health", { signal: AbortSignal.timeout(15000) })
          .then(r => console.log("health", r.status))
          .catch(e => console.warn("health err", e.message)),
        // Scheduler tick — fires overdue jobs
        fetch(BACKEND_ORIGIN + "/api/scheduler/tick", {
          method: "POST",
          headers: { "x-cron-secret": secret },
          signal: AbortSignal.timeout(15000),
        })
          .then(r => r.ok ? console.log("tick ok") : console.warn("tick", r.status))
          .catch(e => console.error("tick err", e.message)),
      ])
    );
  },
};
