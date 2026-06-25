# One-click launcher — runs the Autonomous AI Agency on the LOCAL Ollama brain.
# Double-click "Start-Local-Agency.cmd" (this file is the PowerShell it calls).
$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ROOT
Write-Host "== Autonomous AI Agency - local brain launcher ==" -ForegroundColor Cyan

# Point Ollama at the real model store (qwen3-coder:30b, qwen3.6:35b-a3b, deepseek-r1:32b live here).
$env:OLLAMA_MODELS = "D:\hfkld-qg7ky\local-models\aipc-models"

# 1) Ensure Ollama is serving
$ollamaUp = $false
try { Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 2 | Out-Null; $ollamaUp = $true } catch {}
if (-not $ollamaUp) {
    Write-Host "[1/3] Starting Ollama..." -ForegroundColor Cyan
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    for ($i=0; $i -lt 30; $i++) { Start-Sleep 1; try { Invoke-RestMethod "http://localhost:11434/api/tags" -TimeoutSec 2 | Out-Null; $ollamaUp=$true; break } catch {} }
}
if (-not $ollamaUp) { Write-Host "Ollama did not start - open the Ollama app and retry." -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1 }
Write-Host "[OK] Ollama serving local models" -ForegroundColor Green

# 2) Python (.venv preferred)
$py = if (Test-Path "$ROOT\.venv\Scripts\python.exe") { "$ROOT\.venv\Scripts\python.exe" } else { "python" }

# 3) Start the agency backend (.env forces the local brain; RUN_BACKGROUND_IN_WEB=true runs CEO/dispatch/self-heal loops)
Write-Host "[2/3] Starting agency backend on http://localhost:8001 ..." -ForegroundColor Cyan
Start-Process $py -ArgumentList "-m","uvicorn","backend.server:app","--host","127.0.0.1","--port","8001" -WorkingDirectory $ROOT -WindowStyle Minimized
$up=$false
for ($i=0; $i -lt 90; $i++) { Start-Sleep 1; try { Invoke-RestMethod "http://localhost:8001/api/doctor/public" -TimeoutSec 2 | Out-Null; $up=$true; break } catch {} }
if ($up) { Write-Host "[OK] Backend healthy" -ForegroundColor Green } else { Write-Host "Backend slow to start - check the minimized Python window." -ForegroundColor Yellow }

# 4) Kick the autonomy cycle (CEO + dispatch + self-healing + GitHub issue/PR pickup)
Write-Host "[3/3] Triggering autonomy cycle..." -ForegroundColor Cyan
try { Invoke-RestMethod "http://localhost:8001/api/autonomy/status" -TimeoutSec 60 | Out-Null } catch {}
Start-Process "http://localhost:8001/"
Write-Host ""
Write-Host "Agency is running on the LOCAL brain. Background loops keep working while this stays up." -ForegroundColor Green
Write-Host "Dashboard: http://localhost:8001/   |   Stop: .\stop_server.ps1 (or close the Python window)"
Read-Host "Press Enter to close this window (the agency keeps running)"
