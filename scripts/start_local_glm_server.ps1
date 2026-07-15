# scripts/start_local_glm_server.ps1 — start llama-server.exe serving GLM-5.2.
#
# Called by scripts/local_controller.py when the operator flips the toggle to ON
# on the Cloudflare providers page. Writes the llama-server PID to
# logs\local_brain.pid so the controller can:
#   - probe liveness with `tasklist /FI "PID eq <pid>"`
#   - kill cleanly with `taskkill /PID <pid> /T /F` (the /T flag frees VRAM
#     and the bound TCP port 8072 — without it the next start will fail with
#     WSAEADDRINUSE because the orphaned child keeps the port open)
#
# Defaults match the operator's setup at D:\hfkld-qg7ky\local-models\. Override
# any value via -BinaryPath, -ModelPath, -Port, -ModelId, -ContextSize,
# -Threads, -GpuLayers.
#
# Idempotency: if a live llama-server is already on the requested port, the
# script exits 0 with "already running" so concurrent toggles are safe.
#
# Errors:
#   exit 2  binary missing
#   exit 3  model file missing
#   exit 4  port already bound by a DIFFERENT process (operator must kill it)
#   exit 5  llama-server died within 5s of start (probably OOM / VRAM)
[CmdletBinding()]
param(
    [string]$BinaryPath  = "D:\hfkld-qg7ky\local-models\llama.cpp\build\bin\Release\llama-server.exe",
    [string]$ModelPath   = "D:\hfkld-qg7ky\local-models\GLM-5.2\glm-5.2-instruct-Q4_K_M.gguf",
    [int]   $Port        = 8072,
    [string]$ModelId     = "glm-5.2",
    [int]   $ContextSize = 8192,
    [int]   $Threads     = 8,
    [int]   $GpuLayers   = 99,
    [string]$LogDir      = "C:\Users\swami\qwen-server\logs",
    [string]$ExeLog      = "C:\Users\swami\qwen-server\logs\local_brain-llama-server.log",
    [int]   $ReadyTimeoutSec = 30
)

$ErrorActionPreference = "Stop"

# ── Preflight: ensure directories / log files exist ────────────────────────
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}
$PidFile = Join-Path $LogDir "local_brain.pid"
$LogFile = $ExeLog

# ── Preflight: binary ─────────────────────────────────────────────────────
if (-not (Test-Path $BinaryPath)) {
    Write-Error "FATAL binary missing at $BinaryPath. Open llama.cpp README (https://github.com/ggml-org/llama.cpp) and build with -DBUILD_SHARED_LIBS=OFF then add D:\hfkld-qg7ky\local-models\llama.cpp\build\bin\Release to PATH."
    exit 2
}

# ── Preflight: model file ────────────────────────────────────────────────
if (-not (Test-Path $ModelPath)) {
    Write-Error "FATAL model file missing at $ModelPath. Pull glm-5.2 Q4_K_M (huggingface: openai/glm-5.2 or unsloth/glm-5.2-GGUF) and place it at the expected path."
    exit 3
}

# ── Idempotency: if a previous PID is live, leave it alone ────────────────
if (Test-Path $PidFile) {
    $existing = (Get-Content $PidFile -Raw -ErrorAction SilentlyContinue).Trim()
    if ($existing -and $existing -match '^\d+$') {
        $running = (Get-Process -Id ([int]$existing) -ErrorAction SilentlyContinue)
        if ($running -and $running.ProcessName -like 'llama-server*') {
            Write-Output ("already running pid=" + $existing + " port=" + $Port)
            exit 0
        }
    }
}

# ── Port-in-use check (allow self-replacement) ────────────────────────────
$portBusy = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
if ($portBusy) {
    Write-Error ("FATAL port " + $Port + " already bound by pid=" + $portBusy.OwningProcess + ". Run scripts/stop_local_glm_server.ps1 first or pick a different -Port.")
    exit 4
}

# ── Launch llama-server.exe ───────────────────────────────────────────────
$llamaArgs = @(
    "-m", $ModelPath,
    "--port", $Port.ToString(),
    "--host", "127.0.0.1",
    "-c", $ContextSize.ToString(),
    "-t", $Threads.ToString(),
    "-ngl", $GpuLayers.ToString(),
    "--alias", $ModelId,
    "--jinja",
    "--no-display-prompt"
) | ForEach-Object { [System.Diagnostics.Process]::Start }

# Build the full command line as a single string for clarity in the log
$argList = ($llamaArgs -join ' ')
Write-Output ("starting: " + $BinaryPath + " " + $argList)

try {
    $proc = Start-Process -FilePath $BinaryPath -ArgumentList $argList `
        -NoNewWindow -RedirectStandardOutput $LogFile -RedirectStandardError (Join-Path $LogDir "local_brain-llama-server.err.log") `
        -PassThru
} catch {
    Write-Error ("FATAL llama-server launch failed: " + $_.Exception.Message)
    exit 5
}

# ── Write PID file immediately so the controller can watch liveness ───────
$proc.Id | Out-File -FilePath $PidFile -Encoding ascii -NoNewline

Write-Output ("started pid=" + $proc.Id + " — waiting for /v1/models readiness…")

# ── Poll /v1/models until ready (or timeout) ──────────────────────────────
$deadline = (Get-Date).AddSeconds($ReadyTimeoutSec)
$ready = $false
while ((Get-Date) -lt $deadline) {
    Start-Sleep -Seconds 2
    try {
        # Use a TCP probe first (faster) before trusting the HTTP call against
        # a server that's still bootstrapping SafeTensors mmap.
        $tcp = New-Object System.Net.Sockets.TcpClient
        $iar = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(500)
        if ($ok) {
            $tcp.EndConnect($iar)
            $tcp.Close()
            # Now the HTTP probe — try /v1/models and check for $ModelId
            try {
                $resp = Invoke-WebRequest -Uri "http://127.0.0.1:${Port}/v1/models" -UseBasicParsing -TimeoutSec 5
                if ($resp.StatusCode -eq 200 -and ($resp.Content -match [regex]::Escape($ModelId))) {
                    $ready = $true
                    break
                }
            } catch {
                # Server still loading — keep waiting
            }
        } else {
            $tcp.Close()
        }
    } catch {
        # Port not bound yet — keep waiting
    }
    # Did the process die unexpectedly?
    if ($proc.HasExited) {
        Write-Error ("FATAL llama-server exited code=" + $proc.ExitCode + " within " + $ReadyTimeoutSec + "s. Check $LogFile for details.")
        Remove-Item -Path $PidFile -ErrorAction SilentlyContinue
        exit 5
    }
}

if (-not $ready) {
    Write-Warning ("timed out waiting for /v1/models after " + $ReadyTimeoutSec + "s — llama-server may still be loading. PID file retained so the controller can probe it on the next tick.")
}

Write-Output ("ready port=" + $Port + " pid=" + $proc.Id + " glmmodel=" + $ModelId + " — exiting 0")
exit 0
