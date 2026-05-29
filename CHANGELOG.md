## [Unreleased]

### Added
- **Quality Filters (Stop-Slop)**: New `agent/quality_filters.py` module for detecting and removing AI-generated tells from agent output. Includes:
  - `StopSlopFilter` class for analyzing text quality
  - Detection of banned phrases, vague declaratives, and meta-commentary
  - Text cleaning to remove common AI jargon
  - Authenticity scoring system (0-50 scale) based on directness, rhythm, trust, authenticity, and density
  - Integration with `AgentRunner._quality_check()` for code review
  - Inspired by https://github.com/hardikpandya/stop-slop (#229)
- Quality check method in AgentRunner for Python files and documentation

### Changed
- AgentRunner now includes quality checks during code review

- Update generic scanner.
