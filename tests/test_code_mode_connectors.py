"""Code Mode phases 3-5 (agent/code_mode_connectors.py, agent/code_mode_snippets.py)."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest

from agent import code_mode_connectors as cc
from agent import code_mode_snippets as sn
from agent import prompts
from agent.code_mode import CodeModeError, CodeModeLimits, callable_tools, run_code
from packages.config import settings
from packages.config.code_mode_connectors import OpenApiConnectorSpec, connector_token, openapi_connectors
from packages.config.control_registry import get_control

# Fake values held in names so they read as data, not as hard-coded credentials.
ALICE_GH = "gh-alice"
SERVER_ENV_GH = "gh-env-server"
RENDER_SETTING = "render_api_key"

PROMPT = (
    "Available tools:\n"
    "- read_file(path)\n"
    "- search_code(query, limit=20): Grep the workspace\n"
    "  for a pattern.\n"
    "- head_file(path, lines=50)\n"
    "- edit_file(path, old_string, new_string): Replace text\n"
    "Return ONLY a JSON object\n"
)


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    sn.reset_store()
    monkeypatch.setattr(sn._persist, "collection", lambda name: None)
    monkeypatch.setattr(settings, "agent_code_mode_enabled_raw", "true")
    monkeypatch.setattr(settings, "agent_code_mode_snippets_raw", "true")
    monkeypatch.setattr(settings, "agent_code_mode_mcp_raw", "true")
    monkeypatch.setattr(settings, "agent_code_mode_openapi_raw", "true")
    yield
    sn.reset_store()


async def _no_gate(label: str, args: dict[str, Any], thunk):
    return await thunk()


class _Calls:
    def __init__(self) -> None:
        self.seen: list[tuple[str, dict[str, Any]]] = []

    async def __call__(self, name: str, args: dict[str, Any]) -> Any:
        self.seen.append((name, args))
        return f"{name}:{args.get('path') or args.get('query')}"


def _ctx(calls: _Calls, **kw: Any) -> cc.ConnectorContext:
    return cc.ConnectorContext(
        prompt_text=PROMPT, callable_tools=callable_tools(PROMPT), call_tool=calls,
        governed=kw.pop("governed", _no_gate), scope="u1",
        mcp_servers=kw.pop("mcp_servers", {}), api_connectors=kw.pop("api_connectors", {}), **kw,
    )


def _run(src: str, ctx: cc.ConnectorContext, **limits: Any):
    return asyncio.run(run_code(
        src, ctx.call_tool, ctx.callable_tools, CodeModeLimits(**limits), namespaces=cc.build_namespaces(ctx),
    ))


# ── phase 3: discovery ─────────────────────────────────────────────────────


def test_catalogue_reads_signatures_and_continuations():
    cat = cc.tool_catalogue(PROMPT)
    assert cat["search_code"] == {"signature": "search_code(query, limit=20)", "description": "Grep the workspace for a pattern."}
    assert cat["read_file"]["description"] == ""


def test_tools_search_and_describe_only_cover_callable_tools():
    calls = _Calls()
    out = _run("result = [tools.search('grep pattern'), tools.describe('read_file')]", _ctx(calls))
    assert out.ok, out.error
    found, described = out.result
    assert found[0]["call"] == "tools.search_code(query, limit=20)"
    assert described["signature"] == "read_file(path)"
    assert calls.seen == []
    out = _run("tools.describe('edit_file')", _ctx(calls))
    assert not out.ok and "no callable tool" in out.error


def test_compact_prompt_replaces_catalogue_with_index():
    compact = cc.compact_prompt(PROMPT, list(callable_tools(PROMPT)))
    assert "search_code(query" not in compact and "for a pattern" not in compact
    assert "): head_file, read_file, search_code\n" in compact
    # Codex on #1818: everything that is not a read-only entry stays selectable.
    assert "- edit_file(path, old_string, new_string): Replace text" in compact
    assert compact.endswith("Return ONLY a JSON object\n")
    assert callable_tools(compact) == {}


def test_compact_real_prompt_keeps_write_github_and_code_mode_lines(monkeypatch):
    full = _tool_prompt()
    compact = cc.compact_prompt(full, list(callable_tools(full)))
    for kept in ("- github_comment_on_issue(", "- write_file(", "- run_command(", "- run_code(code)",
                 "tools.search('<need>') ranks tools", "- finish(reason)", "- save_snippet("):
        assert kept in compact, kept
    for dropped in ("- read_file(path)", "- search_code(query"):
        assert dropped not in compact
    assert len(compact) < len(full)


def test_compact_catalog_is_off_by_default_and_live(monkeypatch):
    from agent.loop import _compact_if_enabled

    assert get_control("AGENT_CODE_MODE_COMPACT_CATALOG").default == "false"
    assert _compact_if_enabled(PROMPT) == PROMPT
    monkeypatch.setattr(settings, "agent_code_mode_compact_catalog_raw", "true")
    assert "Read-only tools (arguments" in _compact_if_enabled(PROMPT)


# ── phase 4: MCP ───────────────────────────────────────────────────────────


def _server(log: list[Any]) -> cc.McpServer:
    tools = [
        {"name": "list_services", "description": "List services"},
        {"name": "get_logs", "description": "Read logs", "annotations": {"readOnlyHint": True, "destructiveHint": False}},
        {"name": "query_db", "description": "Run SQL", "annotations": {"readOnlyHint": True, "destructiveHint": False}},
        {"name": "get_danger", "description": "x", "annotations": {"destructiveHint": True}},
        {"name": "trigger_deploy", "description": "Deploy"},
    ]

    async def list_tools() -> list[dict[str, Any]]:
        return tools

    async def call(name: str, args: dict[str, Any]) -> Any:
        log.append((name, args))
        return {"line": "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789 ok", "n": 3}

    return cc.McpServer("render", list_tools, call)


def test_only_read_only_mcp_tools_are_callable_and_results_are_redacted():
    log: list[Any] = []
    gated: list[str] = []

    async def gate(label: str, args: dict[str, Any], thunk):
        gated.append(label)
        return await thunk()

    ctx = _ctx(_Calls(), mcp_servers={"render": _server(log)}, governed=gate)
    out = _run("result = [mcp.render.list_services(limit=2), mcp.render.query_db(sql='select 1')]", ctx)
    assert out.ok, out.error
    assert "ghp_" not in json.dumps(out.result)
    assert gated == ["mcp.render.list_tools", "mcp.render.list_services", "mcp.render.query_db"]
    for blocked in ("trigger_deploy", "get_danger", "nope"):
        bad = _run(f"mcp.render.{blocked}()", ctx)
        assert not bad.ok and "not a read-only tool" in bad.error
    assert [c[0] for c in log] == ["list_services", "query_db"]


def test_mcp_discovery_and_argument_rules():
    ctx = _ctx(_Calls(), mcp_servers={"render": _server([])})
    out = _run("result = [mcp.render.search('logs'), mcp.render.describe('get_logs')]", ctx)
    assert out.ok and out.result[0][0]["name"] == "get_logs" and out.result[1]["name"] == "get_logs"
    assert not _run("mcp.render.list_services('x')", ctx).ok
    assert "no MCP server" in _run("mcp.github.list_prs()", ctx).error
    assert not _run("mcp.render()", ctx).ok


def test_governance_denial_is_returned_not_raised():
    async def deny(label: str, args: dict[str, Any], thunk):
        return "[governance] deny: blocked (rule x)"

    log: list[Any] = []
    ctx = _ctx(_Calls(), mcp_servers={"render": _server(log)}, governed=deny)
    out = _run("result = mcp.render.list_services()", ctx)
    # Codex on #1818: even listing the server's tools is governed.
    assert not out.ok and "not allowed" in out.error and log == []


def test_governance_denial_of_a_call_is_returned_to_the_program():
    async def deny_calls(label: str, args: dict[str, Any], thunk):
        return await thunk() if label.endswith("list_tools") else "[governance] deny: blocked (rule x)"

    ctx = _ctx(_Calls(), mcp_servers={"render": _server([])}, governed=deny_calls)
    out = _run("result = mcp.render.list_services()", ctx)
    assert out.ok and out.result.startswith("[governance] deny")


def test_mcp_namespace_absent_when_switched_off(monkeypatch):
    monkeypatch.setattr(settings, "agent_code_mode_mcp_raw", "false")
    log: list[Any] = []
    out = _run("mcp.render.list_services()", _ctx(_Calls(), mcp_servers={"render": _server(log)}))
    assert not out.ok and out.calls == [] and log == []


# ── phase 4: OpenAPI ───────────────────────────────────────────────────────

DOC = {
    "paths": {
        "/pets": {"get": {"operationId": "listPets", "summary": "List pets",
                          "parameters": [{"name": "limit", "in": "query"}]},
                  "post": {"operationId": "createPet"}},
        "/pets/{petId}": {"parameters": [{"name": "petId", "in": "path", "required": True}],
                          "get": {"summary": "One pet"}},
    }
}


def _api(sent: list[Any]) -> dict[str, cc.OpenApiConnector]:
    spec = OpenApiConnectorSpec("pets", "Pets", "https://api.example.com/openapi.json", "https://api.example.com/v1")

    async def fetch(url: str) -> dict[str, Any]:
        return DOC

    async def send(url: str, query: dict[str, str], headers: dict[str, str]) -> Any:
        sent.append((url, query))
        return {"items": [{"id": 1, "note": "Bearer abcdefghijklmnopqrstuvwxyz"}]}

    return {"pets": cc.OpenApiConnector(spec, fetch, send)}


def test_openapi_indexes_get_operations_only():
    ops = cc.index_operations(DOC)
    assert set(ops) == {"listPets", "get_pets_petid"}
    assert ops["get_pets_petid"]["parameters"] == [{"name": "petId", "in": "path", "required": True}]


def test_openapi_search_describe_call():
    sent: list[Any] = []
    ctx = _ctx(_Calls(), api_connectors=_api(sent))
    out = _run(
        "result = [api.pets.search('pets'), api.pets.describe('listPets'),"
        " api.pets.call('listPets', limit=2), api.pets.call('get_pets_petid', petId='a/b')]",
        ctx,
    )
    assert out.ok, out.error
    assert sent == [("https://api.example.com/v1/pets", {"limit": "2"}), ("https://api.example.com/v1/pets/a%2Fb", {})]
    assert "abcdefghijklmnop" not in json.dumps(out.result)


@pytest.mark.parametrize(
    ("src", "msg"),
    [
        ("api.pets.call('createPet')", "no GET operation"),
        ("api.pets.call('listPets', evil=1)", "unknown parameter"),
        ("api.pets.call('get_pets_petid')", "missing required"),
        ("api.other.call('x')", "no API connector"),
        ("api.pets.delete('x')", "use api.<name>"),
    ],
)
def test_openapi_refusals(src, msg):
    out = _run(src, _ctx(_Calls(), api_connectors=_api([])))
    assert not out.ok and msg in out.error


@pytest.mark.parametrize(
    ("url", "host", "msg"),
    [
        ("http://127.0.0.1/admin", None, "refused URL"),
        ("https://169.254.169.254/latest", None, "refused URL"),
        ("https://evil.example.org/x", "api.example.com", "host differs"),
    ],
)
def test_guarded_get_refuses_unsafe_targets_before_any_request(url, host, msg):
    with pytest.raises(CodeModeError, match=msg):
        asyncio.run(cc._guarded_get(url, {}, {}, host))


def test_connector_config_parsing(tmp_path: Path, monkeypatch):
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "connectors:\n"
        "  - {name: good, spec_url: 'https://a.example.com/s.json', base_url: 'https://a.example.com/', auth_env: GOOD_TOKEN}\n"
        "  - {name: Bad, spec_url: 'https://a.example.com/s.json', base_url: 'https://a.example.com'}\n"
        "  - {name: plain, spec_url: 'http://a.example.com/s.json', base_url: 'https://a.example.com'}\n"
        "  - {name: envbad, spec_url: 'https://a.example.com/s', base_url: 'https://a.example.com', auth_env: 'x y'}\n"
    )
    specs = openapi_connectors(cfg, include_builtins=False)
    assert [s.name for s in specs] == ["good"] and specs[0].base_url == "https://a.example.com"
    monkeypatch.setenv("GOOD_TOKEN", "tok")
    assert connector_token(specs[0]) == "tok"
    assert openapi_connectors(tmp_path / "missing.yaml", include_builtins=False) == []


def test_shipped_config_declares_no_extra_connectors():
    assert openapi_connectors(include_builtins=False) == []


# ── hybrid catalogue: built-ins, inline operations, overrides ──────────────


def _no_tokens(monkeypatch):
    monkeypatch.setattr(settings, "gh_pat", "")
    monkeypatch.setattr(settings, "render_api_key", "")


def test_builtins_switch_on_with_their_credential(monkeypatch, tmp_path):
    empty = tmp_path / "e.yaml"
    empty.write_text("connectors: []\n")
    _no_tokens(monkeypatch)
    assert openapi_connectors(empty) == []
    monkeypatch.setattr(settings, "gh_pat", "gh-test")
    assert [s.name for s in openapi_connectors(empty)] == ["github"]
    monkeypatch.setattr(settings, "render_api_key", "rnd-test")
    specs = {s.name: s for s in openapi_connectors(empty)}
    assert set(specs) == {"github", "render"}
    assert connector_token(specs["render"]) == "rnd-test"


def test_user_runs_never_borrow_the_server_tokens(monkeypatch, tmp_path):
    """Same guard as workflow_orchestrator._resolve_push_token (Codex P1 on #1821)."""
    empty = tmp_path / "e.yaml"
    empty.write_text("connectors: []\n")
    monkeypatch.setattr(settings, "gh_pat", "gh-server")
    monkeypatch.setattr(settings, "render_api_key", "rnd-server")
    monkeypatch.delenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", raising=False)
    assert openapi_connectors(empty, user_id="alice") == []
    specs = {s.name: s for s in openapi_connectors(empty, user_id="alice", user_token=ALICE_GH)}
    assert set(specs) == {"github"}
    assert connector_token(specs["github"], user_id="alice", user_token=ALICE_GH) == "gh-alice"
    assert connector_token(specs["github"], user_id="alice") is None
    monkeypatch.setenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", "true")
    specs = {s.name: s for s in openapi_connectors(empty, user_id="alice")}
    assert connector_token(specs["github"], user_id="alice") == "gh-server" and "render" in specs


def test_server_token_handed_in_as_the_user_token_is_still_guarded(monkeypatch, tmp_path):
    """proxy.py builds user runners with github_token=GH_PAT (verifier FAIL on 8071992)."""
    empty = tmp_path / "e.yaml"
    empty.write_text("connectors: []\n")
    monkeypatch.setattr(settings, "gh_pat", "gh-server")
    monkeypatch.setattr(settings, "render_api_key", "")
    monkeypatch.delenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", raising=False)
    for name in ("GH_PAT", "GH_TOKEN", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    assert openapi_connectors(empty, user_id="alice", user_token=settings.gh_pat) == []
    monkeypatch.setenv("GITHUB_TOKEN", SERVER_ENV_GH)
    assert openapi_connectors(empty, user_id="alice", user_token=SERVER_ENV_GH) == []
    assert [s.name for s in openapi_connectors(empty, user_id=None, user_token=settings.gh_pat)] == ["github"]
    monkeypatch.setenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", "1")
    assert [s.name for s in openapi_connectors(empty, user_id="alice", user_token=SERVER_ENV_GH)] == ["github"]


def test_auth_env_and_github_override_keep_the_guard(monkeypatch, tmp_path):
    """Codex P1 on 1f14ac0: an `auth_env: GH_PAT` override must not hand user runs the server token."""
    _no_tokens(monkeypatch)
    monkeypatch.setenv("GH_PAT", SERVER_ENV_GH)
    monkeypatch.setenv("BILLING_KEY", "billing-server")
    monkeypatch.delenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", raising=False)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "connectors:\n"
        "  - name: github\n"
        "    base_url: 'https://api.github.com'\n"
        "    auth_env: GH_PAT\n"
        "    operations: {/meta: {get: {operationId: meta}}}\n"
        "  - name: billing\n"
        "    base_url: 'https://billing.example.com'\n"
        "    auth_env: BILLING_KEY\n"
        "    operations: {/invoices: {get: {operationId: invoices}}}\n"
        "  - name: public\n"
        "    base_url: 'https://public.example.com'\n"
        "    operations: {/x: {get: {operationId: x}}}\n"
    )
    assert [s.name for s in openapi_connectors(cfg, user_id="alice")] == ["public"]
    specs = {s.name: s for s in openapi_connectors(cfg, user_id="alice", user_token=ALICE_GH)}
    assert set(specs) == {"github", "public"}
    assert connector_token(specs["github"], user_id="alice", user_token=ALICE_GH) == ALICE_GH
    assert openapi_connectors(cfg, user_id="alice", user_token=SERVER_ENV_GH)[0].name == "public"
    system = {s.name: s for s in openapi_connectors(cfg)}
    assert set(system) == {"github", "billing", "public"}
    assert connector_token(system["billing"]) == "billing-server"
    monkeypatch.setenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", "on")
    assert len(openapi_connectors(cfg, user_id="alice")) == 3


def test_user_run_namespace_sends_the_users_token(monkeypatch, tmp_path):
    from packages.config import code_mode_connectors as cfg_mod

    empty = tmp_path / "e.yaml"
    empty.write_text("connectors: []\n")
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", empty)
    monkeypatch.setattr(settings, "gh_pat", "gh-server")
    monkeypatch.setattr(settings, "render_api_key", "rnd-server")
    monkeypatch.delenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", raising=False)
    sent: list[dict[str, str]] = []

    async def fake_get(url, query, headers, host, **_kw):
        sent.append(headers)
        return {"full_name": "o/r"}

    monkeypatch.setattr(cc, "_guarded_get", fake_get)
    apis = cc.openapi_connectors_from_config(user_id="alice", user_token=ALICE_GH)
    assert set(apis) == {"github"}
    asyncio.run(apis["github"].send("https://api.github.com/repos/o/r", {}, {}))
    assert sent[-1]["Authorization"] == "Bearer gh-alice"
    assert cc.openapi_connectors_from_config(user_id="bob") == {}


def test_inline_path_level_parameters_are_kept(monkeypatch, tmp_path):
    """Verifier note on #1822: a path-level parameter list was dropped, leaving the op uncallable."""
    _no_tokens(monkeypatch)
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "connectors:\n"
        "  - name: x\n"
        "    base_url: 'https://x.example.com'\n"
        "    operations:\n"
        "      /items/{item_id}:\n"
        "        parameters: [{name: item_id, in: path, required: true}]\n"
        "        get: {operationId: get-item, parameters: [{name: fields, in: query}]}\n"
    )
    (spec,) = openapi_connectors(cfg)
    ops = cc.index_operations({"paths": spec.operations})
    assert [p["name"] for p in ops["get-item"]["parameters"]] == ["item_id", "fields"]
    url, query = cc.build_url(spec.base_url, "/items/{item_id}", {"item_id": "7", "fields": "a"}, ops["get-item"])
    assert url == "https://x.example.com/items/7" and query == {"fields": "a"}
    assert cc.index_operations({"paths": {"/a": {"parameters": 5, "get": {"parameters": {"x": 1}}}}})["get_a"]["parameters"] == []


