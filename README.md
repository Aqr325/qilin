# 麒麟OS安全运维智能Agent

> Kylin OS Security Intelligent Operations Agent

面向麒麟操作系统的智能安全运维管理平台，集成 Agent 监控、实时告警、安全策略、AI 智能分析和桌面程序于一体。

---

## 项目结构

```
qilin/
├── frontend/                         # Vue 3 + TypeScript 前端
│   ├── src/
│   │   ├── views/                   # 页面组件
│   │   ├── components/              # 公共组件
│   │   ├── layouts/                 # 布局组件
│   │   ├── router/                  # 路由配置 (Hash 模式)
│   │   ├── stores/                  # Pinia 状态管理
│   │   ├── services/api/            # API 服务层
│   │   ├── styles/                  # 全局样式
│   │   ├── types/                   # 类型定义
│   │   └── utils/                   # 工具函数
│   └── vite.config.ts               # Vite 构建配置
│
├── kylin-secops-agent/              # 后端与 Agent
│   ├── backend/                     # FastAPI 后端服务
│   │   ├── app/
│   │   │   ├── api/v1/              # RESTful API
│   │   │   ├── core/                # 核心配置/安全/权限
│   │   │   ├── middleware/          # 中间件
│   │   │   ├── models/              # SQLAlchemy ORM 模型
│   │   │   ├── repositories/        # 数据访问层
│   │   │   ├── schemas/             # Pydantic Schema
│   │   │   ├── services/            # 业务逻辑服务
│   │   │   ├── utils/               # 工具函数
│   │   │   └── ws/                  # WebSocket 处理器
│   │   ├── alembic/                 # 数据库迁移
│   │   ├── docker-compose.yml       # 开发环境 (PostgreSQL + Redis)
│   │   ├── Dockerfile               # 后端容器镜像
│   │   └── requirements.txt         # Python 依赖
│   │
│   ├── agent/                       # 麒麟OS 监控代理
│   │   ├── src/
│   │   │   ├── main.py              # Agent 入口
│   │   │   ├── collector.py         # 系统信息采集
│   │   │   ├── kylin_monitor.py     # 麒麟OS 专项监控
│   │   │   ├── heartbeat.py         # 心跳机制
│   │   │   ├── remote.py            # 远程命令执行
│   │   │   ├── upgrade.py           # 远程升级
│   │   │   ├── ws_client.py         # WebSocket 客户端
│   │   │   └── config.py            # 配置文件
│   │   ├── systemd/                 # Systemd 服务单元
│   │   └── install.sh               # 一键安装脚本
│   │
│   └── deploy/kylin/                # 麒麟OS 部署脚本
│       ├── scripts/                 # 部署脚本
│       ├── nginx/                   # Nginx 反向代理
│       └── systemd/                 # Systemd 服务配置
│
├── desktop/                         # Electron 桌面程序
│   ├── main.js                      # Electron 主进程 (自动启动后端)
│   ├── preload.js                   # 预加载脚本
│   └── resources/
│       ├── config.json              # 应用配置
│       └── kylin_secops.db          # SQLite 数据库
│
├── architecture-design.md           # 系统架构设计文档
├── ai-engine-design.md              # AI 引擎设计文档
└── backend-architecture.md          # 后端架构设计文档
```

## 功能特性

### 前端 (Vue 3 + TypeScript + Vite)

| 模块 | 说明 |
|------|------|
| Dashboard | 运维总览仪表盘 |
| Agent 管理 | Agent 注册、状态监控、远程操作 |
| 告警管理 | 实时告警列表、处理、分配 |
| 策略管理 | 安全策略配置与部署 |
| AI 智能分析 | AI 驱动的安全事件分析 |
| 系统配置 | 全局参数配置 |
| 个人中心 | 用户信息、密码修改 |
| RBAC 权限 | 基于角色的访问控制 |
| Hash 路由 | 兼容 Electron `file://` 协议 |

### 后端 (Python + FastAPI + SQLAlchemy)

