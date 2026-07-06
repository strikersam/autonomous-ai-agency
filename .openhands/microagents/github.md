---
name: github
type: knowledge
version: 1.0.0
triggers:
- github
- pull request
- pr
- merge
- branch
---

GitHub operations in this repo go through `agent/github_tools.py` (GitHubTools),
which runs with the autonomy gate enabled: the agent proposes changes via pull
request and a human merges — never commit or push directly to protected
branches, and never merge a PR from agent code.

PR requirements (CI-enforced): changelog parity entry, tests for new behaviour,
`python -m compileall -q .` clean, and `python agent/loop_registry.py audit
--check` green when workflows are touched. PRs are squash-merged to master.
