#!/bin/bash
#
# Kylin Security Operations — PostgreSQL 数据库初始化脚本
# 适用于 麒麟V10 (KylinOS V10) + PostgreSQL 15/16
#
# 用法:
#   sudo bash setup_postgresql.sh                    # 标准安装
#   sudo bash setup_postgresql.sh --password MyP@ss  # 指定密码
#
set -euo pipefail

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

# ── Configuration ──────────────────────────────────────────────────────────
DB_NAME="kylin_secops"
DB_USER="secops"
DB_PASSWORD="${1:-SecOps@2026!}"  # 默认密码，建议通过参数修改
PG_VERSION=$(psql --version 2>/dev/null | sed 's/.* //' | cut -d. -f1 || echo "16")

# ── Check root ─────────────────────────────────────────────────────────────
if [[ $EUID -ne 0 ]]; then
    log_error "请以 root 身份运行 (sudo bash setup_postgresql.sh)"
    exit 1
fi

# ── Detect Kylin OS ────────────────────────────────────────────────────────
log_info "检测麒麟系统版本..."
if [[ -f /etc/kylin-release ]]; then
    cat /etc/kylin-release
    IS_KYLIN=true
elif [[ -f /etc/openEuler-release ]]; then
    cat /etc/openEuler-release
    IS_KYLIN=false
    log_warn "检测到 openEuler，将使用对应的包管理器"
elif grep -qi "kylin" /etc/os-release 2>/dev/null; then
    IS_KYLIN=true
else
    IS_KYLIN=false
    log_warn "未检测到麒麟系统，将尝试通用安装方式"
fi

# ── Install PostgreSQL ─────────────────────────────────────────────────────
install_postgresql() {
    log_info "安装 PostgreSQL..."

    if command -v psql &>/dev/null; then
        log_info "PostgreSQL $(psql --version) 已安装"
        return
    fi

    if $IS_KYLIN; then
        # 麒麟系统使用 yum/dnf
        if command -v dnf &>/dev/null; then
            dnf install -y postgresql15-server postgresql15-contrib postgresql15-devel
        elif command -v yum &>/dev/null; then
            yum install -y postgresql15-server postgresql15-contrib postgresql15-devel
        else
            log_error "未找到包管理器"
            exit 1
        fi
        # 麒麟系统默认数据目录
        PG_DATA="/var/lib/pgsql/15/data"
    else
        # 通用安装
        if command -v apt &>/dev/null; then
            apt update && apt install -y postgresql postgresql-contrib
        elif command -v yum &>/dev/null; then
            yum install -y postgresql-server postgresql-contrib
        fi
        PG_DATA=$(su - postgres -c "psql -c 'SHOW data_directory'" 2>/dev/null | sed -n '3p' | tr -d ' ') || PG_DATA="/var/lib/pgsql/data"
    fi

    log_info "PostgreSQL 安装完成"
}

# ── Initialize and Start ───────────────────────────────────────────────────
init_postgresql() {
    log_info "初始化 PostgreSQL..."

    if $IS_KYLIN && [[ -f "/usr/pgsql-15/bin/postgresql-15-setup" ]]; then
        /usr/pgsql-15/bin/postgresql-15-setup initdb || true
    elif systemctl is-enabled postgresql &>/dev/null; then
        # 已初始化
        true
    else
        postgresql-setup --initdb || true
    fi

    # 启动服务
    systemctl enable postgresql 2>/dev/null || systemctl enable postgresql-15 2>/dev/null || true
    systemctl start postgresql 2>/dev/null || systemctl start postgresql-15 2>/dev/null || true
    sleep 2

    log_info "PostgreSQL 服务已启动"
}

