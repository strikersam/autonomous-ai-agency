# Refactoring & Improvement Review Framework
**Target System:** Autonomous AI Agency Framework
**Repository:** `strikersam/autonomous-ai-agency` (`local-llm-server`)

---

## 1. PR Analysis Summary & Evaluation Rubric

### Evaluation Rubric

| Dimension | Check | Red Flags Specific to Agent Repos |
|---|---|---|
| **Safety** | Does it widen the agent's blast radius? | New tools without schema validation, timeouts, or permission class; removal of human-approval gates; raised spend thresholds |
| **Necessity** | Solves a real problem vs. gold-plating? | "Refactor" PRs touching the agent loop with no behavioral test coverage |
| **Architecture Fit** | Consistent with (or improving) the core loop? | Bypassing the tool registry with direct API calls; a second, parallel state-management path |
| **Behavioral Tests** | Prompt changes are behavior changes | PRs editing prompt strings with zero eval/behavior tests — the #1 merge hazard in agent repos |
| **Type Safety** | Typed signatures, no `Any` in executor path | `def run(*args, **kwargs)` on tool functions |
| **Secrets** | No credentials in diff | Keys pasted into config files or test fixtures |
| **Concurrency** | Async correctness | `asyncio.create_task` without a stored reference; `gather(return_exceptions=True)` with the result list ignored |

---

### Applying the rubric to open PRs

Per-PR verdicts are produced on demand against the live PR set, not frozen in
this document — a dated triage table is stale the moment it merges and its
"verified" claims cannot be trusted once the PRs move. To score the current
open PRs, run the rubric above over `git log`/the open-PR list and record the
result wherever that review lives (the PR thread, an issue), not here. This
document is the durable *method*; the verdicts are the perishable *output*.

---

## 2. Critical Bugs & Exact Detection Signatures

### 🔴 CRITICAL — Silent Error Propagation in Agent Loop & Tool Dispatch

**Greppable Detection Signatures:**
```bash
grep -rn "except Exception:\s*pass\|except:\s*pass" agent/ packages/
grep -rn "return_exceptions=True" agent/ services/
grep -rn "logging.debug.*error\|logger.debug.*fail" agent/
```

**Location in Codebase:**
- `agent/loop.py`: Tool outputs returning string error messages `[tool error: ...]`.
- `agent/context_manager.py`: Observation truncation masking list/dict outputs (`[dict keys=... - masked]`).

**Drop-in Fix Pattern:**
```python
from dataclasses import dataclass

@dataclass(frozen=True)
class ToolResult:
    ok: bool
    output: dict | str | None
    error: str | None
    retryable: bool
    idempotency_key: str | None = None

    def to_model_observation(self) -> str:
        if self.ok:
            return f"SUCCESS:\n{self.output}"
        return f"TOOL_ERROR (retryable={self.retryable}):\n{self.error}"
```

---

### 🔴 CRITICAL — Unsandboxed Tool Execution & SSRF Vulnerabilities

**Greppable Detection Signatures:**
```bash
grep -rn "_safe_path\|unsafe_target_reason" agent/
grep -rn "subprocess.run\|exec(\|eval(" agent/
```

**Location in Codebase:**
- `agent/tools.py`: `_safe_path()` uses `os.path.realpath` prefix checks (`target.startswith(root + os.sep)`).
- `agent/web_reach.py`: `unsafe_target_reason()` validates initial target IP addresses via `ipaddress.ip_address()`.

**Drop-in Fix Pattern (`agent/web_reach.py`):**
```python
def _safe_get_strict(self, url: str, max_redirects: int = 5) -> httpx.Response:
    current = url
    with httpx.Client(timeout=self.timeout, follow_redirects=False) as client:
        for _ in range(max_redirects + 1):
            reason = unsafe_target_reason(current)
            if reason:
                raise ValueError(f"SSRF Guard Blocked Hop ({current}): {reason}")
            resp = client.get(current, headers={"User-Agent": _UA})
            if resp.is_redirect:
                current = resp.headers.get("location")
                continue
            resp.raise_for_status()
            return resp
    raise ValueError("Too many redirects")
```

---

### 🔴 CRITICAL — Unhandled Rate Limits & State Checkpointing

**Greppable Detection Signatures:**
```bash
grep -rn "checkpoint_agent_state" agent/
grep -rn "TokenBudget" agent/
```

**Drop-in Fix Pattern (`agent/token_budget.py`):**
```python
from aiolimiter import AsyncLimiter
from tenacity import AsyncRetrying, stop_after_attempt, retry_if_exception_type, wait_exponential

llm_gate = AsyncLimiter(max_rate=40, time_period=60)

async def call_llm_with_rate_limit(client, payload):
    async with llm_gate:
        async for attempt in AsyncRetrying(
            stop=stop_after_attempt(5),
            wait=wait_exponential(multiplier=1.5, min=2, max=60),
            retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.TimeoutException)),
            reraise=True,
        ):
            with attempt:
                return await client.post(...)
```

---

## 3. Architectural Refactoring Architecture

```
                     ┌───────────────────────────────────────────────┐
                     │           User / API / Telegram               │
                     └──────────────────────┬────────────────────────┘
                                            │
                                            ▼
                     ┌───────────────────────────────────────────────┐
                     │    services/workflow_orchestrator.py          │
                     │         (Golden Path Execution)               │
                     └──────────────────────┬────────────────────────┘
                                            │
           ┌────────────────────────────────┼────────────────────────────────┐
           ▼                                ▼                                ▼
┌──────────────────────┐        ┌──────────────────────┐         ┌──────────────────────┐
│  agent/user_memory.py│        │agent/procedural_mem. │         │ agent/checkpoint.py  │
│   (Semantic Memory)  │        │ (Skill / Procedural) │         │   (Event Sourcing)   │
└──────────────────────┘        └──────────────────────┘         └──────────────────────┘
```

### Golden Path Orchestration
All agent execution is routed through `services/workflow_orchestrator.py` enforcing the 11-phase Golden Path:
`CLASSIFY` → `PLAN` → `SELECT_SPECIALIST` → `PREFLIGHT` → `BIND_CONTEXT` → `EXECUTE` → `VERIFY` → `JUDGE` → `SUMMARIZE` → `PERSIST` → `MONITOR`.
