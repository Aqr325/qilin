#!/bin/bash
#
# Kylin Security Operations — 麒麟系统一键部署脚本
# 适用于 麒麟V10 (KylinOS V10) 高级服务器版
#
# 功能:
#   1. 安装系统依赖 (Python 3.11+, PostgreSQL, Redis, Nginx)
#   2. 创建 Python 虚拟环境并安装后端依赖
#   3. 初始化 PostgreSQL 数据库并导入种子数据
#   4. 构建前端静态资源
#   5. 配置 Nginx 反向代理
#   6. 安装 systemd 服务并启动
#
# 用法:
#   sudo bash deploy_kylin.sh                    # 完整部署
#   sudo bash deploy_kylin.sh --skip-db          # 跳过数据库初始化
#   sudo bash deploy_kylin.sh --dev              # 开发模式 (SQLite)
#   sudo bash deploy_kylin.sh --help             # 查看帮助
#
set -euo pipefail

# ══════════════════════════════════════════════════════════════════════════
# Configuration
# ══════════════════════════════════════════════════════════════════════════
VERSION="3.2.0"
PROJECT_NAME="kylin-secops-api"

INSTALL_DIR="/opt/${PROJECT_NAME}"
CONFIG_DIR="/etc/${PROJECT_NAME}"
DATA_DIR="/var/lib/${PROJECT_NAME}"
LOG_DIR="/var/log/${PROJECT_NAME}"
RUN_DIR="/var/run/${PROJECT_NAME}"
FRONTEND_DIR="${INSTALL_DIR}/frontend"

# Source project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
PROJECT_ROOT="$(cd "${DEPLOY_DIR}/../.." && pwd)"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
OK="✅"; WARN="⚠️ "; ERR="❌"; INFO="📌"

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ══════════════════════════════════════════════════════════════════════════
# Pre-flight checks
# ══════════════════════════════════════════════════════════════════════════

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "请以 root 身份运行 (sudo bash deploy_kylin.sh)"
        exit 1
    fi
}

detect_kylin() {
    log_info "检测麒麟系统..."
    if [[ -f /etc/kylin-release ]]; then
        log_info "${OK} 检测到麒麟系统: $(head -1 /etc/kylin-release)"
        log_info "  内核版本: $(uname -r)"
        log_info "  架构: $(uname -m)"
        return 0
    else
        log_warn "${WARN} 未检测到麒麟系统，将以通用 Linux 模式部署"
        return 1
    fi
}

# ══════════════════════════════════════════════════════════════════════════
# Phase 1: System Dependencies
# ══════════════════════════════════════════════════════════════════════════

install_system_deps() {
    log_info "${INFO} Phase 1/5: 安装系统依赖..."

    local PKG_MANAGER=""
    if command -v dnf &>/dev/null; then
        PKG_MANAGER="dnf"
    elif command -v yum &>/dev/null; then
        PKG_MANAGER="yum"
    elif command -v apt &>/dev/null; then
        PKG_MANAGER="apt"
    else
        log_error "未找到可用的包管理器"
        exit 1
    fi
    log_info "使用包管理器: $PKG_MANAGER"

    # 麒麟系统特有：安装 EPEL 和 PowerTools
    if [[ -f /etc/kylin-release ]]; then
        if command -v dnf &>/dev/null; then
            dnf install -y epel-release 2>/dev/null || true
            dnf config-manager --set-enabled powertools 2>/dev/null || true
        fi
    fi

    # 安装系统包
    local PKGS=""
    if [[ "$PKG_MANAGER" == "dnf" || "$PKG_MANAGER" == "yum" ]]; then
        PKGS="python3 python3-devel python3-pip postgresql15-server postgresql15-contrib postgresql15-devel redis nginx git gcc gcc-c++ make openssl-devel bzip2-devel libffi-devel zlib-devel"
    else
        PKGS="python3 python3-dev python3-pip python3-venv postgresql postgresql-contrib redis-server nginx git gcc g++ make"
    fi

    $PKG_MANAGER install -y $PKGS

    # 检查 Python 版本 (需要 3.11+)
    local PYTHON_VERSION
    PYTHON_VERSION=$(python3 --version 2>&1 | sed 's/Python //' | cut -d. -f1-2)
    log_info "Python 版本: $(python3 --version 2>&1)"

    if [[ $(echo "$PYTHON_VERSION >= 3.11" | bc 2>/dev/null) != "1" ]]; then
        log_warn "${WARN} Python $PYTHON_VERSION 低于推荐 3.11+"
        log_warn "麒麟 V10 默认 Python 3.9/3.11，如需升级请手动安装 Python 3.11+"
    fi

    # 启动并启用 Redis
    systemctl enable redis 2>/dev/null || systemctl enable redis-server 2>/dev/null || true
    systemctl start redis 2>/dev/null || systemctl start redis-server 2>/dev/null || true

    # 启动并启用 PostgreSQL
    systemctl enable postgresql 2>/dev/null || systemctl enable postgresql-15 2>/dev/null || true
    systemctl start postgresql 2>/dev/null || systemctl start postgresql-15 2>/dev/null || true

    # 启动并启用 Nginx
    systemctl enable nginx 2>/dev/null || true
    systemctl start nginx 2>/dev/null || true

    log_info "${OK} 系统依赖安装完成"
}

