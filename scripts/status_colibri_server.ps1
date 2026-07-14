#!/usr/bin/env pwsh
# scripts/status_colibri_server.ps1 — One-shot status snapshot of `coli serve`.
# Reports: pidfile + live-process check, port 8081 listening check, model-dir
# size on disk, last 10 lines of .colibri.log, and Health Check (/v1/models).
#
# Pure reader — never touches the running process.

[CmdletBinding()]
param(
    [string] $ColibriDir = "D:\hfkld-qg7ky\local-models\colibri",
    [string] $WeightsDir = "D:\hfkld-qg7ky\local-models\glm-5.2",
    [int]    $Port       = 8081
)

$ErrorActionPreference = "Stop"
function W($msg) { Write-Host $msg }
function Ok($msg) { W "  ✓ $msg" }
function Warn($msg) { W "  ⚠ $msg" -ForegroundColor Yellow }
function Fail($msg) { W "  ✗ $msg" -ForegroundColor Red }

W ""
W "=== status_colibri_server.ps1 ==="
W ""

# 1. pidfile + live check
$PidFile = Join-Path $ColibriDir ".colibri.pid"
W "PID file: $PidFile"
if (Test-Path $PidFile) {
    $pid = (Get-Content $PidFile -Raw).Trim()
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if ($proc -and $proc.ProcessName -match '^python') {
        Ok "coli (python wrapper) alive as PID $pid"
    } else {
        Warn "pidfile points at $pid but no python process found"
    }
} else {
    Warn "no pidfile — coli was not started by start_colibri_server.ps1 (or the python wrapper exited)"
}

# 2. Listening on port 8081
W ""
W "Port $Port listening:"
$port = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($port) {
    Ok "port $Port is bound by PID $($port.OwningProcess)"
} else {
    Warn "no listener on port $Port"
}

# 3. /v1/models health check
W ""
W "/v1/models health:"
$healthUrl = "http://localhost:${Port}/v1/models"
try {
    $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 5
    if ($resp.StatusCode -eq 200) {
        Ok "$healthUrl → 200"
        $j = $resp.Content | ConvertFrom-Json -ErrorAction SilentlyContinue
        if ($j -and $j.data) {
            W "  models reported: $(@($j.data) | ConvertTo-Json -Depth 4 -Compress)"
        }
    } else {
        Warn "$healthUrl → $($resp.StatusCode)"
    }
} catch {
    Warn "$healthUrl unreachable: $($_.Exception.Message)"
}

# 4. Model dir size
W ""
W "Model dir: $WeightsDir"
if (Test-Path $WeightsDir) {
    $size = (Get-ChildItem -Recurse -File $WeightsDir | Measure-Object -Property Length -Sum).Sum
    $sizeGb = [math]::Round($size / 1GB, 1)
    Ok "$WeightsDir : $sizeGb GB on disk"
    # Per colibri README, total footprint should be ~370 GB at int4. Flag underfill.
    if ($sizeGb -lt 100) {
        Warn "  expected ~370 GB after full download — incomplete. Run scripts/download_glm52_weights.ps1"
    }
} else {
    Warn "model dir does not exist — run scripts/download_glm52_weights.ps1"
}

# 5. Tail of .colibri.log
W ""
$LogFile = Join-Path $ColibriDir ".colibri.log"
W "Last 10 lines of $LogFile :"
if (Test-Path $LogFile) {
    Get-Content $LogFile -Tail 10
} else {
    Warn "no log file yet"
}
W ""
