# RVC Portable Packaging Script v2
# Fixed: tcl/tk, pandas copy, robocopy silent failures
$ErrorActionPreference = "Continue"
$Host.UI.RawUI.WindowTitle = "RVC Portable Packager"

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PortableDir = Join-Path $ProjectDir "RVC-Portable"
$PythonSrc = "C:\Program Files\Python310"

Write-Host "============================================" -ForegroundColor Cyan
Write-Host "  RVC Portable Packager v2" -ForegroundColor Cyan
Write-Host "============================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "[Info] Output: $PortableDir"

if (-not (Test-Path "$PythonSrc\python.exe")) {
    Write-Host "[ERROR] Python not found at $PythonSrc" -ForegroundColor Red
    Read-Host "Press Enter"
    exit 1
}

if (Test-Path $PortableDir) {
    Write-Host "[Warning] Removing old portable folder..." -ForegroundColor Yellow
    Remove-Item -Path $PortableDir -Recurse -Force -ErrorAction SilentlyContinue
}
New-Item -ItemType Directory -Path "$PortableDir\python" -Force | Out-Null

# ==========================================
# Step 1: Copy Python (using robocopy for speed)
# ==========================================
Write-Host "Step 1/3: Copying Python (~5GB)..." -ForegroundColor Cyan

# Exclude heavy dev-only stuff, keep tcl/tk for FreeSimpleGUI
& robocopy $PythonSrc "$PortableDir\python" /E /NFL /NDL /NP /R:2 /W:5 `
    /XD "Doc" "include" "Tools" "Lib\test" "Lib\idlelib" "Lib\ensurepip" "Lib\turtledemo" `
    /XF "*.pyc" "*.pyo"

if ($LASTEXITCODE -ge 8) {
    Write-Host "[ERROR] robocopy failed! Trying xcopy fallback..." -ForegroundColor Red
    & xcopy "$PythonSrc\*" "$PortableDir\python\" /E /I /Q /EXCLUDE:exclude.txt
}
Write-Host "[OK] Python base copied" -ForegroundColor Green

# ==========================================
# Step 2: Fix critical directories that robocopy might miss
# ==========================================
Write-Host "Step 2/4: Fixing critical paths..." -ForegroundColor Cyan

# tcl/tk directory - required by FreeSimpleGUI (tkinter)
if (-not (Test-Path "$PortableDir\python\tcl\tcl8.6\init.tcl")) {
    Write-Host "  Copying tcl/tk..." -ForegroundColor Yellow
    Copy-Item -Path "$PythonSrc\tcl" -Destination "$PortableDir\python\tcl" -Recurse -Force
    Write-Host "  [OK] tcl/tk" -ForegroundColor Green
}

# pandas fix - robocopy sometimes misses deep subdirectories
$pandasSrc = "$PythonSrc\Lib\site-packages\pandas"
$pandasDest = "$PortableDir\python\Lib\site-packages\pandas"
if ((Test-Path $pandasSrc) -and (Test-Path $pandasDest)) {
    $srcCount = (Get-ChildItem $pandasSrc -Directory -Recurse).Count
    $destCount = (Get-ChildItem $pandasDest -Directory -Recurse -ErrorAction SilentlyContinue).Count
    if ($destCount -lt $srcCount) {
        Write-Host "  Fixing pandas (missing dirs)..." -ForegroundColor Yellow
        Remove-Item $pandasDest -Recurse -Force -ErrorAction SilentlyContinue
        Copy-Item -Path $pandasSrc -Destination $pandasDest -Recurse -Force
        Write-Host "  [OK] pandas fixed" -ForegroundColor Green
    }
}

Write-Host "[OK] Critical paths fixed" -ForegroundColor Green

# ==========================================
# Step 3: Copy project files
# ==========================================
Write-Host "Step 3/4: Copying project files..." -ForegroundColor Cyan

$dirs = @("assets", "infer", "configs", "i18n")
foreach ($d in $dirs) {
    $src = Join-Path $ProjectDir $d
    if (Test-Path $src) {
        & robocopy $src "$PortableDir\$d" /E /NFL /NDL /NP /R:2 /W:5
        Write-Host "  [OK] $d" -ForegroundColor Green
    }
}

# Other optional directories
$optDirs = @("logs", "trainset", "weights", "pretrained", "ckpt")
foreach ($d in $optDirs) {
    $src = Join-Path $ProjectDir $d
    if (Test-Path $src) {
        & robocopy $src "$PortableDir\$d" /E /NFL /NDL /NP /R:2 /W:5
    }
}

# Core files
@("gui_v1.py", "infer-web.py", "requirements.txt") | ForEach-Object {
    Copy-Item (Join-Path $ProjectDir $_) $PortableDir -Force
}

Write-Host "[OK] Project files copied" -ForegroundColor Green

# ==========================================
# Step 4: Generate launchers
# ==========================================
Write-Host "Step 4/4: Generating launchers..." -ForegroundColor Cyan

# GUI launcher
@"
@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   RVC Real-time Voice Changer - Portable
echo ============================================
"%~dp0python\python.exe" "%~dp0gui_v1.py"
pause
"@ | Out-File -FilePath "$PortableDir\start-gui.bat" -Encoding ASCII
Write-Host "  [OK] start-gui.bat" -ForegroundColor Green

# Web launcher
@"
@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ============================================
echo   RVC Web Interface - Portable
echo ============================================
echo   http://localhost:7897
"%~dp0python\python.exe" "%~dp0infer-web.py" --pycmd "%~dp0python\python.exe" --port 7897
pause
"@ | Out-File -FilePath "$PortableDir\start-web.bat" -Encoding ASCII
Write-Host "  [OK] start-web.bat" -ForegroundColor Green

# Readme
@"
RVC Real-time Voice Changer - Portable Edition
================================================

Quick start:
  Double-click: start-gui.bat  (voice changer for games)
  Double-click: start-web.bat  (web interface)

Prerequisites:
  1. Install VB-Cable: https://vb-audio.com/Cable/
  2. Set system default mic to CABLE Output (run: mmsys.cpl)
  3. In RVC GUI, set output device to CABLE Input

Recommended settings:
  Model:  yalin_yujie.pth  (mature female)
  Pitch:  +12
  F0:     rmvpe
  Index:  0.75
  Half-precision: ON

Game audio routing:
  Physical Mic -> RVC -> CABLE Input -> CABLE Output -> Game
"@ | Out-File -FilePath "$PortableDir\README.txt" -Encoding UTF8
Write-Host "  [OK] README.txt" -ForegroundColor Green

# ==========================================
# Verify
# ==========================================
Write-Host ""
Write-Host "Verifying portable Python..." -ForegroundColor Cyan
$testResult = & "$PortableDir\python\python.exe" -c "import torch; import fairseq; import gradio; import FreeSimpleGUI; import flask; print('OK')" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "[OK] All modules verified!" -ForegroundColor Green
} else {
    Write-Host "[WARNING] Some modules may have issues:" -ForegroundColor Yellow
    Write-Host $testResult
}

# Done
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host "  Packaging Complete!" -ForegroundColor Green
Write-Host "  Output: $PortableDir" -ForegroundColor White
Write-Host "============================================" -ForegroundColor Cyan
Read-Host "Press Enter to exit"
