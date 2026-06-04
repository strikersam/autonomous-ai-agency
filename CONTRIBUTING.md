# Contributing to local-llm-server

Thank you for contributing! This guide covers everything you need to get started.

---

## Development Setup

### Prerequisites

- Python 3.13+
- Node.js 20+ (for frontend)
- MongoDB (or use SQLite with `STORAGE_BACKEND=sqlite`)
- Ollama (for running local models)

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/strikersam/local-llm-server.git
cd local-llm-server

# 2. Create virtualenv and install dependencies
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 3. Copy environment template
cp .env.example .env
# Edit .env with your settings

# 4. Activate git hooks
git config core.hooksPath .claude/hooks

# 5. Run tests
pytest -x

# 6. Start the proxy (port 8000)
uvicorn proxy:app --reload --port 8000

# 7. Start the backend (port 8001) — optional, for dashboard
uvicorn backend.server:app --reload --port 8001
```

### Frontend Development

```bash
cd frontend
npm install --legacy-peer-deps
npm start  # Dev server on port 3000
```

---

## How to Contribute

### Bug Reports

1. Search existing issues before creating a new one
2. Include a minimal reproduction case
3. Include environment details (OS, Python version, Ollama version)
4. For security issues, see [SECURITY.md](SECURITY.md) — do NOT open public issues

### Feature Requests

1. Open a GitHub discussion first to validate the idea
2. For large features, create an RFC issue with the `rfc` label
3. Wait for approval before starting implementation

### Pull Requests

1. Fork the repository
2. Create a feature branch: `git checkout -b feat/your-feature`
3. Follow the coding standards below
4. Run `pytest -x` — must pass
5. Update `docs/changelog.md` under `[Unreleased]`
6. Submit a PR with a clear description

---

## Coding Standards

See [AGENTS.md](AGENTS.md) for the full standards. Key points:

- Type annotations on ALL public functions
- `async def` for all I/O operations
- Pydantic models for all API shapes
- `logging` not `print`
- No hardcoded secrets
- No files over 800 lines

---

## Testing Requirements

- New features → new tests
- Bug fixes → regression test first, then fix
- `pytest -x` must pass before submitting

```bash
pytest -x                          # Run all tests (fast fail)
pytest -v --tb=short               # Verbose
pytest --cov=. --cov-report=term   # With coverage
```

---

## Changelog

Every meaningful change must update `docs/changelog.md`:

```markdown
## [Unreleased]

### Added
- New feature description

### Fixed
- Bug fix description (`file.py` line reference)

### Security
- Security fix description
```

The `commit-msg` hook will reject commits without a changelog update (except `chore:`, `docs:`, `style:`, `ci:`, `test:` prefixed commits).

---

## Commit Message Convention

Use conventional commits:

```
type(scope): short description

Longer explanation if needed.
```

Types: `feat`, `fix`, `docs`, `test`, `chore`, `style`, `refactor`, `perf`, `ci`

Examples:
- `feat(router): add vision model routing support`
- `fix(key_store): use hmac.compare_digest for secret comparison`
- `test(agent): add regression test for path traversal guard`

---

## PR Review Checklist

Before requesting review, ensure:

- [ ] Type annotations on all new public functions
- [ ] Tests pass (`pytest -x`)
- [ ] New tests added for new functionality
- [ ] `docs/changelog.md` updated
- [ ] No hardcoded secrets
- [ ] No blocking I/O in async handlers
- [ ] Risky modules reviewed if changed (see `AGENTS.md`)

---

## Architecture

See `AGENTS.md` for the full architecture overview and module map.

Key areas to understand before contributing:
- `proxy.py` — main entry point, auth, rate limiting
- `router/` — model routing logic (read `router/CLAUDE.md` first)
- `agent/` — multi-agent orchestration (read `agent/CLAUDE.md` first)
- `key_store.py`, `admin_auth.py` — risky modules requiring extra care

---

## Getting Help

- Open a GitHub discussion for questions
- See `docs/troubleshooting.md` for common issues
- See `AGENTS.md` for operating the codebase with AI agents
