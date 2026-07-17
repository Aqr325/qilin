#!/bin/bash
#
# 麒麟桌面集成安装脚本
# 安装 .desktop 快捷方式和图标到系统
#
# 用法:
#   sudo bash install-desktop.sh                  # 安装到系统范围
#   bash install-desktop.sh --user                # 安装到当前用户
#   bash install-desktop.sh --remove              # 移除快捷方式
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_NAME="kylin-secops"
DESKTOP_FILE="${SCRIPT_DIR}/${APP_NAME}.desktop"
ICON_FILE="${SCRIPT_DIR}/../../icon.png"

# 安装路径
if [[ "${1:-}" == "--user" ]]; then
    DESKTOP_DIR="${HOME}/.local/share/applications"
    ICON_DIR="${HOME}/.local/share/icons/hicolor/256x256/apps"
else
    DESKTOP_DIR="/usr/share/applications"
    ICON_DIR="/usr/share/icons/hicolor/256x256/apps"
fi

install_desktop() {
    echo "安装麒麟桌面集成..."

    mkdir -p "$DESKTOP_DIR" "$ICON_DIR"

    # 安装 .desktop 文件
    if [[ -f "$DESKTOP_FILE" ]]; then
        cp "$DESKTOP_FILE" "${DESKTOP_DIR}/${APP_NAME}.desktop"
        chmod 644 "${DESKTOP_DIR}/${APP_NAME}.desktop"
        echo "  [OK] .desktop → ${DESKTOP_DIR}/${APP_NAME}.desktop"
    else
        echo "  [WARN] .desktop 文件未找到: $DESKTOP_FILE"
    fi

    # 安装图标
    if [[ -f "$ICON_FILE" ]]; then
        cp "$ICON_FILE" "${ICON_DIR}/${APP_NAME}.png"
        chmod 644 "${ICON_DIR}/${APP_NAME}.png"
        echo "  [OK] icon → ${ICON_DIR}/${APP_NAME}.png"
    else
        echo "  [WARN] 图标文件未找到: $ICON_FILE"
    fi

    # 更新桌面数据库（麒麟 Kylin 特有）
    if command -v update-desktop-database &>/dev/null; then
        update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
    fi
    if command -v gtk-update-icon-cache &>/dev/null; then
        gtk-update-icon-cache "$ICON_DIR" 2>/dev/null || true
    fi

    echo "  [OK] 桌面集成安装完成！"
    echo "  在麒麟开始菜单中搜索"麒麟OS安全运维"即可启动。"
}

remove_desktop() {
    echo "移除麒麟桌面集成..."
    rm -f "${DESKTOP_DIR}/${APP_NAME}.desktop"
    rm -f "${ICON_DIR}/${APP_NAME}.png"
    echo "  [OK] 已移除"
}

case "${1:-}" in
    --remove) remove_desktop ;;
    --user|"") install_desktop ;;
    *)
        echo "用法: $0 [--user | --remove]"
        exit 1
        ;;
esac