def test_operation_level_parameter_overrides_path_level():
    """Codex P2 on #1822: the GET-level declaration wins on the same (name, in)."""
    doc = {"paths": {"/s": {
        "parameters": [{"name": "q", "in": "query", "required": True}, {"name": "q", "in": "path", "required": True}],
        "get": {"operationId": "s", "parameters": [{"name": "q", "in": "query", "required": False}]},
    }}}
    params = cc.index_operations(doc)["s"]["parameters"]
    assert sorted((p["name"], p["in"], p["required"]) for p in params) == [("q", "path", True), ("q", "query", False)]
    from packages.config.code_mode_connectors import _valid_operations

    inline = _valid_operations(doc["paths"], "t")
    assert len(inline["/s"]["get"]["parameters"]) == 2


@pytest.mark.parametrize("body", [
    "- name: github\n", "connectors: 5\n", "connectors: {a: 1}\n", "just text\n",
    # Codex P2 on 11de54e: malformed inline operations inside an otherwise valid entry.
    "connectors:\n  - {name: x, base_url: 'https://x.example.com', operations: {/a: {get: {operationId: a, parameters: 5}}}}\n",
    "connectors:\n  - {name: x, base_url: 'https://x.example.com', operations: {/a: 5}}\n",
    "connectors:\n  - {name: x, base_url: 'https://x.example.com', operations: [1, 2]}\n",
    "connectors:\n  - 5\n  - null\n",
])
def test_malformed_connector_yaml_is_ignored_not_raised(monkeypatch, tmp_path, body):
    _no_tokens(monkeypatch)
    bad = tmp_path / "bad.yaml"
    bad.write_text(body)
    assert openapi_connectors(bad) == []


