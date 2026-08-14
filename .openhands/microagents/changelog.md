---
name: changelog
type: knowledge
version: 2.0.0
triggers:
- changelog
- release
---

See `CLAUDE.md` rule 34. In short: every behaviour-changing PR adds an entry under
`## [Unreleased]` in BOTH `CHANGELOG.md` and `docs/changelog.md`, byte-identical below
the header comment (`python scripts/check_changelog_parity.py` verifies). Commits
prefixed `chore:`, `docs:`, `ci:`, `test:`, `style:`, `revert:`, or `build:` are exempt
— the `commit-msg` hook keys off exactly those and has no severity escape hatch.

Before tagging a release, run the `release-readiness` skill.
