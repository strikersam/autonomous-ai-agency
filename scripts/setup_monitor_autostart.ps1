# scripts/setup_monitor_autostart.ps1
#
# Register a Windows Task Scheduler entry that runs `monitor_colibri supervise`
# at user logon AND on system startup, so the colibri brain watchdog survives
# reboots. Idempotent — any pre-existing `ColibriMonitor` task is unregistered
# first so re-running never piles up duplicates.
#
# Usage:
#   pwsh scripts/setup_monitor_autostart.ps1            # create or replace the task
#   pwsh scripts/setup_monitor_autostart.ps1 -Force     # explicit re-register
#   pwsh scripts/setup_monitor_autostart.ps1 -Unregister # remove only
# Exit code 0 on success.

[CmdletBinding()]
param(
    [switch]$Force,
    [switch]$Unregister
)

$ErrorActionPreference = 'Stop'

$TaskName = 'ColibriMonitor'
$repoRoot = (Resolve-Path -Path (Join-Path $PSScriptRoot '..')).Path
# PowerShell 5.x compatible equivalent of `(Get-Command python -ErrorAction SilentlyContinue)?.Source`.
# The `?.` null-conditional operator was added in PowerShell 7; this box has 5.1.
$pyCmd    = Get-Command python -ErrorAction SilentlyContinue
$pythonExe = if ($pyCmd) { $pyCmd.Source } else { $null }
if (-not $pythonExe) {
    Write-Error "python not on PATH; install Python 3.11+ or activate a virtualenv."
    exit 3
}

# The Task Scheduler executes commands without an interactive shell. Use a
# run-as-SYSTEM token via schtasks /RU SYSTEM so we don't need a password
# prompt; if the user prefers run-as-current-user, we fall back.
$RunAsPrincipal = 'SYSTEM'

function Remove-ExistingTask {
    param([string]$Name)
    $existing = Get-ScheduledTask -TaskName $Name -ErrorAction SilentlyContinue
    if ($existing) {
        Write-Host "Unregistering existing task '$Name'." -ForegroundColor Yellow
        Unregister-ScheduledTask -TaskName $Name -Confirm:$false | Out-Null
    }
}

if ($Unregister) {
    Remove-ExistingTask -Name $TaskName
    Write-Host "Removed task '$TaskName'." -ForegroundColor Green
    exit 0
}

Remove-ExistingTask -Name $TaskName

$Action = New-ScheduledTaskAction `
    -Execute $pythonExe `
    -Argument 'scripts/monitor_colibri.py supervise --max-consecutive-crashes 5'

# AtStartup + AtLogon so a headless box (no user logon) still spawns the
# watchdog; AtLogon catches the common desktop scenario.
$StartupTrigger = New-ScheduledTaskTrigger -AtStartup
$LogonTrigger   = New-ScheduledTaskTrigger -AtLogOn

$Settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -StartWhenAvailable `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $Action `
        -Trigger @($StartupTrigger, $LogonTrigger) `
        -Settings $Settings `
        -Principal (New-ScheduledTaskPrincipal -UserId $RunAsPrincipal -LogonType ServiceAccount -RunLevel Highest) `
        -Description 'Colibri + GLM-5.2 brain watchdog. Restarts colibri on crash; respects manual operator stops.' `
        -Force:$Force | Out-Null
} catch {
    Write-Error "Register-ScheduledTask failed: $_"
    exit 1
}

Write-Host "Registered '$TaskName' (run-as=$RunAsPrincipal, startup+logon, restart x3 every 1m)." -ForegroundColor Green
Write-Host "Manual start:" -ForegroundColor Cyan
Write-Host "  Start-ScheduledTask -TaskName '$TaskName'" -ForegroundColor Gray
Write-Host "Status:" -ForegroundColor Cyan
Write-Host "  Get-ScheduledTask -TaskName '$TaskName' | Get-ScheduledTaskInfo" -ForegroundColor Gray
exit 0
