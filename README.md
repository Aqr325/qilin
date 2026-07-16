# 麒麟OS安全运维智能Agent

> Kylin OS Security Intelligent Operations Agent

面向麒麟操作系统的智能安全运维管理平台，集成 Agent 监控、实时告警、安全策略、AI 智能分析和桌面程序于一体。

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

## 许可证

MIT License

## 仓库地址

https://github.com/Aqr325/qilin
