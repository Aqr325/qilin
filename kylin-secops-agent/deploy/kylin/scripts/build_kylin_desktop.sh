#!/bin/bash
# =============================================================================
# 麒麟 V10 桌面版构建脚本
# =============================================================================
# 在麒麟 V10 系统上构建桌面程序（AppImage），双击即可运行。
#
# 用法:
#   chmod +x build_kylin_desktop.sh
#   sudo bash build_kylin_desktop.sh           # 完整构建
#   bash build_kylin_desktop.sh --no-sudo      # 无需 root 权限
#   bash build_kylin_desktop.sh --help         # 帮助
#
# 构建产物:
#   desktop/release/麒麟OS安全运维-*.AppImage   ← 双击运行！
# =============================================================================

set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
OK="✅"; WARN="⚠️ "; ERR="❌"; INFO="📌"

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# 定位项目根目录
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
NEED_SUDO=true

# 解析参数
for arg in "$@"; do
    case "$arg" in
        --no-sudo) NEED_SUDO=false ;;
        --help)
            echo "麒麟 V10 桌面版构建脚本"
            echo "用法: bash build_kylin_desktop.sh [--no-sudo] [--help]"
            echo "  (无选项)  完整构建（需 sudo 安装系统依赖）"
            echo "  --no-sudo 跳过系统依赖安装（仅构建）"
            echo "  --help    显示帮助"
            exit 0
            ;;
    esac
done

# =============================================================================
# Step 1: 安装系统依赖
# =============================================================================
install_deps() {
    log_info "${INFO} Step 1/5: 安装系统依赖..."

    local PKG_MANAGER=""
    if command -v dnf &>/dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &>/dev/null; then
        PKG_MANAGER="yum"
    elif command -v apt &>/dev/null; then
        PKG_MANAGER="apt"
    else
        log_error "未找到包管理器（dnf/yum/apt），请手动安装依赖"
        return 1
    fi
    log_info "使用包管理器: $PKG_MANAGER"

    if $NEED_SUDO; then
        # 基础开发工具
        if [[ "$PKG_MANAGER" == "dnf" || "$PKG_MANAGER" == "yum" ]]; then
            sudo $PKG_MANAGER install -y \
                python3 python3-devel python3-pip \
                nodejs npm \
                git gcc gcc-c++ make \
                libXScrnSaver libXcomposite libXdamage libXrandr \
                libgbm libpango libcairo libasound \
                libxkbcommon libdbus libegl libnss3 \
                fuse
        else
            sudo $PKG_MANAGER update -y
            sudo $PKG_MANAGER install -y \
                python3 python3-dev python3-pip python3-venv \
                nodejs npm \
                git gcc g++ make \
                libxss1 libxcomposite1 libxdamage1 libxrandr2 \
                libgbm1 libpango-1.0-0 libcairo2 libasound2 \
                libxkbcommon0 libdbus-1-3 libegl1 libnss3 \
                fuse
        fi
        log_info "${OK} 系统依赖安装完成"
    else
        log_info "跳过系统依赖安装（--no-sudo）"
    fi
}

# =============================================================================
# Step 2: 构建后端 (PyInstaller)
# =============================================================================
build_backend() {
    log_info "${INFO} Step 2/5: 构建后端..."

    cd "$PROJECT_ROOT/kylin-secops-agent/backend"

    # 安装 Python 依赖
    pip install --upgrade pip setuptools wheel
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    fi
    pip install pyinstaller

    # 清理旧的构建产物
    rm -rf dist build *.spec 2>/dev/null || true

    # 执行 PyInstaller 打包
    python3 -m PyInstaller backend.spec --noconfirm

    # 验证产物
    if [[ -f "dist/backend" ]]; then
        chmod +x dist/backend
        local SIZE=$(du -h dist/backend | cut -f1)
        log_info "${OK} 后端构建完成: dist/backend (${SIZE})"
    else
        log_error "后端构建失败，dist/backend 未生成"
        ls -la dist/ 2>/dev/null || echo "dist/ 目录不存在"
        exit 1
    fi

    cd "$PROJECT_ROOT"
}