def test_config_can_disable_or_override_a_builtin(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "gh_pat", "gh-test")
    monkeypatch.setattr(settings, "render_api_key", "rnd-test")
    cfg = tmp_path / "c.yaml"
    cfg.write_text(
        "connectors:\n"
        "  - {name: render, enabled: false}\n"
        "  - name: github\n"
        "    base_url: 'https://ghe.example.com/api/v3'\n"
        "    auth_env: GHE_TOKEN\n"
        "    operations:\n"
        "      /meta: {get: {operationId: meta, summary: Meta}}\n"
    )
    specs = {s.name: s for s in openapi_connectors(cfg)}
    assert set(specs) == {"github"} and specs["github"].base_url == "https://ghe.example.com/api/v3"
    assert not specs["github"].builtin


def test_builtin_catalogue_is_get_only_and_has_no_secret_endpoints():
    from packages.config.code_mode_connectors import BUILTIN_CONNECTORS

    for spec in BUILTIN_CONNECTORS:
        ops = cc.index_operations({"paths": spec.operations})
        assert ops and all(set(item) == {"get"} for item in spec.operations.values())
        for op in ops.values():
            assert "env-var" not in op["path"] and "secret" not in op["path"]


def test_inline_operations_need_no_spec_fetch(monkeypatch):
    sent: list[Any] = []
    spec = OpenApiConnectorSpec(
        "render", "", "", "https://api.render.com/v1", token_setting=RENDER_SETTING,
        operations={"/services": {"get": {"operationId": "list-services", "parameters": [{"name": "limit", "in": "query"}]}}},
        headers=(("Accept", "application/json"),),
    )

    async def fetch(url: str) -> dict[str, Any]:
        raise AssertionError("inline operations must not fetch a spec")

    async def send(url, query, headers):
        sent.append((url, query))
        return [{"service": {"id": "srv-1", "name": "web"}}]

    gated: list[str] = []

    async def gate(label, args, thunk):
        gated.append(label)
        return await thunk()

    ctx = _ctx(_Calls(), api_connectors={"render": cc.OpenApiConnector(spec, fetch, send)}, governed=gate)
    out = _run("result = [s['service']['name'] for s in api.render.call('list-services', limit=5)]", ctx)
    assert out.ok, out.error
    assert out.result == ["web"] and sent == [("https://api.render.com/v1/services", {"limit": "5"})]
    assert gated == ["api.render.list-services"]


