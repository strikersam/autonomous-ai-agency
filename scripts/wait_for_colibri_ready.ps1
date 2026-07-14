# scripts/wait_for_colibri_ready.ps1
#
# Wait until BOTH conditions hold:
#   1. The GLM-5.2 huggingface download is complete.
#   2. The local colibri server answers 200 on /v1/models with the expected model id.
#
# Thin wrapper around `python scripts/monitor_colibri.py wait`. Use this from
# any PowerShell launcher that needs a synchronous readiness signal before
# proceeding (e.g. start_server.ps1 cold-start path).
#
# Usage:
#   pwsh scripts/wait_for_colibri_ready.ps1                          # default 12 h timeout, poll 10 s
#   pwsh scripts/wait_for_colibri_ready.ps1 -MaxWaitSeconds 3600     # 1 h timeout
#   pwsh scripts/wait_for_colibri_ready.ps1 -PollSeconds 30          # poll every 30 s
# Exit code 0 on ready, 1 on timeout.

[CmdletBinding()]
param(
    [int]$MaxWaitSeconds = 43200,   # 12 hours
    [int]$PollSeconds    = 10,
    [switch]$Json
)

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path -Path (Join-Path $PSScriptRoot '..')).Path
# PowerShell 5.x compatible equivalent of `(Get-Command python -ErrorAction SilentlyContinue)?.Source`.
# The `?.` null-conditional operator was added in PowerShell 7; this box has 5.1.
$pyCmd   = Get-Command python -ErrorAction SilentlyContinue
$script:python = if ($pyCmd) { $pyCmd.Source } else { $null }
if (-not $script:python) {
    Write-Error "python not on PATH; install Python 3.11+ or activate a virtualenv."
    exit 3
}

$extraArgs = @('--max-wait-s', "$MaxWaitSeconds", '--poll-s', "$PollSeconds")
if ($Json) { Write-Verbose "JSON output enabled (logs go to stdout but WARN-only)." }

Write-Host "wait_for_colibri_ready: polling download + colibri /v1/models (max ${MaxWaitSeconds}s)." -ForegroundColor Cyan
& $script:python (Join-Path $repoRoot 'scripts/monitor_colibri.py') wait @extraArgs
exit $LASTEXITCODE
