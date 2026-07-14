#!/usr/bin/env pwsh
# scripts/start_colibri_server.ps1 — Start `coli serve` (Python wrapper around glm.exe)
# in the background.
#
# Usage:
#   pwsh scripts/start_colibri_server.ps1
#
# What it does:
#   1. Verifies the colibri build artifacts are present:
#        - D:\hfkld-qg7ky\local-models\colibri\c\glm.exe     (the C engine)
#        - D:\hfkld-qg7ky\local-models\colibri\c\coli        (Python wrapper script)
#        - D:\hfkld-qg7ky\local-models\colibri\c\openai_server.py  (OAI-compat gateway)
#   2. Verifies the GLM-5.2 weights are present (D:\hfkld-qg7ky\local-models\glm-5.2\).
#   3. Writes .colibri.pid + spawns `python c/coli serve --serve-port <Port>
#      --model-dir <Weights>` in the background, redirecting stdout/stderr to
#      .colibri.log / .colibri.log.err. The python wrapper transparently invokes
#      glm.exe + openai_server.py.
#
# Idempotent — if .colibri.pid points at a live python process running c/coli,
# exits 0 with status. Also respects env overrides:
#   COLIBRI_PORT, COLIBRI_MODEL_DIR, COLIBRI_LOG.
#
# Exit codes:
#   0 — coli serve running on :8081
#   1 — prerequisite missing or start failed

[CmdletBinding()]
param(
    [string] $WeightsDir = "D:\hfkld-qg7ky\local-models\glm-5.2",
    [string] $ColibriDir = "D:\hfkld-qg7ky\local-models\colibri",
    [int]    $Port       = 8081
)

$ErrorActionPreference = "Stop"
function W($msg) { Write-Host $msg }
function Ok($msg) { W "✓ $msg" }
function Warn($msg) { W "⚠ $msg" -ForegroundColor Yellow }
function Fail($msg) { W "✗ $msg" -ForegroundColor Red }

# Allow env overrides (so this script also runs under bash + WSL patterns)
if ($env:COLIBRI_PORT) { $Port = [int]$env:COLIBRI_PORT }
if ($env:COLIBRI_MODEL_DIR) { $WeightsDir = $env:COLIBRI_MODEL_DIR }

$ColiScript = Join-Path $ColibriDir "c/coli"
$PidFile     = Join-Path $ColibriDir ".colibri.pid"
$LogFile     = Join-Path $ColibriDir ".colibri.log"

W ""
W "=== start_colibri_server.ps1 ==="
W ""

# 1. Verify colibri is built (the C engine GLM-5.2 wrapper `c/coli` is a Python script that
#    spawns `c/glm.exe` + the openai_server.py OAI-compat gateway). Both must exist.
$ColiEngine = Join-Path $ColibriDir "c/glm.exe"
$ColiOpenAi = Join-Path $ColibriDir "c/openai_server.py"
if (-not (Test-Path $ColiEngine)) {
    Fail "glm.exe not found at $ColiEngine"
    W "  Run: pwsh scripts/setup_colibri.ps1 (will produce c\glm.exe)"
    exit 1
}
if (-not (Test-Path $ColiScript)) {
    Fail "coli wrapper not found at $ColiScript"
    W "  This is a Python script shipped in the colibri repo. Re-clone if missing:"
    W "    pwsh scripts/setup_colibri.ps1 -ColibriRepo https://github.com/JustVugg/colibri.git"
    exit 1
}
if (-not (Test-Path $ColiOpenAi)) {
    Fail "openai_server.py not found at $ColiOpenAi"
    W "  Re-clone colibri (it ships with the OAI-compat gateway)."
    exit 1
}
Ok "glm.exe: $ColiEngine"
Ok "c/coli (python wrapper): $ColiScript"
Ok "c/openai_server.py: $ColiOpenAi"

# 2. Verify weights present
if (-not (Test-Path $WeightsDir)) {
    Fail "weights dir not found at $WeightsDir"
    W "  Run: pwsh scripts/download_glm52_weights.ps1"
    exit 1
}
$freeSpace = (Get-PSDrive (Split-Path $WeightsDir -Qualifier).TrimEnd(':')).Free / 1GB
W "  weights dir: $WeightsDir  (free space: $([math]::Round($freeSpace, 1)) GB)"
if ($freeSpace -lt 100) {
    Warn "Less than 100 GB free. coli needs the full expert set on disk to serve."
    $ok = Read-Host "Continue anyway? [y/N]"
    if ($ok -ne 'y') { exit 1 }
}

# 3. Idempotency check: is a previous .colibri.pid alive?
if (Test-Path $PidFile) {
    $oldPid = Get-Content $PidFile -ErrorAction SilentlyContinue
    if ($oldPid -and (Get-Process -Id $oldPid -ErrorAction SilentlyContinue | Select-Object -First 1) -and
        (Get-Process -Id $oldPid).ProcessName -match '^python') {
        Ok "coli (python wrapper) already running as PID $oldPid"
        W "  log: $LogFile"
        exit 0
    } else {
        Warn "Stale pidfile at $PidFile (pid $oldPid not alive). Removing."
        Remove-Item $PidFile -Force -ErrorAction SilentlyContinue
    }
}

# 4. Spawn the python `coli` wrapper on serve mode (it loads glm.exe internally
#    to expose an OpenAI-compat HTTP gateway on $Port).
#    If the local build uses different flags, inspect with:
#       python $ColiScript --help
#       python $ColiScript serve --help
#    and update $argList below accordingly. Common aliases: --port (single-dash),
#    --model/--weights (drop-in for --model-dir) in some colibri forks.
W ""
W "Spawning c\\coli (python) on port $Port (model dir $WeightsDir) ..."
W "  log: $LogFile"

$argList = @(
    $ColiScript,
    "serve",
    "--serve-port",  "$Port",
    "--model-dir",   "$WeightsDir"
)
$proc = Start-Process -FilePath "python" `
                     -ArgumentList $argList `
                     -RedirectStandardOutput $LogFile `
                     -RedirectStandardError  "$LogFile.err" `
                     -WorkingDirectory (Split-Path $ColiScript -Parent) `
                     -PassThru -WindowStyle Hidden -CreateNoWindow

if (-not $proc) {
    Fail "Start-Process did not return a process handle"
    exit 1
}
Set-Content -Path $PidFile -Value $proc.Id -NoNewline
W "Started coli (python wrapper, PID $($proc.Id))"

# 5. Wait up to 60s for HTTP /v1/models to respond
$healthUrl = "http://localhost:${Port}/v1/models"
$ok = $false
for ($i = 0; $i -lt 60; $i++) {
    Start-Sleep -Seconds 1
    try {
        $resp = Invoke-WebRequest -Uri $healthUrl -UseBasicParsing -TimeoutSec 2
        if ($resp.StatusCode -lt 500) {
            $ok = $true
            break
        }
    } catch { }
}
if ($ok) {
    Ok "coli serve responding on $healthUrl"
} else {
    Warn "coli started but did not respond on $healthUrl within 60s — usually means"
    W "  experts are still streaming from disk or the model dir is wrong. Check:"
    W "    cat $LogFile | tail -30"
    W "    cat $LogFile.err | tail -30"
}
W ""
W "Wire the agency brain:"
W "  set COLIBRI_ENABLED=true"
W "  set COLIBRI_URL=http://localhost:${Port}/v1"
W "  set BRAIN_PREFERENCE=colibri"
W ""
W "Stop with:  pwsh scripts/stop_colibri_server.ps1"
