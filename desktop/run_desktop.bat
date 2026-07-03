@echo off
chcp 65001 >nul
title 麒麟OS 安全运维 - 桌面版启动器

echo ╔══════════════════════════════════════════════════════╗
echo ║   麒麟OS 安全智能运维Agent - 桌面版                    ║
echo ║   Kylin SecOps Agent Desktop                         ║
echo ╚══════════════════════════════════════════════════════╝
echo.

:: ── Find project root ──
set DESKTOP_DIR=%~dp0
set PROJECT_DIR=%DESKTOP_DIR%..
set BACKEND_DIR=%PROJECT_DIR%\kylin-secops-agent\backend

:: ── Kill any existing backend ──
echo [1/3] Stopping any existing backend...
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq python.exe" /nh 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
)
for /f "tokens=2" %%p in ('tasklist /fi "imagename eq kylin-secops-backend.exe" /nh 2^>nul') do (
    taskkill /f /pid %%p >nul 2>&1
)
echo   ✓ Cleaned

:: ── Start Backend ──
echo [2/3] Starting backend server...
cd /d "%BACKEND_DIR%"
start /B "" python desktop_server.py
timeout /t 5 /nobreak >nul
echo   ✓ Backend started
echo   • API: http://localhost:8000

:: ── Launch Electron ──
echo [3/3] Launching desktop application...
cd /d "%DESKTOP_DIR%"
:: Path to electron binary
if exist "%DESKTOP_DIR%\electron-dist\electron.exe" (
    start "" "%DESKTOP_DIR%\electron-dist\electron.exe" "%DESKTOP_DIR%"
) else (
    echo   ⚠ Electron binary not found, opening browser instead...
    start http://localhost:5173
    start http://localhost:8000/docs
)
echo   ✓ Done!

echo.
echo 启动完成！后台进程在运行中，关闭窗口即可退出。
echo.