def test_unified_search_spans_tools_mcp_and_apis():
    sent: list[Any] = []
    ctx = _ctx(_Calls(), mcp_servers={"render": _server([])}, api_connectors=_api(sent))
    out = _run("result = [hit['call'] for hit in tools.search('list pets services logs')]", ctx)
    assert out.ok, out.error
    calls = out.result
    assert any(c.startswith("api.pets.call('listPets'") for c in calls)
    assert any(c.startswith("mcp.render.list_services") for c in calls)
    assert all(not c.startswith("mcp.render.trigger_deploy") for c in calls)


def test_unified_search_survives_an_unreachable_source():
    async def deny_all(label, args, thunk):
        return "[governance] deny: no (rule x)"

    ctx = _ctx(_Calls(), mcp_servers={"render": _server([])}, api_connectors=_api([]), governed=deny_all)
    out = _run("result = [hit['call'] for hit in tools.search('grep pattern')]", ctx)
    assert out.ok and out.result[0].startswith("tools.search_code")


def test_unified_search_survives_a_source_raising_a_network_error():
    async def network_down(label, args, thunk):
        raise ConnectionError("unreachable")

    ctx = _ctx(_Calls(), mcp_servers={"render": _server([])}, api_connectors=_api([]), governed=network_down)
    out = _run("result = [hit['call'] for hit in tools.search('grep pattern')]", ctx)
    assert out.ok, out.error
    assert out.result[0].startswith("tools.search_code")


