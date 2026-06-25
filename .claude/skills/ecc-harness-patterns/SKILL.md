# ECC Harness Patterns Skill

**Inspired by:** [ECC](https://github.com/affaan-m/ECC) — the definitive cross-harness agent orchestration system

**Purpose:** Integrate multi-harness patterns from ECC into local-llm-server's agent orchestration layer.

## What's Unique About ECC

ECC is a production-grade system supporting 7+ agent harnesses (Claude Code, Cursor, Codex, OpenCode, Gemini, Zed, GitHub Copilot) with:
- **Harness abstraction layer** — normalize API differences
- **Hook lifecycle** — session start/pause/stop/resume
- **Memory persistence** — skills learned across sessions
- **Cross-harness routing** — intelligent model/capability selection
- **182K+ stars** — battle-tested in real workflows

## Patterns to Adopt

### 1. Harness Detection & Adaptation
```python
# agents/harness_adapter.py
class HarnessAdapter:
    HARNESSES = {
        "claude_code": {"context_key": "workspace", "supports": ["streaming"]},
        "cursor": {"context_key": "editor", "supports": ["streaming", "streaming_chunks"]},
        "codex": {"context_key": "project", "supports": ["completion"]},
    }
    
    def normalize_request(self, harness_id: str, request: dict) -> dict:
        """Convert harness-native request to local-llm-server format"""
```

### 2. Session Lifecycle Hooks
ECC's `/hooks/session-*` pattern applied to local-llm-server:

```
.claude/hooks/
  ├── session-start/
  │   ├── 10-detect-harness.sh       # Identify active harness
  │   ├── 20-load-harness-prefs.sh   # Load harness-specific settings
  │   └── 30-emit-telemetry.sh       # Send harness telemetry
  ├── session-pause/
  │   └── 10-checkpoint-state.sh
  └── session-stop/
      └── 10-summarize-session.sh
```

### 3. Cross-Harness Model Selection
Extend `router/model_router.py` to consider harness capabilities:

```python
class CrossHarnessRouter(ModelRouter):
    def select_model(self, task: TaskRequest, harness: str) -> str:
        """Route considering harness limits and preferences"""
        # Claude Code + reasoning task → deepseek-r1 (powerful)
        # Cursor + quick fix → qwen3-coder (fast)
        # Codex + completion → fastest available
```

### 4. Persistent Harness Registry
Track which harnesses are active and their performance:

```yaml
# .claude/state/harness-registry.json
{
  "active_harnesses": ["claude_code", "cursor"],
  "session_history": [
    {
      "harness": "claude_code",
      "session_id": "sess_123",
      "model": "deepseek-r1:32b",
      "duration_sec": 1847,
      "tasks_completed": 12,
      "success_rate": 0.92
    }
  ]
}
```

## Implementation Plan

1. **Create `agents/harness_adapter.py`** — adapter pattern for harness differences
2. **Extend `.claude/hooks/`** — add session lifecycle management
3. **Update `router/model_router.py`** — add cross-harness routing logic
4. **Create `services/harness_registry.py`** — track active harnesses and performance
5. **Update `backend/server.py`** — emit harness metadata in responses
6. **Add tests** — `tests/test_harness_adapter.py`, `tests/test_cross_harness_router.py`

## Files to Create/Modify

- ✅ `.claude/skills/ecc-harness-patterns/SKILL.md` (this file)
- `agents/harness_adapter.py` (new)
- `services/harness_registry.py` (new)
- `.claude/hooks/session-start/10-detect-harness.sh` (new)
- `router/model_router.py` (extend)
- `docs/architecture/cross-harness-support.md` (new)

## References

- **ECC GitHub:** https://github.com/affaan-m/ECC
- **ECC Cross-Harness Docs:** https://github.com/affaan-m/ECC/blob/main/docs/architecture/cross-harness.md
- **Local-llm-server Agent Orchestration:** `docs/architecture/agent-orchestration.md`
- **Local-llm-server Router:** `docs/adrs/002-model-routing.md`
