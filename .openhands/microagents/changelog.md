---
name: changelog
type: knowledge
version: 1.0.0
triggers:
- changelog
- release
---

Changelog rules: every behaviour-changing PR must add an entry under
`## [Unreleased]` in BOTH `CHANGELOG.md` and `docs/changelog.md` — the two
files must stay byte-identical below the header comment
(`python scripts/check_changelog_parity.py` verifies). PRs prefixed
`chore:`, `docs:`, `ci:`, `test:`, `style:`, `revert:`, `build:` are exempt.
Before tagging a release, run the `release-readiness` skill.
