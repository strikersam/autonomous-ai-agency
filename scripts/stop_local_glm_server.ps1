# scripts/stop_local_glm_server.ps1 — kill the local llama-server.exe (cross-process-tree).
#
# Called by scripts/local_controller.py when:
#   - the operator flipped the toggle to OFF on the cloud providers page
#   - the local probe detected a stale llama-server (still listening but no
#     glm-5.2 in /v1/models) and the controller is restarting it
#
# TASKKILL /T /F is non-negotiable on Windows: the parent llama-server.exe
# forks worker processes for matmul/tokenization, and without /T the parent
# exits but the workers keep holding the GPU context (VRAM not freed) AND
# the TCP port stays bound so the next start fails with WSAEADDRINUSE.
#
# Idempotency: if no pidfile OR the recorded PID is already gone, exit 0.
#
# Exit codes:
#   0  killed (or already gone)
#   1  partial kill (workers remained) — operator should check VRAM
[CmdletBinding()]
param(
    [string]$LogDir = "C:\Users\swami\qwen-server\logs",
    [int]   $KillTimeoutSeconds = 15
)

$ErrorActionPreference = "Stop"

$PidFile = Join-Path $LogDir "local_brain.pid"
$Port = 8072  # default llama-server port — used as a fallback if pidfile is empty

if (-not (Test-Path $PidFile)) {
    # No pidfile. Try a port-based fallback kill.
    Write-Output "no pidfile — falling back to port scan on $Port"
    $busy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    if ($busy) {
        foreach ($conn in $busy) {
            $targetPid = $conn.OwningProcess
            Write-Output ("taskkill /PID " + $targetPid + " /T /F")
            & taskkill /PID $targetPid /T /F 2>&1 | Out-Null
        }
    }
    exit 0
}

$pidRaw = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
if (-not $pidRaw -or -not ($pidRaw -match '^\d+$')) {
    Write-Output "pidfile empty/corrupt — clearing"
    Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
    exit 0
}

$pid = [int]$pidRaw
$live = Get-Process -Id $pid -ErrorAction SilentlyContinue
if (-not $live) {
    Write-Output ("pid " + $pid + " already gone — clearing pidfile")
    Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
    exit 0
}

# Initial kill attempt
Write-Output ("taskkill /PID " + $pid + " /T /F")
& taskkill /PID $pid /T /F 2>&1 | Out-Null

# Poll for actual exit (taskkill returns 0 even if a worker refused to die)
$deadline = (Get-Date).AddSeconds($KillTimeoutSeconds)
$gone = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 1
    $still = Get-Process -Id $pid -ErrorAction SilentlyContinue
    if (-not $still) {
        $gone = $true
        break
    }
}

Remove-Item -Path $PidFile -ErrorAction SilentlyContinue

if ($gone) {
    Write-Output ("stopped pid=" + $pid)
    exit 0
}

Write-Error ("WARN pid=" + $pid + " still alive after " + $KillTimeoutSeconds + "s — check VRAM (nvidia-smi) and pslist for orphans.")
exit 1
