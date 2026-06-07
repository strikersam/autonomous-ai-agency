#!/usr/bin/env bash
# scripts/test_ci.sh — Reproduce the CI test environment locally.
#
# This mirrors .github/workflows/ci.yml exactly so "passes locally" and
# "passes in CI" mean the same thing.
#
# Prerequisites:
#   - Docker running (for MongoDB service container)
#   - Python 3.13 available (via pyenv, mise, or system)
#
# Usage:
#   bash scripts/test_ci.sh            # run full suite
#   bash scripts/test_ci.sh --quick    # syntax + fast-fail only (no Docker)
#
# Exit codes:  0 = all green,  non-zero = failures (same as pytest)

set -euo pipefail

QUICK=false
for arg in "$@"; do
  [[ "$arg" == "--quick" ]] && QUICK=true
done

# ── Colours ───────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
RESET='\033[0m'

ok()   { echo -e "${GREEN}✓${RESET} $*"; }
fail() { echo -e "${RED}✗${RESET} $*"; exit 1; }
warn() { echo -e "${YELLOW}!${RESET} $*"; }

echo ""
echo "══════════════════════════════════════════════════════════"
echo "  local-llm-server — CI parity check"
echo "══════════════════════════════════════════════════════════"
echo ""

# ── Step 0: find Python 3.13 ─────────────────────────────────────────────────
PYTHON=""
for candidate in python3.13 python3.12 python3; do
  if command -v "$candidate" &>/dev/null; then
    ver=$("$candidate" --version 2>&1 | awk '{print $2}')
    major=$(echo "$ver" | cut -d. -f1)
    minor=$(echo "$ver" | cut -d. -f2)
    if [[ "$major" -ge 3 && "$minor" -ge 12 ]]; then
      PYTHON="$candidate"
      ok "Python: $PYTHON ($ver)"
      break
    fi
  fi
done
if [[ -z "$PYTHON" ]]; then
  warn "Python 3.12+ not found on PATH — falling back to whatever python3 is present"
  PYTHON="python3"
fi

# ── Step 1: Syntax check (always runs) ───────────────────────────────────────
echo ""
echo "── Syntax check ──────────────────────────────────────────"
find . -name "*.py" \
  -not -path "./.venv/*" \
  -not -path "./.ci-venv/*" \
  -not -path "./.git/*" \
  | xargs "$PYTHON" -m py_compile && ok "Python syntax OK" || fail "Syntax errors found"

if $QUICK; then
  echo ""
  ok "Quick mode: skipping Docker / test run"
  exit 0
fi

# ── Step 2: Start MongoDB via Docker ─────────────────────────────────────────
echo ""
echo "── MongoDB ────────────────────────────────────────────────"

MONGO_CONTAINER="llm-ci-mongo-$$"
MONGO_PORT="27099"  # high port to avoid collisions with any local mongod

if ! command -v docker &>/dev/null; then
  warn "Docker not found — running tests without MongoDB (some tests may skip/fail)"
  MONGO_URL="mongodb://localhost:27017"
else
  docker run -d \
    --name "$MONGO_CONTAINER" \
    -p "${MONGO_PORT}:27017" \
    mongo:7 \
    > /dev/null
  ok "MongoDB container started: $MONGO_CONTAINER (port $MONGO_PORT)"

  # Wait for MongoDB to be ready (up to 60 s)
  for i in $(seq 1 30); do
    if docker exec "$MONGO_CONTAINER" mongosh --quiet --eval 'db.runCommand({ping:1}).ok' 2>/dev/null | grep -q 1; then
      ok "MongoDB is ready"
      break
    fi
    [[ $i -eq 30 ]] && fail "MongoDB did not become ready within 60 s"
    sleep 2
  done
  MONGO_URL="mongodb://localhost:${MONGO_PORT}"
fi

cleanup() {
  if command -v docker &>/dev/null && docker ps -q -f "name=$MONGO_CONTAINER" | grep -q .; then
    docker rm -f "$MONGO_CONTAINER" > /dev/null 2>&1 && ok "MongoDB container removed"
  fi
}
trap cleanup EXIT

# ── Step 3: Install dependencies ─────────────────────────────────────────────
echo ""
echo "── Dependencies ───────────────────────────────────────────"
if [[ -d ".ci-venv" ]]; then
  VENV_PYTHON=".ci-venv/bin/python"
  ok "Reusing .ci-venv"
else
  "$PYTHON" -m venv .ci-venv
  VENV_PYTHON=".ci-venv/bin/python"
  ok "Created .ci-venv"
fi

"$VENV_PYTHON" -m pip install --upgrade pip -q
"$VENV_PYTHON" -m pip install -r requirements.txt -q
ok "Dependencies installed"

# ── Step 4: Configure git identity (matches CI step) ─────────────────────────
git config user.email "ci@test.local" 2>/dev/null || true
git config user.name  "CI Test Runner" 2>/dev/null || true
git config commit.gpgsign false         2>/dev/null || true
git config init.defaultBranch master    2>/dev/null || true

# ── Step 5: Run tests (exact env vars from ci.yml) ───────────────────────────
echo ""
echo "── Running tests ──────────────────────────────────────────"

export API_KEYS="ci-test-key"
export ADMIN_EMAIL="admin@llmrelay.local"
export ADMIN_PASSWORD="${ADMIN_PASSWORD:? ADMIN_PASSWORD env var must be set — no hardcoded fallback}"
export SECRET_KEY="ci-test-secret-do-not-use"
export OLLAMA_BASE="http://localhost:11434"
export LANGFUSE_SECRET_KEY=""
export LANGFUSE_PUBLIC_KEY=""
export LANGFUSE_HOST=""
export ROUTER_HEALTH_CHECK_ENABLED="false"
export MONGO_URL="$MONGO_URL"
export DB_NAME="llm_wiki_dashboard_ci"

"$VENV_PYTHON" -m pytest -x -v --tb=short
PYTEST_EXIT=$?

echo ""
if [[ $PYTEST_EXIT -eq 0 ]]; then
  ok "All Python tests passed ✓"
else
  fail "Python tests failed (exit $PYTEST_EXIT)"
fi
