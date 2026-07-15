# scripts/setup_local_controller.ps1 — register local_controller.py as a Task Scheduler service.
#
# Why Task Scheduler instead of a Windows Service or NSSM wrapper:
#   - Task Scheduler runs scripts as the current user without needing NSSM,
#     which keeps the install surface small (no extra download).
#   - "AtStartup" + "AtLogon" triggers together cover both server and
#     workstation reboot paths WITHOUT tying the lifetime to a user
#     login session (AtStartup fires before logon completes under SYSTEM context).
#   - Idempotent: if the task already exists, this script drops and recreates,
#     so an updated env-vars block or binary path is picked up cleanly on next
#     re-run.
#
# Required env vars to set BEFORE invoking:
#   LOCAL_BRAIN_TOKEN           SERVICE_TOKEN value the cloud uses on its side
#   AGENCY_URL                  base URL of the cloud agency (default below)
#
# Optional (overrides):
#   LOCAL_BRAIN_HTTP_PORT       default 8072
#   LOCAL_BRAIN_INTERVAL        default 30 seconds
#   LOCAL_BRAIN_BIN             full path to llama-server.exe
#   LOCAL_BRAIN_MODEL_PATH      full path to the GLM-5.2 GGUF
[CmdletBinding()]
param(
    [string]$RepoRoot               = "C:\Users\swami\qwen-server",
    [string]$PythonExe              = "python.exe",
    [string]$TaskName               = "ColibriLocalBrainController",
    [string]$AgencyUrl              = "https://local-llm-server.strikersam.workers.dev",
    [string]$LocalBrainToken        = $env:LOCAL_BRAIN_TOKEN,
    [string]$LogDir                 = (Join-Path $RepoRoot "logs"),
    [string]$ControllerScript       = (Join-Path $RepoRoot "scripts\local_controller.py")
)

$ErrorActionPreference = "Stop"

function Write-Section($msg)  { Write-Output "" ; Write-Output ("=== " + $msg + " ===") ; Write-Output "" }

# ── Preflight ──────────────────────────────────────────────────────────────
Write-Section "Preflight"
if (-not (Test-Path $ControllerScript)) {
    Write-Error ("FATAL controller script not found: " + $ControllerScript)
    exit 2
}
if (-not $LocalBrainToken -or $LocalBrainToken.Trim().Length -lt 16) {
    Write-Error "FATAL LOCAL_BRAIN_TOKEN env var unset or too short. Paste the SERVICE_TOKEN value the cloud backend uses (>= 16 chars)."
    exit 3
}
if (-not (Test-Path $LogDir)) {
    New-Item -ItemType Directory -Path $LogDir -Force | Out-Null
}

# ── Drop prior task if present ─────────────────────────────────────────────
Write-Section "Dropping prior task (if any)"
$existing = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($existing) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
    Write-Output ("dropped prior task: " + $TaskName)
}

# ── Build the action ───────────────────────────────────────────────────────
Write-Section "Creating task with AtStartup + AtLogon triggers"
$pythonArgs = @(
    "-X utf8",
    "-u",
    $ControllerScript,
    "--daemon"
) -join " "

# `ConvertFrom-Json` would help, but plain strings are robust against encodings.
$action = New-ScheduledTaskAction `
    -Execute $PythonExe `
    -Argument $pythonArgs `
    -WorkingDirectory $RepoRoot

# Run as the current user (most common case — the operator who cloned the repo).
# SYSTEM context would also work but loses the .env visibility the operator's
# shell has; for a service-style install operators can swap -UserId "SYSTEM".
$principal = New-ScheduledTaskPrincipal `
    -UserId $env:USERNAME `
    -LogonType Interactive `
    -RunLevel Highest

# Triggers cover reboot + interactive logon. The AtStartup fires once per
# system-boot; AtLogon fires every interactive user logon (so a laptop that
# sleeps + wakes resumes the controller immediately).
$triggers = @()
$triggers += New-ScheduledTaskTrigger -AtStartup
$triggers += New-ScheduledTaskTrigger -AtLogon

# Settings: don't stop on idle, restart every minute if it crashes, allow
# start when on battery (so a laptop with the daemon doesn't lose its brain
# just because the operator unplugged).
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -StartWhenAvailable `
    -RestartCount 10 -RestartInterval (New-TimeSpan -Minutes 1) `
    -ExecutionTimeLimit (New-TimeSpan -Hours 0)  # no timeout — service-style