# ══════════════════════════════════════════════════════════════════════════
# Phase 2: Python Virtual Environment
# ══════════════════════════════════════════════════════════════════════════

setup_python_env() {
    log_info "${INFO} Phase 2/5: 配置 Python 虚拟环境..."

    # 创建目录
    mkdir -p "$INSTALL_DIR" "$CONFIG_DIR" "$DATA_DIR" "$LOG_DIR" "$RUN_DIR"

    # 创建 Python 虚拟环境
    python3 -m venv "${INSTALL_DIR}/venv"
    source "${INSTALL_DIR}/venv/bin/activate"

    # 升级 pip
    pip install --upgrade pip setuptools wheel

    # 安装后端依赖
    if [[ -f "${PROJECT_ROOT}/backend/requirements.txt" ]]; then
        pip install -r "${PROJECT_ROOT}/backend/requirements.txt"
    else
        log_warn "${WARN} requirements.txt 未找到，安装核心依赖..."
        pip install fastapi uvicorn[standard] sqlalchemy asyncpg aiosqlite psycopg2-binary \
            redis celery alembic python-jose[cryptography] passlib[bcrypt] bcrypt \
            pydantic pydantic-settings python-multipart aiofiles httpx websockets \
            prometheus-client
    fi

    # 复制后端代码
    cp -a "${PROJECT_ROOT}/backend/app" "${INSTALL_DIR}/"
    cp -a "${PROJECT_ROOT}/backend/alembic" "${INSTALL_DIR}/" 2>/dev/null || true
    cp -a "${PROJECT_ROOT}/backend/alembic.ini" "${INSTALL_DIR}/" 2>/dev/null || true
    cp -a "${PROJECT_ROOT}/backend/.env.example" "${CONFIG_DIR}/.env" 2>/dev/null || true

    # 创建 .env 配置文件
    cat > "${CONFIG_DIR}/.env" << 'ENVFILE'
# Kylin SecOps 后端配置
DATABASE_URL=postgresql+asyncpg://secops:SecOps@2026!@localhost:5432/kylin_secops
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
DEBUG=False
LOG_LEVEL=INFO
JWT_ALGORITHM=RS256
JWT_SECRET_KEY=/etc/kylin-secops-api/jwt-secret.key
JWT_PUBLIC_KEY=/etc/kylin-secops-api/jwt-public.pem
BCRYPT_ROUNDS=12
CORS_ORIGINS=https://secops.company.com
UVICORN_WORKERS=4
ENVFILE
    chmod 640 "${CONFIG_DIR}/.env"

    # 生成 JWT 密钥对
    if [[ ! -f "${CONFIG_DIR}/jwt-secret.key" ]]; then
        openssl genrsa -out "${CONFIG_DIR}/jwt-secret.key" 2048
        openssl rsa -in "${CONFIG_DIR}/jwt-secret.key" -pubout -out "${CONFIG_DIR}/jwt-public.pem"
        chmod 640 "${CONFIG_DIR}/jwt-secret.key"
        chmod 644 "${CONFIG_DIR}/jwt-public.pem"
    fi

    log_info "${OK} Python 虚拟环境已配置"
}

# ══════════════════════════════════════════════════════════════════════════
# Phase 3: Build Frontend
# ══════════════════════════════════════════════════════════════════════════

