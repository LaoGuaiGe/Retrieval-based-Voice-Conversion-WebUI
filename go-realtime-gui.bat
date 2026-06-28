@echo off
cd /d "%~dp0"

if exist "%~dp0python\python.exe" (
    set "PYTHON=%~dp0python\python.exe"
) else if exist "C:\Program Files\Python310\python.exe" (
    set "PYTHON=C:\Program Files\Python310\python.exe"
) else (
    echo Python not found!
    pause
    exit /b 1
)

"%PYTHON%" gui_v1.py
pause
