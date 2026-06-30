/**
 * Cloudflare Worker entry for the production app.
 *
 * Serves the built React SPA and reverse-proxies /api/* to Render.
 * The frontend has retry logic for cold-start timeouts.
 */
const BACKEND_ORIGIN = "https://local-llm-server.onrender.com";

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

      try {
        const response = await fetch(proxied, { redirect: "manual" });
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
        // Render is cold-starting or unreachable. Return 503 so the
        // frontend's axios interceptor retries automatically.
        return new Response(
          JSON.stringify({ detail: "Backend starting up. Retrying..." }),
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
    }

    // Static assets / SPA routing
    const assetResponse = await env.ASSETS.fetch(request);
    if (assetResponse.status === 200) {
      return assetResponse;
    }
    const indexRequest = new Request(new URL("/", url.origin), request);
    const indexResponse = await env.ASSETS.fetch(indexRequest);
    const spaHeaders = new Headers(indexResponse.headers);
    spaHeaders.set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0");
    return new Response(indexResponse.body, {
      status: 200,
      statusText: "OK",
      headers: spaHeaders,
    });
  },

  async scheduled(event, env, ctx) {
    const secret = env.CRON_SECRET || "";
    ctx.waitUntil(
      fetch(BACKEND_ORIGIN + "/api/health")
        .then(r => console.log("health", r.status))
        .catch(e => console.warn("health err", e.message))
    );
    ctx.waitUntil(
      fetch(BACKEND_ORIGIN + "/api/scheduler/tick", {
        method: "POST",
        headers: { "x-cron-secret": secret },
      })
        .then(r => r.ok ? console.log("tick ok") : console.warn("tick", r.status))
        .catch(e => console.error("tick err", e.message))
    );
  },
};
