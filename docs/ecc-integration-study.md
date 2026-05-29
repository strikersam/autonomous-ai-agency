# ECC Integration Study - local-llm-server

**Date**: May 29, 2026  
**Reference**: Issue #266, #230 (ECC - https://github.com/affaan-m/ECC)

## Executive Summary

ECC (Evolutionary Computation for AI) is a production-grade "harness-native operator system" for multi-agent work. It provides:
- Cross-harness agent configuration (Claude Code, Cursor, Continue, Codex, Zed, GitHub Copilot)
- 63+ agents, 249+ skills, 79 command shims
- Memory persistence, continuous learning, security scanning
- Operator workflows for specialized domains (brand voice, customer ops, prediction markets)

**Relevance**: local-llm-server can adopt ECC's architectural patterns for multi-agent orchestration without full reimplementation.

---

## ECC Architecture - Key Patterns

### 1. **Cross-Harness Abstraction Layer**
ECC supports multiple AI "harnesses" (Claude Code, Cursor, Continue, etc.) through:
- Normalized agent models across harnesses
- Platform-specific adapters (Cursor vs Claude Code vs Continue)
- Unified skill registry usable by any harness

**local-llm-server pattern**: Already abstracts OpenAI-compatible endpoints. Can extend to expose standardized agent interfaces.

### 2. **Skill-Based Capability Composition**
Skills in ECC are:
- Reusable prompt templates with parameter slots
- Stateless, composable units
- Versioned in the repo, referenced by agents

**local-llm-server adoption**: Formalize `.claude/skills/` as a first-class registry with metadata (name, version, inputs, outputs, dependencies).

### 3. **Agent State Persistence & Continuation**
ECC provides:
- Session checkpoints (plan, execution, verification steps)
- Automatic state snapshots for resume capability
- Context packing to persist learnings

**local-llm-server adoption**: Enhance `agent/state.py` with structured checkpointing (already partially done). Add export/import for session portability.

### 4. **Memory Optimization**
ECC implements:
- Token counting per model
- Background process reduction
- System prompt slimming
- Context window management

**local-llm-server adoption**: Leverage `token_budget.py` (already exists). Formalize prompt optimization as a documented pattern.

### 5. **Continuous Learning**
ECC auto-extracts successful patterns from sessions into reusable skills via:
- Pattern detection from verification passes
- Automatic skill generation
- Versioning and rollback

**local-llm-server adoption**: Add telemetry to `agent/loop.py` to track successful workflows. Generate candidate skills for manual review.

### 6. **Operator Workflows**
ECC defines domain-specific operator agents (brand-voice, customer-billing-ops, workspace-audit):
- Specialized agent types with predefined goals
- Cross-harness, reproducible workflows

**local-llm-server adoption**: Formalize `.claude/agents/` patterns. Document operator agent structure (goals, preconditions, success criteria, resources).

---

## Recommended Adoptions (Priority)

### HIGH: Do Now
1. **Formalize Skill Registry**
   - Add `skill_metadata.yaml` to `.claude/skills/` with version, inputs, outputs
   - Document skill lifecycle (preview → stable → deprecated)
   - Auto-generate skill index in `SKILLS.md`

2. **Enhance Agent Checkpoint System**
   - Implement structured checkpointing (already 70% done in `agent/state.py`)
   - Add export for session handoff/review
   - Document checkpoint format

3. **Document Agent Patterns**
   - Create `docs/agent-patterns.md` with roles (planner, executor, reviewer, judge)
   - Define success criteria per agent type
   - Add agent lifecycle (planning → execution → verification → learning)

### MEDIUM: Next Quarter
4. **Implement Continuous Learning**
   - Telemetry collection in `agent/loop.py`
   - Pattern detection for successful workflows
   - Candidate skill generation for manual review

5. **Extend Router for Operator Agents**
   - Support "operator" agent type with specialized goals
   - Map operator workflows to agent capabilities
   - Document operator agent contract

6. **Token Budgeting Dashboard**
   - Visualize token usage per model/session (leverage `token_budget.py`)
   - Alert on budget overrun
   - Suggest model downsizing

### LOW: Future
7. **Cross-Harness Abstraction**
   - Generalize agent interface for Cursor, Continue, other harnesses
   - Normalize message format across harnesses
   - Test portability

---

## Integration Points

### Existing local-llm-server Components That Align with ECC

| local-llm-server | ECC Equivalent | Status |
|---|---|---|
| `agent/state.py` | Session checkpoints | 70% - needs formalization |
| `token_budget.py` | Memory optimization | ~60% - needs dashboard |
| `.claude/skills/` | Skill registry | 50% - needs metadata |
| `.claude/agents/` | Agent definitions | 40% - needs documentation |
| `agent/loop.py` (plan→exec→verify) | Agent orchestration | 90% - core pattern done |
| `agent/quality_filters.py` (NEW) | Verification/grading | NEW - complements ECC |
| `router/model_router.py` | Model selection | 80% - could add operator logic |
| `agent/memory.py` | Memory persistence | Exists but underdocumented |

---

## Concrete Action Items

### Phase 1: Documentation + Metadata (2-3 days)
- [ ] Create `docs/agent-patterns.md` with ECC-inspired patterns
- [ ] Create `skill_metadata.yaml` schema
- [ ] Auto-generate `.claude/SKILLS_INDEX.md`
- [ ] Document operator agent contract
- [ ] Update AGENTS.md with agent lifecycle

### Phase 2: Enhance Checkpointing (3-5 days)
- [ ] Formalize checkpoint format in `agent/state.py`
- [ ] Add export/import for session portability
- [ ] Implement checkpointing in plan/exec/verify loops
- [ ] Add checkpoint versioning

### Phase 3: Continuous Learning (5-7 days)
- [ ] Add telemetry collection to `agent/loop.py`
- [ ] Implement pattern detection for successful workflows
- [ ] Auto-generate candidate skills
- [ ] Create review UI for candidate skills

---

## Non-Adoption Decisions

ECC patterns we explicitly do NOT adopt (and why):

1. **ECC's full skill marketplace/versioning** - Out of scope for local-llm-server's self-hosted model
2. **Cross-harness packaging** - local-llm-server is OpenAI-compatible proxy, not harness-native
3. **Specialized operator skills** (brand-voice, prediction-markets, etc.) - Domain-specific, not core to proxy functionality
4. **Rust control-plane (ECC 2.0)** - Python-first design for local-llm-server

---

## Success Metrics

After adoption of ECC patterns, local-llm-server should have:

1. ✅ Documented agent patterns and roles
2. ✅ Formalized skill registry with metadata
3. ✅ Structured checkpoints for reproducible sessions
4. ✅ Token budgeting visibility
5. ✅ Continuous learning infrastructure
6. ✅ Operator agent support (optional)

---

## References

- **ECC Repo**: https://github.com/affaan-m/ECC
- **ECC Architecture Docs**: https://github.com/affaan-m/ECC/tree/main/docs/architecture
- **ECC Skill Examples**: https://github.com/affaan-m/ECC/tree/main/.agents/skills
- **local-llm-server Agent Loop**: `agent/loop.py`
- **local-llm-server Skills**: `.claude/skills/`

---

## Next Review Point

- Review after Phase 1 documentation is complete
- Gather feedback on agent patterns adoption
- Assess team readiness for Phase 2 checkpointing work
