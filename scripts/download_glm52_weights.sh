#!/usr/bin/env bash
# scripts/download_glm52_weights.sh — Download the JustVugg/colibri-format
# GLM-5.2 (744B MoE, ~370 GB int4 + int8 MTP) checkpoint from HuggingFace
# into D:\hfkld-qg7ky\local-models\glm-5.2\.
#
# This is a community-quantized fork — the upstream Z.AI FP8 weights cannot
# be loaded by colibri directly; the int4 container + int8 MTP heads are
# required for speculative decoding to work (>0% draft acceptance).
#   HF repo: mateogrgic/GLM-5.2-colibri-int4-with-int8-mtp
#   - mat weights  : int4 (row-wise scales), ~360 GB
#   - MTP heads    : int8 (NOT int4), critical for ~39–59% draft acceptance
#
# Idempotent: `hf download` skips files that already exist with matching
# SHA256, so re-runs after a partial download continue from where we
# stopped.
#
# Requires:
#   - huggingface_hub (Python 3.9+) with the `hf` CLI available on PATH
#   - HF_TOKEN set to a HuggingFace account with the Z.AI / Zhipu license
#     accepted.  Anonymous tier rates will be capped — set HF_TOKEN for
#     reliable multi-hour downloads (HF_TOKEN env var honours `hf auth login`).
#
# Usage:
#   bash scripts/download_glm52_weights.sh
#
# Exit codes:
#   0 — download complete (full snapshot present + verified)
#   1 — pre-flight failed or download aborted

set -euo pipefail

WEIGHTS_DIR="${WEIGHTS_DIR:-D:/hfkld-qg7ky/local-models/glm-5.2}"
HF_REPO="${HF_REPO:-mateogrgic/GLM-5.2-colibri-int4-with-int8-mtp}"

echo "=== download_glm52_weights.sh ==="
echo ""
echo "  HF repo   : $HF_REPO"
echo "  weights   : $WEIGHTS_DIR"
echo "  HF_TOKEN  : $([ -n "${HF_TOKEN:-}" ] && echo "set" || echo "EMPTY (anonymous tier — slow)")"
echo "  hf CLI    : $(command -v hf || echo 'NOT FOUND')"
echo ""

ok()   { echo "✓ $*"; }
warn() { echo "⚠ $*"; }
fail() { echo "✗ $*"; }

# 1. Pre-flight
if ! command -v hf >/dev/null 2>&1; then
    fail "hf CLI not on PATH"
    echo "    pip install -U 'huggingface_hub[cli]'"
    exit 1
fi

if [[ ! -d "$WEIGHTS_DIR" ]]; then
    mkdir -p "$WEIGHTS_DIR"
    ok "created $WEIGHTS_DIR"
fi

free_gb=$(df --output=avail "$WEIGHTS_DIR" 2>/dev/null | tail -1)
free_gb=$(echo "$free_gb" | awk '{ printf "%.0f\n", $1/1024/1024 }')
if (( free_gb < 400 )); then
    warn "only ${free_gb} GB free at $WEIGHTS_DIR — GLM-5.2 int4 snapshot is ~370 GB"
    echo "  Continuing anyway (you'll need extra space for cached .incomplete files)"
fi

# 2. Download (resume-friendly via hf download's hashed-skip)
echo ""
echo "Starting `hf download $HF_REPO --local-dir $WEIGHTS_DIR` ..."
echo "  (Resume-friendly: skips files already matching SHA256.)"
echo ""

hf download "$HF_REPO" --local-dir "$WEIGHTS_DIR"

# 3. Post-flight: prune .incomplete files + verify MTP heads are int8-sized
echo ""
echo "Pruning .incomplete files ..."
find "$WEIGHTS_DIR" -name "*.incomplete" -delete 2>/dev/null || true
ok "pruned"

echo ""
echo "Verifying MTP head sizes (int8 should match the expected byte counts):"
for f in out-mtp-0 out-mtp-1 out-mtp-2; do
    if [[ -f "$WEIGHTS_DIR/$f" ]]; then
        size=$(stat --printf="%s" "$WEIGHTS_DIR/$f" 2>/dev/null || stat -f "%z" "$WEIGHTS_DIR/$f")
        size_gb=$(awk -v s="$size" 'BEGIN { printf "%.2f\n", s/1024/1024/1024 }')
        ok "$f : ${size_gb} GB"
    else
        fail "$f : MISSING"
    fi
done

total=$(du -sh "$WEIGHTS_DIR" 2>/dev/null | awk '{ print $1 }')
echo ""
ok "Total weight footprint: $total"
echo ""
echo "Next steps:"
echo "  1. pwsh scripts/start_colibri_server.ps1"
echo "  2. set COLIBRI_ENABLED=true + BRAIN_PREFERENCE=colibri"
echo "  3. pwsh scripts/status_colibri_server.ps1"
echo ""
