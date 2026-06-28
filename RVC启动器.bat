@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

title RVC Portable Launcher

:: Find the zip file (same name as this launcher or default name)
set "ZIP_FILE=%~dp0RVC-Portable.zip"
set "EXTRACT_DIR=%TEMP%\RVC-Portable"

if not exist "%ZIP_FILE%" (
    echo [ERROR] RVC-Portable.zip not found!
    echo         Please put RVC启动器.bat next to RVC-Portable.zip
    pause
    exit /b 1
)

:: Check if already extracted
if exist "%EXTRACT_DIR%\start-gui.bat" (
    echo [INFO] Already extracted, launching...
    goto :launch
)

echo ============================================
echo   RVC Portable - Extracting...
echo   Please wait, this may take 3-5 minutes
echo ============================================
echo.

powershell.exe -NoProfile -Command "Expand-Archive -Path '%ZIP_FILE%' -DestinationPath '%EXTRACT_DIR%' -Force"

if not exist "%EXTRACT_DIR%\start-gui.bat" (
    echo [ERROR] Extraction failed!
    pause
    exit /b 1
)

echo.
echo [OK] Extraction complete!
echo.

:launch
echo Launching RVC Voice Changer...
echo.
start "" /D "%EXTRACT_DIR%" "%EXTRACT_DIR%\start-gui.bat"
exit
