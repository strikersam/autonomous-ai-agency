# Code Mode for the agency — plan

Source: Cloudflare `@cloudflare/codemode` (npm 0.5.5, MIT, experimental), the
"Code Mode" posts (blog.cloudflare.com/code-mode, /code-mode-mcp) and the Agents docs
(developers.cloudflare.com/agents/tools/codemode). Anthropic published the same idea as
"code execution with MCP".

## What Code Mode is

1. **One code tool instead of N tools.** The model writes a small program against a typed
   API (`codemode.getWeather(...)`) instead of emitting one JSON tool call per turn.
2. **Intermediate results stay out of the context.** Only the program's return value goes
   back to the model; the 50 KB file it grepped never enters the prompt.
3. **Progressive discovery.** `codemode.search(query)` / `describe(path)` return ranked tool
   paths and focused type definitions on demand. The Cloudflare API MCP server covers
   ~2,500 endpoints with two tools (`search`, `execute`) in ~1,000 tokens, against an
   estimated 1.17 M tokens for one-tool-per-endpoint (Cloudflare's own tiktoken figure).
4. **Connectors.** MCP servers, OpenAPI specs and plain functions become namespaces
   (`github.list_pull_requests()`); credentials stay host-side, and the sandbox only gets an
   RPC stub.
5. **Host-side policy on every call.** Approval (`requiresApproval`), logging, replay
   (`codemode.step`) and saved snippets (`codemode.run`) are applied where the call crosses
   the sandbox boundary.

## Why it fits this repo

`AgentRunner._execute_step` (`agent/loop.py`) runs up to 15 sequential tool-selection
LLM calls per step. Each call resends the full tool catalogue from `build_tool_prompt()`
(80 lines, ~4,600 characters with the default controls) and the masked observation list. On free models at 5–160 s per call, that loop
is what pushed steps past the task timeout. Code Mode cuts round trips and prompt size at
the same point.

The sandbox is the hard part. Cloudflare uses V8 isolates; this backend is Python on a
512 MB Render instance, and `exec` with stripped builtins is not a security boundary.
Phase 1 therefore **interprets** an AST subset and never executes code.

## Phases

| # | Scope | Status |
|---|-------|--------|
| 1 | `run_code(code)` in the executor tool loop: AST-walking interpreter for a Python subset (`agent/code_mode.py`), read-only tools only, tools limited to what the prompt advertises, each inner call through `_run_tool` (governance + audit), hard limits, live control `AGENT_CODE_MODE_ENABLED` (default on, at the operator's request; phase 2 measures whether it pays off). | **Shipped in this change** |
| 2 | **Measure before turning it on.** Log per-step prompt tokens, LLM calls and wall time with the control on and off (the `code_mode` event already records calls and errors), run both on the same task set, and record the parse-failure rate of open-weights executors (Nemotron) writing code inside a JSON string. Shipped as a live A/B: a stable-hash holdout (`AGENT_CODE_MODE_HOLDOUT_PERCENT`, default 10) runs without `run_code`, and `GET /api/admin/agent/code-mode/metrics` compares the arms. Code Mode stays on only if the verdict says it cuts calls without losing step success. | **Instrumented — collecting live data** |
| 3 | **Progressive discovery.** `tools.search(query)` / `tools.describe(name)` inside `run_code`, over the tools the prompt offers. `AGENT_CODE_MODE_COMPACT_CATALOG` (default off) swaps the full catalogue for a one-line index. | **Shipped** |
| 4 | **Connectors across systems.** `mcp.<server>.<tool>` for configured MCP servers (read-only tools only), `api.<name>.search/describe/call` for OpenAPI connectors in `config/code_mode_openapi.yaml` (GET only, SSRF-checked, token host-side). Governed and redacted. | **Shipped** |
| 5 | **Saved snippets.** `save_snippet` + `snippets.run(name, key=value)`, per user, validated, replayed with the caller's remaining budget. | **Shipped** |
| 6 | **Write tools from programs.** Not built: the session's safety policy refused letting model-written programs make writes. Programs stay read-only; writes stay one direct call at a time. | Not built — needs an explicit decision |
| 7 | **The agency as a Code Mode MCP server.** `POST /api/code-mode/mcp`: `search` + `execute` over the agency API, GET only, with the caller's own permissions. | **Shipped** |

## Phase 1 security model

- Never `exec`/`eval`/`compile`: `ast.parse` then a tree walk over an allow-list of node types.
- Rejected before anything runs: `import`, `def`, `lambda`, `class`, `while`, `with`,
  `try`, `**` unpacking, `%` string formatting, `str.format`, and any name, attribute or
  keyword starting with `_`.
- Attributes only as method calls on `str`/`list`/`dict`/`tuple`/`set`, from a fixed list.
- Limits: 20 tool calls, 50 000 steps, 200 000-element sequences, 4 096-bit integers,
  `range` ≤ 10 000, format width ≤ 1 000, 90 s wall time, 6 000-char result (the rest
  offloaded to `tool_output_store`).
- Tool reach = `READ_ONLY_TOOLS` ∩ the tools the current prompt advertises, so a control
  that hides a tool (web reach, code graph) also hides it from `run_code`.

## Open questions

- Does a 120B open-weights executor write valid programs inside a JSON string often
  enough? Phase 2 measures this; it is not assumed.
- A "Code Mode" response format (code block instead of JSON) would remove the escaping
  problem but touches `_chat_json` and every executor prompt, so it waits for phase 2 data.
