#!/usr/bin/env bash
# scripts/setup_colibri.sh — Bootstrap the JustVugg/colibri C runtime on
# Linux / macOS / WSL. Mirrors scripts/setup_colibri.ps1 (Windows/MinGW).
#
# Usage:
#   bash scripts/setup_colibri.sh
#
# Exit codes:
#   0 — colibri built (coli binary present)
#   1 — prerequisites missing or build failed

set -euo pipefail

COLIBRI_DIR="${COLIBRI_DIR:-${HOME}/local-models/colibri}"
COLIBRI_REPO="${COLIBRI_REPO:-https://github.com/JustVugg/colibri.git}"

echo "=== setup_colibri.sh ==="
echo ""

ok()   { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
fail() { echo "✗ $*"; }

# 1. Verify prerequisites
missing=()
for cmd in git make gcc; do
    if ! command -v "$cmd" >/dev/null 2>&1; then
        fail "$cmd: not found"
        missing+=("$cmd")
    else
        ok "$cmd: $($cmd --version 2>&1 | head -1)"
    fi
done

if (( ${#missing[@]} > 0 )); then
    echo ""
    fail "Missing prerequisites: ${missing[*]}"
    echo ""
    echo "Install (Debian/Ubuntu): sudo apt install build-essential git"
    echo "Install (Fedora):        sudo dnf install gcc make git"
    echo "Install (macOS):         xcode-select --install + brew install git"
    echo ""
    echo "After install, re-run this script."
    exit 1
fi

# 2. Clone if missing
if [[ ! -d "$COLIBRI_DIR" ]]; then
    echo ""
    echo "Cloning JustVugg/colibri → $COLIBRI_DIR ..."
    mkdir -p "$(dirname "$COLIBRI_DIR")"
    git clone "$COLIBRI_REPO" "$COLIBRI_DIR"
    ok "cloned"
else
    ok "colibri repo already present at $COLIBRI_DIR"
fi

# 3. Build
echo ""
echo "Running 'make -C c' (compiles glm.c → coli) ..."
make_args=("-C" "$COLIBRI_DIR/c" "-j")
# On macOS, colibri's Makefile prefers clang+libomp. The c/Makefile autodetects.
( cd "$COLIBRI_DIR/c" && make "${make_args[@]}" )
ok "make -C c succeeded"

COLI_BIN="$COLIBRI_DIR/c/coli"
if [[ -x "$COLI_BIN" ]]; then
    ok "coli binary found at $COLI_BIN"
    echo ""
    echo "Next steps:"
    echo "  1. Download the GLM-5.2 weights:  bash scripts/download_glm52_weights.sh"
    echo "  2. Start coli serve on :8081:      bash scripts/start_colibri_server.sh"
    echo "  3. Wire the agency brain:          export COLIBRI_ENABLED=true BRAIN_PREFERENCE=colibri"
    echo ""
    echo "Or run scripts/status_colibri_server.sh any time to check status."
else
    warn "make succeeded but coli binary not found at expected path. Inspect $COLIBRI_DIR/c/ manually."
    exit 1
fi
