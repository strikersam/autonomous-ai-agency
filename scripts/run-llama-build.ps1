#requires -Version 5.1
<#
scripts/run-llama-build.ps1 - Build llama.cpp + produce llama-server.exe.

Pure PowerShell replacement for the failed .cmd wrapper. Reasons:
  1. cmd.exe //c on Git-Bash lost PATH-prepend output on three successive runs.
  2. PowerShell 5.1's $env:PATH mutation propagates deterministically to nested
     cmd.exe /c child probes.

Auto-discovers the latest MSVC compiler dir (LastWriteTime, not version-string
sort - LastWriteTime is more robust when a hot-fix reinstall bumps an older
target). Trusts cmake's Visual Studio generator to find Windows SDK via vswhere.

usage:
  pwsh scripts/run-llama-build.ps1                              # 4-job CPU build
  pwsh scripts/run-llama-build.ps1 -BuildJobs 8                 # forward to inner
  pwsh scripts/run-llama-build.ps1 -BuildJobs 8 -LlamaCppDir D:\extra\llama.cpp  # -BuildJobs override; other args live in build_llama_cpp.ps1 defaults

exit codes:
  6  MSVC / cmake pre-flight failed (operator install guidance in stdout)
  8  inner build_llama_cpp.ps1 path missing
  ?. inner build_llama_cpp.ps1's exit (1-5); see its header for codes
#>
[CmdletBinding()]
param(
    [int] $BuildJobs = 4
)

$ErrorActionPreference = 'Stop'

# Cheap PS5.1-safe smoke gate: catch any future PS 7-only idiom (??, ?:, ?., ||)
# in <1s instead of after the 15-min compile starts. Exits 1 on parse failure.
try {
    $null = [System.Management.Automation.Language.Parser]::ParseFile(
        $PSCommandPath, [ref]$null, [ref]$null
    )
} catch {
    Write-Host '[FATAL] run-llama-build.ps1 parse error:' -ForegroundColor Red
    Write-Host $_.Exception.Message
    exit 1
}

$msvcRoot = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\VC\Tools\MSVC'
$cmakeBin = 'C:\Program Files (x86)\Microsoft Visual Studio\18\BuildTools\Common7\IDE\CommonExtensions\Microsoft\CMake\CMake\bin'

if (-not (Test-Path (Join-Path $cmakeBin 'cmake.exe'))) {
    Write-Host '[FATAL] cmake.exe missing under BuildTools 18 Common7 IDE' -ForegroundColor Red
    Write-Host ('  expected: ' + (Join-Path $cmakeBin 'cmake.exe'))
    Write-Host '  fix: Visual Studio Installer -> Modify -> Add "C++ CMake tools for Windows"'
    exit 6
}

$msvcVer = Get-ChildItem -Path $msvcRoot -Directory -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (-not $msvcVer) {
    Write-Host ('[FATAL] no MSVC compiler under ' + $msvcRoot) -ForegroundColor Red
    Write-Host '  fix: Visual Studio Installer -> Modify -> Add "MSVC v143 - VS 2022 C++ x64/x86 build tools"'
    exit 6
}

$msvcBin = Join-Path $msvcVer.FullName 'bin\Hostx64\x64'
if (-not (Test-Path (Join-Path $msvcBin 'cl.exe'))) {
    Write-Host ('[FATAL] cl.exe missing at ' + (Join-Path $msvcBin 'cl.exe')) -ForegroundColor Red
    exit 6
}

$buildScript = 'C:\Users\swami\qwen-server\scripts\build_llama_cpp.ps1'
if (-not (Test-Path $buildScript)) {
    Write-Host ('[FATAL] inner build script missing at ' + $buildScript) -ForegroundColor Red
    exit 8
}

$env:PATH = "$msvcBin;$cmakeBin;$env:PATH"
Write-Host ('=== run-llama-build === msvc=' + $msvcVer.Name + ' cmake=ok path-prepended')

# if/else expression form is PS5.1+ safe; the v1 shim + first .ps1 used the
# PS7+ '? :' ternary which fails on PS5.1.
$clLoc = Get-Command cl.exe -ErrorAction SilentlyContinue
$cmLoc = Get-Command cmake.exe -ErrorAction SilentlyContinue
$clWhere = if ($clLoc) { $clLoc.Source } else { 'NOT FOUND' }
$cmWhere = if ($cmLoc) { $cmLoc.Source } else { 'NOT FOUND' }
Write-Host ('cl.exe    -> ' + $clWhere)
Write-Host ('cmake.exe -> ' + $cmWhere)
if (-not $clLoc) {
    Write-Host '[FATAL] cl.exe still not on PATH after prepend' -ForegroundColor Red
    exit 6
}

# Direct named-arg invocation (no splat): avoids the PS 5.1
# `Cannot bind argument to parameter 'Path' because it is an
# empty string` false-negative when forwarding no extra args.
# Override args like -LlamaCppDir belong in build_llama_cpp.ps1
# defaults or env vars — this wrapper passes a fixed
# (-NoCuda, -BuildJobs) arg set.
Write-Host ('running: ' + $buildScript + ' -NoCuda -BuildJobs ' + $BuildJobs)
& $buildScript -NoCuda -BuildJobs $BuildJobs
exit $LASTEXITCODE
