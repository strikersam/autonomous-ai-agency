/**
 * tests/worker/worker_no_cache.test.js — regression test for the Cloudflare CDN
 * caching bug that broke social login.
 *
 * Root cause: the worker's `not_found_handling: "single-page-application"`
 * setting served index.html at /api/auth/github/login, Cloudflare cached that
 * HTML response, and every subsequent browser request got the cached HTML
 * instead of the 307 redirect to GitHub. The social login button appeared to
 * do nothing because the browser navigated to the cached HTML page (which the
 * SPA then redirected to /login).
 *
 * Fix: worker/index.js now sets `Cache-Control: no-store` on every proxied
 * API response so Cloudflare never caches it.
 *
 * This test verifies the worker's fetch handler sets the no-cache headers on
 * proxied responses. It doesn't test the actual Cloudflare CDN (that requires
 * a deployment) — it tests the worker code that prevents the cache from
 * forming.
 */
const { describe, test, expect } = require('@jest/globals');

// Read the worker source + verify the no-cache headers are set
const fs = require('fs');
const path = require('path');

const workerSource = fs.readFileSync(
  path.join(__dirname, '..', '..', '..', 'worker', 'index.js'),
  'utf-8'
);

describe('Worker no-cache headers (social login CDN bug)', () => {
  test('proxied API responses include Cache-Control: no-store', () => {
    // The worker must set Cache-Control: no-store on proxied responses
    // so Cloudflare's CDN never caches them. Without this, the SPA's
    // not_found_handling can serve index.html at /api/* URLs, the CDN
    // caches it, and every subsequent browser request gets the cached
    // HTML instead of the real API response.
    expect(workerSource).toMatch(/Cache-Control.*no-store/);
  });

  test('proxied API responses include Pragma: no-cache', () => {
    // Belt-and-suspenders for HTTP/1.0 caches
    expect(workerSource).toMatch(/Pragma.*no-cache/);
  });

  test('proxied API responses include Expires: 0', () => {
    // Belt-and-suspenders for HTTP/1.0 caches
    expect(workerSource).toMatch(/Expires.*["']0["']/);
  });

  test('the no-cache headers are applied INSIDE the needsProxy branch', () => {
    // The headers must only be set on proxied (API) responses, not on
    // static asset responses (which SHOULD be cached for performance).
    // Match from the needsProxy if-block to the closing brace (the next
    // "return new Response" which is the proxy response).
    const needsProxyBlock = workerSource.match(
      /if \(needsProxy\(url\.pathname\)\) \{[\s\S]*?return new Response\(response\.body/
    );
    expect(needsProxyBlock).toBeTruthy();
    expect(needsProxyBlock[0]).toMatch(/Cache-Control.*no-store/);
  });
});

describe('Worker scheduled() keep-warm redundancy (PR #920)', () => {
  // PR #919 reverted the Worker to the PR #896 state, which left only the
  // secret-gated POST /api/scheduler/tick in scheduled(). If CRON_SECRET
  // drifts between Render env and the Cloudflare Worker secret, every tick
  // silently 403s and Render sleeps after 15 min idle.
  //
  // PR #920 restores a parallel GET /api/ping (unauthenticated, no DB I/O)
  // as the PRIMARY keep-warm signal. The POST /api/scheduler/tick remains
  // as a secondary signal (fires overdue APScheduler jobs).

  test('scheduled() handler exists', () => {
    expect(workerSource).toMatch(/async scheduled\(event,\s*env,\s*ctx\)/);
  });

  test('scheduled() pings GET /api/ping (primary keep-warm, no DB I/O)', () => {
    // The primary keep-warm must be unauthenticated so it works even
    // when CRON_SECRET is mismatched.
    const scheduledBlock = workerSource.match(
      /async scheduled\(event,\s*env,\s*ctx\)\s*\{[\s\S]*?\n\}/
    );
    expect(scheduledBlock).toBeTruthy();
    expect(scheduledBlock[0]).toMatch(/GET \/api\/ping|\/api\/ping.*method:\s*["']GET["']/);
  });

  test('scheduled() still POSTs /api/scheduler/tick (secondary, secret-gated)', () => {
    const scheduledBlock = workerSource.match(
      /async scheduled\(event,\s*env,\s*ctx\)\s*\{[\s\S]*?\n\}/
    );
    expect(scheduledBlock).toBeTruthy();
    expect(scheduledBlock[0]).toMatch(/\/api\/scheduler\/tick/);
    expect(scheduledBlock[0]).toMatch(/x-cron-secret/);
  });

  test('GET /api/ping and POST /api/scheduler/tick both use ctx.waitUntil (parallel)', () => {
    // Both pings must be wrapped in ctx.waitUntil so they run in parallel
    // and the scheduled handler returns immediately. A 403 on the POST
    // must NOT block the GET.
    const scheduledBlock = workerSource.match(
      /async scheduled\(event,\s*env,\s*ctx\)\s*\{[\s\S]*?\n\}/
    );
    expect(scheduledBlock).toBeTruthy();
    const waitUntilCount = (scheduledBlock[0].match(/ctx\.waitUntil/g) || []).length;
    expect(waitUntilCount).toBeGreaterThanOrEqual(2);
  });
});
