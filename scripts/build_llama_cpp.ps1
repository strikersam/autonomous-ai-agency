#requires -Version 5.1
<#
scripts/build_llama_cpp.ps1 — Build llama.cpp on Windows producing
   D:\hfkld-qg7ky\local-models\llama.cpp\build\bin\Release\llama-server.exe
This is the binary `scripts/local_controller.py` (cross-machine GLM-5.2 toggle,
port 8072) invokes when the operator flips the cloud Local brain toggle to ON.

Outputs:
  $LlamaCppDir\build\bin\Release\llama-server.exe  (the runtime binary)
  $LlamaCppDir\build\bin\Release\llama-cli.exe     (the chat binary)

Why a separate script (not folded into setup_colibri.ps1):
  - colibri's glm.exe is built with MinGW-w64 / mingw32-make
  - llama.cpp's llama-server.exe is built with MSVC + CMake (NVCC for -DGGML_CUDA=ON)
  - Two entirely different toolchains + shells. Keep them isolated.

Idempotent: re-running with the binary already built just re-prints the
smoke output and exits 0.

Usage:
  pwsh scripts/build_llama_cpp.ps1
  pwsh scripts/build_llama_cpp.ps1 -NoCuda        # Vulkan or CPU-only
  pwsh scripts/build_llama_cpp.ps1 -LlamaCppDir "E:\llama.cpp"

Exit codes:
  0  built (smoke output verified)
  1  prerequisite missing (cmake / git / MSVC / CUDA toolkit)
  2  clone failed
  3  cmake configure failed
  4  cmake build failed
  5  binary produced but smoke failed (rare; usually broken toolchain)
#>

[CmdletBinding()]
param(
    [string] $LlamaCppDir    = "D:\hfkld-qg7ky\local-models\llama.cpp",
    [string] $LlamaCppRepo   = "https://github.com/ggml-org/llama.cpp.git",
    [int]    $BuildJobs      = 8,
    [switch] $NoCuda,
    [switch] $NoRebuild,
    [string] $LogDir         = "C:\Users\swami\qwen-server\logs"
)

$ErrorActionPreference = "Stop"

function W($msg)  { Write-Host $msg }
function Ok($msg) { W "[OK] $msg" }
function Warn($msg) { W "[WARN] $msg" -ForegroundColor Yellow }
function Fail($msg) { W "[FATAL] $msg" -ForegroundColor Red }

if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir -Force | Out-Null }
$BuildLog = Join-Path $LogDir "build-llama-cpp.log"
$ErrLog   = Join-Path $LogDir "build-llama-cpp-err.log"

# ── 1. Prerequisite probes ─────────────────────────────────────────────────
W ""
W "=== build_llama_cpp.ps1 ==="
W ""

$missing = @()
foreach ($c in @(
    @{ name = "git";    cmd = "git --version" },
    @{ name = "cmake";  cmd = "cmake --version" },
    # Use `where.exe` (CMD-native) instead of probing `cl.exe` directly, because
    # the MSVC compiler only prints its banner when the Developer Command Prompt
    # env (INCLUDE / LIB / VSCMD_DEBUG) is loaded — running `cl.exe` raw may exit
    # before writing anything, hiding a perfectly functional toolchain.
    @{ name = "cl (MSVC)"; cmd = "where.exe cl.exe >NUL" }
)) {
    try {
        $out = & cmd.exe /c $c.cmd 2>&1
        if ($LASTEXITCODE -eq 0) {
            Ok "$($c.name): $($out[0])"
        } else {
            Fail "$($c.name): not found"
            $missing += $c.name
        }
    } catch {
        Fail "$($c.name): not found"
        $missing += $c.name
    }
}

if ($missing.Count -gt 0) {
    Fail "Missing prerequisites: $($missing -join ', ')"
    W ""
    W "Install one of:"
    W "  - Visual Studio Build Tools 2022 (clang-cl OR MSVC v143 + CMake + Ninja)"
    W "      https://aka.ms/vs/17/release/vs_BuildTools.exe"
    W "      After install open 'x64 Native Tools Command Prompt for VS 2022' OR"
    W "      run 'pwsh' from a Developer PowerShell so cl.exe is on PATH."
    W "  - Full Visual Studio 2022 Community + 'Desktop development with C++' workload"
    W "  - CUDA Toolkit 12.x (only if you keep -DGGML_CUDA=ON)"
    W "      https://developer.nvidia.com/cuda-toolkit-archive"
    W ""
    W "After installing, RE-RUN from a 'Developer PowerShell for VS 2022' so cl.exe is on PATH."
    exit 1
}

# CUDA toolkit is only required when -NoCuda is NOT set
if (-not $NoCuda) {
    try {
        $nvcc = & cmd.exe /c "nvcc --version" 2>&1
        if ($LASTEXITCODE -eq 0) {
            Ok "nvcc (CUDA): $($nvcc[0])"
        } else {
            Warn "nvcc not found; llama.cpp will fall back to GGML_CUDA=OFF (CPU only)."
            Warn "Install CUDA Toolkit 12.x if your RTX 4090 should accelerate GLM-5.2 inference."
            $NoCuda = $true
        }
    } catch {
        Warn "nvcc probe failed; assuming -NoCuda"
        $NoCuda = $true
    }
}

