@echo off
chcp 936 >nul
title 麒麟OS安全运维 桌面版

echo =========================================
echo  麒麟OS 安全智能运维Agent 桌面版
echo  KylinSecOps Agent Desktop
echo =========================================
echo.
echo 正在启动桌面程序...
echo.

cd /d "%~dp0"
if exist "麒麟OS安全运维_桌面程序\麒麟OS安全运维.exe" (
    start "" "麒麟OS安全运维_桌面程序\麒麟OS安全运维.exe"
    echo 已启动桌面版，请稍候...
    echo.
    echo 管理员登录: admin / KylinSecOps@2026
    echo 首次启动将自动初始化数据库并应用该默认密码，登录后建议修改。
    echo.
    echo 按任意键关闭此窗口
    pause >nul
) else (
    echo 错误: 找不到 麒麟OS安全运维_桌面程序\麒麟OS安全运维.exe
    echo 请确认交付目录 麒麟OS安全运维_桌面程序 存在
    pause
)
