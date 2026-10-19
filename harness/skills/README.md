# Skills

One folder per skill, each with a `SKILL.md` (YAML frontmatter `name` + `description`,
then instructions). Claude Code, Codex and any agent that reads `SKILL.md` files can
load them. `CATALOG.md` maps use cases to skills.

This index is generated: `python harness/scripts/index_skills.py`.

| Skill | What it does |
|---|---|
| [`agent-browser`](agent-browser/SKILL.md) | Browser automation via Chrome DevTools Protocol — use real Chrome to navigate, interact with, and test web UIs. 93% fewer tokens than Playwright MCP. Use when a… |
| [`agent-harness`](agent-harness/SKILL.md) | Build and run a structured agent harness — an outer loop that gives an LLM a defined set of tools (capabilities) and drives it to task completion. Use when: you… |
| [`ai-engineering-insights`](ai-engineering-insights/SKILL.md) | AI-assisted engineering impact analysis — productivity metrics and code quality insights |
| [`auto-fix`](auto-fix/SKILL.md) | Automatically detect and fix linting, formatting, and type errors across the codebase. Use when: pre-commit cleanup is needed. |
| [`brain-dump`](brain-dump/SKILL.md) | Convert a chaotic list of scattered ideas, notes, or thoughts into a structured, prioritized action plan. Use when: you have a messy list of ideas and need stru… |
| [`branch-cleanup`](branch-cleanup/SKILL.md) | Delete remote and local branches that have been merged into master. Run after every merge to keep the repo to master-only. Supports both git-push deletion and G… |
| [`browserbase-browser`](browserbase-browser/SKILL.md) | Automate real browser interactions via the `browse` CLI — supports local Chrome and remote Browserbase cloud sessions with CAPTCHA solving and residential proxi… |
| [`browserbase-fetch`](browserbase-fetch/SKILL.md) | Fetch HTML, JSON, or headers from any URL via Browserbase infrastructure — handles proxies, redirects, and rate-limited sites without opening a browser. Use for… |
| [`browserbase-search`](browserbase-search/SKILL.md) | Search the web via Browserbase infrastructure and get structured results (title, URL, author, date) without opening a browser. Use before browsing to find the r… |
| [`browserbase-ui-test`](browserbase-ui-test/SKILL.md) | Adversarial UI testing via browser automation — tries to BREAK the app, not confirm it works. Analyzes git diffs to test changed code, or explores the full app … |
| [`brutalist-skill`](brutalist-skill/SKILL.md) | Raw mechanical interfaces fusing Swiss typographic print with military terminal aesthetics. Rigid grids, extreme type scale contrast, utilitarian color, analog … |
| [`changelog-enforcer`](changelog-enforcer/SKILL.md) | Ensure every meaningful change has a proper docs/changelog.md entry. Use before every commit that changes behaviour, adds features, or fixes bugs. |
| [`checkpoint-strategy`](checkpoint-strategy/SKILL.md) | Design and validate checkpointing strategies for LLM training runs. Use when: starting a new training run (set checkpointing policy upfront). |
| [`context-prime`](context-prime/SKILL.md) | Prime Claude with deep repository context before starting any significant task. Use at the start of a session in an unfamiliar area. |
| [`council-review`](council-review/SKILL.md) | Multi-perspective code review before merging. Simulates a council of reviewers (security, correctness, performance, maintainability) independently evaluating a … |
| [`cowork-session`](cowork-session/SKILL.md) | Claude Cowork shared AI pairing sessions with real-time sync, turn-taking, and collaboration context propagation. |
| [`data-quality-audit`](data-quality-audit/SKILL.md) | Audit training data and tokenizer pipelines for quality issues that silently degrade LLM training. Use when: preparing a dataset for LLM pretraining or fine-tun… |
| [`debug-tracer`](debug-tracer/SKILL.md) | Systematically trace and resolve bugs using hypothesis-driven debugging. Use when: a bug report needs investigation. |
| [`dependency-audit`](dependency-audit/SKILL.md) | Review, validate, and update Python dependencies safely. Use when adding a new package, upgrading an existing one, or reviewing the dependency surface. |
| [`deslop`](deslop/SKILL.md) | Remove AI code slop before committing. Review AI-generated code for unnecessary verbosity, redundant comments, over-engineering, and low-signal patterns that de… |
| [`dev-browser`](dev-browser/SKILL.md) | Control a local or remote browser with sandboxed JavaScript scripts. Uses a QuickJS WASM sandbox (not Node.js) with a pre-connected `browser` global and full Pl… |
| [`docs-sync`](docs-sync/SKILL.md) | Keep documentation in sync after code changes. Run after any change that alters module behaviour, APIs, env vars, or architecture. |
| [`duplicate-thread`](duplicate-thread/SKILL.md) | Clone an existing plan, task thread, or agent session so you can explore an alternative approach without losing the original. Use when: you want to try a risky … |
| [`email-triage`](email-triage/SKILL.md) | Rapidly process a backlog of emails by categorizing, prioritizing, and drafting responses or actions. Use when: inbox has grown unmanageable. |
| [`feature-flag`](feature-flag/SKILL.md) | Implement new features behind feature flags to enable safe, gradual rollouts and easy rollbacks without code deployments. Use when: implementing a risky or larg… |
| [`financial-analyst`](financial-analyst/SKILL.md) | Agentic CFO for autonomous financial analysis of AI infrastructure spend. Computes burn rate, runway, gross margin, and ROI-based budget reallocation. |
| [`git-hygiene`](git-hygiene/SKILL.md) | Ensures the repository's git history, branch state, and commit messages are clean, meaningful, and follow project conventions before pushing or merging. Use bef… |
| [`graphify`](graphify/SKILL.md) | Converts this codebase into a queryable knowledge graph so AI sessions query graph.json (71.5x fewer tokens) instead of reading raw source files. Integrates wit… |
| [`hybrid-reasoning`](hybrid-reasoning/SKILL.md) | Hybrid AI combining deterministic rule engines with LLM reasoning for efficient, auditable, and reliable decision-making. |
| [`implementation-planner`](implementation-planner/SKILL.md) | Plan a multi-file or multi-step implementation before writing any code. Use before any change touching more than two files, adding a new feature, or changing a … |
| [`insights`](insights/SKILL.md) | Analytics, heatmaps, and trends from session history. Analyze checkpoint logs, learnings, and git history to surface patterns: which files change most, which st… |
| [`issue-resolver`](issue-resolver/SKILL.md) | Provides a structured, repeatable process for resolving GitHub issues from start to finish — reading the issue, planning a solution, implementing it, testing it… |
| [`karpathy-guidelines`](karpathy-guidelines/SKILL.md) | Andrej Karpathy's coding guidelines for AI agents — concise, correct, and well-tested code |
| [`learn-rule`](learn-rule/SKILL.md) | Persist corrections and patterns to long-term memory. When a mistake is made or a rule is learned, write it to .claude/state/learnings.md so it's never repeated… |
| [`local-ai-query`](local-ai-query/SKILL.md) | Route prompts to a locally running Ollama instance instead of cloud AI APIs. Use when: processing sensitive/proprietary code or data that shouldn't leave the ma… |
| [`lr-schedule-advisor`](lr-schedule-advisor/SKILL.md) | Advise on learning rate schedules for transformer/LLM training. Use when: starting a new training run and unsure about LR settings. |
| [`memory-consolidation`](memory-consolidation/SKILL.md) | Dream Memory Consolidation for clustering session artifacts into structured, queryable memories with tag-based similarity. |
| [`minimalist-skill`](minimalist-skill/SKILL.md) | Clean editorial-style interfaces. Warm monochrome palette, typographic contrast, flat bento grids, muted pastels. No gradients, no heavy shadows. |
| [`modularity-review`](modularity-review/SKILL.md) | Review codebase or design for modularity problems and produce actionable improvement recommendations. Also guides design of new modular boundaries from function… |
| [`multi-agent`](multi-agent/SKILL.md) | Multi-agent team coordination — task delegation, shared state, and inter-agent communication |
| [`obsidian-knowledge-graph`](obsidian-knowledge-graph/SKILL.md) | Obsidian-compatible knowledge graph with bidirectional links and graph-based retrieval |
| [`output-skill`](output-skill/SKILL.md) | Overrides default LLM truncation behavior. Enforces complete code generation, bans placeholder patterns, and handles token-limit splits cleanly. Apply to any ta… |
| [`parallel-agents`](parallel-agents/SKILL.md) | Decompose a large task into N independent subtasks and dispatch them as parallel subagents, then aggregate results. Use when: a task has multiple independent su… |
| [`parallel-worktrees`](parallel-worktrees/SKILL.md) | Git worktree setup for zero dead time. Work on multiple branches simultaneously without switching branches or stashing. Ideal for running tests on main while im… |
| [`perplexity`](perplexity/SKILL.md) | Deep web research using the Perplexity API — get cited, up-to-date answers to research questions without burning context on raw web pages. Use when you need cur… |
| [`pro-workflow`](pro-workflow/SKILL.md) | Core AI coding workflow. Orchestrates 8 patterns: Scout → Plan → Implement → Review, with smart commits, session rituals, and continuous learning capture. This … |
| [`prompt-library`](prompt-library/SKILL.md) | Maintain a structured, versioned library of the prompts and behavioral templates used by agents in this repository. Use when adding a new agent or skill (to reg… |
| [`prompt-transparency`](prompt-transparency/SKILL.md) | Inspired by the CL4R1T4S project (github.com/elder-plinius/CL4R1T4S), this skill audits and surfaces all implicit behavioral instructions, system prompts, and a… |
| [`redesign-skill`](redesign-skill/SKILL.md) | Upgrades existing websites and apps to premium quality. Audits current design, identifies generic AI patterns, and applies high-end design standards without bre… |
| [`release-readiness`](release-readiness/SKILL.md) | Gate check before tagging and releasing a new version. Run this skill before any `git tag vX.Y.Z` operation. |
| [`replay-learnings`](replay-learnings/SKILL.md) | Surface relevant past patterns before starting work. Read the learnings file and extract rules that apply to the current task. Prevents repeating past mistakes. |
| [`repo-memory-updater`](repo-memory-updater/SKILL.md) | Keep CLAUDE.md files and .claude/state/ in sync with the current repo reality. Use after significant structural changes, after adding risky modules, or when CLA… |
| [`research`](research/SKILL.md) | Conduct structured, systematic research on any topic — synthesizing sources, extracting key findings, identifying gaps, and producing a clear research brief. Us… |
| [`research-coordinator`](research-coordinator/SKILL.md) | Multi-agent research coordination — deduplicate findings, assign work, and synthesize results |
| [`resource-panel`](resource-panel/SKILL.md) | Track, display, and summarise all resources consumed or produced during an agent session: files read/written, URLs fetched, tools called, tokens used, and exter… |
| [`sandboxed-exec`](sandboxed-exec/SKILL.md) | Run shell commands or code snippets in an isolated subprocess environment, preventing side effects from leaking into the host workspace. Use when: you need to r… |
| [`scope-guard`](scope-guard/SKILL.md) | Detect and prevent scope creep during implementation. Use at the start of any implementation task (define scope). |
| [`self-improve`](self-improve/SKILL.md) | Enables the agent to analyze its own skill library, identify gaps or weaknesses, and propose or implement improvements to existing skills or new skill definitio… |
| [`session-handoff`](session-handoff/SKILL.md) | Write structured resume documentation for the next session. Captures state, context, and next actions so any AI or developer can continue without archaeology. |
| [`session-planning`](session-planning/SKILL.md) | Mandatory planning workflow for all AI agents — decompose tasks before execution |
| [`skill-composer`](skill-composer/SKILL.md) | Enables the agent to combine multiple existing skills into a coordinated workflow for complex tasks that no single skill covers. Use when a task clearly require… |
| [`smart-commit`](smart-commit/SKILL.md) | Quality gates + conventional commits. Run tests, lint, and typecheck before committing. Format the commit message as a conventional commit. Blocks on failure. |
| [`soft-skill`](soft-skill/SKILL.md) | Teaches the AI to design like a high-end agency. Defines the exact fonts, spacing, shadows, card structures, and animations that make a website feel expensive. … |
| [`stitch-skill`](stitch-skill/SKILL.md) | Semantic Design System Skill for Google Stitch. Generates agent-friendly DESIGN.md files that enforce premium, anti-generic UI standards — strict typography, ca… |
| [`stop-slop-quality`](stop-slop-quality/SKILL.md) | Remove AI writing tells and cliches — enforce natural, human-quality output |
| [`superclaude-commands`](superclaude-commands/SKILL.md) | Slash-command system for AI agent orchestration — /plan, /execute, /review, /deploy |
| [`system-prompt-audit`](system-prompt-audit/SKILL.md) | Audit all system-level instructions embedded in this repository's Claude configuration, surface them as a structured inventory, and validate them for consistenc… |
| [`task-alive-updates`](task-alive-updates/SKILL.md) | Keep long-running agent tasks visibly alive by emitting periodic heartbeat status updates to stdout. Use when: any task expected to run longer than 2 minutes. |
| [`task-scoper`](task-scoper/SKILL.md) | Prevents scope creep by explicitly defining the boundaries of a task before implementation begins. Use at the start of any non-trivial implementation task. |
| [`taste-skill`](taste-skill/SKILL.md) | Senior UI/UX Engineer. Architect digital interfaces overriding default LLM biases. Enforces metric-based rules, strict component architecture, CSS hardware acce… |
| [`test-first-executor`](test-first-executor/SKILL.md) | Write or update tests before (or alongside) implementation. Ensures every code change is verifiably correct before merging. |
| [`ticket-to-pr`](ticket-to-pr/SKILL.md) | Transform a GitHub issue (ticket) into a complete, merged pull request. Use when: given an issue number or URL to implement. |
| [`tokenizer-diagnostics`](tokenizer-diagnostics/SKILL.md) | Deep-dive diagnostics for tokenizer behavior in LLM training and inference. Use when: switching tokenizers between training phases. |
| [`training-stability-monitor`](training-stability-monitor/SKILL.md) | Monitor and diagnose LLM/ML training instability — loss spikes, exploding gradients, dead neurons, and learning rate mismatches. Use when: a training loss curve… |
| [`workflow-engine`](workflow-engine/SKILL.md) | DAG-based workflow execution engine with parallel steps, retries, and conditional branching |
| [`wrap-up`](wrap-up/SKILL.md) | Session closing ritual with learning capture. Run at the end of every coding session. 5 steps: changes audit, quality check, learning capture, next session plan… |
