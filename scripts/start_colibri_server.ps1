#requires -Version 5.1
<#
Colibri GLM-5.2 local-brain launcher (JustVugg/colibri).

Architecture discovered via live diagnostics:
  * c/glm.exe             -> Windows PE32+ engine binary (extensionless `c/glm` does NOT work because Windows Popen uses PATHEXT for .exe resolution)
  * c/openai_server.py   -> OAI-compat HTTP bridge; spawns the engine as subprocess via --engine flag
  * WorkingDirectory must be $ColibriRoot (so 'c/openai_server.py' and 'c/glm.exe' resolve naturally)
  * Single-process correct invocation:
       python c/openai_server.py --engine c/glm.exe --port 8081 --host 127.0.0.1 --model $Env:COLIBRI_WEIGHTS_DIR --model-id glm-5.2
  * Watchdog polls /v1/models until HTTP 200, then exits 0.

Port defaults to 8081 to match the documented COLIBRI_LOCAL_LLAMA_URL in .env.example;
override with $Env:COLIBRI_LOCAL_LLAMA_PORT if needed. All paths come from $Env:COLIBRI_*
with operator-portable fallbacks; no literal D:\... paths anywhere.

KNOWN ISSUE: openai_server.py (JustVugg upstream) Engine.__init__ runs
  `Popen([str(executable), str(cap)])`
and discards --model --port --host --model-id. So even with the --engine fix here,
glm.exe will not receive the model path; see NEXT_ACTION.md for the upstream patch plan.

Flag map verified against `python c/openai_server.py --help`:
  --engine         path to engine binary (we pass 'c/glm.exe' resolved relative to $ColibriRoot)
  --port, --host   OAI-compat listener
  --model          weights directory
  --model-id       the model name advertised by /v1/models
  --api-key        optional auth (unset = open)
  --cors-origin    CORS (use * for local dev)
  --cap, --ctx-size, --gpu-layers are forwarded to the engine if present
#>

$ErrorActionPreference = "Stop"

$ScriptDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$ColibriRoot     = if ($env:COLIBRI_ROOT)         { $env:COLIBRI_ROOT }     else { Join-Path (Split-Path $ScriptDir -Parent) 'colibri' }
$ColibriCDir     = if ($env:COLIBRI_C_DIR)        { $env:COLIBRI_C_DIR }    else { Join-Path $ColibriRoot 'c' }
$WeightsDir      = if ($env:COLIBRI_WEIGHTS_DIR)  { $env:COLIBRI_WEIGHTS_DIR } else { Join-Path (Split-Path $ScriptDir -Parent) 'glm-5.2' }
if ($env:COLIBRI_LOCAL_LLAMA_PORT -and $env:COLIBRI_LOCAL_LLAMA_PORT -match '^\d+$') {
    $Port = [int]$env:COLIBRI_LOCAL_LLAMA_PORT
} else {
    if ($env:COLIBRI_LOCAL_LLAMA_PORT) { Write-Warning "[colibri] COLIBRI_LOCAL_LLAMA_PORT='$env:COLIBRI_LOCAL_LLAMA_PORT' is not an integer; using default 8081" }
    $Port = 8081
}
$BindHost        = if ($env:COLIBRI_HOST)         { $env:COLIBRI_HOST }     else { '127.0.0.1' }
$ModelId         = if ($env:COLIBRI_LOCAL_LLAMA_MODEL) { $env:COLIBRI_LOCAL_LLAMA_MODEL } else { 'glm-5.2' }
$LogDir          = if ($env:COLIBRI_LOG_DIR)      { $env:COLIBRI_LOG_DIR }  else { Join-Path $ScriptDir '..\logs' }
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
    "--engine", "c/glm.exe",
    "--model",  $WeightsDir,
    "--model-id", $ModelId,
    "--port",   $Port,
    "--host",   $BindHost,
    "--cors-origin", "*"
)

# Pre-flight: $ColibriRoot must exist (it is also our WorkingDirectory).
if (-not (Test-Path $ColibriRoot)) {
    Write-Error "[colibri] COLIBRI_ROOT='$ColibriRoot' not found. Clone JustVugg/colibri there, or override `$env:COLIBRI_ROOT."
    exit 2
}
# Pre-flight: c/glm.exe must exist (Windows PE32+ engine binary; we resolve relative to $ColibriRoot).
$EngineBin = Join-Path $ColibriRoot 'c/glm.exe'
if (-not (Test-Path $EngineBin)) {
    Write-Error "[colibri] engine binary not found at '$EngineBin'. Verify JustVugg/colibri checkout has c/glm.exe, or override `$env:COLIBRI_ENGINE_BIN."
    exit 2
}

Write-Host "[colibri] launching: $PythonExe $($Args -join ' ')"
Write-Host "[colibri] engine binary: $EngineBin"
Write-Host "[colibri] logs: $LogFile (stdout), $ErrFile (stderr)"

# Use a single Start-Process call so logs are durably captured.
$Proc = Start-Process -FilePath $PythonExe `
    -ArgumentList $Args `
    -WorkingDirectory $ColibriRoot `
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
            Write-Host "[colibri] READY. Listening on http://$BindHost`:$Port/v1"
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
