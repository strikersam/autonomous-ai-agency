"""Regression tests for the remaining 2026-10 security-audit findings."""

from __future__ import annotations

import pytest


# ── 1. company search text is matched literally, never as a regex ─────────────

class _Cursor:
    def __init__(self):
        self.max_time = None

    def skip(self, n):
        return self

    def limit(self, n):
        return self

    def max_time_ms(self, ms):
        self.max_time = ms
        return self

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


class _Collection:
    def __init__(self):
        self.queries: list = []
        self.cursor = _Cursor()

    def find(self, query):
        self.queries.append(query)
        return self.cursor


class _DB:
    def __init__(self):
        self.companies = _Collection()
        self.knowledge_items = _Collection()


@pytest.mark.asyncio
async def test_company_search_escapes_regex_and_bounds_time(monkeypatch):
    from services import company_graph_store as cgs

    db = _DB()
    store = cgs.MongoDBStore.__new__(cgs.MongoDBStore)
    monkeypatch.setattr(store, "_get_db", lambda: db, raising=False)

    await store.list_companies(owner_id="u1", search="(a+)+$" + "x" * 500)
    clause = db.companies.queries[0]["$or"][0]["name"]["$regex"]
    assert clause.startswith(r"\(a\+\)\+\$")
    assert len(clause) <= 2 * cgs._SEARCH_MAX_CHARS
    assert db.companies.queries[0]["owner_id"] == "u1"
    assert db.companies.cursor.max_time == cgs._SEARCH_MAX_TIME_MS

    await store.search_knowledge(query=".*")
    assert db.knowledge_items.queries[0]["$or"][0]["title"]["$regex"] == r"\.\*"


# ── 2. anonymous autonomy heartbeat never echoes another tenant's task ────────

def test_anonymous_autonomy_tick_redacts_task_identity(monkeypatch):
    from fastapi.testclient import TestClient

    import backend.server as server
    from tasks import service
    from tasks.models import Task

    task = Task(owner_id="alice@example.test", title="CONFIDENTIAL dummy merger plan")

    class _Store:
        async def list_pending(self, limit=1):
            return [task]

        async def list_blocked(self, limit=10):
            return []

    async def held(store, task_id):
        return False

    monkeypatch.setattr("tasks.store.get_task_store", lambda: _Store())
    monkeypatch.setattr(service, "claim_task_run", held)
    monkeypatch.setattr(server, "_anon_tick_last", {})
    monkeypatch.delenv("CRON_SECRET", raising=False)
    monkeypatch.setenv("SELF_BOOTSTRAP_ENABLED", "true")
    body = TestClient(server.app, raise_server_exceptions=False).get("/api/autonomy/tick").text

    assert "CONFIDENTIAL" not in body
    assert task.task_id not in body


def test_autonomy_status_redacts_cached_dispatch(monkeypatch):
    from fastapi.testclient import TestClient

    import backend.server as server

    monkeypatch.setattr(
        server,
        "_autonomy_dispatch_cache",
        {"ran": False, "task_id": "task_secret", "task_title": "CONFIDENTIAL", "error": "boom"},
    )
    body = TestClient(server.app, raise_server_exceptions=False).get("/api/autonomy/status").json()
    assert body["dispatch"] == {"ran": False}


# ── 4. repo-connect OAuth token lands only on the browser-proven initiator ────

class _MemCol:
    def __init__(self):
        self.docs: list[dict] = []

    async def insert_one(self, doc):
        self.docs.append(dict(doc))

    async def find_one(self, query):
        for d in self.docs:
            if all(d.get(k) == v for k, v in query.items()):
                return d
        return None

    async def delete_one(self, query):
        d = await self.find_one(query)
        if d is not None:
            self.docs.remove(d)

    async def update_one(self, query, update, upsert=False):
        d = await self.find_one(query)
        if d is None:
            d = dict(query)
            self.docs.append(d)
        d.update(update.get("$set", {}))


class _MemDB:
    def __init__(self):
        for name in ("oauth_states", "github_oauth_claims", "github_settings", "users"):
            setattr(self, name, _MemCol())


