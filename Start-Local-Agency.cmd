@echo off
REM Double-click me to launch the Autonomous AI Agency on the local Ollama brain.
<<<<<<< HEAD
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start-local-agency.ps1"
=======
REM Requires: PowerShell 5.1+, Ollama, Python 3.13+, and models pulled via download_models.ps1

REM Check if PowerShell is available
where powershell >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo [FAIL] PowerShell not found. This launcher requires PowerShell 5.1 or newer.
    echo        Install from https://github.com/PowerShell/PowerShell
    pause
    exit /b 1
)

REM Check if the PS1 script exists alongside this .cmd
if not exist "%~dp0start-local-agency.ps1" (
    echo [FAIL] start-local-agency.ps1 not found next to this launcher.
    echo        Make sure both files are in the same folder.
    pause
    exit /b 1
)

powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0start-local-agency.ps1"

REM If PowerShell exited with an error, pause so the user can read the message
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [FAIL] Agency launcher exited with error code %ERRORLEVEL%.
    pause
)
>>>>>>> origin/master
