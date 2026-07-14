#!/usr/bin/env pwsh
# scripts/stop_colibri_server.ps1 — Stop `coli serve` started by
# scripts/start_colibri_server.ps1. Reads PID from .colibri.pid, sends
# graceful CloseMainWindow then escalates to /F force kill if needed.

[CmdletBinding()]
param(
    [string] $ColibriDir = "D:\hfkld-qg7ky\local-models\colibri",
    [int]    $GracefulWaitSec = 10
)

$ErrorActionPreference = "Stop"
function W($msg) { Write-Host $msg }
function Ok($msg) { W "✓ $msg" }
function Fail($msg) { W "✗ $msg" -ForegroundColor Red }

$PidFile = Join-Path $ColibriDir ".colibri.pid"

W ""
W "=== stop_colibri_server.ps1 ==="
W ""

if (-not (Test-Path $PidFile)) {
    Warn "No pidfile at $PidFile — coli was not started by this script (or it crashed)."
    W "  Falling back to WMI: any python*.exe whose CommandLine references the coli wrapper."
    # Match both `python.exe` and `pythonw.exe` (windowless Python some operators prefer
    # for headless servers). Operators with non-canonical install paths should restart
    # via this script so the pidfile is written cleanly.
    $proc = Get-CimInstance Win32_Process -Filter "Name LIKE 'python%.exe'" -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -and ($_.CommandLine -match [regex]::Escape((Join-Path $ColibriDir "c/coli"))) } |
        Select-Object -First 1
    if ($proc) {
        W "  found python wrapper PID $($proc.ProcessId) (image: $($proc.Name)) — killing."
        Stop-Process -Id $proc.ProcessId -Force
        Ok "stopped"
    } else {
        W "  no coli (python) process found. Nothing to stop."
    }
    exit 0
}

$pidStr = Get-Content $PidFile -Raw
$pid = 0
if (-not [int]::TryParse($pidStr.Trim(), [ref]$pid)) {
    Fail "pidfile contents are not numeric: '$pidStr'. Removing and bailing."
    Remove-Item $PidFile -Force
    exit 1
}
$proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
if (-not $proc) {
    Warn "PID $pid not alive — pidfile is stale. Removing."
    Remove-Item $PidFile -Force
    exit 0
}
if ($proc.ProcessName -notmatch '^python') {
    Warn "PID $pid is now running '$($proc.ProcessName)', not 'python' (coli wrapper). Removing stale pidfile."
    Remove-Item $PidFile -Force
    exit 0
}

W "Stopping coli (python wrapper, PID $pid) gracefully..."
try {
    Stop-Process -Id $pid -ErrorAction Stop
} catch {
    W "  graceful stop failed: $_"
    W "  escalating to force kill..."
    Stop-Process -Id $pid -Force
}

# Wait for graceful exit
$alive = $true
for ($i = 0; $i -lt $GracefulWaitSec; $i++) {
    Start-Sleep -Seconds 1
    $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if (-not $proc) { $alive = $false; break }
}
if ($alive) {
    Warn "PID $pid still alive after ${GracefulWaitSec}s — force-killing."
    Stop-Process -Id $pid -Force
} else {
    Ok "stopped cleanly"
}
Remove-Item $PidFile -Force -ErrorAction SilentlyContinue

# Verify port 8081 is free
try {
    $port = Get-NetTCPConnection -LocalPort 8081 -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($port) {
        Warn "Port 8081 still bound by PID $($port.OwningProcess) — likely a child process."
    } else {
        Ok "port 8081 is free"
    }
} catch { }
