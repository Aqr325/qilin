# 麒麟OS 安全智能运维 Agent - 桌面安装包项目

本项目基于 `electron-builder` + `electron-updater`，将麒麟OS Agent 打包为 Windows NSIS 安装包，支持自动更新。

## 目录结构

```
electron-app/
├── main.js              # Electron 主进程（含 autoUpdater）
├── preload.js           # 安全桥接脚本
├── frontend/            # Vue SPA 前端资源
├── package.json         # 项目配置 + electron-builder 配置
├── build.bat            # 构建脚本
├── scripts/
│   └── publish-release.js  # 一键发布脚本
├── .github/workflows/  # GitHub Actions 自动发布
├── build/
│   └── icon.png         # 安装包图标
└── release/             # 构建输出目录
```

## 构建安装包

### 快速构建（目录模式，用于测试）

```bash
build.bat
# 选 [1] 目录模式
# 输出: release/win-unpacked/
```

### 构建 NSIS 安装包

```bash
build.bat
# 选 [2] 安装包模式
# 输出: release/麒麟OS安全运维Agent-Setup-2.1.0.exe
#      release/latest.yml
```

### 发布到 GitHub Releases

```bash
build.bat
# 选 [3] 发布模式
# 构建后自动上传到 GitHub Releases
```

## 自动更新机制

使用 `electron-updater` 连接 GitHub Releases：

1. **启动检查**：应用启动后 5 秒自动检查更新
2. **提示下载**：发现新版本时通知用户，自动后台下载
3. **静默下载**：下载进度实时反馈
4. **重启安装**：下载完成后用户选择"重启安装"
5. **退出安装**：app.quit() 时自动触发安装

### 更新流程示例

```
v2.0.0 用户启动应用
  → 自动检查 GitHub Releases 最新版
  → 发现 v2.1.0 → 提示用户
  → 用户确认 → 后台下载
  → 下载完成 → 提示重启
  → 重启 → 安装 v2.1.0 → 应用启动
```

## 发布新版本

### 方法 1：GitHub Actions（推荐）

1. 推送新标签即可自动触发 CI 构建发布：

```bash
git tag v2.1.0
git push origin v2.1.0
```

GitHub Actions 会自动构建并上传到 Releases。

### 方法 2：自动发布脚本

```bash
node scripts/publish-release.js patch   # v2.1.0 → v2.1.1
node scripts/publish-release.js minor   # v2.1.0 → v2.2.0
node scripts/publish-release.js major   # v2.1.0 → v3.0.0
```

### 方法 3：手动发布

```bash
npm run build
# 上传 release/ 目录下的产物到 GitHub Releases
```

## 前置条件

- Node.js 20+
- 如需自动发布: GitHub CLI (`gh`) 已登录
- 如需 CI: GitHub 仓库已配置 Actions 权限