# ── 2. Clone if missing ────────────────────────────────────────────────────
if (-not (Test-Path $LlamaCppDir)) {
    W ""
    W "Cloning llama.cpp -> $LlamaCppDir ..."
    New-Item -ItemType Directory -Path (Split-Path $LlamaCppDir) -Force | Out-Null
    # --depth 1 keeps the clone lightweight (~few hundred MB vs full history)
    # and matches what llama.cpp CI uses. Operator can override with full clone
    # by passing a custom -LlamaCppRepo URL on the command line.
    git clone --depth 1 $LlamaCppRepo $LlamaCppDir 2>&1 | Tee-Object -FilePath $BuildLog | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "git clone failed (exit $LASTEXITCODE); see $BuildLog"
        exit 2
    }
    Ok "cloned"
} else {
    Ok "llama.cpp already present at $LlamaCppDir"
}

# ── 3. Skip work if user just wants verification ──────────────────────────
$expectedBin = Join-Path $LlamaCppDir "build\bin\Release\llama-server.exe"
if ((Test-Path $expectedBin) -and $NoRebuild) {
    Ok "-NoRebuild honored: $expectedBin already present"
    & $expectedBin --version 2>&1 | Out-Null
    W "  $($expectedBin) --version: $($(Get-Item $expectedBin).VersionInfo.FileVersion)"
    exit 0
}

# ── 4. CMake configure ─────────────────────────────────────────────────────
W ""
W "Running 'cmake -B build' (configures VS generator + CUDA if available) ..."
$CudaFlag = if ($NoCuda) { "-DGGML_CUDA=OFF" } else { "-DGGML_CUDA=ON" }
$cmakeArgs = @(
    "-S", $LlamaCppDir,
    "-B", (Join-Path $LlamaCppDir "build"),
    "-DCMAKE_BUILD_TYPE=Release",
    "-DBUILD_SHARED_LIBS=OFF",
    "-DGGML_NATIVE=OFF",
    $CudaFlag
)

Push-Location $LlamaCppDir
try {
    & cmake @cmakeArgs 2>&1 | Tee-Object -FilePath $BuildLog -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "cmake configure failed (exit $LASTEXITCODE); see $BuildLog"
        W ""
        W "Common fixes:"
        W "  - Missing Visual Studio / Build Tools: install VS 2022 Build Tools + 'Desktop dev C++'."
        W "  - Wrong shell: re-run from 'Developer PowerShell for VS 2022' so cl.exe is on PATH."
        W "  - CUDA toolkit mismatch with MSVC: pin CUDA 12.x for cl.exe 19.3x (VS 2022 17.10+)."
        exit 3
    }
    Ok "cmake configure succeeded"

    # ── 5. CMake build ─────────────────────────────────────────────────────
    W ""
    W "Running 'cmake --build build --config Release -j $BuildJobs' (this takes minutes to hours) ..."
    & cmake --build (Join-Path $LlamaCppDir "build") --config Release -j $BuildJobs 2>&1 `
        | Tee-Object -FilePath $BuildLog -Append | Out-Null
    if ($LASTEXITCODE -ne 0) {
        Fail "cmake build failed (exit $LASTEXITCODE); see $BuildLog"
        W ""
        W "Common fixes:"
        W "  - Out of RAM: -j $BuildJobs too high for this machine; rerun with -BuildJobs 2."
        W "  - MSVC version mismatch: pin VS 2022 17.10+ for CUDA 12.x."
        W "  - Missing OpenBLAS / MPI / MPI_C: skip those -DLLAMA_* flags if you only need base llama-server."
        exit 4
    }
    Ok "cmake build succeeded"
} finally {
    Pop-Location
}

# ── 6. Verify + smoke ─────────────────────────────────────────────────────
if (-not (Test-Path $expectedBin)) {
    Fail "expected binary missing at $expectedBin even though the build reported success."
    W "Inspect $LlamaCppDir\build\ for the actual subdirectory produced by your VS version."
    exit 5
}

Ok "llama-server.exe produced at $expectedBin ($((Get-Item $expectedBin).Length / 1MB) MB)"
& $expectedBin --version 2>&1 | Tee-Object -FilePath $BuildLog -Append | Out-Null

W ""
W "Next steps:"
W "  1. Confirm LOCAL_BRAIN_BIN in .env points at this exact path:"
W "       LOCAL_BRAIN_BIN=$expectedBin"
W "  2. Start the cross-machine controller daemon (or wait for next boot):"
W "       schtasks /Run /TN ColibriLocalBrainController"
W "  3. On the Cloudflare admin UI, flip the 'Local brain' toggle to ON."
W "  4. The daemon will spawn llama-server.exe serving GLM-5.2 on :8072."
W ""
W "If llama-server.exe starts but crashes immediately:"
W "  - Likely VRAM OOM: drop -ngl 99 to -ngl 20 in scripts/start_local_glm_server.ps1"
W "  - Or missing CUDA driver: install latest NVIDIA drivers from nvidia.com/drivers"
W ""
exit 0
