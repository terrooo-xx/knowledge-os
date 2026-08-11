@echo off
chcp 936 >nul
setlocal
rem ============================================================
rem  为 Knowledge OS Control Center 创建桌面快捷方式（一次性）
rem  位置无关：由本脚本自身位置反推项目根目录
rem ============================================================
set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..\..") do set "VAULT_ROOT=%%~fI"
set "TARGET=%VAULT_ROOT%\90_System\control_center\start_control_center.bat"
set "DESKTOP=%USERPROFILE%\Desktop"

if not exist "%TARGET%" (
    echo 错误：未找到启动器 %TARGET%
    pause
    exit /b 1
)

powershell -NoProfile -Command "$ws = New-Object -ComObject WScript.Shell; $ln = $ws.CreateShortcut('%DESKTOP%\Knowledge OS Control Center.lnk'); $ln.TargetPath = '%TARGET%'; $ln.WorkingDirectory = '%VAULT_ROOT%'; $ln.IconLocation = 'shell32.dll,13'; $ln.Description = 'Knowledge OS Control Center'; $ln.Save()"
if %ERRORLEVEL% NEQ 0 (
    echo 错误：创建快捷方式失败
    pause
    exit /b 1
)
echo 已创建桌面快捷方式：Knowledge OS Control Center
echo 目标：%TARGET%
echo 以后双击桌面图标即可启动 Control Center。
pause