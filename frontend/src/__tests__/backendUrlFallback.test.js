/**
 * tests/backendUrlFallback.test.js — regression test for the social-login
 * "buttons don't work on GitHub Pages" bug.
 *
 * Root cause: getDefaultBackendUrl() returned window.location.origin when
 * REACT_APP_BACKEND_URL was unset. On github.io that's
 * https://strikersam.github.io — which 404s on every /api/auth/* call.
 * The social login buttons navigated to a 404 and OAuth never started.
 *
 * Fix: detect github.io specifically and fall back to the canonical
 * Cloudflare Worker URL (which reverse-proxies /api/* to the Render
 * backend). The worker is the same-origin production frontend per render.yaml.
 */
import { getBackendUrl } from '../api';

describe('getDefaultBackendUrl (via getBackendUrl) — social login regression', () => {
  const originalLocalStorage = window.localStorage;
  const originalLocation = window.location;

  beforeEach(() => {
    // Clear any cached backend_url override
    window.localStorage.clear();
    // Delete the env var so we test the fallback path
    delete process.env.REACT_APP_BACKEND_URL;
  });

  afterEach(() => {
    // Restore env + location
    delete process.env.REACT_APP_BACKEND_URL;
    // jsdom doesn't allow reassigning window.location directly — use the
    // delete + redefine trick so the next test's beforeEach can set it.
  });

  function setLocation(origin) {
    // jsdom-safe location override
    delete window.location;
    window.location = new URL(origin);
  }

  test('on github.io with no REACT_APP_BACKEND_URL, falls back to the Cloudflare Worker URL', () => {
    // Simulate a user landing on the GitHub Pages mirror
    setLocation('https://strikersam.github.io/autonomous-ai-agency/');
    const url = getBackendUrl();
    expect(url).toBe('https://autonomous-ai-agency.strikersam.workers.dev');
  });

  test('on github.io, REACT_APP_BACKEND_URL still wins (deploy-time baked value)', () => {
    // When the deploy workflow sets REACT_APP_BACKEND_URL (the production
    // setup), that value must win over the github.io fallback — so the
    // GitHub Pages build can point at the Render backend directly.
    process.env.REACT_APP_BACKEND_URL = 'https://local-llm-server.onrender.com';
    setLocation('https://strikersam.github.io/autonomous-ai-agency/');
    const url = getBackendUrl();
    expect(url).toBe('https://local-llm-server.onrender.com');
  });

  test('on the Cloudflare Worker (same-origin), returns window.location.origin', () => {
    // The worker deployment sets REACT_APP_BACKEND_URL='' explicitly so
    // /api/* goes through the worker's own origin (which proxies to Render).
    setLocation('https://autonomous-ai-agency.strikersam.workers.dev/');
    const url = getBackendUrl();
    expect(url).toBe('https://autonomous-ai-agency.strikersam.workers.dev');
  });

  test('on localhost (dev), returns window.location.origin', () => {
    setLocation('http://localhost:3000/');
    const url = getBackendUrl();
    expect(url).toBe('http://localhost:3000');
  });

  test('localStorage backend_url override always wins (used by the setup wizard)', () => {
    // The setup wizard lets the operator paste a backend URL — it goes to
    // localStorage so it persists across reloads. This must take precedence
    // over both env var and the github.io fallback.
    setLocation('https://strikersam.github.io/autonomous-ai-agency/');
    window.localStorage.setItem('backend_url', 'https://my-custom-backend.example.com');
    const url = getBackendUrl();
    expect(url).toBe('https://my-custom-backend.example.com');
  });
});
