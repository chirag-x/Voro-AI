# ==============================================================================
# Voro Windows Build & Installer Script
# ==============================================================================
# 1. Builds Voro.exe standalone bundle using PyInstaller and Voro.spec
# 2. Checks for Inno Setup (supports Inno Setup 7 on E: or C: drive)
# 3. Compiles voro.iss into installer\Voro_Setup.exe
# ==============================================================================

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host ""
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "           VORO PRODUCTION BUILD & PACKAGING              " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host ""

# --- Step 1: Clean old builds ---
Write-Host "[1/3] Cleaning previous build artifacts..." -ForegroundColor Yellow
if (Test-Path "build") { 
    Remove-Item -Recurse -Force "build" 
    Write-Host "      Cleaned 'build/'" -ForegroundColor Gray
}
if (Test-Path "dist") { 
    Remove-Item -Recurse -Force "dist" 
    Write-Host "      Cleaned 'dist/'" -ForegroundColor Gray
}

# --- Step 2: Locate PyInstaller & Build ---
Write-Host "[2/3] Building Voro executable bundle via PyInstaller..." -ForegroundColor Yellow

$pyinstaller = Join-Path $PSScriptRoot ".venv\Scripts\pyinstaller.exe"
if (-not (Test-Path $pyinstaller)) {
    $cmd = Get-Command "pyinstaller" -ErrorAction SilentlyContinue
    if ($cmd) {
        $pyinstaller = $cmd.Source
    } else {
        Write-Error "PyInstaller was not found in .venv\Scripts\pyinstaller.exe or on PATH. Run: pip install pyinstaller"
        exit 1
    }
}

Write-Host "      Using PyInstaller: $pyinstaller" -ForegroundColor Gray
Write-Host "      Using Spec: Voro.spec" -ForegroundColor Gray

& $pyinstaller "Voro.spec" --clean --noconfirm

if ($LASTEXITCODE -ne 0) {
    Write-Error "PyInstaller compilation failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

if (-not (Test-Path "dist\Voro\Voro.exe")) {
    Write-Error "Build finished but 'dist\Voro\Voro.exe' was not generated!"
    exit 1
}

Write-Host "      [SUCCESS] Standalone bundle created at: dist\Voro\Voro.exe" -ForegroundColor Green

# --- Step 3: Inno Setup Compilation ---
Write-Host "[3/3] Looking for Inno Setup compiler (ISCC.exe)..." -ForegroundColor Yellow

$innoCandidates = @(
    "E:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files\Inno Setup 7\ISCC.exe",
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)

$iscc = $null
foreach ($cand in $innoCandidates) {
    if (Test-Path $cand) {
        $iscc = $cand
        break
    }
}

if (-not $iscc) {
    $isccCmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($isccCmd) { $iscc = $isccCmd.Source }
}

if ($iscc) {
    Write-Host "      Found Inno Setup at: $iscc" -ForegroundColor Green
    Write-Host "      Compiling voro.iss into official installer..." -ForegroundColor Cyan
    
    if (-not (Test-Path "installer")) {
        New-Item -ItemType Directory -Path "installer" | Out-Null
    }
    
    & $iscc "voro.iss"
    
    if ($LASTEXITCODE -eq 0 -and (Test-Path "installer\Voro_Setup.exe")) {
        Write-Host ""
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host "  BUILD SUCCESSFUL! ALL ARTIFACTS READY FOR DISTRIBUTION: " -ForegroundColor Green
        Write-Host "==========================================================" -ForegroundColor Green
        Write-Host "  [Executable Folder]: $(Join-Path $PSScriptRoot 'dist\Voro')" -ForegroundColor Cyan
        Write-Host "  [Setup Installer]:   $(Join-Path $PSScriptRoot 'installer\Voro_Setup.exe')" -ForegroundColor Yellow
        Write-Host "==========================================================" -ForegroundColor Green
    } else {
        Write-Warning "Inno Setup compilation did not produce installer\Voro_Setup.exe. You can open voro.iss directly in Inno Setup to compile."
    }
} else {
    Write-Host ""
    Write-Host "NOTE: PyInstaller build succeeded! You can now open 'voro.iss' in Inno Setup to compile the installer." -ForegroundColor Yellow
}
