# CLAUDE.md — agent/

> **RISKY MODULE.** This package orchestrates multi-step AI task execution and writes
> files to the filesystem.
>
> The invariants you must not break are `CLAUDE.md` rules 16–20; the SSRF boundary is
> rule 14; `agent/tools.py` and `agent/web_reach.py` are both gated by rule 15. Read
> those first. This file covers what the package *is* and how to extend it.

---

## What this package does

The three-role orchestration loop:

```
Planner   → produces an AgentPlan with ordered steps
Executor  → applies file changes per step
Verifier  → validates each change before it is written
```

`AgentRunner.run()` in `loop.py` drives the cycle. `RepowiseIntelligence` in
`repowise.py` provides codebase understanding. `WorkspaceTools` in `tools.py` is the
only place that writes to the filesystem.

Per-role models come from `AGENT_PLANNER_MODEL`, `AGENT_EXECUTOR_MODEL`,
`AGENT_VERIFIER_MODEL`, and `AGENT_JUDGE_MODEL`, all defaulting to
`nvidia/llama-3.3-nemotron-super-49b-v1`. Override in `.env` to test without large
models.

---

## Security surface

**`tools.py` → `apply_diff()`** writes arbitrary content to disk. It resolves paths but
does not enforce a strict root boundary by default — any change to path handling must
keep resolved paths inside `self.root`, and must never take a raw path from untrusted
input.

**`loop.py` → `_local_safety_check()`** scans generated code for hardcoded secrets (JWT
secret keys, fake user DBs). Add new risky patterns here — OS command injection, `eval`
— as you find them. The verifier LLM is best-effort and is not a security layer on its
own.

**`loop.py` → `_commit_step()`** auto-commits when `auto_commit=True`. Never pass an
unsanitised step description as a commit message.

---

## Adding a new tool

Two supported paths. Pick one.

**A. Hardcoded dispatch** — for filesystem or container operations that need `self._mcp`
routing or other `AgentRunner` state (see `read_file`, `write_file`, `run_command`):

1. Implement the operation in `tools.py`.
2. Add a dispatch case in `_dispatch_tool()` — it is checked after the tool registry.
3. Document the tool in `agent/models.py` (`ToolCall` schema).
4. Add tests in `tests/test_agent_tools.py`, or `tests/test_repowise_intelligence.py`
   for intelligence tools.

**B. Capability registry** — for self-contained capabilities with no `AgentRunner` state
dependency (see `web_reach.py`'s `fetch_url` / `web_search`):

1. Implement it as its own module, with its own tests. Fail soft — never raise; return a
   result dict the model can read.
2. Register it with `registry.agent_tool(...)` from a `_register_*_tools()` function
   called by `_register_builtin_tools()` in `capability_registry.py`. `_dispatch_tool()`
   already checks the registry first, so no dispatch-chain edit is needed.
3. Add it to `build_tool_prompt()` in `prompts.py` — **rule 19**. Registration alone is
   silent.
4. Test the module directly, plus one test asserting the registry exposes it (see
   `tests/test_web_reach.py`).

Any tool accepting a URL, path, or other externally-influenced target needs its
SSRF/traversal guard before the first network or filesystem call — `unsafe_target_reason()`
in `web_reach.py` is the pattern. That is rule 14, and it is not optional.

---

## Testing

| File | Covers |
|------|--------|
| `tests/test_agent_runner.py` | `AgentRunner` integration, via mocks and monkeypatching |
| `tests/test_agent_tools.py` | `WorkspaceTools` units |
| `tests/test_web_reach.py` | Web Reach capabilities and registry exposure |

```bash
pytest -x tests/test_agent_runner.py tests/test_agent_tools.py
```

---

## Skills worth invoking here

`risky-module-review` (required by rule 15 for `tools.py` and `web_reach.py`),
`test-first-executor`, `implementation-planner`.
