@echo off
chcp 65001 >nul
title 麒麟OS Agent - 构建安装包

echo.
echo  +===========================================+
echo  |  麒麟OS 安全智能运维 Agent - 构建工具      |
echo  +===========================================+
echo.

setlocal enabledelayedexpansion

set "ROOT=%~dp0"
cd /d "%ROOT%"

REM --- 检查 Node.js ---
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo  [错误] 找不到 Node.js
    echo  请安装 Node.js 20+ 后重试
    pause
    exit /b 1
)

REM --- 检查依赖 ---
if not exist "%ROOT%node_modules\" (
    echo  [安装] 安装 npm 依赖...
    call npm install
    if %errorlevel% neq 0 (
        echo  [错误] npm install 失败
        pause
        exit /b 1
    )
)

REM --- 选择构建模式 ---
echo  请选择构建模式:
echo    [1] 目录模式 (build:dir) - 快速测试, 不打包安装包
echo    [2] 安装包模式 (build)   - 生成 NSIS 安装包
echo    [3] 发布模式 (release)   - 构建并上传到 GitHub Releases
echo.

set /p MODE="请输入选项 (1/2/3, 默认 1): "
if "%MODE%"=="" set "MODE=1"

echo.
echo  [构建] 正在构建...

if "%MODE%"=="1" (
    call npm run build:dir
) else if "%MODE%"=="2" (
    call npm run build
) else if "%MODE%"=="3" (
    call npm run release
) else (
    echo  [错误] 无效选项
    pause
    exit /b 1
)

if %errorlevel% equ 0 (
    echo.
    echo  [OK] 构建成功!
    echo  输出目录: "%ROOT%release\"
) else (
    echo.
    echo  [错误] 构建失败，请查看上方日志
)

echo.
pause