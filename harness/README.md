# Agency Harness

The reusable half of [Autonomous AI Agency](../README.md): the skills, subagents, slash
commands, rules, connector configs and loop patterns that make a coding agent behave like
a disciplined engineering team. None of it depends on the agency's Python code. Drop it
into any repository and Claude Code, Codex, Cursor or Gemini CLI can use it.

This folder is self-contained so it can be published on its own. It is MIT-licensed
([`LICENSE`](LICENSE)).

## What's inside

| Folder | What it is | Loaded by |
|---|---|---|
| [`skills/`](skills/README.md) | 70+ task playbooks (`SKILL.md`): planning, test-first, review councils, release gates, browser testing, research, memory, UI taste | Claude Code (`.claude/skills/`), Codex (`.agents/skills/`) |
| [`agents/`](agents/) | Subagent definitions: planner, implementer, reviewer, codebase explorer, docs auditor, risk and verification reviewers | Claude Code (`.claude/agents/`) |
| [`commands/`](commands/) | Slash commands: `/plan`, `/review`, `/fix-bug` | Claude Code (`.claude/commands/`) |
| [`rules/`](rules/AGENT_RULES.md) | The agent-discipline ruleset (verify before asserting, independent verifier before "done") as a drop-in `CLAUDE.md` / `AGENTS.md` section | Any agent that reads an instruction file |
| [`connectors/`](connectors/README.md) | MCP server setup and client configs (Aider, Codex, Continue, Cursor, Zed, VS Code) | You, once per machine |
| [`workflows/`](workflows/README.md) | How the autonomous loops are built: scheduled GitHub Actions + a loop registry with maturity levels and approval gates | GitHub Actions |
| [`plugins/`](plugins/) | Packaged plugins (`sol-advisor`) | Codex marketplace (`.agents/plugins/marketplace.json`) |

## Use it in your repo

```bash
git clone https://github.com/strikersam/autonomous-ai-agency
./autonomous-ai-agency/harness/install.sh /path/to/your-repo          # copy
./autonomous-ai-agency/harness/install.sh /path/to/your-repo --link   # symlink, stays updated
```

The installer puts skills in `.claude/skills/` and `.agents/skills/`, subagents in
`.claude/agents/`, commands in `.claude/commands/`, and writes `AGENT_RULES.md` at the repo
root for you to reference from your own `CLAUDE.md` or `AGENTS.md`. It never overwrites a
file that already exists.

Prefer picking? Copy any single `skills/<name>/` folder into your `.claude/skills/`. Each
skill stands alone.

## How this repo uses it

This folder is the single source. The agency repo points at it with symlinks:
`.claude/skills/<name>` → `harness/skills/<name>` (and the same for each file in
`.claude/agents/` and `.claude/commands/`), and `.agents/skills` → `.claude/skills`.
Skills, subagents and commands wired to the agency's own code (deploy drills,
model-catalogue edits, risky-module review, its scripts and services) stay as real files in
`.claude/`.

**Windows:** symlinks need `git config core.symlinks true` and Developer Mode (or an admin
shell) before cloning. Without them the links check out as small text files and the
harness skills don't load.

## Adding to it

- New generic skill → `harness/skills/<name>/SKILL.md`, then
  `ln -s ../../harness/skills/<name> .claude/skills/<name>` and
  `python harness/scripts/index_skills.py` to refresh the index.
- Anything that names this repo's files, services or deploy → `.claude/skills/` instead.