@pytest.mark.asyncio
async def test_repo_connect_token_requires_claim_by_initiator(monkeypatch):
    import backend.server as server

    db = _MemDB()
    monkeypatch.setattr(server, "get_db", lambda: db)
    monkeypatch.setattr(server, "GITHUB_CLIENT_ID", "cid")

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(server, "log_activity", _noop)

    class _Resp:
        def __init__(self, data):
            self._d = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._d

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def post(self, *a, **k):
            return _Resp({"access_token": "gho_VICTIM"})

        async def get(self, *a, **k):
            return _Resp({"login": "victim-gh"})

    monkeypatch.setattr(server.httpx, "AsyncClient", _Client)

    attacker = {"_id": "attacker-1", "role": "user"}
    start = await server.github_oauth_start(user=attacker, redirect=True)
    state = start["url"].split("state=")[1]

    resp = await server.github_oauth_callback(code="VICTIMCODE", state=state)
    assert db.github_settings.docs == []  # nothing bound by the callback itself
    claim = resp.headers["location"].split("github_claim=")[1]

    victim = {"_id": "victim-2", "role": "user"}
    with pytest.raises(server.HTTPException) as exc:
        await server.github_oauth_claim(server.GitHubOAuthClaimBody(claim_code=claim), user=victim)
    assert exc.value.status_code == 403
    assert db.github_settings.docs == []

    # A login-flow state can never complete a repo connect.
    await db.oauth_states.insert_one({"state": "login-state", "flow_type": "login", "provider": "github"})
    login_resp = await server.github_oauth_callback(code="X", state="login-state")
    assert "github_claim" not in getattr(login_resp, "headers", {}).get("location", "")


@pytest.mark.asyncio
async def test_repo_connect_claim_by_initiator_stores_token(monkeypatch):
    import backend.server as server
    from datetime import datetime, timezone

    db = _MemDB()
    monkeypatch.setattr(server, "get_db", lambda: db)

    async def _noop(*a, **k):
        return None

    monkeypatch.setattr(server, "log_activity", _noop)
    import hashlib
    await db.github_oauth_claims.insert_one({
        "claim_hash": hashlib.sha256(b"c" * 32).hexdigest(), "user_id": "owner-1",
        "token": "gho_OWN", "github_login": "me", "created_at": datetime.now(timezone.utc),
    })
    out = await server.github_oauth_claim(
        server.GitHubOAuthClaimBody(claim_code="c" * 32), user={"_id": "owner-1"}
    )
    assert out == {"connected": True, "login": "me"}
    assert db.github_settings.docs[0]["token"] == "gho_OWN"


# ── 5. Google login links accounts only by a verified, matching identity ─────

def _fake_google_userinfo(monkeypatch, payload):
    import packages.auth.oauth as oauth

    class _Resp:
        status_code = 200

        def json(self):
            return payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return None

        async def get(self, *a, **k):
            return _Resp()

    monkeypatch.setattr(oauth.httpx, "AsyncClient", _Client)
    return oauth


@pytest.mark.asyncio
async def test_google_unverified_email_is_not_usable_for_linking(monkeypatch):
    oauth = _fake_google_userinfo(
        monkeypatch, {"id": "999", "email": "Admin@LLMRelay.local", "verified_email": False}
    )
    assert (await oauth.google_fetch_user("tok"))["email"] == ""

    oauth = _fake_google_userinfo(
        monkeypatch, {"id": "999", "email": "Me@Example.test", "verified_email": True}
    )
    assert (await oauth.google_fetch_user("tok"))["email"] == "me@example.test"


@pytest.mark.asyncio
async def test_google_login_refuses_email_bound_to_other_google_id(monkeypatch):
    import backend.server as server
    from datetime import datetime, timezone
    from starlette.requests import Request

    db = _MemDB()
    await db.oauth_states.insert_one({
        "state": "s1", "flow_type": "login", "provider": "google", "created_at": datetime.now(timezone.utc),
    })
    await db.users.insert_one({"_id": "u1", "email": "me@example.test", "provider": "google",
                               "provider_user_id": "111", "role": "admin"})
    monkeypatch.setattr(server, "get_db", lambda: db)
    monkeypatch.setattr(server, "OAUTH_REDIRECT_BASE", "https://backend.example")

    async def _exchange(code, redirect_uri=None):
        return "tok"

    async def _fetch(token):
        return {"user_id": "goog_222", "email": "me@example.test", "name": "x", "avatar_url": "", "provider": "google"}

    monkeypatch.setattr(server, "google_exchange_code", _exchange)
    monkeypatch.setattr(server, "google_fetch_user", _fetch)
    req = Request({"type": "http", "method": "GET", "path": "/", "headers": [], "query_string": b""})

    with pytest.raises(server.HTTPException) as exc:
        await server.google_callback(req, code="c", state="s1")
    assert exc.value.status_code == 403


# ── 6. logout revokes previously issued access and refresh tokens ────────────

