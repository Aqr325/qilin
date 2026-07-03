@echo off
chcp 65001 >nul
title 麒麟OS 安全运维 - 桌面版

echo ╔══════════════════════════════════════════════════════╗
echo ║   麒麟OS 安全智能运维Agent - 桌面版                    ║
echo ║   Kylin SecOps Agent Desktop                         ║
echo ╚══════════════════════════════════════════════════════╝
echo.

set DESKTOP_DIR=%~dp0
cd /d "%DESKTOP_DIR%"

:: Check Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ✗ 未找到 Python，请安装 Python 3.11+
    pause
    exit /b 1
)

:: Launch
echo 启动桌面版应用...
python desktop_launcher.py

if %errorlevel% neq 0 (
    echo.
    echo ✗ 启动失败，请检查依赖是否安装完整
    echo   运行: cd backend ^&amp; pip install -r requirements.txt
    pause
)