# =============================================================================
# Step 3: 构建前端 (Vite)
# =============================================================================
build_frontend() {
    log_info "${INFO} Step 3/5: 构建前端..."

    cd "$PROJECT_ROOT/frontend"

    # 安装 npm 依赖
    if [[ ! -d "node_modules" ]]; then
        npm install
    fi

    # 清理旧产物
    rm -rf dist

    # 构建
    npx vite build

    if [[ -f "dist/index.html" ]]; then
        log_info "${OK} 前端构建完成: frontend/dist/"
    else
        log_error "前端构建失败"
        exit 1
    fi

    cd "$PROJECT_ROOT"
}

# =============================================================================
# Step 4: 同步产物到交付目录
# =============================================================================
sync_deliveries() {
    log_info "${INFO} Step 4/5: 同步到交付目录..."

    # 主程序 resources
    mkdir -p "$PROJECT_ROOT/desktop/resources/frontend"

    # 复制后端（Linux ELF 二进制）
    cp "$PROJECT_ROOT/kylin-secops-agent/backend/dist/backend" \
       "$PROJECT_ROOT/desktop/resources/backend"
    # 也复制一份 backend.exe（兼容旧版 main.js 回退逻辑）
    cp "$PROJECT_ROOT/kylin-secops-agent/backend/dist/backend" \
       "$PROJECT_ROOT/desktop/resources/backend.exe"

    # 复制前端
    cp -r "$PROJECT_ROOT/frontend/dist/"* "$PROJECT_ROOT/desktop/resources/frontend/"

    log_info "${OK} 同步完成"
}

# =============================================================================
# Step 5: 构建 Electron 桌面程序 (AppImage)
# =============================================================================
build_electron() {
    log_info "${INFO} Step 5/5: 构建 Electron 桌面程序 (AppImage)..."

    cd "$PROJECT_ROOT/desktop"

    # 安装 npm 依赖
    if [[ ! -d "node_modules" ]]; then
        npm install
    fi

    # 构建 AppImage
    export ELECTRON_BUILDER_ALLOW_UNRESOLVED_DEPENDENCIES=true
    npx electron-builder --linux --x64

    # 显示产物
    echo ""
    log_info "=========================================="
    log_info "  🎉 构建完成！"
    log_info "=========================================="
    echo ""

    if [[ -d "release" ]]; then
        echo "产物目录: $PROJECT_ROOT/desktop/release/"
        ls -lh "$PROJECT_ROOT/desktop/release/" | grep -v "^total"
        echo ""

        # 找到 AppImage
        APPIMAGE=$(ls "$PROJECT_ROOT/desktop/release/"*.AppImage 2>/dev/null | head -1)
        if [[ -n "$APPIMAGE" ]]; then
            chmod +x "$APPIMAGE"
            log_info "${OK} 双击以下文件即可运行:"
            echo "  $APPIMAGE"
            echo ""
            log_info "或在终端中运行:"
            echo "  $APPIMAGE"
        fi
    fi

    cd "$PROJECT_ROOT"
}

# =============================================================================
# Main
# =============================================================================
main() {
    echo ""
    echo "=========================================="
    echo " 麒麟 V10 桌面版构建"
    echo " 麒麟OS安全运维 — 双击 AppImage 运行"
    echo "=========================================="
    echo ""

    # 检查是否需要 sudo
    if $NEED_SUDO && [[ $EUID -ne 0 ]]; then
        log_info "检测到非 root 用户，使用 sudo 安装系统依赖..."
        echo ""
    fi

    install_deps
    build_backend
    build_frontend
    sync_deliveries
    build_electron

    echo ""
    log_info "${OK} 全部完成！尽情享用 🚀"
    echo ""
}

main "$@"