@pytest.mark.asyncio
async def test_logout_revokes_tokens_issued_before_it(monkeypatch):
    import jwt
    from starlette.requests import Request

    import backend.server as server

    users = {"u1": {"_id": "u1", "email": "u1@example.test", "role": "user"}}

    class _Users:
        async def find_one(self, q):
            u = users.get(str(q.get("_id")))
            return dict(u) if u else None

        async def update_one(self, q, upd):
            users[str(q.get("_id"))].update(upd["$set"])

    class _DB:
        users = _Users()

    monkeypatch.setattr(server, "get_db", lambda: _DB())
    monkeypatch.setattr(server, "_user_id_filter", lambda uid: {"_id": uid})

    def _req(token):
        return Request({"type": "http", "method": "GET", "path": "/api/auth/me", "query_string": b"",
                        "headers": [(b"authorization", f"Bearer {token}".encode())]})

    stolen_access = server.create_access_token("u1", "u1@example.test")
    stolen_refresh = server.create_refresh_token("u1")
    issued = jwt.decode(stolen_access, options={"verify_signature": False})["iat"]
    assert await server.get_optional_user(_req(stolen_access)) is not None

    monkeypatch.setattr(server._time, "time", lambda: issued + 5)
    await server.logout(user={"_id": "u1", "email": "u1@example.test"})

    assert await server.get_optional_user(_req(stolen_access)) is None
    refresh_req = Request({"type": "http", "method": "POST", "path": "/api/auth/refresh",
                           "query_string": b"", "headers": []})

    async def _body():
        return {"refresh_token": stolen_refresh}

    refresh_req.json = _body
    with pytest.raises(server.HTTPException) as exc:
        await server.refresh_token(refresh_req)
    assert exc.value.status_code == 401

    # A login in or after the logout second is still accepted.
    assert server._token_revoked({"iat": issued + 5}, users["u1"]) is False
    assert server._token_revoked({"iat": issued + 4}, users["u1"]) is True


# ── 7. DNS rebinding: the connection dials the address the check approved ────

def test_pinned_fetch_never_reaches_a_rebound_private_address(monkeypatch):
    import http.server
    import socket
    import threading

    from agent import web_reach

    hits: list[str] = []

    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            hits.append(self.path)
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"internal")

        def log_message(self, *a):
            return None

    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    port = srv.server_address[1]
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    real = socket.getaddrinfo
    calls = {"n": 0}

    def _rebinding(host, *a, **k):
        if host == "rebind.test":
            calls["n"] += 1
            addr = "93.184.216.34" if calls["n"] == 1 else "127.0.0.1"
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (addr, port))]
        return real(host, *a, **k)

    monkeypatch.setattr(socket, "getaddrinfo", _rebinding)
    reach = web_reach.WebReach(timeout=2)
    try:
        with pytest.raises(Exception):
            reach.safe_get(f"http://rebind.test:{port}/internal")
    finally:
        srv.shutdown()
    assert hits == []


def test_vet_host_rejects_any_private_answer(monkeypatch):
    import socket

    from agent import web_reach

    monkeypatch.setattr(socket, "getaddrinfo", lambda *a, **k: [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", 0)),
    ])
    addr, reason = web_reach.vet_host("mixed.test")
    assert addr is None and "non-public" in reason


# ── 8. SEO browser fetch refuses internal targets (navigation, redirects, subrequests) ──

@pytest.mark.asyncio
async def test_browser_guard_aborts_internal_requests(monkeypatch):
    from services import scanner, seo_fetch

    monkeypatch.setattr(scanner, "_is_safe_url", lambda u: "internal" not in u)

    class _Req:
        def __init__(self, url, nav):
            self.url = url
            self._nav = nav

        def is_navigation_request(self):
            return self._nav

    class _Route:
        def __init__(self, url, nav):
            self.request = _Req(url, nav)
            self.outcome = None

        async def abort(self):
            self.outcome = "abort"

        async def continue_(self):
            self.outcome = "continue"

    for url, nav, want in [
        ("http://internal.example/", True, "abort"),
        ("https://public.example/", True, "continue"),
        ("http://169.254.169.254/latest/meta-data/", False, "abort"),
        ("https://cdn.example/app.js", False, "continue"),
    ]:
        r = _Route(url, nav)
        await seo_fetch._browser_ssrf_guard(r)
        assert r.outcome == want, url


@pytest.mark.asyncio
async def test_browser_redirect_chain_to_internal_is_refused(monkeypatch):
    from services import scanner, seo_fetch

    monkeypatch.setattr(scanner, "_is_safe_url", lambda u: "internal" not in u)

    class _R:
        def __init__(self, url, prev=None):
            self.url = url
            self.redirected_from = prev

    class _Resp:
        request = _R("http://internal.example/secret", _R("https://public.example/"))

    with pytest.raises(ValueError):
        await seo_fetch._refuse_unsafe_redirects(_Resp(), "https://public.example/landing")
    await seo_fetch._refuse_unsafe_redirects(None, "https://public.example/landing")


# ── 9. quick-note CI: model-driven shell never sees the job's credentials ─────

