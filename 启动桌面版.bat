@echo off
chcp 936 >nul
title KylinSecOps Desktop

echo =========================================
echo  麒麟OS 安全智能运维Agent 桌面版
echo  KylinSecOps Agent Desktop
echo =========================================
echo.
echo 正在启动后台服务...
echo.

cd /d "%~dp0desktop\dist"
if exist "KylinSecOps.exe" (
    start "" "KylinSecOps.exe"
    echo 已启动桌面版，请稍候...
    echo.
    echo 管理员登录: admin / admin123
    echo 如果浏览器没有自动打开，请手动访问:
    echo   http://localhost:8000/docs
    echo.
    echo 按任意键关闭此窗口
    pause >nul
) else (
    echo 错误: 找不到 KylinSecOps.exe
    echo 请先运行构建脚本
    pause
)
