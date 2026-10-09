/**
 * @vitest-environment node
 *
 * The Worker serves the static landing page (frontend/public/home.html) at "/"
 * and the SPA everywhere else. Crawlers that do not run JavaScript only ever saw
 * the app's login shell, so the agency had no indexable page.
 */
import worker from '../../../worker/index.js';

// The Vitest node environment may not expose the Fetch API globals the Worker
// runtime has. These stand-ins cover exactly what worker/index.js uses.
class FakeHeaders {
  constructor(init) {
    this.map = new Map(init instanceof FakeHeaders ? init.map : Object.entries(init || {}));
  }
  get(k) { return this.map.has(k.toLowerCase()) ? this.map.get(k.toLowerCase()) : null; }
  set(k, v) { this.map.set(k.toLowerCase(), v); }
}
class FakeResponse {
  constructor(body, init = {}) {
    this.body = body;
    this.status = init.status ?? 200;
    this.statusText = init.statusText || '';
    this.headers = new FakeHeaders(init.headers);
  }
  async text() { return String(this.body); }
}
class FakeRequest {
  constructor(input, init = {}) {
    this.url = typeof input === 'string' || input instanceof URL ? String(input) : input.url;
    this.method = init.method || input.method || 'GET';
    this.headers = new FakeHeaders(init.headers instanceof FakeHeaders ? init.headers : undefined);
  }
}
if (typeof globalThis.Request === 'undefined') {
  Object.assign(globalThis, { Request: FakeRequest, Response: FakeResponse, Headers: FakeHeaders });
}

const ORIGIN = 'https://agency.example';

function assets(files) {
  const seen = [];
  return {
    seen,
    fetch: async (req) => {
      const { pathname } = new URL(req.url);
      seen.push(pathname);
      const body = files[pathname];
      return body === undefined
        ? new Response('not found', { status: 404 })
        : new Response(body, { status: 200, headers: { 'Content-Type': 'text/html' } });
    },
  };
}

const call = (path, env, method = 'GET') => worker.fetch(new Request(ORIGIN + path, { method }), env);

describe('landing page at "/"', () => {
  test('"/" serves home.html, not the app shell', async () => {
    const env = { ASSETS: assets({ '/home': 'LANDING', '/': 'APP_SHELL' }) };
    const res = await call('/', env);
    expect(res.status).toBe(200);
    expect(await res.text()).toBe('LANDING');
  });

  test('HEAD "/" is answered from the landing page too', async () => {
    const env = { ASSETS: assets({ '/home': 'LANDING', '/': 'APP_SHELL' }) };
    expect((await call('/', env, 'HEAD')).status).toBe(200);
    expect(env.ASSETS.seen[0]).toBe('/home');
  });

  test('app routes still get the SPA shell', async () => {
    const env = { ASSETS: assets({ '/home': 'LANDING', '/': 'APP_SHELL' }) };
    for (const path of ['/login', '/v5', '/v5/tasks', '/auth/callback']) {
      const res = await call(path, env);
      expect(await res.text()).toBe('APP_SHELL');
    }
  });

  test('a missing landing asset falls back to the SPA instead of failing', async () => {
    const env = { ASSETS: assets({ '/': 'APP_SHELL' }) };
    expect(await (await call('/', env)).text()).toBe('APP_SHELL');
  });

  test('static files such as robots.txt and sitemap.xml are served as-is', async () => {
    const env = { ASSETS: assets({ '/robots.txt': 'ROBOTS', '/sitemap.xml': 'SITEMAP', '/': 'APP_SHELL' }) };
    expect(await (await call('/robots.txt', env)).text()).toBe('ROBOTS');
    expect(await (await call('/sitemap.xml', env)).text()).toBe('SITEMAP');
  });

  test('/home, /home/ and /home.html permanently redirect to the canonical "/"', async () => {
    const env = { ASSETS: assets({ '/home': 'LANDING', '/': 'APP_SHELL' }) };
    for (const path of ['/home', '/home/', '/home.html']) {
      const res = await call(path, env);
      expect(res.status).toBe(301);
      expect(res.headers.get('location')).toBe(ORIGIN + '/');
    }
  });

  test('an asset redirect is passed through, not swallowed into the noindex app shell', async () => {
    const env = {
      ASSETS: {
        fetch: async (req) => (new URL(req.url).pathname === '/docs/'
          ? new Response(null, { status: 308, headers: { Location: '/docs' } })
          : new Response('APP_SHELL', { status: 200 })),
      },
    };
    const res = await call('/docs/', env);
    expect(res.status).toBe(308);
  });

  test('a missing file is a 404, not a 200 app shell', async () => {
    const env = { ASSETS: assets({ '/': 'APP_SHELL' }) };
    expect((await call('/favicon.ico', env)).status).toBe(404);
    expect((await call('/login', env)).status).toBe(200);
  });
});
