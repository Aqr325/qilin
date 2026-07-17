# 麒麟OS安全运维智能Agent

> Kylin OS Security Intelligent Operations Agent

[![麒麟OS双平台构建](https://github.com/Aqr325/qilin/actions/workflows/build.yml/badge.svg)](https://github.com/Aqr325/qilin/actions/workflows/build.yml)

面向麒麟操作系统的智能安全运维管理平台，集成 Agent 监控、实时告警、安全策略、AI 智能分析和桌面程序于一体。

**双平台支持**：Windows ✕ 🐧 麒麟 V10 (AppImage)

## 快速开始

### Windows 一键桌面版（推荐）

1. 下载 [最新 Release](https://github.com/Aqr325/qilin/releases/latest)
2. 解压，双击 `麒麟OS安全运维.exe` 启动
3. 浏览器打开 `http://127.0.0.1:8001`，使用默认账号登录

默认账号：

| 账号 | 密码 | 角色 |
|------|------|------|
| `admin` | `KylinSecOps@2026` | 管理员（全部权限） |
| `operator` | `KylinSecOps@2026` | 操作员（Agent 管理、告警、策略、AI） |
| `auditor` | `KylinSecOps@2026` | 审计员（只读 + 审计、告警导出） |
| `viewer` | `KylinSecOps@2026` | 查看者（只读） |

> **安全提示**：首次登录后请立即修改默认密码。

### Agent 部署（监控远程 Windows 机器）

在目标 Windows 机器上部署 `kylin-agent-win.exe`（在 Agent 交付包中），配置文件 `config.json` 指向后端地址后，Agent 自动注册并每 30 秒上报心跳，数据实时显示在 Agent 管理页面。

## 功能特性

### Agent 管理

| 功能 | 说明 |
|------|------|
| Agent 注册 | 自动注册 + 凭据管理，bootstrap token 鉴权 |
| 在线状态 | 实时心跳检测，离线检测与报警 |
| 健康评分 | 综合 CPU/内存/磁盘/心跳新鲜度/状态加权评分（0-100） |
| 批量重启 | 多 Agent 批量重启操作 |
| 远程指标 | CPU、内存、磁盘、网络实时指标展示 |

### 告警管理

| 功能 | 说明 |
|------|------|
| 实时告警 | 告警列表、详情、处理、分配 |
| 状态流转 | 告警状态变更追踪 |
| MITRE ATT&CK | 攻击框架映射 |
| 告警导出 | CSV/JSON 格式导出 |

### 策略管理

| 功能 | 说明 |
|------|------|
| 策略配置 | 安全策略规则定义 |
| 规则校验 | 策略语法实时校验 |
| 部署追踪 | 策略下发状态追踪 |

### AI 智能分析

| 功能 | 说明 |
|------|------|
| AI 对话 | 基于安全事件的对话分析 |
| 模型配置 | 多模型配置管理 |

### 系统监控

| 功能 | 说明 |
|------|------|
| 本机状态 | 纯标准库采集 CPU/内存/磁盘/网络（无需 psutil） |
| 仪表盘 | 运维总览 |
| 审计日志 | 操作审计 |
| 系统配置 | 全局参数配置 |

### RBAC 权限

| 角色 | 权限数 | 覆盖模块 |
|------|--------|----------|
| admin | 24 | 全部 |
| operator | 14 | Agent 全、告警读写、策略全、AI 读写、仪表盘、本机状态 |
| auditor | 9 | 告警读+导出、Agent 读、策略读、审计、仪表盘、AI 读、系统读、本机状态 |
| readonly | 7 | Agent/告警/策略/仪表盘/审计/AI/本机状态（纯只读） |

## 项目结构

```
qilin/
├── frontend/                         # Vue 3 + TypeScript 前端
│   └── src/
│       ├── views/                   # 页面组件
│       ├── components/              # 公共组件
│       ├── stores/                  # Pinia 状态管理
│       ├── services/api/            # API 服务层
│       └── types/                   # 类型定义
│
├── kylin-secops-agent/              # 后端与 Agent
│   ├── backend/                     # FastAPI 后端服务 (端口 8000)
│   │   ├── app/
│   │   │   ├── api/v1/              # RESTful API
│   │   │   ├── core/                # 核心配置/权限
│   │   │   ├── models/              # SQLAlchemy ORM 模型
│   │   │   ├── repositories/        # 数据访问层
│   │   │   ├── schemas/             # Pydantic Schema
│   │   │   ├── services/            # 业务逻辑服务
│   │   │   └── ws/                  # WebSocket 处理器
│   │   ├── alembic/                 # 数据库迁移
│   │   └── backend.spec             # PyInstaller 打包配置
│   │
│   └── agent-win/                   # Windows Agent 客户端 (端口 8000)
│       └── src/                     # Agent 源码 (PyInstaller 打包)
│
├── electron-app/                    # Electron 桌面程序源码
│   └── release/                     # 打包输出
│       └── win-unpacked/            # Windows 分发目录
│
├── desktop/                         # 桌面构建资源
│   ├── main.js                      # Electron 主进程
│   ├── preload.js                   # 预加载脚本
│   └── resources/                   # 运行时资源
│
├── 麒麟OS安全运维_桌面程序/            # 主程序交付目录 (端口 8001)
│   └── resources/
│       ├── backend.exe              # PyInstaller 打包后端
│       ├── frontend/                # Vite 构建前端
│       ├── config.json              # 应用配置
│       └── kylin_secops.db          # SQLite 数据库
│
└── 麒麟OS安全智能运维Agent_桌面版交付/    # Agent 交付目录 (端口 8000)
    └── resources/                   # 同主程序结构
```

## 后端 API

后端启动在 `http://127.0.0.1:8000`（Agent 模式）或 `http://127.0.0.1:8001`（主程序模式）。

| 模块 | API 路径 | 权限要求 |
|------|----------|----------|
| 认证授权 | `POST /api/v1/auth/login` | 无需认证 |
| 本机状态 | `GET /system/local-status` | `LOCAL_STATUS_READ` |
| Agent 列表 | `GET /api/v1/agents` | `AGENT_READ` |
| Agent 注册 | `POST /api/v1/agents/register` | bootstrap token |
| Agent 心跳 | `POST /api/v1/agents/heartbeat` | bootstrap token / 凭据 |
| Agent 健康评分 | `GET /api/v1/agents/{id}/health-score` | `AGENT_READ` |
| 批量重启 | `POST /api/v1/agents/batch-restart` | `AGENT_RESTART` |
| 告警管理 | `GET/POST/PUT/DELETE /api/v1/alerts` | `ALERT_READ`/`ALERT_WRITE` |
| 策略管理 | `GET/POST/PUT/DELETE /api/v1/policies` | `POLICY_READ`/`POLICY_WRITE` |
| AI 对话 | `GET/POST /api/v1/ai/conversations` | `AI_READ`/`AI_WRITE` |
| 模型配置 | `GET/POST/PUT/DELETE /api/v1/ai/model-configs` | `AI_READ`/`AI_WRITE` |
| 仪表盘 | `GET /api/v1/dashboard` | `DASHBOARD_READ` |
| 审计日志 | `GET /api/v1/audit-logs` | `AUDIT_READ` |
| 数据库迁移 | `GET /api/v1/db/migrate` | `SYSTEM_WRITE` |
| WebSocket | `WS /api/v1/ws` | JWT 认证 |
| API 文档 | `GET /api/v1/docs` | JWT 认证（403 保护） |

## 开发指南

### 构建前端

```bash
cd frontend
npm install
npm run dev      # 开发服务器
npm run build    # 生产构建
```

构建产物自动同步到各交付目录 `resources/frontend/`。

### 构建后端

```bash
cd kylin-secops-agent/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

PyInstaller 打包（生产用）：

```bash
python -m PyInstaller backend.spec --noconfirm
```

### 构建 Windows Agent

```bash
cd kylin-secops-agent/agent-win
python -m PyInstaller agent_win.spec --noconfirm
# 输出: dist/kylin-agent-win.exe
```

### 数据库迁移

```bash
cd kylin-secops-agent/backend
alembic upgrade head
```

### 添加新 API

1. `app/schemas/` — 定义 Pydantic Schema
2. `app/repositories/` — 数据访问逻辑
3. `app/services/` — 业务逻辑
4. `app/api/v1/` — 路由端点（记得加 `require_permission` 权限门禁）
5. `app/api/v1/__init__.py` — 注册路由

### 权限门禁

所有管理端点必须加权限门禁：

```python
from app.core.permissions import Permission, require_permission
from fastapi import Depends

@router.get("/items")
async def list_items(current_user: dict = Depends(require_permission(Permission.ITEM_READ))):
    ...
```

## 架构与配置

### 数据库

- **桌面版**: SQLite（`kylin_secops.db`），零配置
- **生产环境**: PostgreSQL + Redis（docker-compose 启动）

### 安全特性

- JWT 认证（`python-jose`）
- bcrypt 密码哈希（`passlib + bcrypt`）
- HMAC 安全比较（防时序攻击）
- 首次登录强制改密
- seed_password 种子密码（通过 `config.json` 配置）
- 后端 `/docs` 端点 403 保护（需有效 JWT）
- gitleaks 密钥扫描门禁

### 可观测性

- `/metrics` — Prometheus 格式指标（纯标准库实现）
- 日志落盘 — Electron 应用日志（`resources/logs/`），按天滚动
- PowerShell 单机自检脚本（`observability/check-agent-status.ps1`）
- Grafana 看板 JSON（`observability/kylin-agent-dashboard.json`）

## 默认端口

| 模式 | 端口 | 说明 |
|------|------|------|
| 主程序 | 8001 | Electron 桌面版，含前端 + 后端 |
| Agent 交付 | 8000 | 独立后端 + 前端，用于 Agent 管理 |
| 开发环境 | 8000 | 本地开发后端 |

## 跨平台构建 (Windows + 麒麟 V10)

### 统一构建脚本

```bash
# 构建当前平台完整包（自动检测 Windows / Linux）
python build.py

# 分步构建
python build.py --backend-only      # 仅构建后端 (PyInstaller)
python build.py --frontend-only     # 仅构建前端 (Vite)
python build.py --electron-only     # 仅构建 Electron 桌面包
python build.py --sync-only         # 仅同步产物到交付目录
python build.py --platform linux    # 指定构建平台 (可选)
```

### Windows 构建

```bash
# 前置条件
#   1. Python 3.11+ (推荐 desktop-build-env 虚拟环境)
#   2. Node.js 20+
#   3. UPX (可选，自动检测 C:\ProgramData\chocolatey\bin\upx.exe)

cd qilin
python build.py
```

### 麒麟 V10 构建 (桌面版 AppImage)

**推荐使用专用构建脚本**（自动处理所有步骤）：

```bash
# 一步到位
sudo bash kylin-secops-agent/deploy/kylin/scripts/build_kylin_desktop.sh

# 或使用通用构建脚本
python3 build.py
```

**手动分步构建：**

```bash
# 1. 安装系统依赖
sudo dnf install -y python3 python3-devel python3-pip nodejs npm \
  libXScrnSaver libXcomposite libXdamage libXrandr libgbm \
  libpango libcairo libasound libxkbcommon libdbus libegl libnss3 fuse

# 2. 构建后端
cd kylin-secops-agent/backend
pip install -r requirements.txt pyinstaller
python3 -m PyInstaller backend.spec --noconfirm
cd ../..

# 3. 构建前端
cd frontend && npm install && npx vite build && cd ..

# 4. 同步到交付目录
cp kylin-secops-agent/backend/dist/backend desktop/resources/backend
cp -r frontend/dist/* desktop/resources/frontend/

# 5. 构建 Electron AppImage
cd desktop && npm install && npx electron-builder --linux --x64

# 输出: desktop/release/麒麟OS安全运维-*.AppImage  ← 双击即运行！
```

### 麒麟 V10 生产部署（非桌面，服务端模式）

```bash
# 使用一键部署脚本
cd kylin-secops-agent/deploy/kylin
sudo bash scripts/deploy_kylin.sh

# 或手动部署
# 1. 安装系统依赖
sudo dnf install -y python3 python3-devel python3-pip postgresql-server redis nginx

# 2. 安装 Python 依赖
pip install -r kylin-secops-agent/backend/requirements.txt

# 3. 通过 Python 直接运行后端（无需 PyInstaller）
cd kylin-secops-agent/backend
python backend_entry.py

# 4. 安装 systemd 服务
sudo cp deploy/kylin/systemd/kylin-secops-api.service /usr/lib/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now kylin-secops-api

# 5. 配置 Nginx 反向代理
sudo cp deploy/kylin/nginx/kylin-secops.conf /etc/nginx/conf.d/
sudo nginx -t && sudo systemctl reload nginx
```

### 麒麟桌面集成

麒麟 V10 桌面版用户可安装快捷方式到开始菜单：

```bash
# 安装桌面快捷方式
sudo bash kylin-secops-agent/deploy/kylin/desktop/install-desktop.sh

# 安装到当前用户
bash kylin-secops-agent/deploy/kylin/desktop/install-desktop.sh --user

# 移除
bash kylin-secops-agent/deploy/kylin/desktop/install-desktop.sh --remove
```

### 构建产物

| 平台 | 后端形态 | Electron 输出 | 图标 |
|------|---------|--------------|------|
| Windows | `backend.exe` (PE) | `.exe` / NSIS 安装包 | `.ico` |
| 麒麟 V10 (x86_64) | `backend` (ELF) | `.AppImage` | `.png` |
| 麒麟 V10 (aarch64) | `backend` (ELF) | `.AppImage` (arm64) | `.png` |

### GitHub Actions 自动构建 (推荐)

本仓库配置了自动构建流水线，**无需在本地搭建麒麟环境**，GitHub 服务器自动为两个平台构建包。

**触发方式**：

| 操作 | 触发构建 | 产出 |
|------|---------|------|
| `git push` 到 `main` 分支 | ✅ 自动构建 | 上传 Artifact (工作台可下载) |
| 推送 tag `v*` (如 `v2.5.0`) | ✅ 自动构建+发布 | 创建 GitHub Release，包含全部附件 |
| 手动触发 | ✅ 在 Actions 页点 "Run workflow" | 上传 Artifact |

**麒麟 V10 用户获取 AppImage 的步骤**：

```bash
# 方法 1: 从 Release 下载 (最简单的办法)
# 访问: https://github.com/Aqr325/qilin/releases/latest
# 下载: 麒麟OS安全运维-*.AppImage

# 方法 2: 从 Actions Artifact 下载
# 访问: https://github.com/Aqr325/qilin/actions
# 选择最新成功的工作流 → Artifacts → 麒麟OS安全运维_Linux

# 在麒麟系统上运行
chmod +x 麒麟OS安全运维-*.AppImage
./麒麟OS安全运维-*.AppImage   # 或直接双击
```

### 架构说明

- **后端**: 跨平台 Python 代码，无需修改。PyInstaller 在各自平台打出对应二进制
- **前端**: Vue3 静态资源，编译结果完全一致
- **Electron 壳**: 平台相关，通过 `electron-builder` 分平台打包
- **数据库**: SQLite 文件，跨平台即拷即用
- **配置**: config.json 统一管理，`main.js` 根据 `process.platform` 自动适配后端路径

## 许可证

MIT License

## 仓库地址

https://github.com/Aqr325/qilin
