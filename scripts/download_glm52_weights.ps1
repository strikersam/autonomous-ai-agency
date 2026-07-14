#!/usr/bin/env pwsh
# scripts/download_glm52_weights.ps1 — Windows/Download the JustVugg/colibri-format
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
#   - huggingface_hub with the `hf` CLI on PATH
#   - HF_TOKEN set (or in env) — anonymous tier will be rate-limited; the
#     Z.AI / Zhipu license is gated and requires accepting the model card.

[CmdletBinding()]
param(
    [string] $WeightsDir = "D:\hfkld-qg7ky\local-models\glm-5.2",
    [string] $HfRepo     = "mateogrgic/GLM-5.2-colibri-int4-with-int8-mtp"
)

$ErrorActionPreference = "Stop"
function W($msg) { Write-Host $msg }
function Ok($msg) { W "  ✓ $msg" }
function Warn($msg) { W "  ⚠ $msg" -ForegroundColor Yellow }
function Fail($msg) { W "  ✗ $msg" -ForegroundColor Red }

W ""
W "=== download_glm52_weights.ps1 ==="
W ""
W "  HF repo   : $HfRepo"
W "  weights   : $WeightsDir"
W "  HF_TOKEN  : $(if ($env:HF_TOKEN) { 'set' } else { 'EMPTY (anonymous tier — slower)' })"
W ""

# 1. Locate hf CLI
$hf = Get-Command hf -ErrorAction SilentlyContinue
if (-not $hf) {
    Fail "hf CLI not on PATH"
    W "    pip install -U 'huggingface_hub[cli]'"
    exit 1
}
Ok "hf CLI: $($hf.Source) ($(& hf --version 2>&1 | Out-String).Trim())"

# 2. Weights dir
if (-not (Test-Path $WeightsDir)) {
    New-Item -ItemType Directory -Path $WeightsDir -Force | Out-Null
    Ok "created $WeightsDir"
} else {
    Ok "$WeightsDir already present"
}

$free = (Get-PSDrive (Split-Path $WeightsDir -Qualifier).TrimEnd(':')).Free / 1GB
if ($free -lt 400) {
    Warn "only $([math]::Round($free, 1)) GB free at $WeightsDir — GLM-5.2 int4 snapshot is ~370 GB"
    $ok = Read-Host "  Continue anyway? [y/N]"
    if ($ok -ne 'y') { exit 1 }
}

# 3. Run hf download
W ""
W "Starting:  hf download $HfRepo --local-dir $WeightsDir"
W "  (Resume-friendly: skips files already matching SHA256.)"
W ""

& hf download $HfRepo --local-dir $WeightsDir
if ($LASTEXITCODE -ne 0) {
    Fail "`hf download` exited with $LASTEXITCODE"
    W "  Re-run this script to resume — files already on disk are skipped by SHA256."
    exit $LASTEXITCODE
}
Ok "hf download completed"

# 4. Prune .incomplete files
W ""
W "Pruning .incomplete files ..."
Get-ChildItem -Path $WeightsDir -Recurse -Filter "*.incomplete" -ErrorAction SilentlyContinue | ForEach-Object {
    Remove-Item $_.FullName -Force
    W "  removed $($_.FullName)"
}
Ok "pruned"

# 5. Verify MTP heads are int8-sized (3.5 GB / 5.4 GB / 1.1 GB expected)
W ""
W "Verifying MTP head sizes (int8 should match the expected byte counts):"
$expectedSizes = @{
    "out-mtp-0" = 3527131672
    "out-mtp-1" = 5366238584
    "out-mtp-2" = 1065950496
}
foreach ($name in @("out-mtp-0", "out-mtp-1", "out-mtp-2")) {
    $path = Join-Path $WeightsDir $name
    if (Test-Path $path) {
        $size = (Get-Item $path).Length
        $expected = $expectedSizes[$name]
        if ($size -eq $expected) {
            Ok "$name : $([math]::Round($size/1GB,2)) GB (matches int8 expected)"
        } else {
            Warn "$name : $([math]::Round($size/1GB,2)) GB (expected $expected bytes for int8 —"
            W "      got $size. If significantly smaller (~50%), MTP heads were int4-quantized"
            W "      and speculative decoding won't work. Re-pull from $HfRepo only those 3 files.)"
        }
    } else {
        Fail "$name : MISSING"
    }
}

$total = (Get-ChildItem -Recurse -File $WeightsDir | Measure-Object -Property Length -Sum).Sum
W ""
Ok "Total weight footprint: $([math]::Round($total/1GB,1)) GB"
W ""
W "Next steps:"
W "  1. pwsh scripts/start_colibri_server.ps1"
W "  2. set COLIBRI_ENABLED=true + BRAIN_PREFERENCE=colibri"
W "  3. pwsh scripts/status_colibri_server.ps1"
W ""