build_frontend() {
    log_info "${INFO} Phase 3/5: 构建前端资源..."

    local FRONTEND_SRC="${PROJECT_ROOT}/frontend"
    mkdir -p "$FRONTEND_DIR"

    if [[ -d "$FRONTEND_SRC/dist" ]]; then
        # 使用已构建的 dist
        cp -a "${FRONTEND_SRC}/dist/" "${FRONTEND_DIR}/"
        log_info "${OK} 使用已有构建产物"
    elif [[ -f "${FRONTEND_SRC}/package.json" ]]; then
        # 在前端目录构建
        command -v node &>/dev/null || {
            log_warn "${WARN} Node.js 未安装，尝试安装..."
            if command -v dnf &>/dev/null; then
                dnf module install -y nodejs:20 2>/dev/null || dnf install -y nodejs 2>/dev/null || true
            else
                curl -fsSL https://rpm.nodesource.com/setup_20.x | bash - 2>/dev/null || true
                dnf install -y nodejs 2>/dev/null || true
            fi
        }

        if command -v node &>/dev/null; then
            cd "$FRONTEND_SRC"
            npm ci
            npm run build
            cp -a "${FRONTEND_SRC}/dist/" "${FRONTEND_DIR}/"
            log_info "${OK} 前端构建完成"
        else
            log_warn "${WARN} Node.js 不可用，跳过前端构建"
        fi
    else
        log_warn "${WARN} 前端源码未找到，跳过前端构建"
    fi
}

# ══════════════════════════════════════════════════════════════════════════
# Phase 4: Database Setup
# ══════════════════════════════════════════════════════════════════════════

setup_database() {
    log_info "${INFO} Phase 4/5: 配置数据库..."

    # 调用专门的 PostgreSQL 设置脚本
    if [[ -f "${SCRIPT_DIR}/setup_postgresql.sh" ]]; then
        bash "${SCRIPT_DIR}/setup_postgresql.sh"
    fi

    # 初始化数据库表和数据
    source "${INSTALL_DIR}/venv/bin/activate"
    cd "$INSTALL_DIR"

    # 运行 Alembic 迁移
    if [[ -f "alembic.ini" ]]; then
        alembic upgrade head 2>/dev/null || {
            log_warn "${WARN} Alembic 迁移失败，尝试直接创建表..."
            python3 -c "
import sys; sys.path.insert(0, '.')
import os; os.environ['DATABASE_URL'] = '$(grep DATABASE_URL ${CONFIG_DIR}/.env | cut -d= -f2-)'
from app.models import Base
from app.core.database import engine
import asyncio
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    print('Tables created successfully')
    await engine.dispose()
asyncio.run(init())
" 2>&1
        }
    fi

    # 导入种子数据
    if [[ -f "${PROJECT_ROOT}/backend/seed_orm.py" ]]; then
        log_info "导入种子数据..."
        python3 "${PROJECT_ROOT}/backend/seed_orm.py" 2>/dev/null || \
        log_warn "${WARN} 种子数据导入跳过（PostgreSQL 模式下请手动运行）"
    fi

    log_info "${OK} 数据库配置完成"
}

# ══════════════════════════════════════════════════════════════════════════
# Phase 5: Configure Services
# ══════════════════════════════════════════════════════════════════════════

configure_services() {
    log_info "${INFO} Phase 5/5: 配置系统服务..."

    # 安装 Nginx 配置
    if [[ -f "${DEPLOY_DIR}/nginx/kylin-secops.conf" ]]; then
        cp "${DEPLOY_DIR}/nginx/kylin-secops.conf" "/etc/nginx/conf.d/${PROJECT_NAME}.conf"
        nginx -t 2>/dev/null && systemctl reload nginx || \
        log_warn "${WARN} Nginx 配置检查失败，请手动检查"
    fi

    # 安装 API systemd 服务
    if [[ -f "${DEPLOY_DIR}/systemd/kylin-secops-api.service" ]]; then
        cp "${DEPLOY_DIR}/systemd/kylin-secops-api.service" "/usr/lib/systemd/system/"
        systemctl daemon-reload
        systemctl enable "${PROJECT_NAME}.service"
        systemctl start "${PROJECT_NAME}.service" || \
        log_warn "${WARN} API 服务启动失败，请检查 journalctl -u ${PROJECT_NAME}"
    fi

    # 创建管理员用户
    source "${INSTALL_DIR}/venv/bin/activate"
    cd "$INSTALL_DIR"
    python3 -c "
import sys; sys.path.insert(0, '.')
import os; os.environ['DATABASE_URL'] = '$(grep DATABASE_URL ${CONFIG_DIR}/.env | cut -d= -f2-)'
import asyncio
from app.core.database import async_session_factory
from app.services import auth_service

async def create_admin():
    async with async_session_factory() as db:
        try:
            await auth_service.create_user(db, 'admin', 'admin123', 'Administrator')
            print('Admin user created')
        except Exception as e:
            print(f'Skip admin creation: {e}')

asyncio.run(create_admin())
" 2>/dev/null || true

    log_info "${OK} 系统服务配置完成"
}

