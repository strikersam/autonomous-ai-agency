/**
 * Login flow regression test (PR #922).
 *
 * Root cause being addressed: PR #920 added a 60s default axios timeout +
 * 90s login-specific timeout + a retry interceptor to frontend/src/api.js.
 * On Render free-tier cold starts (>90s), the login request would:
 *   1. Hit the 90s timeout
 *   2. Retry once (due to a _retried flag bug, only 1 retry fired)
 *   3. Hit the 90s timeout again
 *   4. Show "Login failed" after ~182s (~3 minutes)
 *
 * PR #922 reverts frontend/src/api.js to the #896 state (no timeout, no
 * retry) so login requests hang indefinitely until the backend responds —
 * same as #896 which the user confirmed is "very fast".
 *
 * This test verifies the #896 axios config is preserved:
 *   - No `timeout` key on the axios.create() call
 *   - No RETRY_DELAYS_MS / RETRYABLE_ERRORS constants
 *   - No retry interceptor in the response interceptor chain
 *   - login() does NOT pass a {timeout: ...} override
 *
 * It also verifies social login buttons still work (regression guard for
 * the OAuth callback path that #920 improved with request.url_for()).
 *
 * No sensitive credentials are used — this is a source-inspection test
 * that reads api.js as text and verifies the config. It does NOT make
 * real HTTP requests or use any real passwords/tokens.
 */
const { describe, test, expect } = require('@jest/globals');

const fs = require('fs');
const path = require('path');

const apiSource = fs.readFileSync(
  path.join(__dirname, '..', 'api.js'),
  'utf-8'
);

describe('Login flow: no aggressive axios timeout (PR #922 — restore #896 behavior)', () => {
  test('axios.create() does NOT set a `timeout` key (was 60s in #920, caused login to fail mid-cold-start)', () => {
    // Extract the axios.create({...}) block
    const createMatch = apiSource.match(/axios\.create\(\s*\{[\s\S]*?\}\s*\)/);
    expect(createMatch).toBeTruthy();
    // The #920 version had `timeout: DEFAULT_API_TIMEOUT_MS,` inside this block.
    // The #896 version does NOT. Verify it's absent.
    expect(createMatch[0]).not.toMatch(/timeout\s*:/);
  });

  test('api.js does NOT define DEFAULT_API_TIMEOUT_MS or LOGIN_TIMEOUT_MS', () => {
    // These constants were added by #920 and are the root cause of the
    // login slowness. They must NOT exist in the #896/#922 version.
    expect(apiSource).not.toMatch(/DEFAULT_API_TIMEOUT_MS/);
    expect(apiSource).not.toMatch(/LOGIN_TIMEOUT_MS/);
  });

  test('api.js does NOT define RETRY_DELAYS_MS or RETRYABLE_ERRORS', () => {
    // The retry interceptor was added by #920. It must NOT exist in the
    // #896/#922 version — retries on ECONNABORTED just double the wait
    // on a struggling backend.
    expect(apiSource).not.toMatch(/RETRY_DELAYS_MS/);
    expect(apiSource).not.toMatch(/RETRYABLE_ERRORS/);
  });

  test('response interceptor does NOT contain a retry block (no _retried / _retryAttempt flags)', () => {
    // The #920 retry interceptor set `orig._retried = true` on the first
    // retry, which gated out the second retry (only 1 fired instead of 2).
    // Verify these flags are absent.
    expect(apiSource).not.toMatch(/_retried/);
    expect(apiSource).not.toMatch(/_retryAttempt/);
    expect(apiSource).not.toMatch(/_noRetry/);
  });

  test('login() does NOT pass a {timeout: ...} override (was 90s in #920)', () => {
    // Extract the login function body
    const loginMatch = apiSource.match(/export const login[\s\S]*?^};/m);
    expect(loginMatch).toBeTruthy();
    // The #920 version had `{ timeout: LOGIN_TIMEOUT_MS }` as the 3rd arg
    // to API.post. The #896 version has no 3rd arg. Verify it's absent.
    expect(loginMatch[0]).not.toMatch(/timeout\s*:/);
  });

  test('login() self-heal retry also does NOT pass a timeout override', () => {
    // The #920 version's catch block had a second API.post with
    // { timeout: LOGIN_TIMEOUT_MS }. Verify it's absent.
    const loginMatch = apiSource.match(/export const login[\s\S]*?^};/m);
    expect(loginMatch).toBeTruthy();
    // Count API.post calls — #896 has 2 (initial + self-heal), both without timeout
    const postCalls = loginMatch[0].match(/API\.post\(/g) || [];
    expect(postCalls.length).toBeGreaterThanOrEqual(2);
    // None of them should have a timeout arg
    expect(loginMatch[0]).not.toMatch(/timeout/);
  });
});

describe('Login flow: social login buttons still work (regression guard)', () => {
  // This is a sanity check that the OAuth callback improvements from #920
  // (request.url_for(), fire-and-forget log_activity) didn't get reverted
  // when we reverted api.js. The social login button hrefs are generated
  // in LoginPage.js, not api.js — so they should be unaffected. But we
  // verify anyway because the user explicitly said "I don't want social
  // login or anything else to be broken anymore."

  test('api.js still exports the functions LoginPage needs for social login', () => {
    // LoginPage.js imports: login, fmtErr, getBackendUrl, API
    expect(apiSource).toMatch(/export const login/);
    expect(apiSource).toMatch(/export function fmtErr/);
    expect(apiSource).toMatch(/export function getBackendUrl/);
    expect(apiSource).toMatch(/export const API/);
  });

  test('api.js CORS self-heal logic is intact (needed for social login redirects)', () => {
    // The CORS self-heal clears a stale backend_url when the configured
    // backend is unreachable. This is separate from the #920 retry
    // interceptor and MUST be preserved.
    expect(apiSource).toMatch(/_corsHeal/);
    expect(apiSource).toMatch(/ERR_NETWORK/);
  });

  test('api.js 401 token refresh logic is intact (needed for session expiry)', () => {
    // The 401 refresh interceptor handles expired access tokens by
    // calling /api/auth/refresh. This is separate from the #920 retry
    // interceptor and MUST be preserved.
    expect(apiSource).toMatch(/\/api\/auth\/refresh/);
    expect(apiSource).toMatch(/isRefreshing/);
    expect(apiSource).toMatch(/refreshQueue/);
  });
});