# ── Configure Authentication ───────────────────────────────────────────────
configure_auth() {
    log_info "配置数据库认证方式..."

    # 查找 pg_hba.conf
    local PG_HBA
    PG_HBA=$(su - postgres -c "psql -c 'SHOW hba_file'" 2>/dev/null | sed -n '3p' | tr -d ' ') || \
    PG_HBA=$(find / -name "pg_hba.conf" -path "*/pgsql/*" 2>/dev/null | head -1) || \
    PG_HBA="/var/lib/pgsql/15/data/pg_hba.conf"

    if [[ -f "$PG_HBA" ]]; then
        # 添加 scram-sha-256 认证
        sed -i 's/ident$/scram-sha-256/g' "$PG_HBA"
        sed -i 's/peer$/scram-sha-256/g' "$PG_HBA"

        # 添加本地 host 连接
        if ! grep -q "kylin_secops" "$PG_HBA"; then
            echo "# Kylin SecOps database" >> "$PG_HBA"
            echo "host    $DB_NAME    $DB_USER    127.0.0.1/32    scram-sha-256" >> "$PG_HBA"
            echo "host    $DB_NAME    $DB_USER    ::1/128         scram-sha-256" >> "$PG_HBA"
        fi

        systemctl reload postgresql 2>/dev/null || systemctl reload postgresql-15 2>/dev/null || true
        log_info "认证配置已完成"
    else
        log_warn "未找到 pg_hba.conf，请手动配置认证方式"
    fi
}

# ── Create Database and User ───────────────────────────────────────────────
create_database() {
    log_info "创建数据库和用户..."

    # 创建用户
    su - postgres -c "psql -c \"CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';\"" 2>/dev/null || \
    su - postgres -c "psql -c \"ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';\"" 2>/dev/null || true

    # 创建数据库
    su - postgres -c "psql -c \"CREATE DATABASE $DB_NAME OWNER $DB_USER ENCODING 'UTF8' LC_COLLATE 'zh_CN.UTF-8' LC_CTYPE 'zh_CN.UTF-8' TEMPLATE template0;\"" 2>/dev/null || \
    log_info "数据库 $DB_NAME 已存在"

    # 授予权限
    su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;\"" 2>/dev/null || true

    # 安装 pgvector 扩展 (用于 RAG 向量存储)
    log_info "安装 pgvector 扩展..."
    if command -v dnf &>/dev/null; then
        dnf install -y pgvector_15 2>/dev/null || dnf install -y pgvector 2>/dev/null || log_warn "pgvector 安装失败，AI 向量功能将不可用"
    fi

    log_info "数据库创建完成"
    log_info "  数据库: $DB_NAME"
    log_info "  用户名: $DB_USER"
    log_info "  密码:   $DB_PASSWORD"
}

# ── Verify ─────────────────────────────────────────────────────────────────
verify_setup() {
    log_info "验证数据库连接..."
    PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -c "SELECT version();" 2>/dev/null || {
        log_warn "连接测试未通过，请检查配置"
        return 1
    }
    log_info "✅ PostgreSQL 连接测试成功"
}

# ── Migrate from SQLite to PostgreSQL ──────────────────────────────────────
migrate_from_sqlite() {
    local SQLITE_DB="${1:-kylin_secops_dev.db}"
    if [[ ! -f "$SQLITE_DB" ]]; then
        log_warn "未找到 SQLite 数据库文件 $SQLITE_DB，跳过迁移"
        return
    fi

    log_info "从 SQLite 迁移数据到 PostgreSQL..."
    log_info "请确保已配置 DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
    log_info "然后运行: python3 -m app.scripts.migrate_sqlite_to_pg $SQLITE_DB"
    log_info "或重新 seed 数据库: python3 seed_orm.py"
}

# ══════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════

main() {
    echo ""
    echo "=========================================="
    echo " Kylin SecOps — PostgreSQL 数据库初始化"
    echo "=========================================="
    echo ""

    if [[ $# -ge 1 && "$1" =~ ^-- ]]; then
        DB_PASSWORD="${2:-SecOps@2026!}"
    fi

    install_postgresql
    init_postgresql
    configure_auth
    create_database
    verify_setup

    echo ""
    log_info "=========================================="
    log_info " PostgreSQL 初始化完成！"
    log_info "=========================================="
    echo ""
    echo "连接信息:"
    echo "  数据库地址: postgresql+asyncpg://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
    echo ""
    echo "配置后端 .env 文件:"
    echo "  DATABASE_URL=postgresql+asyncpg://$DB_USER:$DB_PASSWORD@localhost:5432/$DB_NAME"
    echo "  REDIS_HOST=localhost"
    echo ""
    echo "运维命令:"
    echo "  查看服务:  systemctl status postgresql"
    echo "  连接数据库: psql -h 127.0.0.1 -U $DB_USER -d $DB_NAME"
    echo "  备份数据库: pg_dump -h 127.0.0.1 -U $DB_USER -d $DB_NAME > secops_backup.sql"
    echo ""
}

main "$@"
