---
name: graphify
description: >
  Converts this codebase into a queryable knowledge graph so AI sessions
  query graph.json (71.5x fewer tokens) instead of reading raw source files.
  Integrates with Claude Code via /graphify and auto-refreshes on session start.
triggers:
  - "/graphify"
  - "build knowledge graph"
  - "graphify the codebase"
  - "save tokens"
  - "reduce context"
  - "token optimization"
references:
  - CLAUDE.md
  - docs/architecture/overview.md
  - .claude/skills/repowise-intelligence/SKILL.md
upstream: https://github.com/safishamsi/graphify
---

# Skill: graphify — Knowledge Graph Token Optimization

## Why This Exists

Reading raw source files to understand context is expensive. On a codebase this
size, a single "understand the auth flow" task can consume 8–20k tokens just in
file reads. Graphify pre-processes every file into a structured knowledge graph
(`graph.json`) using local AST parsing (no API calls for code). Claude queries
the graph instead of reading files — the upstream benchmark shows **71.5x fewer
tokens per query** on large mixed corpora.

## Installation (one-time per machine)

```bash
# Install the CLI
pip install graphifyy        # PyPI name uses double-y; CLI stays `graphify`
# macOS managed envs: use pipx install graphifyy instead

# Install the /graphify slash command into Claude Code
graphify install

# Build the initial graph for this repo
cd /path/to/local-llm-server
graphify .
```

On success you'll have:
```
graph.json          ← persistent, queryable graph (commit this)
graph.html          ← interactive visualization (gitignored)
GRAPH_REPORT.md     ← high-level report: god nodes, surprising edges
cache/              ← SHA256 change-detection cache
```

## Session-Start Auto-Refresh

`settings.json` in this repo configures a `SessionStart` hook that runs
`graphify . --update` when any Claude Code session opens. This keeps the graph
current without full rebuilds — only changed files are re-processed.

The hook prints a one-line status so Claude knows the graph state:
- `[graphify] graph ready — N nodes, M edges` → query graph.json
- `[graphify] not installed — reading raw files` → fallback to normal file reads

## How to Use the Graph (Token Savings Protocol)

### Instead of reading raw files:

```
# EXPENSIVE (reads 300-line file = ~1200 tokens)
/graphify explain "How does ModelRouter select a model?"

# Returns a targeted 200-token answer from the pre-built graph
```

### Key commands:

| Command | What it does |
|---------|--------------|
| `graphify .` | Full build (first run or after major restructure) |
| `graphify . --update` | Incremental refresh (only changed files) |
| `graphify query "question"` | Query conceptual relationships |
| `graphify path "ModelRouter" "proxy"` | Find connection between two nodes |
| `graphify explain "Concept"` | Detailed concept analysis from graph |
| `graphify . --watch` | Auto-sync as files change during development |

### Claude's query protocol (use this instead of Read tool for exploration):

1. **Start session**: Check `GRAPH_REPORT.md` first — it lists god nodes (highest-connected
   concepts) and surprising relationships for free.
2. **Targeted lookup**: `graphify query "X"` to understand a concept without opening files.
3. **Path tracing**: `graphify path "A" "B"` to trace how two modules connect.
4. **Only then open files**: Use `Read` only when you need the actual implementation
   line numbers to make an edit.

## Token Savings — Concrete Examples for This Repo

| Task (naive) | Tokens (raw read) | Tokens (graph query) | Saving |
|---|---|---|---|
| "How does auth work?" | ~6,000 (proxy.py + admin_auth.py + key_store.py) | ~200 | 30x |
| "What calls ModelRouter?" | ~4,000 (grep + read 3 files) | ~150 | 27x |
| "Agent loop dependencies" | ~8,000 (loop.py + tools.py + state.py) | ~300 | 27x |
| "All endpoints in proxy.py" | ~5,000 | ~180 | 28x |

## Graph Artifacts — What to Commit

```
graph.json          ✅ commit — enables team-shared graph queries
GRAPH_REPORT.md     ✅ commit — readable summary, useful in PRs
graph.html          ❌ gitignore — large binary-like HTML, regenerated on demand
cache/              ❌ gitignore — local SHA cache
```

Add to `.gitignore`:
```
graph.html
cache/
```

## Relationship to repowise-intelligence Skill

Both skills target token reduction through pre-computed codebase structure.
They are complementary:

- **graphify**: external tool, runs CLI, produces `graph.json` + `GRAPH_REPORT.md`;
  best for exploration queries and initial orientation.
- **repowise-intelligence**: internal skill, produces `.claude/skills/repowise-intelligence/intelligence/`;
  best for deep dependency tracing, git history, and decision archaeology.

Use graphify first (cheaper to bootstrap), escalate to repowise-intelligence
for questions graphify can't answer.

## Acceptance Checks

- [ ] `pip install graphifyy && graphify install` completed on this machine
- [ ] `graphify .` produced `graph.json` and `GRAPH_REPORT.md` at repo root
- [ ] `graph.json` is committed (enables shared graph queries)
- [ ] `graph.html` and `cache/` are in `.gitignore`
- [ ] `settings.json` `SessionStart` hook is active
- [ ] At least one `graphify query` runs in <500ms returning useful output
- [ ] Claude uses `graphify explain` before opening files for exploration tasks
