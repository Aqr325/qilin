# 麒麟OS安全智能运维Agent — 后端架构设计文档

> **版本**: v1.0  
> **作者**: 侯端序 — 开发工程专家团·后端与架构  
> **日期**: 2026-06-23  

---

## 目录

1. [系统总体架构](#1-系统总体架构)
2. [后端模块架构](#2-后端模块架构)
3. [完整RESTful API端点清单](#3-完整restful-api端点清单)
4. [WebSocket事件清单](#4-websocket事件清单)
5. [数据库ER设计](#5-数据库er设计)
6. [核心接口请求/响应示例](#6-核心接口请求响应示例)
7. [Alembic迁移策略](#7-alembic迁移策略)
8. [Redis数据结构设计](#8-redis数据结构设计)

---

## 1. 系统总体架构

### 1.1 端-云拓扑图

```
┌─────────────────────────────────────────────────────────────────────┐
│                         安全管理平台 (Cloud)                          │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │                     Nginx / 负载均衡                            │  │
│  └──────────┬────────────────────────────────┬─────────────────┘  │
│             │ HTTPS/WS                        │ HTTPS/WS           │
│  ┌──────────▼──────────┐         ┌───────────▼───────────┐        │
│  │   FastAPI App       │         │   FastAPI App         │        │
│  │   (Instance 1)      │◄────────►   (Instance 2)        │        │
│  └──────────┬──────────┘  Redis  └───────────┬───────────┘        │
│             │            Pub/Sub              │                    │
│  ┌──────────▼──────────────────────────────────▼───────────┐      │
│  │                    PostgreSQL 15+                        │      │
│  └─────────────────────────────────────────────────────────┘      │
│  ┌─────────────────────────────────────────────────────────┐      │
│  │                    Redis Cluster                          │      │
│  │         (Cache / Pub/Sub / Task Queue / Session)         │      │
│  └─────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────┘
           │                        │
       HTTPS/WS                  HTTPS/WS
           │                        │
┌──────────▼──────────┐  ┌─────────▼──────────┐
│   Agent Client 01   │  │   Agent Client 02  │  ... 200 Agents
│   麒麟OS v10         │  │   麒麟OS v10        │
│   kylin-node-01     │  │   kylin-node-02    │
└─────────────────────┘  └────────────────────┘
```

### 1.2 技术栈选型依据

| 组件 | 选型 | 理由 |
|------|------|------|
| 后端框架 | **FastAPI** | 麒麟OS Python生态最佳，异步原生支持，自动OpenAPI文档 |
| 数据库 | **PostgreSQL 15+** | 丰富的索引类型（GIN/BRIN/部分索引），JSONB支持Agent上报数据，并行查询 |
| ORM | **SQLAlchemy 2.0** | 声明式映射，异步session，与FastAPI深度集成 |
| 迁移工具 | **Alembic** | 自动生成迁移脚本，版本化数据库变更 |
| 消息队列 | **Redis** | Pub/Sub广播WebSocket，List做任务队列，Stream做心跳缓冲 |
| 认证 | **JWT (python-jose)** | 无状态认证，适合分布式部署 |
| 密码哈希 | **passlib (bcrypt)** | 麒麟OS推荐加密算法 |
| API文档 | **OpenAPI + Redoc** | FastAPI自动生成，Redoc渲染更专业 |

---

## 2. 后端模块架构

### 2.1 分层架构图

```
══════════════════════════════════════════════════════════════════════
                        API 路由层 (Routers)
┌─────────┬──────────┬──────────┬──────────┬─────────┬───────────┐
│  Auth    │  Agent   │  Alert   │ Policy   │ System  │    AI     │
│ Router   │  Router  │  Router  │  Router  │ Router  │  Router   │
└────┬─────┴────┬─────┴────┬─────┴────┬─────┴────┬────┴─────┬────┘
     │          │          │          │          │          │
═════╪══════════╪══════════╪══════════╪══════════╪══════════╪══════
     │          │          │          │          │          │
     ▼          ▼          ▼          ▼          ▼          ▼
┌──────────────────────────────────────────────────────────────────┐
│                    中间件层 (Middlewares)                          │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │ JWT认证  │ │ RBAC权限 │ │ 请求日志 │ │ 速率限制(Rate   │  │
│  │ 中间件   │ │ 中间件   │ │ 中间件   │ │  Limiter)        │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                             │
═════════════════════════════╪═══════════════════════════════════════
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                      业务服务层 (Services)                         │
│                                                                  │
│  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌────────────────┐  │
│  │ AuthSvc   │ │ AgentSvc  │ │ AlertSvc  │ │ PolicySvc      │  │
│  ├───────────┤ ├───────────┤ ├───────────┤ ├────────────────┤  │
│  │ JWT签发   │ │ 心跳处理  │ │ 告警聚合  │ │ 策略CRUD       │  │
│  │ RBAC验证  │ │ 状态管理  │ │ MITRE映射  │ │ 版本管理      │  │
│  │ Token刷新 │ │ 版本管理  │ │ 状态流转  │ │ 目标Agent解析 │  │
│  └───────────┘ └───────────┘ └───────────┘ └────────────────┘  │
│                                                                  │
│  ┌───────────┐ ┌───────────┐ ┌────────────────────────────────┐  │
│  │ SystemSvc │ │ AISvc     │ │ WebSocketSvc                   │  │
│  ├───────────┤ ├───────────┤ ├────────────────────────────────┤  │
│  │ 用户管理  │ │ NL查询    │ │ 连接管理(连接池)               │  │
│  │ 角色管理  │ │ 研判建议  │ │ 频道管理                        │  │
│  │ 审计日志  │ │ 上下文管理│ │ Redis Pub/Sub桥接              │  │
│  └───────────┘ └───────────┘ └────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                             │
═════════════════════════════╪═══════════════════════════════════════
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                   数据访问层 (Repository/DAO)                      │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────┐  │
│  │ UserRepo │ │ AgentRepo│ │AlertRepo │ │PolicyRepo│ │...   │  │
│  └──────────┘ └──────────┘ └──────────┘ └──────────┘ └──────┘  │
└──────────────────────────────────────────────────────────────────┘
                             │
═════════════════════════════╪═══════════════════════════════════════
                             ▼
┌──────────────────────────────────────────────────────────────────┐
│                   基础设施层 (Infrastructure)                      │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────────────┐  │
│  │ PostgreSQL   │ │ Redis        │ │ 外部服务                 │  │
│  │ 15+          │ │ (Cache/Pub/  │ │ (通知网关/CMDB/           │  │
│  │              │ │  Sub/Queue)  │ │  SIEM对接)               │  │
│  └──────────────┘ └──────────────┘ └──────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
══════════════════════════════════════════════════════════════════════
```

### 2.2 模块间依赖关系

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Auth Router │────>│  Agent Router│────>│  Alert Router│
│              │     │              │     │              │
│ 依赖: AuthSvc│     │依赖: AgentSvc│     │依赖: AlertSvc│
│      UserRepo│     │  AlertSvc    │     │  AgentSvc    │
└──────────────┘     │  WS Channel  │     │  MITRE映射   │
                     └──────────────┘     └──────────────┘
                                                  │
┌──────────────┐     ┌──────────────┐            │
│  Policy      │     │  System      │            │
│  Router      │     │  Router      │            │
│              │     │              │            │
│依赖: PolicySv│     │依赖: SystemSv│            │
│  AgentSvc    │     │  AuthSvc     │            │
│  WS Channel  │     └──────────────┘            │
└──────────────┘                                  │
                         ┌──────────────┐         │
                         │  AI Router   │─────────┘
                         │              │
                         │依赖: AISvc   │
                         │  AlertSvc    │
                         │  AgentSvc    │
                         └──────────────┘

┌──────────────────────────────────────────────────────────────┐
│                WebSocket Manager (全局单例)                    │
│                                                              │
│   ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐ │
│   │ 连接注册表   │  │ 频道路由表   │  │  Redis Pub/Sub桥接  │ │
│   │ conn_id →    │  │ channel →   │  │  channel→redis→     │ │
│   │ WebSocket    │  │ Set<conn_id>│  │  broadcast         │ │
│   └─────────────┘  └─────────────┘  └─────────────────────┘ │
└──────────────────────────────────────────────────────────────┘
```

### 2.3 项目目录结构

```
kylin-secops-backend/
├── alembic/                     # Alembic迁移目录
│   ├── versions/                # 迁移版本文件
│   ├── env.py                   # Alembic环境配置
│   └── script.py.mako           # 迁移模板
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI应用入口
│   ├── config.py                # 配置管理（pydantic-settings）
│   ├── dependencies.py          # 依赖注入（DB session, current user）
│   │
│   ├── api/                     # API路由层
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── auth.py          # 认证相关路由
│   │   │   ├── agents.py        # Agent管理路由
│   │   │   ├── alerts.py        # 告警管理路由
│   │   │   ├── policies.py      # 策略管理路由
│   │   │   ├── system.py        # 系统管理路由
│   │   │   ├── ai.py            # AI对话路由
│   │   │   └── websocket.py     # WebSocket路由
│   │   └── deps.py              # API层依赖（分页、过滤）
│   │
│   ├── models/                  # SQLAlchemy ORM模型
│   │   ├── __init__.py
│   │   ├── base.py              # 声明基类
│   │   ├── user.py              # 用户模型
│   │   ├── agent.py             # Agent模型
│   │   ├── alert.py             # 告警模型
│   │   ├── policy.py            # 策略模型
│   │   ├── audit.py             # 审计日志模型
│   │   └── ai.py                # AI对话模型
│   │
│   ├── schemas/                 # Pydantic Schema（请求/响应）
│   │   ├── __init__.py
│   │   ├── auth.py
│   │   ├── agent.py
│   │   ├── alert.py
│   │   ├── policy.py
│   │   ├── system.py
│   │   ├── ai.py
│   │   └── common.py            # 通用分页、响应包装
│   │
│   ├── services/                # 业务服务层
│   │   ├── __init__.py
│   │   ├── auth_service.py
│   │   ├── agent_service.py
│   │   ├── alert_service.py
│   │   ├── policy_service.py
│   │   ├── system_service.py
│   │   ├── ai_service.py
│   │   └── websocket_service.py
│   │
│   ├── repositories/            # 数据访问层
│   │   ├── __init__.py
│   │   ├── base.py              # 通用CRUD基类
│   │   ├── user_repo.py
│   │   ├── agent_repo.py
│   │   ├── alert_repo.py
│   │   ├── policy_repo.py
│   │   └── audit_repo.py
│   │
│   ├── middleware/               # 中间件
│   │   ├── __init__.py
│   │   ├── jwt_middleware.py
│   │   ├── rbac_middleware.py
│   │   ├── logging_middleware.py
│   │   └── rate_limit.py
│   │
│   ├── ws/                      # WebSocket管理器
│   │   ├── __init__.py
│   │   ├── manager.py           # 连接/频道管理
│   │   ├── events.py            # 事件类型定义
│   │   └── redis_bridge.py      # Redis Pub/Sub桥接
│   │
│   └── utils/                   # 工具函数
│       ├── __init__.py
│       ├── security.py          # JWT、密码哈希
│       ├── mitre_mapping.py     # MITRE ATT&CK映射工具
│       └── pagination.py        # 分页工具
│
├── tests/                       # 测试
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_agents.py
│   ├── test_alerts.py
│   └── test_policies.py
│
├── alembic.ini                  # Alembic配置
├── requirements.txt
├── Dockerfile
└── docker-compose.yml
```

---

## 3. 完整RESTful API端点清单

### 3.1 认证授权 (Auth)

| 方法 | 路径 | 说明 | 权限 | 请求体 | 响应 |
|------|------|------|------|--------|------|
| POST | `/api/v1/auth/login` | 用户登录 | 公开 | `{username, password}` | `{access_token, refresh_token, token_type, expires_in}` |
| POST | `/api/v1/auth/refresh` | 刷新Token | 公开(Bearer) | `{refresh_token}` | `{access_token, refresh_token}` |
| POST | `/api/v1/auth/logout` | 退出登录 | 匿名~管理员 | - | `{message}` |
| GET  | `/api/v1/auth/me` | 获取当前用户信息 | 匿名~管理员 | - | `UserProfile` |
| PUT  | `/api/v1/auth/me/password` | 修改当前用户密码 | 匿名~管理员 | `{old_password, new_password}` | `{message}` |
| GET  | `/api/v1/auth/me/permissions` | 获取当前用户权限列表 | 匿名~管理员 | - | `[Permission]` |

### 3.2 Agent通信 (Agent Communication)

| 方法 | 路径 | 说明 | 权限 | 请求体/参数 | 响应 |
|------|------|------|------|-------------|------|
| POST | `/api/v1/agent/heartbeat` | Agent心跳上报 | AgentToken | `HeartbeatPayload` | `{code, message, next_action, config_version}` |
| POST | `/api/v1/agent/register` | Agent注册 | AgentToken | `RegisterPayload` | `{agent_id, credential, config}` |
| POST | `/api/v1/agent/events` | Agent批量事件上报 | AgentToken | `{events: [Event]}` | `{received, failed}` |
| GET  | `/api/v1/agent/{agent_id}/config` | Agent拉取配置 | AgentToken | - | `AgentConfig` |
| POST | `/api/v1/agent/{agent_id}/result` | Agent任务结果上报 | AgentToken | `{task_id, status, output}` | `{message}` |

### 3.3 告警管理 (Alerts)

| 方法 | 路径 | 说明 | 权限 | 参数 | 响应 |
|------|------|------|------|------|------|
| GET  | `/api/v1/alerts` | 告警列表（分页+筛选） | 运维员/审计员/管理员 | `?page,size,status,severity,type,agent_id,start_time,end_time,mitre_technique,keyword` | `Page<AlertSummary>` |
| GET  | `/api/v1/alerts/stats` | 告警统计概览 | 运维员/审计员/管理员 | `?time_range` | `AlertStats` |
| GET  | `/api/v1/alerts/{alert_id}` | 告警详情 | 运维员/审计员/管理员 | - | `AlertDetail` |
| PUT  | `/api/v1/alerts/{alert_id}/status` | 更新告警状态 | 运维员/管理员 | `{status, comment}` | `AlertDetail` |
| POST | `/api/v1/alerts/batch/status` | 批量处置告警 | 运维员/管理员 | `{alert_ids, status, comment}` | `{processed, failed}` |
| POST | `/api/v1/alerts/{alert_id}/assign` | 指派告警处理人 | 管理员 | `{assignee_id}` | `AlertDetail` |
| GET  | `/api/v1/alerts/{alert_id}/history` | 告警状态流转历史 | 运维员/管理员 | - | `[StatusChangeLog]` |
| GET  | `/api/v1/alerts/{alert_id}/related` | 关联告警查询 | 运维员/管理员 | - | `[AlertSummary]` |
| POST | `/api/v1/alerts/{alert_id}/suppress` | 添加告警抑制规则 | 管理员 | `{rule_config, expire_time}` | `SuppressRule` |
| GET  | `/api/v1/alerts/mitre-matrix` | 获取MITRE ATT&CK矩阵 | 运维员/管理员 | - | `MitreMatrix` |
| GET  | `/api/v1/alerts/timeline` | 告警时间线视图 | 运维员/审计员 | `?start_time,end_time,interval` | `TimelineData` |
| GET  | `/api/v1/alerts/export` | 导出告警数据 | 审计员/管理员 | `?format=csv/xlsx` | 文件流 |

### 3.4 Agent管理 (Agent Management)

| 方法 | 路径 | 说明 | 权限 | 参数 | 响应 |
|------|------|------|------|------|------|
| GET  | `/api/v1/agents` | Agent列表（分页+筛选） | 运维员/管理员 | `?page,size,status,version,keyword,os_version` | `Page<AgentSummary>` |
| GET  | `/api/v1/agents/stats` | Agent全局统计 | 运维员/管理员 | - | `AgentGlobalStats` |
| GET  | `/api/v1/agents/{agent_id}` | Agent详情 | 运维员/管理员 | - | `AgentDetail` |
| GET  | `/api/v1/agents/{agent_id}/metrics` | Agent实时指标 | 运维员/管理员 | `?time_range` | `AgentMetrics` |
| GET  | `/api/v1/agents/{agent_id}/heartbeats` | Agent心跳历史 | 运维员/管理员 | `?page,size,start_time,end_time` | `Page<HeartbeatRecord>` |
| POST | `/api/v1/agents/upgrade` | 远程升级Agent | 管理员 | `{agent_ids, version, package_url}` | `{task_id, scheduled_count}` |
| GET  | `/api/v1/agents/{agent_id}/upgrade-history` | Agent升级历史 | 管理员 | - | `[UpgradeRecord]` |
| POST | `/api/v1/agents/{agent_id}/restart` | 远程重启Agent | 管理员 | - | `{task_id}` |
| GET  | `/api/v1/agents/{agent_id}/tasks` | Agent任务列表 | 运维员/管理员 | `?status,type` | `[AgentTask]` |
| GET  | `/api/v1/agents/online-map` | Agent在线分布地图 | 管理员/审计员 | - | `OnlineMap` |
| GET  | `/api/v1/agents/health-check` | Agent健康检查总览 | 管理员 | - | `HealthOverview` |

### 3.5 策略管理 (Policies)

| 方法 | 路径 | 说明 | 权限 | 参数/请求体 | 响应 |
|------|------|------|------|-------------|------|
| POST | `/api/v1/policies` | 创建策略 | 管理员 | `PolicyCreate` | `PolicyDetail` |
| GET  | `/api/v1/policies` | 策略列表 | 运维员/管理员 | `?page,size,status,type,keyword` | `Page<PolicySummary>` |
| GET  | `/api/v1/policies/{policy_id}` | 策略详情 | 运维员/管理员 | - | `PolicyDetail` |
| PUT  | `/api/v1/policies/{policy_id}` | 更新策略（创建新版本） | 管理员 | `PolicyUpdate` | `PolicyDetail` |
| DELETE | `/api/v1/policies/{policy_id}` | 删除策略（软删除） | 管理员 | - | `{message}` |
| POST | `/api/v1/policies/{policy_id}/deploy` | 下发策略到目标Agent | 管理员 | `{agent_ids, force}` | `{task_id, deploy_count}` |
| POST | `/api/v1/policies/{policy_id}/toggle` | 切换策略启用/禁用 | 管理员 | `{enabled}` | `PolicyDetail` |
| PUT  | `/api/v1/policies/{policy_id}/versions` | 回滚到指定版本 | 管理员 | `{version_number}` | `PolicyDetail` |
| GET  | `/api/v1/policies/{policy_id}/versions` | 策略版本历史 | 管理员 | - | `[PolicyVersion]` |
| GET  | `/api/v1/policies/{policy_id}/deploy-status` | 策略下发状态追踪 | 管理员 | - | `DeployStatusMap` |
| POST | `/api/v1/policies/validate` | 策略规则语法校验 | 管理员 | `{rules}` | `{valid, errors}` |
| POST | `/api/v1/policies/preview-targets` | 预览策略目标Agent范围 | 管理员 | `{target_expression}` | `{agent_count, sample_list}` |

### 3.6 系统管理 (System)

| 方法 | 路径 | 说明 | 权限 | 请求体/参数 | 响应 |
|------|------|------|------|-------------|------|
| POST | `/api/v1/system/users` | 创建用户 | 管理员 | `UserCreate` | `UserDetail` |
| GET  | `/api/v1/system/users` | 用户列表 | 管理员 | `?page,size,role,status,keyword` | `Page<UserSummary>` |
| GET  | `/api/v1/system/users/{user_id}` | 用户详情 | 管理员 | - | `UserDetail` |
| PUT  | `/api/v1/system/users/{user_id}` | 更新用户 | 管理员 | `UserUpdate` | `UserDetail` |
| DELETE | `/api/v1/system/users/{user_id}` | 删除用户 | 管理员 | - | `{message}` |
| PUT  | `/api/v1/system/users/{user_id}/status` | 启用/禁用用户 | 管理员 | `{is_active}` | `UserDetail` |
| GET  | `/api/v1/system/roles` | 角色列表 | 管理员 | - | `[RoleDetail]` |
| POST | `/api/v1/system/roles` | 创建角色 | 管理员 | `RoleCreate` | `RoleDetail` |
| PUT  | `/api/v1/system/roles/{role_id}` | 更新角色权限 | 管理员 | `RoleUpdate` | `RoleDetail` |
| DELETE | `/api/v1/system/roles/{role_id}` | 删除角色 | 管理员 | - | `{message}` |
| GET  | `/api/v1/system/permissions` | 权限清单 | 管理员 | - | `[Permission]` |
| GET  | `/api/v1/system/login-logs` | 登录日志 | 审计员/管理员 | `?page,size,user_id,start_time,end_time,ip,status` | `Page<LoginLog>` |
| GET  | `/api/v1/system/audit-logs` | 操作审计日志 | 审计员/管理员 | `?page,size,user_id,action,resource_type,start_time,end_time` | `Page<AuditLog>` |
| GET  | `/api/v1/system/audit-logs/stats` | 审计统计 | 审计员/管理员 | `?time_range` | `AuditStats` |
| GET  | `/api/v1/system/settings` | 系统设置 | 管理员 | - | `SystemSettings` |
| PUT  | `/api/v1/system/settings` | 更新系统设置 | 管理员 | `SystemSettingsUpdate` | `SystemSettings` |

### 3.7 AI对话 (AI Assistant)

| 方法 | 路径 | 说明 | 权限 | 请求体/参数 | 响应 |
|------|------|------|------|-------------|------|
| POST | `/api/v1/ai/query` | 自然语言运维查询 | 运维员/管理员 | `{question, context_alert_id?}` | `AIQueryResponse` |
| POST | `/api/v1/ai/suggest` | AI告警研判建议 | 运维员/管理员 | `{alert_id}` | `AISuggestion` |
| POST | `/api/v1/ai/playbook` | AI生成处置剧本 | 管理员 | `{alert_ids, scenario}` | `{steps: [PlaybookStep]}` |
| GET  | `/api/v1/ai/conversations` | AI对话历史 | 运维员/管理员 | `?page,size` | `Page<ConversationSummary>` |
| GET  | `/api/v1/ai/conversations/{conv_id}` | 对话详情 | 运维员/管理员 | - | `ConversationDetail` |
| DELETE | `/api/v1/ai/conversations/{conv_id}` | 删除对话 | 管理员 | - | `{message}` |
| POST | `/api/v1/ai/feedback` | AI回答反馈 | 运维员/管理员 | `{conversation_id, message_id, rating, comment}` | `{message}` |

### 3.8 仪表盘 (Dashboard)

| 方法 | 路径 | 说明 | 权限 | 参数 | 响应 |
|------|------|------|------|------|------|
| GET  | `/api/v1/dashboard/overview` | 全局安全概览 | 管理员/运维员 | - | `DashboardOverview` |
| GET  | `/api/v1/dashboard/alert-trend` | 告警趋势图数据 | 管理员/运维员 | `?days=7` | `TrendData` |
| GET  | `/api/v1/dashboard/agent-heatmap` | Agent健康热力图 | 管理员/运维员 | `?hours=24` | `HeatmapData` |
| GET  | `/api/v1/dashboard/top-alerts` | Top N告警类型 | 管理员/运维员 | `?limit=10,time_range` | `[TopAlertType]` |

### 3.9 通用响应格式

```json
// 成功响应
{
  "code": 0,
  "message": "success",
  "data": { ... },
  "request_id": "req-abc123"
}

// 分页响应
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [...],
    "total": 156,
    "page": 1,
    "size": 20,
    "total_pages": 8
  },
  "request_id": "req-abc123"
}

// 错误响应
{
  "code": 40101,
  "message": "认证令牌已过期",
  "detail": "请刷新token后重试",
  "request_id": "req-abc123"
}
```

---

## 4. WebSocket事件清单

### 4.1 WebSocket连接

```
wss://{host}/api/v1/ws?token={jwt_token}
```

### 4.2 客户端→服务端事件

| 事件类型 | 说明 | 载荷 | 触发时机 |
|---------|------|------|---------|
| `ping` | 心跳保活 | `{}` | 每30秒 |
| `subscribe` | 订阅频道 | `{channels: ["alerts:*", "agents:*"]}` | 连接后 |
| `unsubscribe` | 取消订阅 | `{channels: ["agents:*"]}` | 任意时间 |
| `alert.ack` | 告警确认回执 | `{alert_id, action}` | 收到告警推送后 |

### 4.3 服务端→客户端事件

| 事件类型 | 频道 | 说明 | 目标角色 | 载荷 |
|---------|------|------|---------|------|
| `pong` | - | 心跳回复 | 所有 | `{server_time}` |
| `subscribed` | - | 订阅确认 | 所有 | `{channels, ok}` |
| `alert.new` | `alerts:new` | 新告警产生 | 运维员/管理员 | `AlertSummary` |
| `alert.updated` | `alerts:updates` | 告警状态变更 | 运维员/管理员/审计员 | `{alert_id, old_status, new_status, operator}` |
| `alert.batch_update` | `alerts:updates` | 批量处置结果 | 运维员/管理员 | `{processed, failed, status}` |
| `agent.status` | `agents:status` | Agent在线状态变更 | 运维员/管理员 | `{agent_id, old_status, new_status, timestamp}` |
| `agent.heartbeat_lost` | `agents:alerts` | Agent心跳丢失告警 | 管理员 | `{agent_id, last_heartbeat, threshold}` |
| `agent.upgrade` | `agents:upgrade` | Agent升级进度 | 管理员 | `{agent_id, version, progress, status}` |
| `policy.deployed` | `policies:ops` | 策略下发完成 | 管理员 | `{policy_id, version, agent_count, results}` |
| `policy.updated` | `policies:ops` | 策略内容变更通知 | 管理员 | `{policy_id, version, action}` |
| `system.user_update` | `system:users` | 用户状态变更 | 管理员 | `{user_id, action}` |
| `ai.suggestion_ready` | `ai:suggestions` | AI研判完成 | 运维员/管理员 | `{alert_id, suggestion_id}` |
| `system.announcement` | `system:all` | 系统广播通知 | 所有 | `{title, content, level}` |

### 4.4 频道订阅规则

```
alerts:*          → 所有告警相关事件
alerts:new        → 仅新告警
alerts:updates    → 仅告警状态变更
agents:*          → 所有Agent相关事件
agents:status     → 仅Agent状态变更
agents:upgrade    → 仅Agent升级
policies:*        → 所有策略相关事件
system:*          → 所有系统事件
system:users      → 仅用户管理
ai:*              → AI相关事件
```

---

## 5. 数据库ER设计

### 5.1 整体ER图（文本描述）

```
┌─────────────┐     ┌──────────────────┐     ┌────────────────┐
│    users    │1──N │   user_roles     │N──1 │    roles       │
└─────────────┘     └──────────────────┘     └───────┬────────┘
                                                      │1
                                                      │N
┌─────────────┐     ┌──────────────────┐     ┌───────▼────────┐
│ login_logs  │N──1 │     users        │     │role_permissions│
└─────────────┘     └──────────────────┘     └───────┬────────┘
                                                      │N
                                                      │1
┌─────────────┐     ┌──────────────────┐     ┌───────▼────────┐
│ audit_logs  │N──1 │     users        │     │  permissions   │
└─────────────┘     └──────────────────┘     └────────────────┘

┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│     agents       │1──N │ agent_heartbeats │     │                  │
│                  │     │                  │     │    policies      │
│  ID: UUID        │     │  ID: BIGSERIAL   │     │                  │
│  agent_id: UNIQUE│     │  agent_id: FK    │     │  ID: UUID        │
│  hostname        │     │  payload: JSONB   │     │  name            │
│  ip_address      │     │  received_at     │     │  type: ENUM      │
│  os_version      │     └──────────────────┘     │  version         │
│  kernel_version  │                               │  rules: JSONB    │
│  agent_version   │     ┌──────────────────┐     │  status: ENUM    │
│  cpu_cores       │     │   alert_status_  │     │  created_by: FK  │
│  total_memory    │     │   history        │     └────────┬─────────┘
│  status: ENUM    │     │  ID: BIGSERIAL   │              │1
│  last_heartbeat  │     │  alert_id: FK    │              │N
│  registered_at   │     │  from_status     │     ┌────────▼─────────┐
│  tags: JSONB     │     │  to_status       │     │ policy_targets   │
│  metadata: JSONB │     │  operator_id: FK │     │                  │
└────────┬─────────┘     │  comment         │     │ policy_id: FK    │
         │1              │  created_at      │     │ agent_id         │
         │N              └──────────────────┘     │ group_expression │
┌────────▼─────────┐                               └──────────────────┘
│     alerts       │
│                  │     ┌──────────────────┐
│  ID: UUID        │     │ ai_conversations │
│  alert_id_seq    │     │                  │
│  agent_id: FK    │     │  ID: UUID        │
│  alert_type: ENUM│     │  user_id: FK     │
│  severity: ENUM  │     │  title           │
│  title           │     │  messages: JSONB  │
│  description     │     │  created_at      │
│  source: ENUM    │     │  updated_at      │
│  status: ENUM    │     └──────────────────┘
│  mitre_technique │
│  mitre_tactic    │     ┌──────────────────┐
│  mitre_id        │     │ operation_logs   │
│  raw_data: JSONB │     │                  │
│  assignee_id: FK │     │  ID: BIGSERIAL   │
│  suppressed: BOOL│     │  user_id: FK     │
│  suppressed_until│     │  action          │
│  suppress_reason │     │  resource_type   │
│  detected_at     │     │  resource_id     │
│  created_at      │     │  detail: JSONB   │
│  updated_at      │     │  ip_address      │
│  resolved_at     │     │  user_agent      │
└──────────────────┘     │  created_at      │
                         └──────────────────┘
```

### 5.2 完整表结构定义

---

#### 表1: `roles` — 角色表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| name | VARCHAR(50) | UNIQUE, NOT NULL | 角色名称（admin/operator/auditor/readonly） |
| display_name | VARCHAR(100) | NOT NULL | 显示名称 |
| description | TEXT | NULLABLE | 角色描述 |
| is_system | BOOLEAN | DEFAULT FALSE | 系统内置角色（不可删除） |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**索引**: `idx_roles_name` ON (name)

**预置数据**: admin(管理员), operator(运维员), auditor(审计员), readonly(只读)

---

#### 表2: `permissions` — 权限表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK | 主键 |
| code | VARCHAR(100) | UNIQUE, NOT NULL | 权限编码（如 `alert:read`） |
| name | VARCHAR(100) | NOT NULL | 权限名称 |
| module | VARCHAR(50) | NOT NULL | 所属模块（auth/agent/alert/policy/system/ai） |
| action | VARCHAR(50) | NOT NULL | 操作类型（read/create/update/delete/approve） |
| description | TEXT | NULLABLE | 权限说明 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**: 
- `idx_permissions_code` ON (code) UNIQUE
- `idx_permissions_module` ON (module)

---

#### 表3: `role_permissions` — 角色权限关联表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| role_id | UUID | FK → roles(id) ON DELETE CASCADE | 角色ID |
| permission_id | UUID | FK → permissions(id) ON DELETE CASCADE | 权限ID |
| PRIMARY KEY | (role_id, permission_id) | | 联合主键 |

**索引**: `idx_role_permissions_role` ON (role_id)

---

#### 表4: `users` — 用户表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| username | VARCHAR(64) | UNIQUE, NOT NULL | 用户名 |
| password_hash | VARCHAR(256) | NOT NULL | bcrypt哈希密码 |
| display_name | VARCHAR(100) | NOT NULL | 显示名称 |
| email | VARCHAR(128) | UNIQUE, NOT NULL | 邮箱 |
| phone | VARCHAR(20) | NULLABLE | 手机号 |
| is_active | BOOLEAN | DEFAULT TRUE | 启用状态 |
| is_locked | BOOLEAN | DEFAULT FALSE | 锁定状态 |
| locked_until | TIMESTAMPTZ | NULLABLE | 锁定到期时间 |
| login_attempts | INTEGER | DEFAULT 0 | 连续登录失败次数 |
| last_login_at | TIMESTAMPTZ | NULLABLE | 最后登录时间 |
| last_login_ip | INET | NULLABLE | 最后登录IP |
| mfa_enabled | BOOLEAN | DEFAULT FALSE | 是否启用MFA |
| mfa_secret | VARCHAR(64) | NULLABLE | MFA密钥 |
| password_changed_at | TIMESTAMPTZ | DEFAULT NOW() | 密码最后修改时间 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**索引**:
- `idx_users_username` ON (username) UNIQUE
- `idx_users_email` ON (email) UNIQUE
- `idx_users_is_active` ON (is_active) WHERE is_active = TRUE
- `idx_users_last_login` ON (last_login_at)

---

#### 表5: `user_roles` — 用户角色关联表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| user_id | UUID | FK → users(id) ON DELETE CASCADE | 用户ID |
| role_id | UUID | FK → roles(id) ON DELETE CASCADE | 角色ID |
| granted_by | UUID | FK → users(id) | 授权人ID |
| granted_at | TIMESTAMPTZ | DEFAULT NOW() | 授权时间 |
| PRIMARY KEY | (user_id, role_id) | | 联合主键 |

**索引**: `idx_user_roles_user` ON (user_id)

---

#### 表6: `agents` — Agent表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 内部主键 |
| agent_id | VARCHAR(128) | UNIQUE, NOT NULL | Agent标识（如 `kylin-node-01`） |
| hostname | VARCHAR(256) | NOT NULL | 主机名 |
| ip_address | INET | NOT NULL | IP地址 |
| os_version | VARCHAR(64) | NOT NULL | 麒麟OS版本 |
| kernel_version | VARCHAR(64) | NULLABLE | 内核版本 |
| agent_version | VARCHAR(32) | NOT NULL | Agent版本号 |
| cpu_cores | INTEGER | NOT NULL | CPU核心数 |
| total_memory | BIGINT | NOT NULL | 总内存(MB) |
| disk_total | BIGINT | NULLABLE | 总磁盘(GB) |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'offline' | 状态：online/offline/error/upgrading |
| last_heartbeat | TIMESTAMPTZ | NULLABLE | 最后心跳时间 |
| last_heartbeat_ip | INET | NULLABLE | 最后心跳来源IP |
| registered_at | TIMESTAMPTZ | DEFAULT NOW() | 注册时间 |
| first_seen_at | TIMESTAMPTZ | DEFAULT NOW() | 首次发现时间 |
| tags | JSONB | DEFAULT '[]' | 标签数组 |
| metadata | JSONB | DEFAULT '{}' | 扩展元数据 |
| config_version | INTEGER | DEFAULT 0 | 当前配置版本号 |
| is_deleted | BOOLEAN | DEFAULT FALSE | 软删除标记 |
| deleted_at | TIMESTAMPTZ | NULLABLE | 删除时间 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**索引**:
- `idx_agents_agent_id` ON (agent_id) UNIQUE
- `idx_agents_status` ON (status)
- `idx_agents_last_heartbeat` ON (last_heartbeat) WHERE is_deleted = FALSE
- `idx_agents_agent_version` ON (agent_version)
- `idx_agents_tags` GIN (tags)
- `idx_agents_os_version` ON (os_version)

**分区建议**: 当Agent数量超过5000时，可按 `status` 字段进行列表分区。

---

#### 表7: `agent_heartbeats` — 心跳流水表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PK | 自增主键 |
| agent_id | VARCHAR(128) | NOT NULL | Agent标识 |
| received_at | TIMESTAMPTZ | NOT NULL, DEFAULT NOW() | 接收时间 |
| cpu_usage | REAL | NULLABLE | CPU使用率(%) |
| cpu_cores | SMALLINT | NULLABLE | CPU核心数 |
| memory_total | INTEGER | NULLABLE | 总内存(MB) |
| memory_used | INTEGER | NULLABLE | 已用内存(MB) |
| memory_percent | REAL | NULLABLE | 内存使用率(%) |
| disk_json | JSONB | NULLABLE | 磁盘信息数组 |
| processes_total | INTEGER | NULLABLE | 总进程数 |
| processes_running | INTEGER | NULLABLE | 运行中进程数 |
| agent_version | VARCHAR(32) | NULLABLE | Agent版本 |
| payload | JSONB | NOT NULL | 原始上报完整数据 |
| ip_address | INET | NULLABLE | 来源IP |

**索引**:
- `idx_heartbeats_agent_time` ON (agent_id, received_at DESC)
- `idx_heartbeats_received_at` ON (received_at)
- `idx_heartbeats_cpu_usage` ON (agent_id, received_at DESC, cpu_usage) — 趋势查询

**分区策略**: 按月分区 (PARTITION BY RANGE (received_at))

```sql
CREATE TABLE agent_heartbeats (
    ...
) PARTITION BY RANGE (received_at);

CREATE TABLE agent_heartbeats_2026_06 PARTITION OF agent_heartbeats
    FOR VALUES FROM ('2026-06-01') TO ('2026-07-01');

CREATE TABLE agent_heartbeats_2026_07 PARTITION OF agent_heartbeats
    FOR VALUES FROM ('2026-07-01') TO ('2026-08-01');
-- 后续按月自动创建
```

**数据保留策略**: 原始心跳数据保留90天，聚合数据保留1年。

---

#### 表8: `alerts` — 告警表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| alert_seq | BIGSERIAL | NOT NULL | 告警序号（人工可读） |
| agent_id | VARCHAR(128) | NOT NULL | 关联Agent标识 |
| alert_type | VARCHAR(32) | NOT NULL | 告警类型（见下方枚举） |
| severity | VARCHAR(16) | NOT NULL | 严重度：critical/high/medium/low/info |
| title | VARCHAR(256) | NOT NULL | 告警标题 |
| description | TEXT | NOT NULL | 告警描述 |
| detail | JSONB | DEFAULT '{}' | 告警详细数据 |
| source | VARCHAR(32) | NOT NULL, DEFAULT 'agent' | 来源：agent/system/manual |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'new' | 状态：new/acknowledged/investigating/resolved/false_positive/closed |
| status_changed_at | TIMESTAMPTZ | NULLABLE | 最后状态变更时间 |
| mitre_technique_id | VARCHAR(32) | NULLABLE | MITRE ATT&CK技术ID（如 T1078） |
| mitre_tactic | VARCHAR(64) | NULLABLE | MITRE ATT&CK战术 |
| mitre_technique_name | VARCHAR(128) | NULLABLE | MITRE技术名称 |
| assignee_id | UUID | FK → users(id), NULLABLE | 处理人 |
| assigned_at | TIMESTAMPTZ | NULLABLE | 指派时间 |
| suppressed | BOOLEAN | DEFAULT FALSE | 是否被抑制 |
| suppressed_until | TIMESTAMPTZ | NULLABLE | 抑制到期时间 |
| suppress_reason | TEXT | NULLABLE | 抑制原因 |
| resolved_at | TIMESTAMPTZ | NULLABLE | 解决时间 |
| resolved_by | UUID | FK → users(id), NULLABLE | 解决人 |
| correlation_key | VARCHAR(128) | NULLABLE | 关联聚合键 |
| correlation_count | INTEGER | DEFAULT 1 | 聚合告警计数 |
| first_detected_at | TIMESTAMPTZ | NOT NULL | 首次检测时间 |
| last_detected_at | TIMESTAMPTZ | NOT NULL | 最后检测时间 |
| alert_count | INTEGER | DEFAULT 1 | 告警聚合次数 |
| is_deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**告警类型枚举** (alert_type):

| 类型值 | 说明 | MITRE战术映射 |
|--------|------|-------------|
| `file_monitor` | 文件监控告警 | TA0003(持久化) / TA0005(防御规避) |
| `process_monitor` | 进程异常告警 | TA0002(执行) |
| `network_monitor` | 网络连接异常 | TA0011(命令与控制) |
| `login_monitor` | 登录行为异常 | TA0001(初始访问) |
| `user_monitor` | 用户行为异常 | TA0004(权限提升) |
| `vulnerability` | 漏洞告警 | TA0007(发现) |
| `malware` | 恶意软件告警 | TA0002~TA0040 |
| `privilege_escalation` | 提权告警 | TA0004(权限提升) |
| `lateral_movement` | 横向移动告警 | TA0008(横向移动) |
| `persistence` | 持久化告警 | TA0003(持久化) |
| `defense_evasion` | 防御规避告警 | TA0005(防御规避) |
| `anomaly` | 行为异常告警 | TA0043(侦察) |

**严重度分级**:

| 级别 | 值 | 响应时限 | 颜色 |
|------|-----|---------|------|
| 致命 | critical | 15分钟 | #E02020 |
| 高 | high | 30分钟 | #FF6B00 |
| 中 | medium | 2小时 | #FFC107 |
| 低 | low | 8小时 | #1890FF |
| 信息 | info | 不处理 | #8C8C8C |

**状态流转图**:

```
new ──► acknowledged ──► investigating ──► resolved
  │                        │                 │
  ├──► false_positive ─────┘                 │
  │                                          │
  ├────────────────────► closed ─────────────┘
  │
  └──► (auto-suppress)
```

**索引**:
- `idx_alerts_agent_id` ON (agent_id, created_at DESC)
- `idx_alerts_status` ON (status, created_at DESC)
- `idx_alerts_severity` ON (severity, created_at DESC)
- `idx_alerts_type` ON (alert_type, created_at DESC)
- `idx_alerts_mitre_technique` ON (mitre_technique_id)
- `idx_alerts_assignee` ON (assignee_id) WHERE assignee_id IS NOT NULL
- `idx_alerts_created_at` ON (created_at DESC)
- `idx_alerts_correlation_key` ON (correlation_key)
- `idx_alerts_search` GIN (to_tsvector('chinese', title || ' ' || COALESCE(description, '')))
- `idx_alerts_active` ON (status) WHERE status IN ('new', 'acknowledged', 'investigating')
- `idx_alerts_suppressed` ON (suppressed) WHERE suppressed = TRUE

---

#### 表9: `alert_status_history` — 告警状态流转历史表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PK | 自增主键 |
| alert_id | UUID | FK → alerts(id) ON DELETE CASCADE | 告警ID |
| from_status | VARCHAR(20) | NULLABLE | 原状态 |
| to_status | VARCHAR(20) | NOT NULL | 新状态 |
| operator_id | UUID | FK → users(id), NULLABLE | 操作人 |
| operator_name | VARCHAR(64) | NULLABLE | 操作人名称（冗余防删除） |
| operation | VARCHAR(32) | NOT NULL | 操作类型 |
| comment | TEXT | NULLABLE | 备注 |
| source | VARCHAR(16) | DEFAULT 'manual' | 来源：manual/auto/ai |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**:
- `idx_alert_history_alert` ON (alert_id, created_at)
- `idx_alert_history_operator` ON (operator_id)

---

#### 表10: `policies` — 策略表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| name | VARCHAR(128) | NOT NULL | 策略名称 |
| description | TEXT | NULLABLE | 策略描述 |
| policy_type | VARCHAR(32) | NOT NULL | 策略类型（见下方枚举） |
| version | INTEGER | NOT NULL, DEFAULT 1 | 当前版本号 |
| rules | JSONB | NOT NULL | 策略规则集 |
| status | VARCHAR(20) | NOT NULL, DEFAULT 'draft' | 状态：draft/enabled/disabled/archived |
| target_type | VARCHAR(20) | NOT NULL, DEFAULT 'all' | 目标类型：all/tags/agent_ids/expression |
| target_value | JSONB | DEFAULT '[]' | 目标值 |
| priority | INTEGER | DEFAULT 100 | 策略优先级（数字越小优先级越高） |
| effective_start | TIMESTAMPTZ | NULLABLE | 生效开始时间 |
| effective_end | TIMESTAMPTZ | NULLABLE | 生效结束时间 |
| is_template | BOOLEAN | DEFAULT FALSE | 是否模板 |
| created_by | UUID | FK → users(id) | 创建人 |
| updated_by | UUID | FK → users(id) | 最后修改人 |
| deployed_version | INTEGER | DEFAULT 0 | 已下发版本号 |
| last_deployed_at | TIMESTAMPTZ | NULLABLE | 最后下发时间 |
| is_deleted | BOOLEAN | DEFAULT FALSE | 软删除 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**策略类型枚举**:

| 类型值 | 说明 | 典型规则 |
|--------|------|---------|
| `file_integrity` | 文件完整性监控 | `{paths: [...], hash_algorithm: "sha256", check_interval: 300}` |
| `process_whitelist` | 进程白名单 | `{allowed: [...], denied: [...], action: "alert|block"}` |
| `network_firewall` | 网络访问控制 | `{rules: [{direction, port, proto, action}]}` |
| `login_policy` | 登录安全策略 | `{max_attempts, lockout_duration, allowed_ip_ranges}` |
| `vulnerability_scan` | 漏洞扫描策略 | `{scan_interval, cve_filter, severity_threshold}` |
| `log_audit` | 日志审计规则 | `{log_types, retention_days, forward_target}` |

**索引**:
- `idx_policies_status` ON (status) WHERE is_deleted = FALSE
- `idx_policies_type` ON (policy_type)
- `idx_policies_created_by` ON (created_by)
- `idx_policies_name` ON (name)

---

#### 表11: `policy_versions` — 策略版本表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| policy_id | UUID | FK → policies(id) ON DELETE CASCADE | 策略ID |
| version | INTEGER | NOT NULL | 版本号 |
| rules | JSONB | NOT NULL | 该版本的规则集 |
| changelog | TEXT | NULLABLE | 变更说明 |
| created_by | UUID | FK → users(id) | 创建人 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**:
- `idx_policy_versions_policy` ON (policy_id, version DESC) UNIQUE
- `idx_policy_versions_created_by` ON (created_by)

---

#### 表12: `policy_targets` — 策略目标Agent表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PK | 自增主键 |
| policy_id | UUID | FK → policies(id) ON DELETE CASCADE | 策略ID |
| agent_id | VARCHAR(128) | NOT NULL | Agent标识 |
| status | VARCHAR(20) | DEFAULT 'pending' | 下发状态：pending/deployed/failed |
| deployed_version | INTEGER | NULLABLE | 实际下发版本号 |
| deployed_at | TIMESTAMPTZ | NULLABLE | 下发时间 |
| error_message | TEXT | NULLABLE | 失败原因 |
| retry_count | INTEGER | DEFAULT 0 | 重试次数 |

**索引**:
- `idx_policy_targets_policy_agent` ON (policy_id, agent_id) UNIQUE
- `idx_policy_targets_agent` ON (agent_id)
- `idx_policy_targets_status` ON (status)

---

#### 表13: `login_logs` — 登录日志表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PK | 自增主键 |
| user_id | UUID | FK → users(id), NULLABLE | 用户ID（失败可能为空） |
| username | VARCHAR(64) | NOT NULL | 登录用户名 |
| status | VARCHAR(16) | NOT NULL | 状态：success/failed/locked/mfa_required |
| failure_reason | VARCHAR(64) | NULLABLE | 失败原因 |
| ip_address | INET | NOT NULL | 登录IP |
| user_agent | TEXT | NULLABLE | 客户端UA |
| session_id | VARCHAR(128) | NULLABLE | 会话ID |
| auth_method | VARCHAR(32) | NOT NULL, DEFAULT 'password' | 认证方式 |
| login_at | TIMESTAMPTZ | DEFAULT NOW() | 登录时间 |

**索引**:
- `idx_login_logs_user` ON (user_id, login_at DESC)
- `idx_login_logs_username` ON (username, login_at DESC)
- `idx_login_logs_login_at` ON (login_at DESC)
- `idx_login_logs_ip` ON (ip_address)

**分区策略**: 按月分区

---

#### 表14: `audit_logs` — 操作审计日志表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | BIGSERIAL | PK | 自增主键 |
| user_id | UUID | FK → users(id), NULLABLE | 操作人 |
| username | VARCHAR(64) | NOT NULL | 操作人用户名 |
| action | VARCHAR(64) | NOT NULL | 操作类型：create/update/delete/action/login/export |
| resource_type | VARCHAR(64) | NOT NULL | 资源类型：alert/policy/agent/user/role/system |
| resource_id | VARCHAR(128) | NULLABLE | 资源ID |
| resource_name | VARCHAR(256) | NULLABLE | 资源名称 |
| detail | JSONB | DEFAULT '{}' | 操作详情（变更前后） |
| ip_address | INET | NULLABLE | 操作来源IP |
| user_agent | TEXT | NULLABLE | 客户端UA |
| duration_ms | INTEGER | NULLABLE | 操作耗时(ms) |
| result | VARCHAR(16) | DEFAULT 'success' | 结果：success/failure/partial |
| error_message | TEXT | NULLABLE | 错误信息 |
| correlation_id | VARCHAR(128) | NULLABLE | 关联追踪ID |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |

**索引**:
- `idx_audit_logs_user` ON (user_id, created_at DESC)
- `idx_audit_logs_action` ON (action, created_at DESC)
- `idx_audit_logs_resource` ON (resource_type, resource_id)
- `idx_audit_logs_created_at` ON (created_at DESC)
- `idx_audit_logs_correlation_id` ON (correlation_id)
- `idx_audit_logs_search` GIN (to_tsvector('chinese', COALESCE(resource_name, '') || ' ' || COALESCE(detail::text, '')))

**分区策略**: 按月分区

---

#### 表15: `ai_conversations` — AI对话记录表

| 字段名 | 类型 | 约束 | 说明 |
|--------|------|------|------|
| id | UUID | PK, DEFAULT gen_random_uuid() | 主键 |
| user_id | UUID | FK → users(id) | 用户ID |
| title | VARCHAR(256) | NULLABLE | 对话标题（自动摘要） |
| messages | JSONB | NOT NULL, DEFAULT '[]' | 消息数组 |
| context | JSONB | DEFAULT '{}' | 上下文数据 |
| related_alert_id | UUID | FK → alerts(id), NULLABLE | 关联告警 |
| feedback_score | SMALLINT | NULLABLE | 用户反馈评分 (1-5) |
| feedback_comment | TEXT | NULLABLE | 反馈评论 |
| token_usage | INTEGER | DEFAULT 0 | Token消耗 |
| model_name | VARCHAR(64) | NULLABLE | AI模型名称 |
| duration_ms | INTEGER | NULLABLE | 处理耗时 |
| created_at | TIMESTAMPTZ | DEFAULT NOW() | 创建时间 |
| updated_at | TIMESTAMPTZ | DEFAULT NOW() | 更新时间 |

**索引**:
- `idx_ai_conv_user` ON (user_id, updated_at DESC)
- `idx_ai_conv_alert` ON (related_alert_id)

---

### 5.3 数据库初始化SQL摘要

```sql
-- 1. 启用必要扩展
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements";

-- 2. 创建自定义枚举类型
CREATE TYPE agent_status AS ENUM ('online', 'offline', 'error', 'upgrading');
CREATE TYPE alert_status AS ENUM ('new', 'acknowledged', 'investigating', 'resolved', 'false_positive', 'closed');
CREATE TYPE alert_severity AS ENUM ('critical', 'high', 'medium', 'low', 'info');
CREATE TYPE policy_status AS ENUM ('draft', 'enabled', 'disabled', 'archived');

-- 3. 创建updated_at自动更新函数
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. 为所有含updated_at的表创建触发器
-- (每个表单独执行)
```

---

## 6. 核心接口请求/响应示例

### 6.1 POST /api/v1/auth/login — 用户登录

**Request**:
```json
{
  "username": "admin",
  "password": "Kylin@2026!Secure",
  "mfa_code": null
}
```

**Response (200)**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "access_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "refresh_token": "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "expires_in": 3600,
    "refresh_expires_in": 86400,
    "user": {
      "id": "a1b2c3d4-...",
      "username": "admin",
      "display_name": "系统管理员",
      "roles": [
        {"id": "...", "name": "admin", "display_name": "管理员"}
      ],
      "permissions": [
        "agent:read", "agent:write", "alert:read", "alert:write",
        "policy:read", "policy:write", "system:read", "system:write",
        "audit:read", "ai:read", "ai:write"
      ]
    }
  },
  "request_id": "req-abc123"
}
```

**Response (401)**:
```json
{
  "code": 40101,
  "message": "用户名或密码错误",
  "detail": "剩余重试次数: 4",
  "request_id": "req-abc123"
}
```

**Response (423)**:
```json
{
  "code": 40103,
  "message": "账户已被锁定",
  "detail": "请15分钟后重试，或联系管理员解锁",
  "request_id": "req-abc123"
}
```

---

### 6.2 POST /api/v1/agent/heartbeat — Agent心跳上报

**Request**:
```json
{
  "agentId": "kylin-node-01",
  "timestamp": "2026-06-23T20:00:00Z",
  "cpu": {"usage": 45.2, "cores": 8},
  "memory": {"total": 16384, "used": 8192, "percent": 50.0},
  "disk": [
    {"mount": "/", "total": 500, "used": 320, "percent": 64.0},
    {"mount": "/data", "total": 2000, "used": 1200, "percent": 60.0}
  ],
  "processes": {"total": 245, "running": 12},
  "version": "3.2.0",
  "status": "online"
}
```

**Response (200)** — 正常回应：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "server_time": "2026-06-23T20:00:02Z",
    "next_heartbeat_interval": 10,
    "config_version": 3,
    "pending_tasks": [
      {"task_id": "task-001", "type": "upgrade", "params": {"version": "3.2.1", "package_url": "..."}},
      {"task_id": "task-002", "type": "policy_sync", "params": {"policy_ids": ["policy-01"]}}
    ],
    "ack_action": "continue"
  },
  "request_id": "req-agent-hb-001"
}
```

**Response (200)** — 配置需要更新：
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "server_time": "2026-06-23T20:00:02Z",
    "next_heartbeat_interval": 5,
    "config_version": 5,
    "config_update_required": true,
    "pending_tasks": [],
    "ack_action": "reconfigure"
  },
  "request_id": "req-agent-hb-002"
}
```

**处理逻辑**：
```
1. 验证Agent Token
2. 查询/缓存Agent记录，更新 status=online, last_heartbeat=NOW()
3. 解析payload写入 agent_heartbeats 表
4. 检测Agent状态变更 → 如有变更，通过WebSocket广播 agent.status
5. 检测心跳丢失阈值恢复 → 清除离线告警
6. 查询是否有待处理任务或配置更新
7. 返回心跳间隔和待处理任务
```

---

### 6.3 GET /api/v1/alerts — 告警列表（带筛选）

**Request**:
```
GET /api/v1/alerts?page=1&size=20&status=new,acknowledged&severity=critical,high
    &alert_type=login_monitor,privilege_escalation
    &agent_id=kylin-node-01
    &start_time=2026-06-01T00:00:00Z&end_time=2026-06-23T23:59:59Z
    &mitre_technique=T1078
    &keyword=brute+force
    &sort_by=severity&sort_order=desc
```

**Response (200)**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "items": [
      {
        "id": "alert-001",
        "alert_seq": 10245,
        "agent_id": "kylin-node-01",
        "hostname": "kylin-node-01",
        "alert_type": "login_monitor",
        "alert_type_label": "登录行为异常",
        "severity": "critical",
        "severity_label": "致命",
        "title": "检测到SSH暴力破解攻击",
        "description": "kylin-node-01 在5分钟内收到 156 次 SSH 登录失败尝试，来源IP: 192.168.1.100",
        "status": "new",
        "status_label": "待处理",
        "mitre_technique_id": "T1110",
        "mitre_tactic": "TA0006",
        "mitre_technique_name": "暴力破解",
        "assignee": null,
        "assigned_at": null,
        "suppressed": false,
        "correlation_count": 1,
        "first_detected_at": "2026-06-23T19:55:00Z",
        "last_detected_at": "2026-06-23T20:00:00Z",
        "alert_count": 1,
        "created_at": "2026-06-23T20:00:01Z"
      }
    ],
    "total": 1,
    "page": 1,
    "size": 20,
    "total_pages": 1,
    "filter_summary": {
      "status_filter": "new,acknowledged",
      "severity_filter": "critical,high",
      "time_range": "2026-06-01 ~ 2026-06-23"
    }
  },
  "request_id": "req-alert-list-001"
}
```

---

### 6.4 POST /api/v1/alerts/batch/status — 批量处置告警

**Request**:
```json
{
  "alert_ids": [
    "alert-001",
    "alert-002",
    "alert-003"
  ],
  "status": "resolved",
  "comment": "已确认并修复SSH配置，添加了IP白名单和fail2ban保护",
  "notify_assignee": true
}
```

**Response (200)**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "total": 3,
    "processed": 3,
    "failed": 0,
    "details": [
      {"alert_id": "alert-001", "success": true, "from_status": "new", "to_status": "resolved"},
      {"alert_id": "alert-002", "success": true, "from_status": "acknowledged", "to_status": "resolved"},
      {"alert_id": "alert-003", "success": true, "from_status": "investigating", "to_status": "resolved"}
    ]
  },
  "request_id": "req-batch-status-001"
}
```

**Response (207)** — 部分成功：
```json
{
  "code": 0,
  "message": "部分操作成功",
  "data": {
    "total": 5,
    "processed": 3,
    "failed": 2,
    "details": [
      {"alert_id": "alert-001", "success": true, "from_status": "new", "to_status": "resolved"},
      {"alert_id": "alert-002", "success": true, "from_status": "new", "to_status": "resolved"},
      {"alert_id": "alert-004", "success": false, "error": "告警状态已为closed，不允许变更"},
      {"alert_id": "alert-005", "success": false, "error": "告警不存在或已删除"}
    ]
  },
  "request_id": "req-batch-status-002"
}
```

**处理逻辑**：
```
1. 验证当前用户权限（需要 alert:write）
2. 批量查询告警，验证状态机是否允许目标状态流转
3. 逐条执行状态更新 + 写入 alert_status_history
4. 如果有指派处理人变更，更新 assignee_id
5. 如 resolved，记录 resolved_at 和 resolved_by
6. 通过WebSocket广播 alert.updated 事件
7. 记录操作审计日志
8. 返回处理结果
```

---

### 6.5 POST /api/v1/policies — 创建策略

**Request**:
```json
{
  "name": "核心服务器文件完整性监控",
  "description": "对核心生产服务器的关键目录进行文件完整性监控",
  "policy_type": "file_integrity",
  "rules": {
    "paths": [
      "/etc/passwd",
      "/etc/shadow",
      "/etc/ssh/sshd_config",
      "/etc/sudoers",
      "/usr/lib/systemd/system/",
      "/opt/kylin-secops/etc/"
    ],
    "exclude_paths": [
      "/opt/kylin-secops/etc/cache/"
    ],
    "hash_algorithm": "sha256",
    "check_interval": 300,
    "action_on_change": "alert",
    "alert_severity": "high",
    "include_metadata": true
  },
  "target_type": "tags",
  "target_value": ["production", "core-server"],
  "priority": 10,
  "effective_start": "2026-06-24T00:00:00Z",
  "effective_end": null
}
```

**Response (201)**:
```json
{
  "code": 0,
  "message": "策略创建成功",
  "data": {
    "id": "policy-001",
    "name": "核心服务器文件完整性监控",
    "description": "对核心生产服务器的关键目录进行文件完整性监控",
    "policy_type": "file_integrity",
    "policy_type_label": "文件完整性监控",
    "version": 1,
    "rules": { "...": "..." },
    "status": "draft",
    "status_label": "草稿",
    "target_type": "tags",
    "target_value": ["production", "core-server"],
    "preview_target_count": 12,
    "priority": 10,
    "effective_start": "2026-06-24T00:00:00Z",
    "effective_end": null,
    "created_by": {
      "id": "user-001",
      "username": "admin",
      "display_name": "系统管理员"
    },
    "created_at": "2026-06-23T20:05:00Z",
    "updated_at": "2026-06-23T20:05:00Z"
  },
  "request_id": "req-policy-create-001"
}
```

---

### 6.6 POST /api/v1/ai/query — AI自然语言运维查询

**Request**:
```json
{
  "question": "最近24小时内，有多少台Agent的CPU使用率超过80%？列出这些Agent的名称和当前的CPU使用率",
  "context_alert_id": null,
  "timezone": "Asia/Shanghai"
}
```

**Response (200)**:
```json
{
  "code": 0,
  "message": "success",
  "data": {
    "conversation_id": "conv-001",
    "message_id": "msg-001",
    "answer": "根据查询，最近24小时内共有 **3台** Agent的CPU使用率超过80%：\n\n| Agent名称 | 当前CPU使用率 | 峰值时间 | 持续时长 |\n|-----------|-------------|---------|---------|\n| kylin-node-07 | 92.3% | 2026-06-23 14:30 | 已持续2小时 |\n| kylin-node-12 | 87.1% | 2026-06-23 16:45 | 约45分钟 |\n| kylin-node-23 | 85.6% | 2026-06-23 19:20 | 约15分钟 |\n\n**建议操作**：\n1. 检查 kylin-node-07 是否运行了异常的定时任务或进程\n2. 使用 `ssh kylin-node-07 'top -b -n 1 | head -20'` 查看当前进程\n3. 如确认正常负载，考虑为该节点增加资源分配",
    "confidence": 0.95,
    "data_sources": [
      {"type": "agent_heartbeats", "time_range": "24h", "records_analyzed": 86400},
      {"type": "alerts", "filter": "severity>=high,last_24h", "records_analyzed": 15}
    ],
    "suggested_actions": [
      {"type": "command", "label": "查看kylin-node-07进程", "command": "ssh kylin-node-07 'top -b -n 1 | head -20'"},
      {"type": "link", "label": "查看kylin-node-07告警", "url": "/agents/kylin-node-07/alerts"},
      {"type": "action", "label": "创建处理工单", "action": "create_ticket"}
    ],
    "token_usage": 2048,
    "processing_time_ms": 3200
  },
  "request_id": "req-ai-query-001"
}
```

---

### 6.7 WebSocket事件示例 — 告警实时推送

**服务端→客户端** (频道: `alerts:new`):

```json
{
  "type": "alert.new",
  "channel": "alerts:new",
  "timestamp": "2026-06-23T20:01:00Z",
  "data": {
    "id": "alert-003",
    "alert_seq": 10246,
    "agent_id": "kylin-node-07",
    "alert_type": "privilege_escalation",
    "severity": "critical",
    "title": "检测到可疑sudo提权操作",
    "description": "用户 'devops' 在非预期时间执行sudo命令: /usr/bin/su root",
    "status": "new",
    "mitre_technique_id": "T1548.003",
    "created_at": "2026-06-23T20:01:00Z"
  }
}
```

---

## 7. Alembic迁移策略

### 7.1 初始化配置

```ini
# alembic.ini
[alembic]
script_location = alembic
sqlalchemy.url = postgresql+asyncpg://kylin_secops:password@localhost:5432/kylin_secops
# 异步支持
# 使用 async def run_migrations_online() 在 env.py 中配置
```

### 7.2 迁移目录结构

```
alembic/
├── versions/
│   ├── 0001_initial_schema.py           # 初始表结构
│   ├── 0002_seed_rbac_data.py           # 注入角色和权限
│   ├── 0003_add_alert_status_history.py # 告警状态流转表
│   ├── 0004_add_ai_conversations.py     # AI对话表
│   ├── 0005_add_agent_heartbeat_partitions.py  # 心跳表分区
│   └── 0006_add_fulltext_search_indexes.py     # 全文索引
├── env.py           # 异步环境配置
├── script.py.mako   # 迁移模板
└── README
```

### 7.3 异步迁移配置 (env.py)

```python
# alembic/env.py
import asyncio
from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine
from app.models import Base  # 所有模型的声明基类

target_metadata = Base.metadata

def run_migrations_offline():
    """离线模式：使用URL直接生成SQL"""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,      # 检测字段类型变更
        compare_server_default=True,  # 检测默认值变更
    )
    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online():
    """在线模式：异步引擎执行迁移"""
    connectable = create_async_engine(
        config.get_main_option("sqlalchemy.url"),
        poolclass=NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
```

### 7.4 迁移编写规范

```python
"""0001_initial_schema.py — 初始表结构

Revision ID: 0001
Revises: 
Create Date: 2026-06-23 20:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '0001'
down_revision = None
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. 启用扩展
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "pgcrypto"')
    
    # 2. 创建枚举类型（使用原生PG枚举提高性能）
    op.execute("CREATE TYPE agent_status AS ENUM ('online', 'offline', 'error', 'upgrading')")
    op.execute("CREATE TYPE alert_status AS ENUM ('new', 'acknowledged', 'investigating', 'resolved', 'false_positive', 'closed')")
    op.execute("CREATE TYPE alert_severity AS ENUM ('critical', 'high', 'medium', 'low', 'info')")
    
    # 3. 创建 updated_at 触发器函数
    op.execute("""
        CREATE OR REPLACE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $$
        BEGIN
            NEW.updated_at = NOW();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
    """)
    
    # 4. 创建 users 表
    op.create_table('users',
        sa.Column('id', postgresql.UUID(), server_default=sa.text('gen_random_uuid()'), nullable=False),
        sa.Column('username', sa.String(64), nullable=False),
        sa.Column('password_hash', sa.String(256), nullable=False),
        sa.Column('display_name', sa.String(100), nullable=False),
        sa.Column('email', sa.String(128), nullable=False),
        sa.Column('phone', sa.String(20), nullable=True),
        sa.Column('is_active', sa.Boolean(), server_default=sa.text('TRUE'), nullable=False),
        sa.Column('is_locked', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('locked_until', sa.DateTime(timezone=True), nullable=True),
        sa.Column('login_attempts', sa.Integer(), server_default=sa.text('0'), nullable=False),
        sa.Column('last_login_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_login_ip', postgresql.INET(), nullable=True),
        sa.Column('mfa_enabled', sa.Boolean(), server_default=sa.text('FALSE'), nullable=False),
        sa.Column('mfa_secret', sa.String(64), nullable=True),
        sa.Column('password_changed_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('NOW()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('email'),
    )
    op.create_index('idx_users_is_active', 'users', ['is_active'], postgresql_where=sa.text('is_active = TRUE'))
    op.execute("""
        CREATE TRIGGER update_users_updated_at 
            BEFORE UPDATE ON users 
            FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
    """)
    
    # ... 后续表结构依次创建
```

### 7.5 迁移执行策略

| 阶段 | 操作 | 命令 |
|------|------|------|
| 开发 | 自动生成迁移 | `alembic revision --autogenerate -m "description"` |
| 开发 | 升级到最新 | `alembic upgrade head` |
| 开发 | 回滚一个版本 | `alembic downgrade -1` |
| 预发布 | 检查SQL | `alembic upgrade head --sql > migration.sql` |
| 生产 | 灰度执行 | 先读库副本执行 `upgrade head --sql`，审核后执行 |
| 生产 | 失败回滚 | `alembic downgrade <prev_revision>` |

### 7.6 迁移注意事项

1. **大表迁移（心跳表/审计日志）**：
   - 使用 `batch_alter_table` 模式避免锁表
   - 先创建新表，再通过触发器同步，最后切换

2. **索引创建**：
   - 使用 `CONCURRENTLY` 参数在线创建索引
   - 对于大于100万行的表，在业务低峰期执行

3. **数据迁移**：
   - 使用独立的数据迁移脚本（不混入 schema 迁移）
   - 分批处理，每批 1000 条，带进度日志

---

## 8. Redis数据结构设计

### 8.1 Redis使用场景总览

| 用途 | 数据结构 | Key命名空间 | TTL | 说明 |
|------|---------|------------|-----|------|
| Token缓存 | String | `token:{jwt_jti}` | 3600s | JWT令牌白名单 |
| 刷新Token | String | `refresh:{jti}` | 86400s | 刷新令牌 |
| Agent在线状态 | Hash | `agent:status` | 无 | `{agent_id → status_json}` |
| Agent最后心跳 | Hash | `agent:heartbeat` | 无 | `{agent_id → timestamp}` |
| Agent心跳间隔 | String | `agent:hb_interval:{agent_id}` | 3600s | 动态调整心跳间隔 |
| 在线Agent集合 | Set | `agents:online` | 无 | 在线Agent ID集合 |
| 告警计数 | SortedSet | `alert:count:{date}` | 7d | 按类型统计日告警数 |
| WebSocket连接 | Hash | `ws:connections` | 无 | `{conn_id → user_info}` |
| 频道订阅 | Set | `ws:channel:{channel}` | 无 | 订阅某频道的连接ID集合 |
| 用户频道映射 | Set | `ws:user:{user_id}:channels` | 无 | 用户订阅的频道 |
| 任务队列 | List | `task:queue:{type}` | 无 | Agent待处理任务列表 |
| 策略下发队列 | List | `task:policy_deploy` | 无 | 策略下发任务 |
| 速率限制 | String | `ratelimit:{ip}:{endpoint}` | 60s | 接口调用频率控制 |
| 分布式锁 | String | `lock:{resource}` | 10s | 分布式锁 |
| 会话存储 | String | `session:{session_id}` | 3600s | Web会话数据 |
| AI回答缓存 | String | `ai:cache:{hash(question)}` | 3600s | AI查询缓存 |
| 告警去重 | Set | `alert:dedup:{alert_type}:{date}` | 86400s | 防止重复告警 |
| 配置缓存 | Hash | `config:agent:{agent_id}` | 300s | Agent配置缓存 |
| 全局计数器 | String | `counter:alert_seq` | 无 | 告警序号生成 |
| 心跳写入缓冲 | Stream | `stream:heartbeat:raw` | 7d(消息保留) | 缓冲写入DB |

### 8.2 详细设计

#### 8.2.1 Token缓存

```redis
# 存储JWT Token白名单
SET token:{jti} '{"user_id":"...","username":"admin","roles":["admin"],"exp":1234567890}' EX 3600

# 刷新Token
SET refresh:{jti} '{"user_id":"...","token_id":"..."}' EX 86400

# Token黑名单（退出登录时使用）
SET token:blacklist:{jti} '1' EX {剩余过期时间}
```

#### 8.2.2 Agent在线状态管理

```redis
# Agent在线状态 Hash — 整个集群共享的实时状态
HSET agent:status kylin-node-01 '{"status":"online","last_hb":"2026-06-23T20:00:00Z","version":"3.2.0","ip":"10.0.1.1"}'
HSET agent:status kylin-node-02 '{"status":"offline","last_hb":"2026-06-23T19:55:00Z","version":"3.1.9","ip":"10.0.1.2"}'

# 获取所有在线Agent
SMEMBERS agents:online

# 获取单个Agent状态
HGET agent:status kylin-node-01

# 心跳时间戳（用于快速检测超时）
HSET agent:heartbeat kylin-node-01 "2026-06-23T20:00:00Z"

# 心跳间隔
SET agent:hb_interval:kylin-node-01 10 EX 3600
```

**离线检测逻辑（后台定时任务）**:
```python
# 每60秒执行一次
async def check_offline_agents():
    now = datetime.utcnow()
    threshold = now - timedelta(seconds=30)  # 30秒无心跳视为离线
    
    async for agent_id in redis.hscan_iter('agent:heartbeat'):
        last_hb = await redis.hget('agent:heartbeat', agent_id)
        if last_hb and last_hb < threshold.isoformat():
            # 标记离线
            old_status = await redis.hget('agent:status', agent_id)
            await redis.hset('agent:status', agent_id, {...离线状态...})
            await redis.srem('agents:online', agent_id)
            # 广播状态变更
            await redis.publish('ws:broadcast', json.dumps({
                'type': 'agent.status',
                'data': {'agent_id': agent_id, 'old_status': 'online', 'new_status': 'offline'}
            }))
```

#### 8.2.3 WebSocket频道管理

```redis
# 连接注册
HSET ws:connections conn-uuid-1 '{"user_id":"...","username":"admin","roles":["admin"],"connected_at":"..."}'

# 频道订阅
# 用户订阅频道时：
SADD ws:channel:alerts:new conn-uuid-1
SADD ws:channel:agents:status conn-uuid-1
SADD ws:user:user-001:channels alerts:new
SADD ws:user:user-001:channels agents:status

# 取消订阅时：
SREM ws:channel:alerts:new conn-uuid-1
SREM ws:user:user-001:channels alerts:new

# 断开连接时清理：
DEL ws:user:user-001:channels
HDEL ws:connections conn-uuid-1
# 并从所有频道Set中移除
```

#### 8.2.4 Redis Pub/Sub 频道设计

| 频道名称 | 用途 | 消费者 |
|---------|------|--------|
| `ws:broadcast:alert:new` | 新告警广播 | 所有WebSocket节点 |
| `ws:broadcast:alert:update` | 告警状态变更 | 所有WebSocket节点 |
| `ws:broadcast:agent:status` | Agent状态变更 | 所有WebSocket节点 |
| `ws:broadcast:policy:deploy` | 策略下发通知 | 所有WebSocket节点 |
| `ws:broadcast:system:announce` | 系统广播 | 所有WebSocket节点 |
| `task:heartbeat:process` | 心跳处理任务 | 工作节点 |
| `task:alert:correlate` | 告警关联分析 | 工作节点 |
| `task:policy:deploy` | 策略下发执行 | 工作节点 |

#### 8.2.5 心跳流式写入（Redis Stream）

```redis
# Producer（Agent心跳入口API）
XADD stream:heartbeat:raw MAXLEN ~ 500000 * \
    agent_id kylin-node-01 \
    payload '{...原始JSON...}' \
    received_at "2026-06-23T20:00:00Z"

# Consumer Group（批量写入DB的后台任务）
XGROUP CREATE stream:heartbeat:raw heartbeat_writers $ MKSTREAM

# 消费者读取（每次批量读取100条）
XREADGROUP GROUP heartbeat_writers writer-1 COUNT 100 BLOCK 2000 \
    STREAMS stream:heartbeat:raw >

# 写入DB后确认
XACK stream:heartbeat:raw heartbeat_writers message-id-1
```

#### 8.2.6 任务队列

```redis
# Agent升级任务
LPUSH task:queue:agent_upgrade '{"task_id":"upg-001","agent_id":"kylin-node-01","version":"3.2.1"}'

# 策略下发任务
LPUSH task:queue:policy_deploy '{"task_id":"dep-001","policy_id":"policy-001","agent_ids":["node-01","node-02"]}'

# 工作节点轮询
BRPOP task:queue:agent_upgrade task:queue:policy_deploy 0
```

#### 8.2.7 速率限制

```redis
# 基于滑动窗口的速率限制
# Lua脚本在Redis中原子执行
# Key: ratelimit:{ip}:{endpoint}:{window_start}
# 每60秒一个窗口

# 例如：限制 /api/v1/auth/login 每个IP每分钟5次
INCR ratelimit:192.168.1.1:auth:login:1624468800
EXPIRE ratelimit:192.168.1.1:auth:login:1624468800 60

# 更精确的滑动窗口（使用Sorted Set）
ZADD ratelimit:ip:192.168.1.1:auth:login 1624468800 1624468800
ZREMRANGEBYSCORE ratelimit:ip:192.168.1.1:auth:login 0 1624468740
ZCARD ratelimit:ip:192.168.1.1:auth:login  # 返回窗口内请求数
EXPIRE ratelimit:ip:192.168.1.1:auth:login 60
```

#### 8.2.8 分布式锁

```redis
# 使用SET NX EX 实现分布式锁
# 用于以下场景：
# 1. 告警关联聚合时的并发控制
# 2. Agent状态变更的互斥操作
# 3. 策略下发时的串行化

SET lock:alert:correlate:alert-001 {random_value} NX EX 10

# Lua脚本释放锁
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

#### 8.2.9 缓存策略

| 数据 | Key模式 | TTL | 更新策略 |
|------|--------|-----|---------|
| 用户权限缓存 | `cache:user:{user_id}:perms` | 300s | 权限变更时主动失效 |
| Agent配置 | `cache:agent:{agent_id}:config` | 60s | 策略下发时主动更新 |
| 告警统计 | `cache:alert:stats:{time_range}` | 60s | 新告警产生时失效 |
| MITRE矩阵 | `cache:mitre:matrix` | 3600s | 手动刷新 |
| Agent列表 | `cache:agents:list:{page}:{filter_hash}` | 30s | 状态变更时失效 |
| 系统设置 | `cache:system:settings` | 600s | 设置变更时更新 |

---

## 附录

### A. 关键性能指标目标

| 指标 | 目标 | 测量方式 |
|------|------|---------|
| API P95 响应时间 | < 200ms | APM监控 |
| 数据库查询P95 | < 50ms | pg_stat_statements |
| 告警写入吞吐 | > 500 TPS | 压测 |
| 心跳处理吞吐 | > 5000 TPS | 压测（批量写入） |
| WebSocket消息延迟 | < 100ms | 端到端测量 |
| 告警列表查询（100万条） | < 500ms | 性能测试 |
| 并发在线用户 | 50 | 负载测试 |
| 同时WebSocket连接 | 500 | 负载测试 |

### B. 安全设计要点

1. **JWT Token**：RS256签名（非对称密钥），Access Token 1小时，Refresh Token 24小时
2. **密码策略**：最少12位，含大小写字母+数字+特殊字符，bcrypt加密（rounds=12）
3. **登录锁定**：连续5次失败锁定15分钟
4. **API速率限制**：登录接口每分钟5次/IP，其他接口每分钟60次/IP
5. **Agent通信**：独立Token鉴权，双向TLS
6. **SQL注入防护**：全程参数化查询，ORM禁止拼接SQL
7. **XSS防护**：所有用户输入输出进行HTML转义
8. **审计完整性**：审计日志只追加不修改，使用append-only表

### C. 高可用设计

- **FastAPI**：多实例部署，Nginx负载均衡
- **PostgreSQL**：主从复制 + Patroni自动故障切换
- **Redis**：Redis Sentinel哨兵模式或Redis Cluster
- **WebSocket**：Redis Pub/Sub实现跨实例消息广播
- **无状态设计**：所有会话状态存储在Redis，应用层无状态