---
name: github
type: knowledge
version: 2.0.0
triggers:
- github
- pull request
- pr
- merge
- branch
---

GitHub operations from agent code go through `agent/github_tools.py` (GitHubTools) with
the autonomy gate enabled: the agent proposes changes via pull request and a human
merges. Never commit or push directly to a protected branch, and never merge a PR from
agent code.

Merge and CI requirements are `CLAUDE.md` rules 34–38. Credentials are rule 42.
