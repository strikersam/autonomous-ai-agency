# This repository is maintained by its own agents

The strongest evidence that this platform's agent loop works is not a benchmark — it's the commit history of this repository. The platform's own agents (running through the same plan → execute → verify loop the product ships) develop, test, and release the product.

## The numbers (verifiable via the GitHub API)

As of 2026-07-10:

| Metric | Count | Verify it yourself |
|---|---|---|
| Merged pull requests, total | **642** | [`is:pr is:merged`](https://github.com/strikersam/autonomous-ai-agency/pulls?q=is%3Apr+is%3Amerged) |
| Merged PRs opened by agent sessions (`claude/*` head branches) | **176** | [`is:pr is:merged head:claude/`](https://github.com/strikersam/autonomous-ai-agency/pulls?q=is%3Apr+is%3Amerged+head%3Aclaude%2F) |
| Merged PRs opened by agent sessions (`codex/*` head branches) | **8** | [`is:pr is:merged head:codex/`](https://github.com/strikersam/autonomous-ai-agency/pulls?q=is%3Apr+is%3Amerged+head%3Acodex%2F) |

**184 of 642 merged PRs (29%) were opened by AI agent sessions**, identifiable by their head branch prefix alone. The true share of agent-written code is higher — many commits land from agent sessions pushing to shared branches — but this table only claims what a branch-name query proves.

Every one of these PRs went through the same gates as a human PR: full pytest suite, frontend Jest + build, Bandit SAST, CodeQL, loop-registry audit, changelog parity, and human review before merge. Agents propose; CI verifies; a human approves. That is exactly the HITL model the platform ships.

## A sample of what the agents shipped (all merged, all real)

| PR | What the agent built |
|---|---|
| [#999](https://github.com/strikersam/autonomous-ai-agency/pull/999) | Autonomous self-healing system: task dedup + brain deadlock recovery |
| [#996](https://github.com/strikersam/autonomous-ai-agency/pull/996) | CI hardening: secret masking in nightly regression + report from captured output |
| [#992](https://github.com/strikersam/autonomous-ai-agency/pull/992) | Universal multi-provider brain failover system |
| [#988](https://github.com/strikersam/autonomous-ai-agency/pull/988) | In-process WebSocket gateway + mobile web UI for iOS control |
| [#954](https://github.com/strikersam/autonomous-ai-agency/pull/954) | Anthropic prompt caching + extended thinking in the outbound router |
| [#953](https://github.com/strikersam/autonomous-ai-agency/pull/953) | E2B Firecracker micro-VM sandbox for isolated agent execution |
| [#946](https://github.com/strikersam/autonomous-ai-agency/pull/946) | Auth fix: separated admin login from social login + onboarding gate |
| [#426](https://github.com/strikersam/autonomous-ai-agency/pull/426) | Agentic portfolio management (WSJF) + v5 Portfolio screen |
| [#323](https://github.com/strikersam/autonomous-ai-agency/pull/323) | Graphify knowledge-graph integration (71× token reduction for agent sessions) |

Browse the full list with the search links in the table above — titles, diffs, CI runs, and review threads are all public.

## Why this matters if you're evaluating the platform

When the README says agents can "open PRs, pass CI, and wait for your approval," that claim is not aspirational — it describes how this repository has been built for months. The same loop, pointed at your codebase and your business systems, is what a deployment of this platform is.