def test_implement_agent_tool_env_has_no_credentials(monkeypatch, tmp_path):
    import importlib.util
    from pathlib import Path

    spec = importlib.util.spec_from_file_location(
        "implement_agent", Path(__file__).resolve().parents[1] / ".github/scripts/implement_agent.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    for k, v in {"GH_PAT": "x", "GITHUB_TOKEN": "x", "NVIDIA_API_KEY": "x", "CEREBRAS_API_KEY": "x",
                 "AWS_SECRET_ACCESS_KEY": "x", "PATH": "/usr/bin", "HOME": str(tmp_path)}.items():
        monkeypatch.setenv(k, v)
    env = mod._tool_env()
    assert "PATH" in env and "HOME" in env
    assert not {"GH_PAT", "GITHUB_TOKEN", "NVIDIA_API_KEY", "CEREBRAS_API_KEY", "AWS_SECRET_ACCESS_KEY"} & set(env)


def test_quick_note_agent_steps_hide_persisted_git_credential():
    from pathlib import Path

    import yaml

    root = Path(__file__).resolve().parents[1]
    wf = yaml.safe_load((root / ".github/workflows/process-quick-note.yml").read_text())
    steps = {s.get("id"): s for job in wf["jobs"].values() for s in job["steps"] if s.get("id")}
    for sid in ("implement", "review_apply"):
        assert "--unset-all http.https://github.com/.extraheader" in steps[sid]["run"], sid
    gen = yaml.safe_load((root / ".github/workflows/issue-context-generator.yml").read_text())
    dispatch = [s for job in gen["jobs"].values() for s in job["steps"]
                if s.get("name") == "Comment + dispatch auto-implementation"][0]
    assert "author_association" in dispatch["if"]


# ── 10. social-login callback carries the per-click browser nonce ────────────

@pytest.mark.asyncio
async def test_login_state_keeps_browser_nonce_and_callback_echoes_it(monkeypatch):
    import backend.server as server

    db = _MemDB()
    monkeypatch.setattr(server, "get_db", lambda: db)
    await server._store_login_state("st", "github", "abc123xyz")
    await server._store_login_state("st2", "github", "../bad nonce")
    assert db.oauth_states.docs[0]["browser_nonce"] == "abc123xyz"
    assert db.oauth_states.docs[1]["browser_nonce"] is None

    resp = server._callback_redirect("A", "R", db.oauth_states.docs[0])
    assert resp.headers["location"].endswith("&nonce=abc123xyz")
    assert "nonce=" not in server._callback_redirect("A", "R", db.oauth_states.docs[1]).headers["location"]


# ── 11. hardening ─────────────────────────────────────────────────────────────

def test_observability_diag_reports_presence_not_key_prefixes(monkeypatch):
    from fastapi.testclient import TestClient

    import backend.server as server

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "pk-lf-SECRETPREFIX123")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "sk-lf-SECRETPREFIX456")
    monkeypatch.setenv("LANGFUSE_HOST", "http://diag.invalid")
    body = TestClient(server.app, raise_server_exceptions=False).get("/api/observability/diag").text
    assert "SECRETPREFIX" not in body and "pk-lf" not in body and "sk-l" not in body


def test_admin_seed_requires_testing_exactly_true(monkeypatch):
    from fastapi.testclient import TestClient

    import backend.server as server

    monkeypatch.setenv("TESTING", "false")
    assert TestClient(server.app, raise_server_exceptions=False).post("/api/admin/seed").status_code == 404


# ── 12. self-repo shipping: only platform-owned or admin-owned work ──────────

@pytest.mark.asyncio
async def test_only_system_or_admin_tasks_may_ship_code(monkeypatch):
    import backend.server as server
    from tasks import service

    class _Users:
        async def find_one(self, q):
            return {"u-admin": {"role": "admin"}, "u-user": {"role": "user"}}.get(q.get("_id"))

    class _DB:
        users = _Users()

    monkeypatch.setattr(server, "get_db", lambda: _DB())
    monkeypatch.setattr(server, "_doc_id_filter", lambda i: {"_id": i})
    assert await service._owner_may_ship_code("system") is True
    assert await service._owner_may_ship_code("u-admin") is True
    assert await service._owner_may_ship_code("u-user") is False
    assert await service._owner_may_ship_code("unknown") is False
    assert await service._owner_may_ship_code("") is False


def test_v4_quick_note_submit_is_admin_only():
    import json

    from fastapi import FastAPI, Request
    from fastapi.testclient import TestClient

    import backend.v4_api as v4

    app = FastAPI()

    @app.middleware("http")
    async def _user(request: Request, call_next):
        request.state.user = json.loads(request.headers["x-test-user"])
        return await call_next(request)

    app.include_router(v4.v4_router)
    resp = TestClient(app).post(
        "/v4/quick-notes", json={"content": "ship something"},
        headers={"x-test-user": json.dumps({"_id": "u", "role": "user"})},
    )
    assert resp.status_code == 403