@pytest.mark.parametrize("bad", ["..", ".", "", "%2e%2e", "a%2Fb"])
def test_path_parameters_cannot_escape_the_declared_operation(bad):
    op = {"parameters": [{"name": "owner", "in": "path", "required": True}, {"name": "repo", "in": "path", "required": True}]}
    with pytest.raises(CodeModeError, match="dot segment"):
        cc.build_url("https://api.github.com", "/repos/{owner}/{repo}", {"owner": bad, "repo": "user"}, op)
    url, _ = cc.build_url("https://api.github.com", "/repos/{owner}/{repo}", {"owner": "a.b", "repo": "c..d"}, op)
    assert url == "https://api.github.com/repos/a.b/c..d"


def test_spec_fetch_refuses_oversize_instead_of_truncating(monkeypatch):
    class FakeResp:
        status_code = 200
        is_redirect = False

        async def aiter_text(self):
            for _ in range(10):
                yield "x" * 1000

    out = asyncio.run(cc._read_capped(FakeResp(), 2500))
    assert out == ("x" * 2500, True)
    assert asyncio.run(cc._read_capped(FakeResp(), 20_000)) == ("x" * 10_000, False)


# ── phase 5: snippets ──────────────────────────────────────────────────────


def test_snippet_save_validation():
    store = sn.get_snippet_store()
    assert "name must be" in store.save("u1", "Bad Name", "x = 1", "")
    assert "valid run_code program" in store.save("u1", "ok_name", "import os", "")
    assert "at most" in store.save("u1", "big", "x = 1\n" * 1000, "")
    assert store.save("u1", "ok_name", "result = args['p']", "echo") is None
    assert store.list("u1") == [{"name": "ok_name", "description": "echo"}]
    assert store.list("u2") == []


