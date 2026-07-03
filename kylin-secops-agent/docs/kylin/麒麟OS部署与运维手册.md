# 麒麟OS安全智能运维平台 — 部署与运维手册

> **版本**: 3.2.0
> **适用系统**: 麒麟V10 (KylinOS V10) 高级服务器版 / 银河麒麟高级服务器操作系统 V10
> **架构**: x86_64 / aarch64 (鲲鹏/飞腾)
> **最后更新**: 2026-06-24

---

## 目录

1. [系统概述](#1-系统概述)
2. [环境要求](#2-环境要求)
3. [快速部署](#3-快速部署)
4. [后端安装](#4-后端安装)
5. [数据库配置](#5-数据库配置)
6. [前端部署](#6-前端部署)
7. [Agent 客户端安装](#7-agent-客户端安装)
8. [Nginx 配置](#8-nginx-配置)
9. [系统运维](#9-系统运维)
10. [安全加固](#10-安全加固)
11. [故障排查](#11-故障排查)
12. [附录](#12-附录)

---

## 1. 系统概述

麒麟OS安全智能运维平台是一个端到端的安全运维管理系统，包含三个核心组件：

| 组件 | 描述 | 技术栈 |
|------|------|--------|
| **后端 API** | 中央管理平台，提供 REST API + WebSocket | FastAPI + PostgreSQL + Redis |
| **前端 SPA** | 管理控制台 | Vue 3 + TypeScript + Chart.js |
| **Agent** | 被管主机端监控代理 | Python asyncio + psutil + SQLite |

### 系统架构

```text
┌──────────────────────────────────────────────────────┐
│                   管理平台 (KylinOS V10 Server)       │
│                                                      │
│  ┌──────────┐    ┌──────────────┐  ┌──────────────┐ │
│  │ Nginx    │───▶│ Uvicorn x4   │  │ Redis 7      │ │
│  │ (443/80) │    │ (FastAPI)    │  │ (缓存/队列)   │ │
│  └──────────┘    └──────┬───────┘  └──────────────┘ │
│                         │                            │
│                  ┌──────▼───────┐                    │
│                  │ PostgreSQL 16│                    │
│                  │ (pgvector)   │                    │
│                  └──────────────┘                    │
└──────────────────────────────────────────────────────┘
         │                         ▲
         │ WebSocket               │ WS reconnect
         ▼                         │
┌────────────────────┐   ┌────────────────────┐
│ 被管主机 (x200)    │   │ 被管主机           │
│ ┌────────────────┐ │   │ ┌────────────────┐ │
│ │ Agent Client   │ │   │ │ Agent Client   │ │
│ │ · 心跳采集     │ │   │ · 心跳采集       │ │
│ │ · 安全监控     │ │   │ · 安全监控       │ │
│ │ · 策略引擎     │ │   │ · 策略引擎       │ │
│ │ · 离线缓存     │ │   │ · 离线缓存       │ │
│ └────────────────┘ │   └────────────────┘ │
│ ┌────────────────┐ │   ┌────────────────┐ │
│ │ kysec/SELinux  │ │   │ kysec/SELinux  │ │
│ │ auditd         │ │   │ auditd         │ │
│ │ firewalld      │ │   │ firewalld      │ │
│ └────────────────┘ │   └────────────────┘ │
└────────────────────┘   └────────────────────┘
```

---

## 2. 环境要求

### 2.1 管理平台（后端服务器）

| 项目 | 最低配置 | 推荐配置 |
|------|---------|---------|
| CPU | 4 核 | 8 核+ |
| 内存 | 8 GB | 16 GB+ |
| 磁盘 | 100 GB SSD | 200 GB SSD |
| 网络 | 100 Mbps | 1 Gbps |
| 操作系统 | 麒麟V10 Server | 麒麟V10 SP1+ |

### 2.2 被管主机（Agent 客户端）

| 项目 | 最低配置 |
|------|---------|
| CPU | 1 核 |
| 内存 | 256 MB |
| 磁盘 | 1 GB (日志缓冲) |
| 操作系统 | 麒麟V10 Server/Desktop, 银河麒麟V10 |

### 2.3 软件依赖

| 软件 | 版本要求 |
|------|---------|
| Python | ≥ 3.11 |
| PostgreSQL | ≥ 15 (推荐 16) |
| Redis | ≥ 6.2 (推荐 7) |
| Nginx | ≥ 1.20 |
| Node.js | ≥ 18 (仅构建时需要) |
| OpenSSL | ≥ 1.1.1 |

---

## 3. 快速部署

### 3.1 一键部署（推荐）

```bash
# 以 root 身份执行
sudo bash deploy/kylin/scripts/deploy_kylin.sh
```

脚本执行内容：
1. 安装系统依赖（Python 3.11+, PostgreSQL 16, Redis 7, Nginx）
2. 创建 Python 虚拟环境并安装后端依赖
3. 初始化 PostgreSQL 数据库
4. 构建前端静态资源
5. 配置 Nginx 反向代理
6. 安装 systemd 服务并启动

### 3.2 分步部署

如果一键部署不适用，请按照以下章节逐步安装。

---

## 4. 后端安装

### 4.1 创建用户和目录

```bash
# 创建服务用户
groupadd -r kylin-secops
useradd -r -g kylin-secops -d /opt/kylin-secops-api -s /sbin/nologin -c "Kylin SecOps API" kylin-secops

# 创建目录
mkdir -p /opt/kylin-secops-api/{app,alembic}
mkdir -p /etc/kylin-secops-api
mkdir -p /var/{lib,log,run}/kylin-secops-api

# 设置权限
chown -R kylin-secops:kylin-secops /opt/kylin-secops-api
chown -R kylin-secops:kylin-secops /var/{lib,log,run}/kylin-secops-api
chmod 750 /etc/kylin-secops-api
```

### 4.2 配置 Python 虚拟环境

```bash
# 创建虚拟环境
python3 -m venv /opt/kylin-secops-api/venv
source /opt/kylin-secops-api/venv/bin/activate

# 安装依赖
pip install --upgrade pip setuptools wheel
pip install fastapi uvicorn[standard] sqlalchemy asyncpg aiosqlite psycopg2-binary \
    redis celery alembic python-jose[cryptography] passlib[bcrypt] bcrypt \
    pydantic pydantic-settings python-multipart aiofiles httpx websockets \
    prometheus-client
```

### 4.3 复制后端代码

```bash
# 复制后端代码
cp -a backend/app /opt/kylin-secops-api/
cp -a backend/alembic /opt/kylin-secops-api/ 2>/dev/null || true
cp -a backend/alembic.ini /opt/kylin-secops-api/ 2>/dev/null || true
cp backend/.env.example /etc/kylin-secops-api/.env
```

### 4.4 生成 JWT 密钥

```bash
# 生成 RSA 密钥对（生产环境使用 RS256，开发环境可用 HS256）
openssl genrsa -out /etc/kylin-secops-api/jwt-secret.key 2048
openssl rsa -in /etc/kylin-secops-api/jwt-secret.key -pubout -out /etc/kylin-secops-api/jwt-public.pem
chmod 640 /etc/kylin-secops-api/jwt-secret.key
chmod 644 /etc/kylin-secops-api/jwt-public.pem
```

### 4.5 配置环境变量

编辑 `/etc/kylin-secops-api/.env`：

```ini
# Database
DATABASE_URL=postgresql+asyncpg://secops:YourPassword@localhost:5432/kylin_secops

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# JWT
JWT_ALGORITHM=RS256
JWT_SECRET_KEY=/etc/kylin-secops-api/jwt-secret.key
JWT_PUBLIC_KEY=/etc/kylin-secops-api/jwt-public.pem
BCRYPT_ROUNDS=12

# Server
DEBUG=False
LOG_LEVEL=INFO
CORS_ORIGINS=https://secops.yourcompany.com
UVICORN_WORKERS=4
```

### 4.6 配置 systemd 服务

```bash
# 部署服务文件
cp deploy/kylin/systemd/kylin-secops-api.service /usr/lib/systemd/system/
systemctl daemon-reload
systemctl enable --now kylin-secops-api.service

# 检查状态
systemctl status kylin-secops-api.service
journalctl -fu kylin-secops-api.service
```

---

## 5. 数据库配置

### 5.1 手动安装 PostgreSQL

```bash
# 麒麟系统安装 PostgreSQL 15
dnf install -y postgresql15-server postgresql15-contrib postgresql15-devel
/usr/pgsql-15/bin/postgresql-15-setup initdb
systemctl enable --now postgresql-15

# 安装 pgvector 扩展（用于 AI 向量检索）
dnf install -y pgvector_15
```

### 5.2 创建数据库和用户

```bash
# 创建数据库用户
su - postgres -c "psql -c \"CREATE USER secops WITH PASSWORD 'YourPassword';\"" 
su - postgres -c "psql -c \"CREATE DATABASE kylin_secops OWNER secops ENCODING 'UTF8' LC_COLLATE 'zh_CN.UTF-8' LC_CTYPE 'zh_CN.UTF-8' TEMPLATE template0;\"" 
su - postgres -c "psql -c \"GRANT ALL PRIVILEGES ON DATABASE kylin_secops TO secops;\""

# 启用 pgvector
su - postgres -c "psql -d kylin_secops -c \"CREATE EXTENSION IF NOT EXISTS vector;\""
```

### 5.3 配置连接认证

编辑 pg_hba.conf（位置：`/var/lib/pgsql/15/data/pg_hba.conf`）：

```
# 添加以下行
host    kylin_secops    secops    127.0.0.1/32    scram-sha-256
```

然后重载配置：

```bash
systemctl reload postgresql-15
```

### 5.4 初始化数据库表

```bash
# 使用 Alembic 迁移
source /opt/kylin-secops-api/venv/bin/activate
cd /opt/kylin-secops-api
DATABASE_URL="postgresql+asyncpg://secops:YourPassword@localhost:5432/kylin_secops" \
    alembic upgrade head

# 或者直接创建表
python3 << 'EOF'
import asyncio, os
os.environ['DATABASE_URL'] = 'postgresql+asyncpg://secops:YourPassword@localhost:5432/kylin_secops'
from app.models import Base
from app.core.database import engine
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await engine.dispose()
    print("Tables created successfully")
asyncio.run(init())
EOF
```

### 5.5 导入种子数据

```bash
# 修改 seed_orm.py 中的数据库连接，然后运行
# 或在后端启动后通过 API 创建管理员
curl -X POST "http://localhost:8000/api/v1/auth/register" \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"admin123","display_name":"Administrator"}'
```

---

## 6. 前端部署

### 6.1 构建前端

```bash
# 安装依赖
cd frontend
npm ci

# 构建生产版本
npm run build

# 将构建产物复制到后端目录
cp -a dist/ /opt/kylin-secops-api/frontend/
```

### 6.2 配置前端 API 地址

编辑 `frontend/src/services/api.ts` 或构建时设置环境变量：

```typescript
// 修改 API 基础地址为后端地址
const API_BASE_URL = 'https://secops.yourcompany.com/api/v1'
```

---

## 7. Agent 客户端安装

### 7.1 在被管麒麟系统上安装

```bash
# 方法一：从部署平台在线安装
curl -fsSL https://secops.yourcompany.com/install.sh | sudo bash

# 方法二：手动安装
sudo bash agent/install.sh

# 方法三：RPM 包安装（仅限 KylinOS V10）
sudo rpm -ivh kylin-secops-agent-3.2.0-1.kylinv10.x86_64.rpm
```

### 7.2 配置 Agent

编辑 `/etc/kylin-secops-agent/config.yaml`：

```yaml
platform:
  host: "secops.yourcompany.com"
  port: 443
  use_ssl: true
  ws_path: "/api/v1/ws/agent"
  token: "your-agent-registration-token"

heartbeat:
  interval_min: 5
  interval_max: 12
  cpu_threshold: 90.0
  disk_threshold: 5.0

websocket:
  ping_interval: 15
  reconnect_min_delay: 1
  reconnect_max_delay: 60
  offline_timeout: 30

collector:
  enabled: true
  process_monitor: true
  network_monitor: true
  file_monitor: true
  log_monitor: true
  file_watch_paths:
    - /etc/passwd
    - /etc/shadow
    - /etc/ssh/sshd_config
    - /etc/cron.allow
    - /etc/sudoers
    - /etc/kysec/kysec.conf    # 麒麟安全内核配置
  log_files:
    - /var/log/secure
    - /var/log/messages
    - /var/log/audit/audit.log
    - /var/log/kylin-security.log  # 麒麟安全审计日志

logging:
  level: "INFO"
  max_bytes: 10485760
  backup_count: 30
```

### 7.3 启动 Agent

```bash
systemctl enable --now kylin-secops-agent
systemctl status kylin-secops-agent
journalctl -fu kylin-secops-agent
```

---

## 8. Nginx 配置

### 8.1 安装配置

```bash
# 安装 Nginx
dnf install -y nginx

# 部署配置
cp deploy/kylin/nginx/kylin-secops.conf /etc/nginx/conf.d/
nginx -t && systemctl reload nginx
```

### 8.2 SSL 证书配置

麒麟系统支持国密 SSL 证书（SM2）和标准 RSA 证书：

```bash
# RSA 证书（推荐）
# 将证书文件放置在:
/etc/nginx/ssl/secops.company.com.pem
/etc/nginx/ssl/secops.company.com.key

# 或使用 Let's Encrypt
dnf install -y certbot python3-certbot-nginx
certbot --nginx -d secops.yourcompany.com
```

### 8.3 麒麟系统国密支持（可选）

```bash
# 安装国密 SSL 支持
dnf install -y gmssl-nginx

# 配置 SM2 证书
# 将 SM2 证书放置到 /etc/nginx/ssl/ 并修改配置
```

---

## 9. 系统运维

### 9.1 服务管理

```bash
# 后端 API 服务
systemctl status kylin-secops-api        # 查看状态
systemctl restart kylin-secops-api       # 重启
journalctl -fu kylin-secops-api -n 100  # 查看实时日志

# Agent 客户端
systemctl status kylin-secops-agent       # 查看状态
systemctl restart kylin-secops-agent      # 重启
journalctl -fu kylin-secops-agent -n 100 # 查看实时日志

# 基础设施
systemctl status postgresql-15            # PostgreSQL
systemctl status redis                    # Redis
systemctl status nginx                    # Nginx
```

### 9.2 日志管理

```bash
# 后端日志
tail -f /var/log/kylin-secops-api/uvicorn.log

# Agent 日志
tail -f /var/log/kylin-secops-agent/agent.log

# 麒麟系统安全日志
tail -f /var/log/kylin-security.log
tail -f /var/log/audit/audit.log
```

### 9.3 数据库备份

```bash
#!/bin/bash
# 每日备份脚本 — 建议添加到 crontab
BACKUP_DIR="/var/backups/kylin-secops"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
mkdir -p "$BACKUP_DIR"

# 备份 PostgreSQL
pg_dump -h 127.0.0.1 -U secops -d kylin_secops \
    -F c -f "${BACKUP_DIR}/kylin_secops_${TIMESTAMP}.dump"

# 保留最近 30 天备份
find "$BACKUP_DIR" -name "kylin_secops_*.dump" -mtime +30 -delete

# 恢复命令:
# pg_restore -h 127.0.0.1 -U secops -d kylin_secops -c backup.dump
```

### 9.4 监控告警

```bash
# 检查关键指标
ss -tlnp | grep -E "8000|5432|6379"  # 端口监听
df -h /var/lib/postgresql/             # 磁盘空间
free -h                                 # 内存使用
uptime                                  # 系统负载

# 集成 Prometheus
# 后端已集成 /metrics 端点
curl http://127.0.0.1:8000/metrics
```

### 9.5 日常巡检清单

| 周期 | 检查项 | 命令 |
|------|--------|------|
| 每日 | API 服务运行 | `systemctl is-active kylin-secops-api` |
| 每日 | Agent 在线率 | 平台 Dashboard |
| 每日 | 磁盘空间 | `df -h /var/lib/postgresql/ /var/log/` |
| 每周 | 数据库备份 | 检查备份目录 |
| 每周 | 日志轮转 | `ls -lh /var/log/kylin-*` |
| 每月 | 安全更新 | `dnf check-update --security` |
| 每月 | 安全基线 | 平台安全基线报告 |

---

## 10. 安全加固

### 10.1 麒麟系统安全基线

```bash
# 1. 启用 kysec（麒麟安全内核）
kysec-config --set enforcing
systemctl restart kysec-daemon

# 2. 配置防火墙
firewall-cmd --permanent --add-service=https
firewall-cmd --permanent --add-service=http
firewall-cmd --reload

# 3. 内核参数加固
cat >> /etc/sysctl.d/99-kylin-secops.conf << 'EOF'
# 麒麟安全运维 Agent 推荐内核参数
kernel.kptr_restrict = 2
kernel.dmesg_restrict = 1
kernel.printk = 3 3 3 3
kernel.unprivileged_bpf_disabled = 1
net.core.bpf_jit_enable = 0
net.ipv4.tcp_syncookies = 1
net.ipv4.conf.all.rp_filter = 1
net.ipv4.conf.default.rp_filter = 1
net.ipv4.conf.all.accept_source_route = 0
net.ipv4.conf.default.accept_source_route = 0
EOF
sysctl -p /etc/sysctl.d/99-kylin-secops.conf

# 4. 审计配置
auditctl -e 1
# 添加关键审计规则
auditctl -w /etc/passwd -p wa -k passwd_changes
auditctl -w /etc/shadow -p wa -k shadow_changes
auditctl -w /etc/kysec/kysec.conf -p wa -k kysec_config
auditctl -w /opt/kylin-secops-api -p wa -k secops_api
```

### 10.2 平台安全加固

```bash
# 1. 数据库最小权限
# 确保 secops 用户仅能访问 kylin_secops 数据库
su - postgres -c "psql -c \"REVOKE ALL ON DATABASE postgres FROM secops;\""

# 2. 后端服务沙箱
# systemd 已配置 ProtectSystem=full, NoNewPrivileges=yes

# 3. JWT 密钥轮换
# 建议每 90 天轮换一次
openssl genrsa -out /etc/kylin-secops-api/jwt-secret.key 2048
openssl rsa -in /etc/kylin-secops-api/jwt-secret.key -pubout -out /etc/kylin-secops-api/jwt-public.pem
systemctl restart kylin-secops-api
```

### 10.3 Agent 安全

```bash
# 1. 配置文件权限
chmod 640 /etc/kylin-secops-agent/config.yaml
chown root:root /etc/kylin-secops-agent/config.yaml

# 2. 禁用危险的远程命令
# 在 /etc/kylin-secops-agent/config.yaml 中添加:
# remote:
#   enabled: true
#   whitelist:
#     - "/usr/bin/systemctl"
#     - "/usr/bin/journalctl"
#   blacklist:
#     - "rm"
#     - "dd"
#     - "mkfs"
#   timeout: 30

# 3. OTA 升级签名验证（默认启用）
# 升级包必须携带 SHA256 签名
```

---

## 11. 故障排查

### 11.1 后端无法启动

```bash
# 检查日志
journalctl -fu kylin-secops-api -n 50

# 常见问题:

# 1. PostgreSQL 连接失败
# 检查连接串
psql -h 127.0.0.1 -U secops -d kylin_secops -c "SELECT 1"

# 2. 端口冲突
ss -tlnp | grep 8000
# 如果被占用，修改端口或杀掉冲突进程

# 3. Python 依赖缺失
source /opt/kylin-secops-api/venv/bin/activate
pip list | grep -i "fastapi\|uvicorn\|sqlalchemy\|asyncpg"

# 4. 数据库未初始化
# 检查表是否存在
psql -h 127.0.0.1 -U secops -d kylin_secops -c "\dt"
```

### 11.2 Agent 无法连接到平台

```bash
# 1. 检查配置文件
cat /etc/kylin-secops-agent/config.yaml | grep -A3 platform

# 2. 测试网络连通性
curl -k -I "https://secops.yourcompany.com/api/v1/"

# 3. 检查 Agent 日志
journalctl -fu kylin-secops-agent -n 50

# 4. 检查 WebSocket 连接
# 如果平台有 nginx，确保 ws 配置正确
curl -i -N -H "Connection: Upgrade" \
    -H "Upgrade: websocket" \
    -H "Host: secops.yourcompany.com" \
    "https://secops.yourcompany.com/api/v1/ws/agent"
```

### 11.3 麒麟系统特有故障

```bash
# 1. kysec 导致文件访问拒绝
getkysec status
# 临时放行（测试用）： kysec-config --set permissive
# 添加策略： kysec-policy --add /opt/kylin-secops-api --type bin_t

# 2. SELinux 上下文错误
restorecon -Rv /opt/kylin-secops-api/
ausearch -m avc -ts recent

# 3. 审计日志磁盘满
du -sh /var/log/audit/
# 增大 auditd 的 max_log_file 或配置日志轮转
```

### 11.4 性能问题

```bash
# 1. 数据库查询慢
# 查看慢查询
psql -h 127.0.0.1 -U secops -d kylin_secops -c "
SELECT query, calls, total_time
FROM pg_stat_statements
ORDER BY total_time DESC
LIMIT 10;"

# 2. 连接数不足
# 检查 PostgreSQL 连接数
psql -h 127.0.0.1 -U secops -d kylin_secops -c "
SELECT count(*) FROM pg_stat_activity;"

# 3. Redis 内存使用
redis-cli info memory | grep used_memory_human
```

---

## 12. 附录

### 12.1 端口清单

| 端口 | 协议 | 服务 | 说明 |
|------|------|------|------|
| 80 | TCP | Nginx | HTTP 重定向 |
| 443 | TCP | Nginx | HTTPS 前端+API |
| 8000 | TCP | Uvicorn | 后端 API (仅本地) |
| 5432 | TCP | PostgreSQL | 数据库 (仅本地) |
| 6379 | TCP | Redis | 缓存/队列 (仅本地) |

### 12.2 目录结构

```
/opt/kylin-secops-api/
├── app/                    # 后端 Python 代码
│   ├── api/               # API 路由
│   ├── core/              # 核心配置
│   ├── models/            # 数据库模型
│   ├── services/          # 业务逻辑
│   └── repositories/      # 数据访问层
├── alembic/               # 数据库迁移
├── frontend/              # 前端静态资源
│   └── dist/              # 构建产物
├── venv/                  # Python 虚拟环境
└── alembic.ini            # 迁移配置

/etc/kylin-secops-api/
├── .env                   # 环境变量
├── jwt-secret.key         # JWT 私钥
└── jwt-public.pem         # JWT 公钥

/var/log/kylin-secops-api/ # 后端日志
/var/lib/kylin-secops-api/ # 后端数据
/var/run/kylin-secops-api/ # PID 文件
```

### 12.3 常用命令速查

```bash
# 查看完整日志
journalctl -u kylin-secops-api -n 200 --no-pager

# 实时跟踪日志
journalctl -fu kylin-secops-api

# 查看指定时间范围日志
journalctl -u kylin-secops-api --since "2026-06-24 10:00:00" --until "2026-06-24 12:00:00"

# 后端 API 健康检查
curl -s http://127.0.0.1:8000/api/v1/dashboard/overview

# API 文档
# http://127.0.0.1:8000/docs

# Prometheus 指标
curl -s http://127.0.0.1:8000/metrics
```

### 12.4 联系与支持

- **文档**: https://secops.company.com/docs
- **技术支持**: dev@secops.company.com
- **问题反馈**: https://github.com/secops/kylin-secops-agent/issues

---

> **文档版本**: 3.2.0 | **最后更新**: 2026-06-24
> **适用平台**: 麒麟V10 (KylinOS V10) 高级服务器版