# ══════════════════════════════════════════════════════════════════════════
# Verify Deployment
# ══════════════════════════════════════════════════════════════════════════

verify_deployment() {
    log_info "${INFO} 验证部署..."

    echo ""
    echo "==================== 部署验证 ===================="

    # 检查服务状态
    local SERVICES=("nginx" "redis" "postgresql" "${PROJECT_NAME}")
    for svc in "${SERVICES[@]}"; do
        if systemctl is-active --quiet "$svc" 2>/dev/null; then
            echo -e "  ${OK} $svc: 运行中"
        elif systemctl is-active --quiet "${svc}-server" 2>/dev/null; then
            echo -e "  ${OK} ${svc}-server: 运行中"
        elif systemctl is-active --quiet "${svc}@.service" 2>/dev/null; then
            echo -e "  ${OK} ${svc}: 运行中"
        elif systemctl is-active --quiet "postgresql-15" 2>/dev/null; then
            echo -e "  ${OK} postgresql-15: 运行中"
        else
            echo -e "  ${WARN} $svc: 未运行"
        fi
    done

    # 检查 API 端口
    if ss -tlnp | grep -q ":8000"; then
        echo -e "  ${OK} API (8000): 正在监听"
    else
        echo -e "  ${WARN} API (8000): 未监听"
    fi

    # 检查前端
    if [[ -f "${FRONTEND_DIR}/index.html" ]]; then
        echo -e "  ${OK} 前端: 已部署 (${FRONTEND_DIR})"
    fi

    echo "================================================="
    echo ""

    if ss -tlnp | grep -q ":443"; then
        log_info "${OK} 部署完成！访问 https://secops.company.com"
    else
        log_info "${OK} 部署完成！"
        log_info "  前端: http://<server-ip>/"
        log_info "  API:  http://<server-ip>:8000/docs"
        log_info "  登录: admin / admin123"
        log_info ""
        log_info "运维命令:"
        log_info "  systemctl status ${PROJECT_NAME}"
        log_info "  journalctl -fu ${PROJECT_NAME} -n 100"
        log_info "  systemctl status nginx redis postgresql"
    fi
}

# ══════════════════════════════════════════════════════════════════════════
# Post-Installation: Agent Setup
# ══════════════════════════════════════════════════════════════════════════

show_agent_setup() {
    echo ""
    echo "==================== Agent 客户端安装 ===================="
    echo ""
    echo "在被管主机上执行以下命令安装 Agent:"
    echo ""
    echo "  # 方式 1: 通过部署平台分发"
    echo "  curl -fsSL https://secops.company.com/install.sh | sudo bash"
    echo ""
    echo "  # 方式 2: 手动安装"
    echo "  sudo bash ${PROJECT_ROOT}/agent/install.sh"
    echo ""
    echo "安装后配置:"
    echo "  vim /etc/kylin-secops-agent/config.yaml"
    echo "  修改 platform.host = secops.company.com"
    echo "  修改 platform.token = <注册令牌>"
    echo ""
    echo "然后重启: systemctl restart kylin-secops-agent"
    echo "========================================================"
    echo ""
}

# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

main() {
    echo ""
    echo "=========================================="
    echo " Kylin SecOps v${VERSION}"
    echo " 麒麟安全智能运维平台 — 一键部署"
    echo "=========================================="
    echo ""

    local SKIP_DB=false
    local DEV_MODE=false

    for arg in "$@"; do
        case "$arg" in
            --skip-db) SKIP_DB=true ;;
            --dev) DEV_MODE=true ;;
            --help)
                echo "用法: $0 [选项]"
                echo "  (无选项)  完整生产部署"
                echo "  --skip-db 跳过数据库初始化"
                echo "  --dev     开发模式 (使用 SQLite)"
                echo "  --help    显示帮助"
                exit 0
                ;;
        esac
    done

    check_root
    detect_kylin
    install_system_deps
    setup_python_env
    build_frontend

    if ! $SKIP_DB && ! $DEV_MODE; then
        setup_database
    elif $DEV_MODE; then
        log_info "${INFO} 开发模式：使用 SQLite 数据库"
    fi

    configure_services
    verify_deployment
    show_agent_setup

    echo ""
    log_info "${OK} 麒麟安全智能运维平台部署完成！"
    echo ""
}

main "$@"