def test_snippet_runs_with_args_and_shares_the_call_budget():
    store = sn.get_snippet_store()
    store.save("u1", "two_reads", "result = [tools.read_file(path=p) for p in args['paths']]", "")
    calls = _Calls()
    out = _run("result = snippets.run('two_reads', paths=['a', 'b'])", _ctx(calls))
    assert out.ok, out.error
    assert out.result == ["read_file:a", "read_file:b"]
    assert out.calls == ["snippets.run", "snippet:read_file", "snippet:read_file"]
    out = _run("result = snippets.run('two_reads', paths=['a', 'b', 'c'])", _ctx(_Calls()), max_tool_calls=3)
    assert not out.ok and "more than" in out.error


def test_snippet_cannot_run_a_snippet_and_unknown_is_reported():
    store = sn.get_snippet_store()
    store.save("u1", "inner", "result = 1", "")
    store.save("u1", "outer", "result = snippets.run('inner')", "")
    out = _run("snippets.run('outer')", _ctx(_Calls()))
    assert not out.ok and "cannot run another snippet" in out.error
    assert "no saved snippet" in _run("snippets.run('ghost')", _ctx(_Calls())).error


def test_snippets_scoped_per_user():
    sn.get_snippet_store().save("someone-else", "theirs", "result = 1", "")
    assert "no saved snippet" in _run("snippets.run('theirs')", _ctx(_Calls())).error


