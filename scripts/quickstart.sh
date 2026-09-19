#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# quickstart.sh — one command to run the whole Autonomous AI Agency locally.
#
#   ./scripts/quickstart.sh
#
# What it brings up (on your machine, nothing leaves it):
#   • the FastAPI backend + dashboard UI on http://localhost:8001
#   • the 24×7 autonomy loops in-process (RUN_BACKGROUND_IN_WEB=true)
#   • zero-dependency SQLite storage — no MongoDB, no cloud account, no Docker
#
# It is idempotent: safe to re-run. On the first run it writes a local .env,
# creates a virtualenv, installs backend deps, and builds the React UI so the
# backend can serve it at /. Later runs skip the slow steps and just start up.
#
# Flags:
#   --api-only     Skip the frontend build (API on :8001, no dashboard UI)
#   --rebuild-ui   Force a fresh frontend build even if one exists
#   --reinstall    Reinstall Python dependencies even if already present
#   --port N       Backend port (default: 8001, or $PORT)
#   -h, --help     Show this help
#
# What this does NOT start (by design — see docs/local-setup.md):
#   • MongoDB (production storage), Cloudflare Worker / public tunnel,
#     Telegram bot, or the containerised runtime sidecars. Those are the
#     production topology; this is the single-process developer path.
# ─────────────────────────────────────────────────────────────────────────────
set -euo pipefail

# ── Resolve repo root (this script lives in scripts/) ────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$ROOT"

API_ONLY=0
REBUILD_UI=0
REINSTALL=0
PORT="${PORT:-8001}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-only)   API_ONLY=1; shift ;;
    --rebuild-ui) REBUILD_UI=1; shift ;;
    --reinstall)  REINSTALL=1; shift ;;
    --port)       PORT="${2:?--port needs a value}"; shift 2 ;;
    -h|--help)    sed -n '2,40p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
done

say()  { printf '\033[36m%s\033[0m\n' "$*"; }
ok()   { printf '\033[32m✓ %s\033[0m\n' "$*"; }
warn() { printf '\033[33m! %s\033[0m\n' "$*"; }
die()  { printf '\033[31m✗ %s\033[0m\n' "$*" >&2; exit 1; }

say "== Autonomous AI Agency — local quickstart =="

# ── 1. Toolchain checks ──────────────────────────────────────────────────────
PYTHON_BIN="${PYTHON_EXE:-python3}"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || die "Python 3 not found. Install Python 3.11+ and re-run (macOS: brew install python; Ubuntu: sudo apt install python3 python3-venv)."
if [[ "$API_ONLY" -eq 0 ]]; then
  command -v npm >/dev/null 2>&1 || die "npm not found (needed to build the dashboard UI). Install Node 20+ (https://nodejs.org), or run with --api-only for the API surface only."
fi
ok "Python: $("$PYTHON_BIN" --version 2>&1)"

# ── 2. Local .env with safe local defaults (never overwrites your values) ────
ENV_FILE="$ROOT/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$ROOT/.env.example" "$ENV_FILE"
  ok "Created .env from .env.example"
else
  ok "Using existing .env"
fi

# Set KEY=VALUE only if no *active* (uncommented) KEY= line already exists.
ensure_env() {
  local key="$1" val="$2"
  if ! grep -qE "^${key}=" "$ENV_FILE"; then
    printf '%s=%s\n' "$key" "$val" >> "$ENV_FILE"
  fi
}

ensure_env STORAGE_BACKEND sqlite
ensure_env ACTIVATION_REQUIRED false
ensure_env RUN_BACKGROUND_IN_WEB true
ensure_env ADMIN_EMAIL admin@localhost
if ! grep -qE "^JWT_SECRET=" "$ENV_FILE"; then
  ensure_env JWT_SECRET "$("$PYTHON_BIN" -c 'import secrets; print(secrets.token_urlsafe(48))')"
  ok "Generated a random JWT_SECRET for this instance"
fi
# ADMIN_PASSWORD ships as 'changeme' in .env.example — keep it for local, but say so.
ADMIN_PW="$(grep -E '^ADMIN_PASSWORD=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]' || true)"
[[ -z "$ADMIN_PW" ]] && ADMIN_PW="changeme"
ADMIN_EMAIL_VAL="$(grep -E '^ADMIN_EMAIL=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '[:space:]' || true)"
[[ -z "$ADMIN_EMAIL_VAL" ]] && ADMIN_EMAIL_VAL="admin@localhost"

if ! grep -qiE '^(NVIDIA_API_KEY|TOKENIN_API_KEY|GROQ_API_KEY|CEREBRAS_API_KEY|ANTHROPIC_API_KEY|OPENAI_API_KEY)=.+' "$ENV_FILE"; then
  warn "No LLM provider key set in .env. The agency boots and the UI works, but"
  warn "  agent output is degraded until you add one (a free NVIDIA NIM key is the"
  warn "  quickest: https://build.nvidia.com → NVIDIA_API_KEY=nvapi-... in .env)."
fi

# ── 3. Python virtualenv + backend dependencies ──────────────────────────────
VENV="$ROOT/.venv"
[[ -d "$VENV" ]] || { say "[setup] Creating virtualenv (.venv)…"; "$PYTHON_BIN" -m venv "$VENV"; }
VENV_PY="$VENV/bin/python"
DEPS_SENTINEL="$VENV/.backend-deps-installed"
if [[ ! -f "$DEPS_SENTINEL" || "$REINSTALL" -eq 1 ]]; then
  say "[setup] Installing backend dependencies (first run only, ~1–2 min)…"
  "$VENV_PY" -m pip install --upgrade pip --quiet
  "$VENV_PY" -m pip install -r "$ROOT/backend/requirements.txt" --quiet
  touch "$DEPS_SENTINEL"
  ok "Backend dependencies installed"
else
  ok "Backend dependencies already installed (--reinstall to refresh)"
fi

# ── 4. Frontend build (so the backend serves the dashboard at /) ─────────────
if [[ "$API_ONLY" -eq 0 ]]; then
  if [[ ! -d "$ROOT/frontend/build" || "$REBUILD_UI" -eq 1 ]]; then
    say "[setup] Building the dashboard UI (first run only, ~2–4 min)…"
    ( cd "$ROOT/frontend" && npm install --no-audit --no-fund && CI=true npm run build )
    ok "Dashboard UI built"
  else
    ok "Dashboard UI already built (--rebuild-ui to refresh)"
  fi
fi

# ── 5. Launch ─────────────────────────────────────────────────────────────────
echo
ok "Setup complete. Starting the agency…"
echo
say  "  Dashboard : http://localhost:${PORT}/"
say  "  Login     : ${ADMIN_EMAIL_VAL} / ${ADMIN_PW}"
[[ "$ADMIN_PW" == "changeme" ]] && warn "  (default password — change ADMIN_PASSWORD in .env before exposing this)"
say  "  Stop      : Ctrl-C"
echo

exec "$VENV/bin/uvicorn" backend.server:app --host 127.0.0.1 --port "$PORT"
