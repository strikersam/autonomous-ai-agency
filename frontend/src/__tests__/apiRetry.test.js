/**
 * Tests for the frontend axios timeout + bounded retry config added in PR #920.
 *
 * Root cause being addressed: PR #919 reverted the frontend to the PR #896
 * state (no axios timeout, no retry interceptor) to fix the login
 * breakage caused by PR #911-918's over-aggressive retry. The revert was
 * correct for correctness but left no cold-start recovery — a single
 * transient ERR_NETWORK during a Render free-tier cold start showed the
 * user "Network Error" with no auto-retry.
 *
 * PR #920 re-adds a MINIMAL, SAFE version:
 *   - 60s default axios timeout (was: none → hung forever on a dead backend)
 *   - 2 retries with 2s/5s backoff on ERR_NETWORK / ECONNABORTED /
 *     ECONNREFUSED / ETIMEDOUT only (was: 4 retries, 120s — too aggressive)
 *   - HTTP error responses (4xx/5xx) are NOT retried — they're real errors
 *
 * This test reads the api.js source and verifies the config is present and
 * bounded. It doesn't actually fire HTTP requests (that would require a
 * running backend) — it tests the source code that produces the config.
 */
const { describe, test, expect } = require('@jest/globals');

const fs = require('fs');
const path = require('path');

const apiSource = fs.readFileSync(
  path.join(__dirname, '..', 'api.js'),
  'utf-8'
);

describe('Frontend axios timeout + retry config (PR #920)', () => {
  test('axios.create is called with a 60_000 ms (60s) default timeout', () => {
    // 60s is long enough to survive a Render cold start (30-60s) but short
    // enough to not hang forever on a truly dead backend.
    expect(apiSource).toMatch(/timeout:\s*DEFAULT_API_TIMEOUT_MS/);
    expect(apiSource).toMatch(/DEFAULT_API_TIMEOUT_MS\s*=\s*60[_]?000/);
  });

  test('RETRYABLE_ERRORS set includes ERR_NETWORK, ECONNABORTED, ECONNREFUSED, ETIMEDOUT', () => {
    // These are the only axios error codes that indicate a transient
    // connection failure (no HTTP response). 4xx/5xx responses are NOT
    // in this set — they are real errors and must not be retried.
    expect(apiSource).toMatch(/'ERR_NETWORK'/);
    expect(apiSource).toMatch(/'ECONNABORTED'/);
    expect(apiSource).toMatch(/'ECONNREFUSED'/);
    expect(apiSource).toMatch(/'ETIMEDOUT'/);
  });

  test('retry backoff is bounded to 2 retries (2s + 5s = 7s max backoff)', () => {
    // PR #911-918 used 4 retries with up to 12s delays — total 42s of
    // backoff on top of a 120s timeout = 8 min before the user saw an
    // error. PR #920 caps it at 2 retries / 7s total backoff.
    expect(apiSource).toMatch(/RETRY_DELAYS_MS\s*=\s*\[\s*2[_]?000\s*,\s*5[_]?000\s*\]/);
  });

  test('retry interceptor only fires when there is NO HTTP response', () => {
    // The guard `!error.response` ensures 4xx/5xx responses are NOT
    // retried. This is the bug PR #911-918 had — it retried 502s, which
    // masked real outages and amplified load on a struggling backend.
    const retryBlock = apiSource.match(
      /if \(\s*!error\.response[\s\S]*?RETRYABLE_ERRORS\.has\(error\.code\)\s*\)/
    );
    expect(retryBlock).toBeTruthy();
    expect(retryBlock[0]).toMatch(/!error\.response/);
    expect(retryBlock[0]).toMatch(/!orig\._retried/);
  });

  test('login uses a longer 90s timeout (cold-start tolerance for first visit)', () => {
    // Login is the first call after the page loads, so it's the most
    // likely to hit a cold start. 90s gives 30s of headroom over the
    // default 60s — enough for a slow Render cold start to finish.
    expect(apiSource).toMatch(/LOGIN_TIMEOUT_MS\s*=\s*90[_]?000/);
    expect(apiSource).toMatch(/timeout:\s*LOGIN_TIMEOUT_MS/);
  });

  test('retry is opt-out per-request via config._noRetry', () => {
    // Long-running operations that have their own retry logic (e.g.
    // chat polling) can set _noRetry: true to disable the interceptor.
    expect(apiSource).toMatch(/!orig\._noRetry/);
  });
});
