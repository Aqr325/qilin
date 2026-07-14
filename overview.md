# 麒麟OS安全智能运维Agent — 最终交付报告

> 更新于 2026-07-07（含 v2.1.2：前端数据持久化修复与 AgentTask 真实化）

> ⚠️ **安全模型已更新（v2.4.5）**：已彻底移除所有静态/共享口令。现每次安装首次启动随机生成 4 个账号口令并写入 `data/bootstrap.txt`（0600），且强制首次登录改密；交付包不再预置 `kylin_secops.db`、不再随附任何已知口令。下文 2026-07-07 段落为历史记录，其中提到的静态口令均已废弃，请勿沿用。

## 一、项目状态

功能开发 → 安全审计 → P0 漏洞修复 → 回归测试 → 桌面程序打包 → 登录可用性修复，全部完成，交付物就绪。

## 二、安全审计与 P0 修复（2026-07-04）

- **审计**：代码审查（33 问题 / 7 P0）、数据库审计、安全审计（20 发现，综合高风险）
- **P0 修复清单**

| # | 漏洞 | 修复位置 |
|---|------|----------|
| P0-01 | Agent Token 绕过 | `api/deps.py` 新增 `validate_agent_token` 参数化查询，无效 token 返回 401 |
| P0-02 | WebSocket 认证缺失 | `api/v1/websocket.py` 新增令牌校验 + IDOR 防护，无 token 以 1008 拒绝 |
| P0-03 | 系统管理端点越权 | `api/v1/system.py` 18 个端点全部加 `require_permission` |
| P0-04 | 硬编码密码 | `core/permissions.py` 改为环境变量/随机 24 位，新增 `.env.example` |
| P0-05 | 审计/登录日志主键类型 | 迁移 `0005`：BigInteger → UUID |
| P0-06 | Agent `credential` 字段缺失回填 | `models/agent.py` 加字段 + `agent_service.py` 生成 + 迁移 `0006` |

- **回归测试**：11 项后端测试全部 PASS
- **打包**：前端 Vite 构建 + 后端 PyInstaller 编译 + Electron 打包，输出至 `麒麟OS安全运维_桌面程序/`

## 三、登录可用性修复（2026-07-07）

**问题**：7/4 去掉硬编码密码后，桌面版首次启动、库为空时种子密码为**静默随机串且不可见**，用户无法登录。

**根因**：`desktop/main.js` 的 `startBackend()` 仅注入 `PYTHONUNBUFFERED`，未注入 `KYLIN_SEED_PASSWORD`，全仓也无人设置该变量。

**修复**：
1. 桌面版 `config.json` 增加 `seed_password: "（历史静态测试口令，v2.4.5 起已废弃）"`（交付目录 / 打包源 / 源码副本三处同步）
2. `main.js` 启动时读取 config 的 `seed_password`，作为 `KYLIN_SEED_PASSWORD` 注入后端进程环境变量
3. 重新打包桌面版（`electron-builder --dir`，签名跳过），同步交付目录

**验证（2026-07-07 登录冒烟测试）**：用全新空库 + `KYLIN_SEED_PASSWORD=（历史静态测试口令，v2.4.5 起已废弃）` 启动 `backend.exe`，`GET /health` 返回 200；`POST /api/v1/auth/login` 用 `admin / （历史静态测试口令，v2.4.5 起已废弃）` 返回 200 及 JWT，`admin / WrongPass@123` 返回 401（拒绝错误密码）；数据库种子化出 4 个用户。证明「config.seed_password → 注入 KYLIN_SEED_PASSWORD → 后端按已知密码种子化」链路真实生效。

**交付库修正**：原交付 `kylin_secops.db` 是修复前的遗留半成品（仅 3 个用户、密码为不可见的随机串，导致登不进）。已替换为冒烟测试验证通过的数据库——4 个账号（补齐 viewer）、17 张表齐全、密码统一为 `（历史静态测试口令，v2.4.5 起已废弃）`。双保险：即使首次启动注入有意外，已知密码仍可用。

## 四、前端数据持久化与 AgentTask 真实化（v2.1.2，2026-07-07）

**问题**：前端修改的数据（如告警状态、系统设置）切换界面后恢复原样。根因：全局 Pinia `alerts` store 被后台 30s 轮询 / 看板挂载时的重拉覆盖本地编辑。

**修复**：
1. 前端 `stores/alerts.ts` 新增 `dirtyAlerts`(ref Set)、`localStatus`(Map)、`setAlertStatus(id, status, confirmed)`、`applyLocalOverrides()`；`fetchAlerts` 在赋值后重新套用未确认编辑，防止轮询覆盖。
2. `AlertsView.vue` 批量/单条状态编辑走 `alertsStore.setAlertStatus`；`SystemView.vue` 保存失败改 toast 反馈；`ProfileView.vue` 保存成功同步 `authStore.user.phone`。
3. 后端新增 `AgentTask` 模型（含 `0007_add_agent_tasks` 迁移），`agent_service` 的升级/重启由桩改真实落库 `AgentTask`；`policy_service` 策略下发真实写入 `PolicyTarget` 并提升 `Agent.config_version`；`system_service.create_user` 补 `db.refresh` 返回正确角色。

**构建与交付**：重新编译 `backend.exe`（修复 `desktop-build-env` 缺 sqlalchemy 等依赖，产物 27.9MB），刷新交付目录与发布包 `麒麟OS安全运维_桌面程序-v2.1.2.zip`（142.6MB，103 文件）。commit `38df886`，tag `v2.1.2`。

## 五、交付物

| 项目 | 路径 |
|------|------|
| 桌面程序目录 | `麒麟OS安全运维_桌面程序/` |
| 主程序 | `麒麟OS安全运维_桌面程序/麒麟OS安全运维.exe` |
| 后端 | `resources/backend.exe` |
| 前端 | `resources/frontend/` |
| 配置 | `resources/config.json`（v2.4.5 起不再含 `seed_password`，口令随机生成） |
| 数据库 | 首次启动自动建库于 `resources/kylin_secops.db`（4 个账号，口令随机写入 `data/bootstrap.txt`） |

## 六、默认登录凭证（v2.4.5 起：随机口令 + 强制改密）

首次启动自动建库并随机生成 4 个账号口令，写入本地 `data/bootstrap.txt`（权限 0600，仅本机可读）。**所有账号均标记 `must_change_password`，首次登录必须修改口令后才能继续使用。**

| 角色 | 用户名 | 初始口令获取 |
|------|--------|--------------|
| 管理员 | admin | 见 `data/bootstrap.txt` |
| 运维 | operator | 见 `data/bootstrap.txt` |
| 审计 | auditor | 见 `data/bootstrap.txt` |
| 查看 | viewer | 见 `data/bootstrap.txt` |

> 初始口令为每次安装随机生成，**不会跨安装相同**，请妥善保管 `data/bootstrap.txt` 并在首次登录后立即修改。

## 七、运行方式

- 双击 `麒麟OS安全运维_桌面程序/麒麟OS安全运维.exe`，或运行项目根目录 `启动桌面版.bat`
- 后端自动启动于 `127.0.0.1:8001`，前端在 Electron 窗口内渲染

## 八、技术栈

FastAPI + SQLAlchemy(async) + Alembic + SQLite ／ Vue 3 + TypeScript + Vite ／ Electron + PyInstaller
