# One-click launcher - runs the Autonomous AI Agency on the LOCAL Ollama brain.
# Double-click "Start-Local-Agency.cmd" (this file is the PowerShell it calls).
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT
Write-Host "== Autonomous AI Agency - local brain launcher ==" -ForegroundColor Cyan

# -- Load .env ------------------------------------------------------------------
$ENV_FILE = "$ROOT\.env"
if (Test-Path $ENV_FILE) {
    Get-Content $ENV_FILE | Where-Object { $_ -notmatch "^\s*#" -and $_ -match "=" } | ForEach-Object {
        $parts = $_ -split "=", 2
        [System.Environment]::SetEnvironmentVariable($parts[0].Trim(), $parts[1].Trim(), "Process")
    }
    Write-Host "[OK] Loaded .env" -ForegroundColor Green
} else {
    Write-Host "[WARN] .env not found. Copy .env.example to .env and configure it." -ForegroundColor Yellow
    Write-Host "       Using defaults — set OLLAMA_MODELS, API_KEYS, etc. in .env for production use." -ForegroundColor Yellow
}

# -- Configure Ollama model storage ---------------------------------------------
if (-not $env:OLLAMA_MODELS) {
    # Default to the standard model directory used by download_models.ps1
    $defaultModels = "D:\aipc-models"
    if (Test-Path $defaultModels) {
        $env:OLLAMA_MODELS = $defaultModels
    } else {
        Write-Host "[WARN] OLLAMA_MODELS not set and default path ($defaultModels) not found." -ForegroundColor Yellow
        Write-Host "       Run .\download_models.ps1 first, or set OLLAMA_MODELS in .env" -ForegroundColor Yellow
    }
}
if ($env:OLLAMA_MODELS) {
    Write-Host "[OK] Model storage: $env:OLLAMA_MODELS" -ForegroundColor Gray
}

# Standard Ollama host
if (-not $env:OLLAMA_HOST) { $env:OLLAMA_HOST = "127.0.0.1:11434" }

# -- 1) Ensure Ollama is serving ------------------------------------------------
$ollamaUp = $false
try { Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 2 | Out-Null; $ollamaUp = $true } catch {}
if (-not $ollamaUp) {
    Write-Host "[1/4] Starting Ollama..." -ForegroundColor Cyan
    
    # Resolve ollama executable — respect OLLAMA_EXE from .env, then try desktop app, then PATH
    $ollamaExe = $env:OLLAMA_EXE
    if (-not $ollamaExe -or -not (Test-Path $ollamaExe)) {
        $desktopApp = "$env:LOCALAPPDATA\Programs\Ollama\ollama app.exe"
        if (Test-Path $desktopApp) {
            $ollamaExe = $desktopApp
        } else {
            $found = Get-Command ollama -ErrorAction SilentlyContinue
            if ($found) { $ollamaExe = $found.Source }
        }
    }
    
    if (-not $ollamaExe) {
        Write-Host "[FAIL] Ollama not found. Install from https://ollama.com or set OLLAMA_EXE in .env" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }
    
    # Start it: desktop app doesn't take arguments; CLI needs "serve"
    if ($ollamaExe -match "ollama app\.exe$") {
        Start-Process $ollamaExe
    } else {
        Start-Process $ollamaExe -ArgumentList "serve" -WindowStyle Hidden
    }
    
    Write-Host "  Waiting for Ollama..." -ForegroundColor Gray
    for ($i=0; $i -lt 60; $i++) {
        Start-Sleep 1
        try { Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 2 | Out-Null; $ollamaUp=$true; break } catch {}
    }
}
if (-not $ollamaUp) {
    Write-Host "[FAIL] Ollama did not start. Open the Ollama app from the Start menu, then re-run this launcher." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Ollama serving local models" -ForegroundColor Green
try {
    $tagsResp = Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 3
    $tagsResp.models | ForEach-Object { Write-Host "     - $($_.name)" -ForegroundColor Gray }
} catch {}

# -- 2) Resolve Python ---------------------------------------------------------
Write-Host "[2/4] Resolving Python..." -ForegroundColor Cyan
$py = $env:PYTHON_EXE
if (-not $py) {
    if (Test-Path "$ROOT\.venv\Scripts\python.exe") {
        $py = "$ROOT\.venv\Scripts\python.exe"
    } else {
        $found = Get-Command python -ErrorAction SilentlyContinue
        if (-not $found) { $found = Get-Command python3 -ErrorAction SilentlyContinue }
        if ($found) { $py = $found.Source }
    }
}
if (-not $py) {
    Write-Host "[FAIL] Python not found. Set PYTHON_EXE in .env or install Python 3." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}
Write-Host "[OK] Python: $py" -ForegroundColor Gray

# -- 3) Configure backend environment -------------------------------------------
# RUN_BACKGROUND_IN_WEB runs CEO/dispatch/self-heal loops inside the web process
if (-not $env:RUN_BACKGROUND_IN_WEB) { $env:RUN_BACKGROUND_IN_WEB = "true" }

# Port for the backend (default 8001)
$backendPort = if ($env:PORT) { $env:PORT } else { "8001" }

# -- 4) Start the agency backend ------------------------------------------------
Write-Host "[3/4] Starting agency backend on http://localhost:$backendPort ..." -ForegroundColor Cyan
Start-Process $py -ArgumentList "-m","uvicorn","backend.server:app","--host","127.0.0.1","--port",$backendPort -WorkingDirectory $ROOT -WindowStyle Minimized
$up=$false
for ($i=0; $i -lt 90; $i++) {
    Start-Sleep 1
    try { Invoke-RestMethod "http://localhost:$backendPort/api/doctor/public" -TimeoutSec 2 | Out-Null; $up=$true; break } catch {}
}
if ($up) {
    Write-Host "[OK] Backend healthy" -ForegroundColor Green
} else {
    Write-Host "[WARN] Backend slow to start — check the minimized Python window." -ForegroundColor Yellow
}

# -- 5) Kick the autonomy cycle -------------------------------------------------
Write-Host "[4/4] Triggering autonomy cycle..." -ForegroundColor Cyan
try {
    Invoke-RestMethod "http://localhost:$backendPort/api/autonomy/status" -TimeoutSec 60 | Out-Null
} catch {
    Write-Host "[WARN] Autonomy status endpoint not reachable — backend may still be starting." -ForegroundColor Yellow
}

# Open the dashboard
Start-Process "http://localhost:$backendPort/"

Write-Host ""
Write-Host "Agency is running on the LOCAL brain. Background loops keep working while this stays up." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:$backendPort/   |   Stop: close the Python backend window (or kill via Task Manager)"
Write-Host ""
Read-Host "Press Enter to close this window (the agency keeps running in the background)"
