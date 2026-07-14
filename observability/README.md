# 麒麟OS安全智能运维Agent —— 可观测性配套

本目录提供三层可观测能力，覆盖你提出的「日志落盘 / 单机自检 / 接 Prometheus」三项需求。

> 版本：v2.4.6 ｜ 可观测性端点：`/health` 与 `/metrics` **不受 `backend.debug` 影响，始终可用**；`/docs`、`/redoc`、`/api/v1/openapi.json` 仅在 `backend.debug=true` 时挂载（生产默认 `false`，返回 404，详见交付说明「API 文档」节）。

## 1. 日志落盘（已内置，无需额外配置）

`build/main.js` 已改造，运行时会把日志按天写入安装目录下的 `resources/logs/`：

| 文件 | 内容 |
|------|------|
| `resources/logs/app-YYYY-MM-DD.log` | Electron 主进程（Desktop 侧）日志，含崩溃兜底 `uncaughtException` / `unhandledRejection` |
| `resources/logs/backend-YYYY-MM-DD.log` | 后端 `backend.exe` 的 stdout/stderr 输出（Uvicorn 启动、业务报错等） |

- 日志目录在进程启动时自动创建，不会写入 `app.asar`（只读包）内。
- 按日期滚动，跨天自动新建文件。
- 每次写入均为追加单行，不会因日志异常导致程序崩溃。

## 2. 单机状态自检脚本

`check-agent-status.ps1` —— 纯 Windows PowerShell 5.1+，无第三方依赖。

```powershell
# 在 Agent 安装主机上直接运行
.\check-agent-status.ps1
# 或指定端口
.\check-agent-status.ps1 -Port 8000
```

输出三段状态：
1. **进程**：`backend.exe` 与 `麒麟OS安全智能运维Agent.exe` 是否存活
2. **端口**：后端监听端口（默认 8000）是否可连通
3. **健康检查**：`GET /health` 与 `GET /metrics` 是否可达并正常

退出码 `0` 表示健康，`1` 表示异常（可在计划任务/监控里据此告警）。

## 3. Prometheus + Grafana

- `prometheus.yml`：抓取配置，`job=kylin-agent`，目标 `127.0.0.1:8000/metrics`，间隔 15s。
  远程部署时把 `targets` 的 IP 改为对应主机即可。
- `kylin-agent-dashboard.json`：Grafana 看板，含运行时长 / 健康状态 / 请求速率 / 累计请求 / 构建信息 5 个面板。

### 部署步骤

```bash
# 1) 启动 Prometheus（指向本目录配置）
prometheus --config.file=prometheus.yml

# 2) 启动 Grafana，导入看板
#    Grafana -> Connections -> Data sources -> 添加 Prometheus（URL: http://localhost:9090）
#    Dashboards -> Import -> 上传 kylin-agent-dashboard.json
#    导入时把 DS_PROMETHEUS 变量绑定到上面的 Prometheus 数据源
```

### 暴露的指标

| 指标 | 类型 | 含义 |
|------|------|------|
| `kylin_agent_info` | gauge | 构建静态信息（version / service），值恒为 1 |
| `kylin_agent_uptime_seconds` | gauge | 进程已运行秒数 |
| `kylin_agent_requests_total` | counter | 后端累计处理的 HTTP 请求数（不含 `/metrics` 自身抓取） |
| `kylin_agent_health_status` | gauge | `/health` 正常为 1，异常为 0 |

> 注：`/metrics` 为纯标准库 text 格式实现，未引入任何新 Python 依赖，避免 PyInstaller 冻结风险；多机场景建议在反向代理层加 Basic Auth 或局域网白名单保护该端点。
>
> **与 `/docs` 的区别**：`/metrics` 与 `/health` 在任何模式下都暴露（即使 `backend.debug=false`），Prometheus 抓取无需开启 DEBUG；而 Swagger UI（`/docs`）、ReDoc（`/redoc`）、OpenAPI schema（`/api/v1/openapi.json`）在 v2.4.6 起被 `DEBUG` 门控，生产态不挂载。因此**监控采集和 API 文档预览是两个独立的开关**，不要为看文档而长期开启 DEBUG。