def test_save_snippet_tool_on_runner(monkeypatch):
    from agent.loop import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    ok = asyncio.run(runner._save_snippet({"name": "x_y", "code": "result = 2"}, "u9"))
    assert "saved snippet" in ok and sn.get_snippet_store().get("u9", "x_y") is not None
    bad = asyncio.run(runner._save_snippet({"name": "x", "code": "def f(): pass"}, "u9"))
    assert "refused" in bad
    monkeypatch.setattr(settings, "agent_code_mode_snippets_raw", "false")
    assert "switched off" in asyncio.run(runner._save_snippet({"name": "z", "code": "result = 1"}, "u9"))


# ── prompt + controls ──────────────────────────────────────────────────────


def _tool_prompt() -> str:
    return prompts.build_tool_prompt(goal="g", step={"description": "s"}, observations=[], remaining_calls=3)[0]["content"]


def test_prompt_advertises_enabled_namespaces_only(monkeypatch):
    text = _tool_prompt()
    assert "tools.search(" in text and "snippets.run(" in text and "- save_snippet(" in text
    assert "**" not in text.split("CODE MODE")[1].split("GITHUB API")[0]
    monkeypatch.setattr(settings, "agent_code_mode_snippets_raw", "false")
    text = _tool_prompt()
    assert "snippets.run(" not in text and "save_snippet" not in text
    assert "save_snippet" not in callable_tools(text)


def test_prompt_lists_only_the_apis_this_run_can_call(monkeypatch, tmp_path):
    """Codex P2 on 06ce1f3: a user run must not be told about system-only connectors."""
    from packages.config import code_mode_connectors as cfg_mod

    empty = tmp_path / "e.yaml"
    empty.write_text("connectors: []\n")
    monkeypatch.setattr(cfg_mod, "CONFIG_PATH", empty)
    monkeypatch.setattr(settings, "gh_pat", "gh-server")
    monkeypatch.setattr(settings, "render_api_key", "rnd-server")
    monkeypatch.delenv("ORCHESTRATOR_ALLOW_SERVER_TOKEN_FOR_USER_RUNS", raising=False)

    def prompt(api_user):
        return prompts.build_tool_prompt(
            goal="g", step={"description": "s"}, observations=[], remaining_calls=3, api_user=api_user,
        )[0]["content"]

    assert "APIs: github, render." in prompt(None)
    assert "APIs (GET only)" not in prompt(("alice", None))
    assert "APIs: github." in prompt(("alice", ALICE_GH))


@pytest.mark.parametrize(
    ("key", "default"),
    [
        ("AGENT_CODE_MODE_COMPACT_CATALOG", "false"),
        ("AGENT_CODE_MODE_MCP_ENABLED", "true"),
        ("AGENT_CODE_MODE_OPENAPI_ENABLED", "true"),
        ("AGENT_CODE_MODE_SNIPPETS_ENABLED", "true"),
        ("CODE_MODE_MCP_SERVER_ENABLED", "true"),
    ],
)
def test_controls_are_live_with_expected_defaults(key, default):
    control = get_control(key)
    assert control is not None and control.live is True and control.default == default


def test_runner_run_code_uses_namespaces(monkeypatch):
    from agent.loop import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)
    runner._log_event = lambda *a, **k: None  # type: ignore[method-assign]

    async def fake_run_tool(tool, args, user_id=None, memory_store=None):
        return f"{tool}:{args.get('path')}"

    runner._run_tool = fake_run_tool  # type: ignore[method-assign]
    text = asyncio.run(runner._run_code_mode(
        {"code": "result = [tools.describe('read_file')['signature'], tools.read_file('a')]"}, PROMPT,
    ))
    assert json.loads(text)["result"] == ["read_file(path)", "read_file:a"]


def test_governed_external_passes_through_when_governance_off(monkeypatch):
    from agent.loop import AgentRunner

    monkeypatch.setattr("packages.governance.enforcement.governance_enabled", lambda: False)
    runner = AgentRunner.__new__(AgentRunner)

    async def thunk():
        return 42

    assert asyncio.run(runner._governed_external("mcp.render.list_services", {}, thunk)) == 42


