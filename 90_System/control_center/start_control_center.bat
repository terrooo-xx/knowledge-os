@echo off
chcp 936 >nul
setlocal enabledelayedexpansion
rem ============================================================
rem  Knowledge OS Control Center - Windows one-click launcher
rem  位置无关：由本脚本自身位置反推项目根目录，不硬编码路径
rem ============================================================

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "VAULT_ROOT=%%~fI"
set "SERVER_PY=%VAULT_ROOT%\90_System\control_center\server.py"
set "URL=http://localhost:8765"
set "HEALTH_URL=http://localhost:8765/api/health"
set "LOG=%SCRIPT_DIR%launcher.log"

if not exist "%SERVER_PY%" (
    echo [%date% %time%] server.py not found: %SERVER_PY% >> "%LOG%"
    powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Knowledge OS Control Center 启动失败：未找到 server.py。请检查 Knowledge Base 路径。')"
    exit /b 1
)

rem 情况 B：服务已在运行 -> 直接打开浏览器，不启动第二个服务
curl.exe -s -o NUL --max-time 2 "%HEALTH_URL%" >nul 2>&1
if not errorlevel 1 (
    echo [%date% %time%] already running, open browser >> "%LOG%"
    rundll32 url.dll,FileProtocolHandler "%URL%"
    exit /b 0
)

rem 选择 Python 解释器（PATH 中的 python 或 py，不硬编码）
set "PY="
where python >nul 2>&1 && set "PY=python"
if not defined PY where py >nul 2>&1 && set "PY=py"
if not defined PY (
    echo [%date% %time%] python not found >> "%LOG%"
    powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Knowledge OS Control Center 启动失败：未找到 Python。请安装 Python 并加入 PATH。')"
    exit /b 1
)
echo [%date% %time%] python: %PY% >> "%LOG%"
echo [%date% %time%] vault : %VAULT_ROOT% >> "%LOG%"

rem 独立启动 server（不依赖本窗口；工作目录已切到项目根）
pushd "%VAULT_ROOT%"
start "Knowledge OS Control Center server" /min cmd /c ""%PY%" "90_System\control_center\server.py" >> "%LOG%" 2>&1"
popd

rem 轮询等待服务真正可访问（最多 15 秒，用 curl 探测）
set /a TRY=0
:waitloop
set /a TRY+=1
curl.exe -s -o NUL --max-time 2 "%HEALTH_URL%" >nul 2>&1
if not errorlevel 1 goto ready
if %TRY% GEQ 15 goto failed
timeout /t 1 /nobreak >nul
goto waitloop

:ready
echo [%date% %time%] server ready after %TRY% s >> "%LOG%"
rundll32 url.dll,FileProtocolHandler "%URL%"
exit /b 0

:failed
echo [%date% %time%] server not ready within 15s >> "%LOG%"
powershell -NoProfile -Command "Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show('Knowledge OS Control Center 启动失败。请检查：' + [char]10 + '1. Python 是否已安装并加入 PATH' + [char]10 + '2. Knowledge Base 路径是否正确' + [char]10 + '3. 启动日志：90_System/control_center/launcher.log')"
exit /b 1