| 模块 | API 路径 |
|------|----------|
| 认证授权 | `POST /api/v1/auth/login` |
| Agent 管理 | `GET/POST /api/v1/agents` |
| 告警管理 | `GET/POST/PUT/DELETE /api/v1/alerts` |
| 策略管理 | `GET/POST/PUT/DELETE /api/v1/policies` |
| 系统信息 | `GET /api/v1/system` |
| 仪表盘 | `GET /api/v1/dashboard` |
| AI 分析 | `POST /api/v1/ai/analyze` |
| WebSocket | `WS /api/v1/ws` |
| 数据库迁移 | Alembic |

### Agent (麒麟OS 监控代理)

| 功能 | 说明 |
|------|------|
| 系统采集 | CPU、内存、磁盘、网络、进程信息 |
| 麒麟OS 专项 | Kylin 系统专属安全指标监控 |
| 心跳机制 | 定时上报存活状态 |
| 远程命令 | 通过 API 下发并执行命令 |
| 远程升级 | 支持 Agent 自身热更新 |
| WebSocket 通信 | 与后端实时双向通信 |

### 桌面程序 (Electron + PyInstaller)

| 特性 | 说明 |
|------|------|
| 一键启动 | 自动启动后端服务 (端口 8001) |
| SQLite 数据库 | 本地数据持久化 |
| 内置前端 | 打包后的 Vue 3 SPA |
| 资源隔离 | 所有依赖打包在 `resources/` 目录 |

## 快速开始

### 方式一：Docker Compose（推荐用于开发）

```bash
# 进入后端目录
cd kylin-secops-agent/backend

# 启动 PostgreSQL + Redis
docker-compose up -d

# 安装 Python 依赖
pip install -r requirements.txt

# 运行后端
python backend_entry.py
```

后端将启动在 `http://127.0.0.1:8001`，API 文档访问 `http://127.0.0.1:8001/docs`。

### 方式二：直接启动桌面程序

```bash
# Windows
# 双击 麒麟OS安全运维.exe

# 或使用启动脚本
# 双击 启动.bat
```

### 方式三：前端独立开发

```bash
# 进入前端目录
cd frontend

# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 生产构建
npm run build
```

### 方式四：Agent 部署到麒麟OS

```bash
# 在麒麟OS 目标机器上执行
cd kylin-secops-agent/agent

# 一键安装
sudo ./install.sh

# 启动服务
sudo systemctl start kylin-secops-agent

# 查看状态
sudo systemctl status kylin-secops-agent
```

## 默认账号

| 账号 | 密码 | 角色 | 权限说明 |
|------|------|------|----------|
| `admin` | `admin123` | 管理员 | 全部权限 |
| `operator` | `operator123` | 操作员 | Agent 管理、告警处理、策略部署、AI 分析 |
| `auditor` | `auditor123` | 审计员 | 只读 + 审计日志、告警导出 |
| `viewer` | `viewer123` | 查看者 | 只读权限 |

> **安全提示**：首次登录后请立即修改默认密码。

## 技术栈

### 前端

| 技术 | 版本 | 用途 |
|------|------|------|
| Vue | 3.x | 渐进式框架 |
| TypeScript | 5.x | 类型安全 |
| Vite | 5.x | 构建工具 |
| Vue Router | 4.x | 路由管理 (Hash 模式) |
| Pinia | 2.x | 状态管理 |
| Element Plus | 2.x | UI 组件库 |

### 后端

| 技术 | 版本 | 用途 |
|------|------|------|
| Python | 3.11+ | 运行时 |
| FastAPI | 0.110+ | Web 框架 |
| Uvicorn | 0.27+ | ASGI 服务器 |
| SQLAlchemy | 2.0+ | ORM |
| Alembic | 1.13+ | 数据库迁移 |
| Pydantic | 2.5+ | 数据校验 |
| python-jose | 3.3+ | JWT 认证 |
| passlib + bcrypt | 1.7+ / 4.0+ | 密码哈希 |
| Redis | 5.0+ | 缓存/消息队列 |
| Celery | 5.3+ | 异步任务 |
| websockets | 12.0+ | 实时通信 |