# ── Codex review on #1818 ──────────────────────────────────────────────────


def test_api_spec_fetch_is_governed():
    labels: list[tuple[str, dict[str, Any]]] = []

    async def gate(label: str, args: dict[str, Any], thunk):
        labels.append((label, args))
        return "[governance] deny: no (rule net)" if label.endswith(".spec") else await thunk()

    out = _run("api.pets.search('pets')", _ctx(_Calls(), api_connectors=_api([]), governed=gate))
    assert not out.ok and "not allowed" in out.error
    assert labels == [("api.pets.spec", {"url": "https://api.example.com/openapi.json"})]


def test_connector_calls_are_classified_for_governance():
    from packages.governance.policy import Surface

    assert cc.governance_surface("api.pets.listPets", {"url": "https://API.example.com/v1/pets"}) == (Surface.NETWORK, "api.example.com")
    assert cc.governance_surface("mcp.render.list_services", {}) == (Surface.MCP, "mcp.render.list_services")
    assert cc.governance_surface("save_snippet", {}) is None


def test_runner_passes_network_surface_to_the_gate(monkeypatch):
    from agent.loop import AgentRunner
    from packages.governance.policy import Surface

    seen: dict[str, Any] = {}

    class FakeGate:
        async def guard(self, identity, tool, args, *, surface=None, action=None, **kw):
            seen.update(tool=tool, surface=surface, action=action)

            class R:
                allowed = False
                denial_message = "[governance] deny: host (rule net)"
            return R()

    monkeypatch.setattr("packages.governance.enforcement.governance_enabled", lambda: True)
    monkeypatch.setattr("packages.governance.enforcement.get_gate", lambda: FakeGate())
    monkeypatch.setattr("packages.governance.enforcement.resolve_identity_for_runner", lambda *a, **k: "id")
    runner = AgentRunner.__new__(AgentRunner)

    async def thunk():
        raise AssertionError("must not run when denied")

    out = asyncio.run(runner._governed_external("api.pets.listPets", {"url": "https://api.example.com/x"}, thunk))
    assert out.startswith("[governance] deny")
    assert seen == {"tool": "api.pets.listPets", "surface": Surface.NETWORK, "action": "api.example.com"}


def test_save_snippet_goes_through_governance(monkeypatch):
    from agent.loop import AgentRunner

    runner = AgentRunner.__new__(AgentRunner)

    async def deny(label, args, thunk):
        assert label == "save_snippet"
        return "[governance] deny: no snippets (rule s)"

    runner._governed_external = deny  # type: ignore[method-assign]
    out = asyncio.run(runner._save_snippet({"name": "x_y", "code": "result = 1"}, "u7"))
    assert out.startswith("[governance] deny")
    assert sn.get_snippet_store().get("u7", "x_y") is None


def test_program_source_is_bounded_before_parsing():
    out = asyncio.run(run_code("x = 1\n" * 5000, _Calls(), {}))
    assert not out.ok and "longer than" in out.error


def test_query_param_named_url_cannot_change_the_governed_host():
    doc = {"paths": {"/fetch": {"get": {"operationId": "fetchIt", "parameters": [{"name": "url", "in": "query"}]}}}}
    spec = OpenApiConnectorSpec("svc", "", "https://api.example.com/o.json", "https://api.example.com")
    seen: list[dict[str, Any]] = []

    async def fetch(url: str) -> dict[str, Any]:
        return doc

    async def send(url: str, query: dict[str, str], headers: dict[str, str]) -> Any:
        return {"ok": True}

    async def gate(label: str, args: dict[str, Any], thunk):
        seen.append(args)
        return await thunk()

    ctx = _ctx(_Calls(), api_connectors={"svc": cc.OpenApiConnector(spec, fetch, send)}, governed=gate)
    out = _run("result = api.svc.call('fetchIt', url='https://allowed.example.org/')", ctx)
    assert out.ok, out.error
    call_args = seen[-1]
    assert call_args["url"] == "https://api.example.com/fetch"
    assert cc.governance_surface("api.svc.fetchIt", call_args)[1] == "api.example.com"


def test_same_name_in_path_and_query_fills_both():
    """Verifier note on #1822: a name declared in both locations lost its path slot."""
    op = {"parameters": [
        {"name": "q", "in": "path", "required": True}, {"name": "q", "in": "query", "required": False},
    ]}
    assert cc.build_url("https://x.example.com", "/s/{q}", {"q": "v"}, op) == ("https://x.example.com/s/v", {"q": "v"})
    with pytest.raises(CodeModeError, match="missing required"):
        cc.build_url("https://x.example.com", "/s/{q}", {}, op)
