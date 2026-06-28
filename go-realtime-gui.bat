@echo off
chcp 65001 >nul
cd /d "%~dp0"

:: 优先使用便携版 Python，其次使用系统安装版
if exist "%~dp0python\python.exe" (
    set "PYTHON=%~dp0python\python.exe"
    echo [便携模式] 使用内置 Python
) else if exist "C:\Program Files\Python310\python.exe" (
    set "PYTHON=C:\Program Files\Python310\python.exe"
    echo [系统模式] 使用系统 Python
) else (
    echo [错误] 找不到 Python！请安装 Python 3.10 到默认路径
    pause
    exit /b 1
)

"%PYTHON%" gui_v1.py
pause