### 基础设施

| 技术 | 用途 |
|------|------|
| PostgreSQL | 生产数据库 |
| Redis | 缓存/会话/消息 |
| Nginx | 反向代理 |
| Docker Compose | 开发环境编排 |
| Electron | 桌面程序容器 |
| PyInstaller | Python 打包 |

## API 文档

后端启动后，访问以下地址查看交互式 API 文档：

- **Swagger UI**: http://127.0.0.1:8001/docs
- **ReDoc**: http://127.0.0.1:8001/redoc
- **OpenAPI JSON**: http://127.0.0.1:8001/openapi.json

## 配置说明

### 后端配置 (`config.json`)

```json
{
  "backend": {
    "host": "127.0.0.1",
    "port": 8001,
    "database": {
      "dialect": "sqlite",
      "url": "kylin_secops.db"
    }
  }
}
```

### 前端环境变量

```env
# .env.development
VITE_API_BASE_URL=http://127.0.0.1:8001/api/v1
```

## 目录说明

### 后端核心目录

```
app/
├── core/
│   ├── config.py      # 配置加载
│   ├── database.py    # 数据库连接
│   ├── permissions.py # 权限模型与种子数据
│   └── security.py    # 密码哈希/JWT
├── models/
│   ├── agent.py       # Agent 模型
│   ├── alert.py       # 告警模型
│   ├── audit.py       # 审计日志/登录日志
│   ├── policy.py      # 安全策略模型
│   ├── settings.py    # 系统配置模型
│   └── user.py        # 用户/角色/权限模型
├── services/
│   └── auth_service.py # 认证业务逻辑
└── ws/
    └── handlers.py    # WebSocket 消息处理
```

### Agent 核心目录

```
src/
├── main.py            # 主入口，协调各模块
├── collector.py       # 系统指标采集器
├── kylin_monitor.py   # 麒麟OS 专项监控
├── heartbeat.py       # 心跳定时上报
├── remote.py          # 远程命令处理器
├── upgrade.py         # Agent 自升级模块
├── ws_client.py       # WebSocket 客户端连接
└── config.py          # Agent 配置解析
```

## 开发指南

### 数据库迁移

```bash
cd kylin-secops-agent/backend

# 生成迁移脚本
alembic revision --autogenerate -m "description"

# 执行迁移
alembic upgrade head
```

### 添加新 API

1. 在 `app/schemas/` 定义 Pydantic Schema
2. 在 `app/repositories/` 实现数据访问逻辑
3. 在 `app/services/` 编写业务逻辑
4. 在 `app/api/v1/` 创建路由端点
5. 在 `app/api/v1/__init__.py` 注册路由

### 前端开发规范

- **路由**: 使用 `createWebHashHistory()`（兼容 Electron）
- **API**: 通过 `services/api/` 下的模块调用，统一封装 axios
- **状态**: 使用 Pinia Store 管理全局状态
- **样式**: 使用 SCSS，全局变量在 `styles/` 目录

## 部署

### 麒麟OS 生产部署

```bash
# 1. 部署后端 + 数据库
cd kylin-secops-agent/deploy/kylin
sudo ./scripts/setup_postgresql.sh
sudo ./scripts/deploy_kylin.sh

# 2. 启动服务
sudo systemctl enable kylin-secops-api
sudo systemctl start kylin-secops-api

# 3. 配置 Nginx 反向代理
sudo cp nginx/kylin-secops.conf /etc/nginx/sites-available/
sudo ln -s /etc/nginx/sites-available/kylin-secops.conf /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

详细部署手册见 `kylin-secops-agent/docs/`。

## 设计文档

- [系统架构设计](./architecture-design.md)
- [AI 引擎设计](./ai-engine-design.md)
- [后端架构设计](./backend-architecture.md)

## 许可证

MIT License

## 仓库地址

https://github.com/Aqr325/qilin
