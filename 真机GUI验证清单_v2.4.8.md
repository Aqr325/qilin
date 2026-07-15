# 真机 GUI 验证清单（v2.4.8）

> 说明：沙箱环境无显示器，GUI 窗口交互无法在此自动验证。以下为你在**真机双击 exe 后**的逐步核对清单，覆盖"按 id 编辑 / 删除配置"全链路 + Electron 退出清理。所有接口断言已在沙箱用真实 `backend.exe`（含本次修复）跑通；本清单负责把同一结论在真实窗口里再坐实一遍。

---

## 0. 前置

- 双击对应 exe：
  - 主程序（端口 **8001**）：`麒麟OS安全运维_桌面程序/麒麟OS安全运维.exe`
  - Agent（端口 **8000**）：`麒麟OS安全智能运维Agent_桌面版交付/麒麟OS安全智能运维Agent.exe`
- 首次启动：`backend.exe` 在 `resources/` 下生成 per-install `secret.key`（0600）与 `kylin_secops.db`；登录账号 `admin` / 密码 `KylinSecOps@2026`。
- ⚠️ 交付 / 同步**不要携带 `secret.key`**（否则所有安装共用一把 JWT 密钥）。本版已确保四处交付目录不含 `secret.key`。

---

## 1. 强制改密首登（H1 修复验证）

| 步骤 | 操作 | 预期 |
|---|---|---|
| 1.1 | 用 `admin` / `KylinSecOps@2026` 登录 | 登录成功，但系统检测到 `must_change_password=True`，自动弹出"修改密码"框 |
| 1.2 | 不改密码，直接去"模型配置"页点保存 | 被拦截（**403**）并提示先改密——这是预期行为，证明 H1 强制改密生效 |
| 1.3 | 在弹窗里把密码改成新密码（如 `NewPass@2026`）并提交 | 改密成功，自动重登录 |
| 1.4 | 重登录后再次进入"模型配置" | 业务接口不再 403，可正常读写 |

---

## 2. 按 id 编辑 / 删除配置（UUID 修复验证）

| 步骤 | 操作 | 预期 |
|---|---|---|
| 2.1 | 模型配置列表 → 新建（填 名称 / provider / model 等必填）→ 保存 | 200，列表出现新条目，带合法 UUID |
| 2.2 | 点该条目"编辑" → 改某个字段 → 保存 | 200（`PUT /api/v1/ai/model-configs/{id}`），改动生效 |
| 2.3 | 点"设为默认" | 200（`PUT /api/v1/ai/model-configs/{id}/set-default`） |
| 2.4 | 复制该条目 id，在接口工具 / 浏览器 `GET /api/v1/ai/model-configs/{id}` | 200，返回该配置 |
| 2.5 | 点"删除" | 200（`DELETE /api/v1/ai/model-configs/{id}`），条目从列表消失 |
| 2.6 | 再次 `GET` 已删除的 id | **404**（不再是 500）——证明 `uuid.UUID()` 二次构造根因已根除 |
| 2.7 | 用肉眼明显非法的 id（如 `not-a-uuid`）`GET` | **404 或 422**（非 500）。`model-configs` 路径参数声明为 UUID 类型，非法字符串在 FastAPI 校验层即被拦成 422；二者都是 4xx 客户端错误，证明不再触发 500 |

> **判定标准**：2.2 / 2.3 / 2.5 全部 200，2.6 返回 404、2.7 返回 404/422（均非 500），即 UUID 修复在真机 GUI 上坐实生效。

---

## 3. 其他模块按 id 查询（同类隐患已统一修复）

对话 / 策略 / 告警 / 系统用户·角色 的"按 id 查询"同样修过：

- 合法 id → 200
- 非法 / 不存在 id → **404**（不再 500）

可在各模块点开详情、刷新、删除，观察浏览器 DevTools 的 Network 面板是否出现 500。

---

## 4. Electron 退出清理（本次修复验证）

| 步骤 | 操作 | 预期 |
|---|---|---|
| 4.1 | 运行中打开任务管理器，确认有 `backend.exe` 进程 | 存在（被 Electron `spawn` 为子进程） |
| 4.2 | 直接点窗口右上角 ✕ 关闭 GUI | 窗口隐藏到系统托盘（**不是退出**）——这是设计行为，`backend.exe` 仍在跑 |
| 4.3 | 右键托盘图标 → "退出" | Electron 先 `spawnSync` 同步杀掉 `backend.exe` 进程树（含 `/t`），300ms 后真正退出 |
| 4.4 | 退出后立刻看任务管理器 | `backend.exe` 与 Electron 主进程**均无残留**；`resources/` 下无 sqlite 锁文件残留 |
| 4.5（可选复验） | 退出后立刻再双击 exe 做覆盖升级式启动 | 因 `backend.exe` 已释放文件锁，启动不卡、不报"数据库被锁" |

> 若 4.4 仍看到 `backend.exe` 残留 → 说明退出清理未生效，需回查 `stopBackend()` 是否被同步调用。本版已用 `spawnSync` + `before-quit` 防竞态修好。

---

## 5. 可选：自动化冒烟脚本（HTTP 级，沙箱已跑通）

见同目录 `verify_model_config_e2e.py`：它会拉起真实 `backend.exe`（隔离临时库）→ 登录 → 改密 → 重登录 → 按 id 创建/编辑/设默认/删除（断言 200）→ 非法 id 查询（断言 404）。你在真机也可直接跑它对后端做无 GUI 的快速回归：

```bash
# 主程序（8001）
python verify_model_config_e2e.py --exe "麒麟OS安全运维_桌面程序/resources/backend.exe" --config "麒麟OS安全运维_桌面程序/resources/config.json"
# Agent（8000）
python verify_model_config_e2e.py --host 127.0.0.1:8000 --exe "麒麟OS安全智能运维Agent_桌面版交付/resources/backend.exe" --config "麒麟OS安全智能运维Agent_桌面版交付/resources/config.json"
```

---

## 附：本版修复清单（v2.4.8）

| 项 | 内容 |
|---|---|
| Electron 退出清理 | `stopBackend()` 改 `spawnSync` 同步终止进程树；`before-quit` 用 `preventDefault` + 延时 300ms 再 `app.quit()`，消除竞态，关 GUI 后不再残留 `backend.exe` |
| UUID 二次构造根因 | 全仓库统一 `uuid.UUID(X)` → `uuid.UUID(str(X))`，根除"按 id 查询/编辑/删除"的 500 |
| `startBackendInternal` 旧 typo | `desktop/main.js` 重启分支误调未定义函数，改回 `startBackend()`（主程序源码与已干净的 asar 一致） |
| 版本号 | `2.4.7` → `2.4.8`（config.py + 各处 config.json，backend.exe 已重建同步四处） |
