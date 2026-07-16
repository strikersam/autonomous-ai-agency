#requires -Version 5.1
<#
Colibri GLM-5.2 local-brain launcher (JustVugg/colibri).

Architecture discovered via live diagnostics:
  * c/coli serve         -> model runner (NO HTTP listener)
  * c/openai_server.py   -> OAI-compat HTTP bridge; itself spawns `c/coli serve` as subprocess via --engine flag
  * Single-process correct invocation: python c/openai_server.py --engine coli --port 28081 --host 127.0.0.1 --model <weights> --model-id glm-5.2
  * Watchdog polls /v1/models until HTTP 200, then exits 0.

Port 28081 chosen to dodge Windows Hyper-V dynamic-port + bind-permission reserved ranges
(observed WinError 10013 on earlier 8081 attempts). .env COLIBRI_LOCAL_LLAMA_URL must match.

Flag map verified against `python c/openai_server.py --help`:
  --engine         subprocess to spawn (we pass 'coli' so it runs `c/coli serve` internally)
  --port, --host   OAI-compat listener
  --model          weights directory
  --model-id       the model name advertised by /v1/models
  --api-key        optional auth (unset = open)
  --cors-origin    CORS (use * for local dev)
  --cap, --ctx-size, --gpu-layers are forwarded to the engine if present
#>

$ErrorActionPreference = "Stop"

$ScriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$ColibriRoot     = "D:\hfkld-qg7ky\local-models\colibri"
$ColibriCDir     = Join-Path $ColibriRoot "c"
$WeightsDir      = "D:\hfkld-qg7ky\local-models\glm-5.2"
$Port            = 28081
$Host            = "127.0.0.1"
$ModelId         = "glm-5.2"
$LogDir          = "C:\Users\swami\qwen-server\logs"
$LogFile         = Join-Path $LogDir "colibri-openai.log"
$ErrFile         = Join-Path $LogDir "colibri-openai-err.log"
$ReadyUrl        = "http://localhost:$Port/v1/models"
$PollSeconds     = 5
$MaxWaitSeconds  = 600  # 10 minutes (operator typically kicks this off after HUD startup)

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Force -Path $LogDir | Out-Null }

function Kill-PriorColibri {
    Get-Process python -ErrorAction SilentlyContinue |
        Where-Object { $_.CommandLine -match 'coli|colibri|openai_server' } |
        ForEach-Object {
            try { Stop-Process -Id $_.Id -Force -ErrorAction Stop; Write-Host "Killed PID $($_.Id)" }
            catch { Write-Host "Kill failed for PID $($_.Id): $_" }
        }
}

Write-Host "[colibri] killing prior colibri procs (if any)"
Kill-PriorColibri
Start-Sleep -Seconds 2

# Launch ONE process: openai_server.py --engine coli
$PythonExe = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $PythonExe) { $PythonExe = "python" }

$Args = @(
    "c/openai_server.py",
    "--engine", "coli",
    "--model",  $WeightsDir,
    "--model-id", $ModelId,
    "--port",   $Port,
    "--host",   $Host,
    "--cors-origin", "*"
)

Write-Host "[colibri] launching: $PythonExe $($Args -join ' ')"
Write-Host "[colibri] logs: $LogFile (stdout), $ErrFile (stderr)"

# Use a single Start-Process call so logs are durably captured.
$Proc = Start-Process -FilePath $PythonExe `
    -ArgumentList $Args `
    -WorkingDirectory $ColibriCDir `
    -RedirectStandardOutput $LogFile `
    -RedirectStandardError  $ErrFile `
    -NoNewWindow `
    -PassThru
Write-Host "[colibri] openai_server.py PID=$($Proc.Id)"

# Watchdog loop -- probe /v1/models until 200, then exit 0
$Deadline = (Get-Date).AddSeconds($MaxWaitSeconds)
$LastStatus = $null
while ((Get-Date) -lt $Deadline) {
    try {
        $Resp = Invoke-WebRequest -Uri $ReadyUrl -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        Write-Host "[colibri] /v1/models -> HTTP $($Resp.StatusCode) at $(Get-Date -Format 'HH:mm:ss')"
        if ($Resp.StatusCode -eq 200) {
            Write-Host "[colibri] READY. Listening on http://$Host`:$Port/v1"
            exit 0
        }
    } catch {
        $LastStatus = $_
        $Msg = $_.Exception.Message
        if ($Msg.Length -gt 120) { $Msg = $Msg.Substring(0,120) + '...' }
        Write-Host "[colibri] /v1/models not ready: $Msg"
    }
    Start-Sleep -Seconds $PollSeconds
}

Write-Error "[colibri] watchdog timed out after $MaxWaitSeconds seconds. See $ErrFile"
exit 1
