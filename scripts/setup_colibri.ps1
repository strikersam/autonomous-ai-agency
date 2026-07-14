#!/usr/bin/env pwsh
# scripts/setup_colibri.ps1 — Bootstrap the JustVugg/colibri C runtime on Windows.
#
# What this does:
#   1. Verifies prerequisites — git + a C toolchain (MinGW-w64 / w64devkit / MSYS2 gcc).
#      Probes `make` first; transparently falls back to `mingw32-make` (choco's mingw
#      ships the GNU make binary as `mingw32-make.exe` without a `make.exe` shim).
#   2. Clones JustVugg/colibri into D:\hfkld-qg7ky\local-models\colibri\ if absent.
#   3. Runs `mingw32-make -j -C c` (or `make` if found) to compile `c\glm.c` into
#      `c\glm.exe`. Note: `c\coli` is a SEPARATE Python wrapper (~35 KB) shipped
#      in the upstream repo that drives `glm.exe` + `c\openai_server.py` to expose
#      an OpenAI-compat HTTP API. Invoke via `python c/coli serve --help`.
#
# Idempotent — safe to re-run.
#
# Why not just use WSL on this machine?
#   The colibri README documents both native-Windows MinGW-w64 builds AND WSL.
#   Native MinGW is what `make -C c` runs in `c/compat.h` paths; the build is
#   fast (~30 sec). WSL adds a Linux layer for no benefit on Windows. MinGW-w64
#   is the recommended path.
#
# Recommended MinGW installs (in order of operator-friendliness):
#   - w64devkit (portable ~150 MB, hackable: 7z; ships gcc + make + winpthreads)
#     https://github.com/skeeto/w64devkit/releases
#     → extract, prepend <w64devkit>\bin to PATH
#   - MSYS2 (heavier; uCRT64 environment with pacman)
#     https://www.msys2.org/ → pacman -S mingw-w64-ucrt-x86_64-gcc make
#
# Usage:
#   pwsh scripts/setup_colibri.ps1
#
# Exit codes:
#   0 — colibri built (c\glm.exe present)
#   1 — prerequisites missing or build failed

[CmdletBinding()]
param(
    [string] $ColibriDir = "D:\hfkld-qg7ky\local-models\colibri",
    [string] $ColibriRepo = "https://github.com/JustVugg/colibri.git"
)

$ErrorActionPreference = "Stop"
function W($msg) { Write-Host $msg }
function Ok($msg) { W "✓ $msg" }
function Warn($msg) { W "⚠ $msg" -ForegroundColor Yellow }
function Fail($msg) { W "✗ $msg" -ForegroundColor Red }

W ""
W "=== setup_colibri.ps1 ==="
W ""

# 1. Verify prerequisites. Probe `make` first; on Windows choco-mingw / Git-Bash-mingw
#    the GNU make binary renames itself to `mingw32-make.exe` and does NOT ship a
#    `make.exe` shim. We auto-fall-back transparently so the operator does not
#    have to know about the rename.
$prereqs = @()
$prereqs += @{ name = "git"; cmd = "git --version" }
$missing = @()

# Detect a working `make` (try `make` first, then `mingw32-make`).
$makeCmd = $null
foreach ($candidate in @("make", "mingw32-make")) {
    try {
        $out = & cmd.exe /c "$candidate --version" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Ok "$candidate found: $($out[0])"
            $makeCmd = $candidate
            break
        }
    } catch { }
}
if ($makeCmd -eq $null) {
    W ""
    Fail "Neither `make` nor `mingw32-make` is on PATH in this shell."
    W ""
    W "Install one of:"
    W "  • w64devkit  — https://github.com/skeeto/w64devkit/releases (portable, uCRT64)"
    W "  • MSYS2      — https://www.msys2.org/  →  pacman -S mingw-w64-ucrt-x86_64-gcc make"
    W "  • Strawberry Perl — https://strawberryperl.com/  (ships gcc + make)"
    W ""
    W "Then open a NEW shell so PATH picks up the new binaries and re-run this script."
    exit 1
}
$prereqs += @{ name = "gcc"; cmd = "gcc --version" }
foreach ($p in $prereqs) {
    try {
        $version = & cmd.exe /c $p.cmd 2>&1
        if ($LASTEXITCODE -eq 0) {
            Ok "$($p.name): $($version[0])"
        } else {
            Fail "$($p.name): not found"
            $missing += $p.name
        }
    } catch {
        Fail "$($p.name): not found"
        $missing += $p.name
    }
}

if ($missing.Count -gt 0) {
    W ""
    Fail "Missing prerequisites: $($missing -join ', ')"
    W ""
    W "Install one of:"
    W "  • w64devkit  — https://github.com/skeeto/w64devkit/releases (portable, no install)"
    W "                Extract and prepend <w64devkit>\bin to PATH."
    W "  • MSYS2      — https://www.msys2.org/  →  pacman -S mingw-w64-ucrt-x86_64-gcc make"
    W "  • Strawberry Perl — https://strawberryperl.com/  (ships gcc + make with PATH in PATH)"
    W ""
    W "After install, open a NEW shell so the updated PATH is loaded, then re-run this script."
    exit 1
}

# 2. Clone colibri repo if missing
if (-not (Test-Path $ColibriDir)) {
    W ""
    W "Cloning JustVugg/colibri → $ColibriDir ..."
    New-Item -ItemType Directory -Path (Split-Path $ColibriDir) -Force | Out-Null
    git clone $ColibriRepo $ColibriDir
    if ($LASTEXITCODE -ne 0) {
        Fail "git clone failed"
        exit 1
    }
    Ok "cloned"
} else {
    Ok "colibri repo already present at $ColibriDir"
}

# 3. Build
W ""
W "Running `$makeCmd -C c` (compiles glm.c → glm.exe) ..."
Push-Location (Join-Path $ColibriDir "c")
try {
    & $makeCmd -j
    if ($LASTEXITCODE -ne 0) {
        Fail "`$makeCmd -C c` failed (exit $LASTEXITCODE)"
        W ""
        W "If the failure is `cannot find -lpthread` or `winpthreads` missing, install"
        W "a w64devkit/MSYS2 uCRT64 toolchain (NOT mingw32 / MSVCRT — those lack winpthreads)."
        Pop-Location
        exit 1
    }
    Ok "$makeCmd -C c succeeded"
} finally {
    Pop-Location
}

$coliEngine = Join-Path $ColibriDir "c/glm.exe"
if (Test-Path $coliEngine) {
    Ok "glm.exe found at $coliEngine (the C engine) — `coli` is a Python wrapper (35 KB, no .py extension) served from c\\coli"
    W ""
    W "Next steps:"
    W "  1. Download the GLM-5.2 weights:  pwsh scripts/download_glm52_weights.ps1"
    W "  2. Start coli serve on :8081:      pwsh scripts/start_colibri_server.ps1"
    W "  3. Wire the agency brain:          set COLIBRI_ENABLED=true + BRAIN_PREFERENCE=colibri"
    W ""
    W "Or run scripts/status_colibri_server.ps1 any time to check status."
} else {
    Warn "make succeeded but glm.exe not found at expected path. Inspect $ColibriDir\c\ manually."
    exit 1
}
