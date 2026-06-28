@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ============================================
echo   RVC 便携版打包工具
echo ============================================
echo.

set "PORTABLE_DIR=%~dp0RVC-Portable"
set "PYTHON_SRC=C:\Program Files\Python310"
set "PROJECT_SRC=%~dp0"

echo [信息] 源 Python: %PYTHON_SRC%
echo [信息] 源项目:   %PROJECT_SRC%
echo [信息] 输出目录: %PORTABLE_DIR%
echo.

:: ==========================================
:: Step 1: 检查源目录是否存在
:: ==========================================
if not exist "%PYTHON_SRC%\python.exe" (
    echo [错误] 找不到 %PYTHON_SRC%\python.exe
    echo        请先运行一键部署安装 Python 3.10
    pause
    exit /b 1
)

:: ==========================================
:: Step 2: 创建目标目录
:: ==========================================
if exist "%PORTABLE_DIR%" (
    echo [警告] 目标目录已存在，正在删除旧版本...
    rmdir /s /q "%PORTABLE_DIR%"
)
mkdir "%PORTABLE_DIR%"
mkdir "%PORTABLE_DIR%\python"

echo.
echo ============================================
echo   Step 1/3: 复制 Python 环境（约 6GB，请耐心等待...）
echo ============================================

:: 排除不需要的目录以减小体积
robocopy "%PYTHON_SRC%" "%PORTABLE_DIR%\python" /E /NFL /NDL /NJH /NJS ^
    /XD "Doc" "include" "Lib\test" "Lib\idlelib" "Lib\ensurepip" ^
        "Lib\site-packages\pip" "Lib\site-packages\setuptools" ^
        "Lib\site-packages\wheel" "Lib\__pycache__" ^
        "Scripts" "Tools" "tcl" "share" ^
    /XF "*.pyc" "*.pyo" "*.exe.log"

if %ERRORLEVEL% GEQ 8 (
    echo [错误] Python 复制失败！错误代码: %ERRORLEVEL%
    pause
    exit /b 1
)
echo [完成] Python 环境复制完毕

echo.
echo ============================================
echo   Step 2/3: 复制项目文件
echo ============================================

:: 模型文件
robocopy "%PROJECT_SRC%assets" "%PORTABLE_DIR%\assets" /E /NFL /NDL /NJH /NJS /XF "*.pyc"
if %ERRORLEVEL% GEQ 8 ( echo [错误] assets 复制失败 & pause & exit /b 1 )

:: 推理引擎
robocopy "%PROJECT_SRC%infer" "%PORTABLE_DIR%\infer" /E /NFL /NDL /NJH /NJS /XF "*.pyc"
if %ERRORLEVEL% GEQ 8 ( echo [错误] infer 复制失败 & pause & exit /b 1 )

:: 配置文件
robocopy "%PROJECT_SRC%configs" "%PORTABLE_DIR%\configs" /E /NFL /NDL /NJH /NJS /XF "*.pyc"

:: 核心 Python 文件
robocopy "%PROJECT_SRC%" "%PORTABLE_DIR%" gui_v1.py infer-web.py requirements.txt ^
    /NFL /NDL /NJH /NJS
robocopy "%PROJECT_SRC%" "%PORTABLE_DIR%" *.bat /NFL /NDL /NJH /NJS

:: i18n 国际化
if exist "%PROJECT_SRC%i18n" (
    robocopy "%PROJECT_SRC%i18n" "%PORTABLE_DIR%\i18n" /E /NFL /NDL /NJH /NJS /XF "*.pyc"
)

:: 其他需要的目录
for %%d in (logs trainset weights pretrained ckpt) do (
    if exist "%PROJECT_SRC%%%d" (
        robocopy "%PROJECT_SRC%%%d" "%PORTABLE_DIR%\%%d" /E /NFL /NDL /NJH /NJS /XF "*.pyc"
    )
)

echo [完成] 项目文件复制完毕

echo.
echo ============================================
echo   Step 3/3: 生成便携启动脚本
echo ============================================

:: 实时变声 GUI
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%%~dp0"
echo echo RVC 实时变声 - 便携版启动中...
echo "%%~dp0python\python.exe" "%%~dp0gui_v1.py"
echo pause
) > "%PORTABLE_DIR%\start-gui.bat"

:: Web 界面
(
echo @echo off
echo chcp 65001 ^>nul
echo cd /d "%%~dp0"
echo echo RVC Web 界面 - 便携版启动中...
echo echo 浏览器打开: http://localhost:7897
echo "%%~dp0python\python.exe" "%%~dp0infer-web.py" --pycmd "%%~dp0python\python.exe" --port 7897
echo pause
) > "%PORTABLE_DIR%\start-web.bat"

:: 使用说明
(
echo RVC 实时变声 - 便携版
echo ======================
echo.
echo 启动方式：
echo   start-gui.bat   实时变声 GUI（游戏语音用这个）
echo   start-web.bat   Web 训练/推理界面（浏览器操作）
echo.
echo 首次使用请确保：
echo   1. 已安装 VB-Cable：https://vb-audio.com/Cable/
echo   2. 系统默认麦克风设为 CABLE Output（mmsys.cpl）
echo   3. 模型文件已放在 assets\weights\ 目录下
echo.
echo 参数推荐：
echo   模型：yalin_yujie.pth（御姐音）
echo   音高：+12
echo   F0 算法：rmvpe
echo   Index Rate：0.75
echo   半精度：开启
echo.
echo 游戏音频路由：
echo   物理麦克风 → RVC 变声 → CABLE Input → （虚拟线）→ CABLE Output → 游戏
echo.
) > "%PORTABLE_DIR%\使用说明.txt"

echo [完成] 便携启动脚本生成完毕

:: ==========================================
:: 最终统计
:: ==========================================
echo.
echo ============================================
echo   打包完成！
echo ============================================
echo   便携版路径: %PORTABLE_DIR%
echo.

:: 显示总大小
for /f "tokens=3" %%a in ('dir /s "%PORTABLE_DIR%" ^| findstr "File(s)"') do set total_bytes=%%a
echo   总大小: 请查看资源管理器

echo.
echo   下次使用时：
echo   - 将 RVC-Portable 文件夹复制到 U 盘或移动硬盘
echo   - 网吧电脑插入后，双击 start-gui.bat 即可
echo.
echo ============================================
pause