# Register with /create /XML instead of the cmdlet to keep the env block
# intact (-SettingString is awkward to roundtrip on Windows PowerShell 5.1).
$xml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Local-GLM-5.2 controller daemon — polls the cloud agency toggle and starts/stops the local llama-server.exe. Requires LOCAL_BRAIN_TOKEN env var to be set in the user's shell (this script writes it to the task XML).</Description>
    <Author>colibri-brain-team</Author>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger>
      <Enabled>true</Enabled>
    </BootTrigger>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <UserId>$env:USERNAME</UserId>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$env:USERNAME</UserId>
      <LogonType>Interactive</LogonType>
      <RunLevel>Highest</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <AllowStartIfOnBatteries>true</AllowStartIfOnBatteries>
    <DontStopIfGoingOnBatteries>true</DontStopIfGoingOnBatteries>
    <DontStopOnIdleEnd>true</DontStopOnIdleEnd>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>10</Count>
    </RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions>
    <Exec>
      <Command>$PythonExe</Command>
      <Arguments>-X utf8 -u $ControllerScript --daemon</Arguments>
      <WorkingDirectory>$RepoRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@

$xmlPath = Join-Path $LogDir "ColibriLocalBrainController.xml"
$xml | Out-File -FilePath $xmlPath -Encoding Unicode

# Set environment variables for the task via the env_block trick: schtasks
# doesn't support per-task env vars directly, so we write them to a wrapper
# batch file that the task invokes.
#
# PowerShell 5.1 caveat: `Out-File -Encoding ascii` writes UTF-8-with-BOM
# (the parameter is broken — it never emits ASCII); cmd.exe rejects the BOM
# silently by treating the first line as garbage and dropping it. We use the
# System.IO.File API directly to guarantee an actual ASCII file.
$wrapperPath = Join-Path $LogDir "ColibriLocalBrainController-wrapper.cmd"
$wrapperText = @"
@echo off
set LOCAL_BRAIN_TOKEN=$LocalBrainToken
set AGENCY_URL=$AgencyUrl
set AGENCY_BASE_URL=$AgencyUrl
set "PYTHONPATH=$RepoRoot;%PYTHONPATH%"
"@
[System.IO.File]::WriteAllText($wrapperPath, $wrapperText, [System.Text.Encoding]::ASCII)

# Overwrite the Exec in the XML to point at the wrapper
$wrapperXml = @"
<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.4" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Author>colibri-brain-team</Author>
    <Description>Local GLM 5.2 controller daemon. Polls Cloudflare agency toggle and (de)commissions llama-server.exe.</Description>
  </RegistrationInfo>
  <Triggers>
    <BootTrigger><Enabled>true</Enabled></BootTrigger>
    <LogonTrigger><Enabled>true</Enabled><UserId>$env:USERNAME</UserId></LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <UserId>$env:USERNAME</UserId>
      <LogonType>Interactive</LogonType>
      <RunLevel>Highest</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <AllowStartIfOnBatteries>true</AllowStartIfOnBatteries>
    <DontStopIfGoingOnBatteries>true</DontStopIfGoingOnBatteries>
    <DontStopOnIdleEnd>true</DontStopOnIdleEnd>
    <StartWhenAvailable>true</StartWhenAvailable>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <RestartOnFailure><Interval>PT1M</Interval><Count>10</Count></RestartOnFailure>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
  </Settings>
  <Actions>
    <Exec>
      <Command>cmd.exe</Command>
      <Arguments>/c "$wrapperPath" &amp;&amp; "$PythonExe" -X utf8 -u "$ControllerScript" --daemon</Arguments>
      <WorkingDirectory>$RepoRoot</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"@
$wrapperXml | Out-File -FilePath $xmlPath -Encoding Unicode

& schtasks /Create /TN $TaskName /XML $xmlPath /F | Out-Null
if ($LASTEXITCODE -ne 0) {
    Write-Error ("FATAL schtasks /Create failed: " + $LASTEXITCODE)
    exit 4
}

# ── Run a single diagnose tick so the operator sees the state right away ──
Write-Section "Running initial --diagnose tick"
try {
    & $PythonExe -X utf8 -u $ControllerScript --diagnose 2>&1 | Out-Null
} catch {
    Write-Warning ("diagnose tick raised (non-fatal): " + $_.Exception.Message)
}

Write-Output ""
Write-Output ("=== OK ===  Task '" + $TaskName + "' is registered. Run 'schtasks /Run /TN " + $TaskName + "' to start it now, or reboot.")
Write-Output ("Logs: " + $LogDir + "\local_brain.log")
Write-Output ("Healbeats: see the Providers page 'Local brain' toggle card on the cloud admin UI.")
exit 0
