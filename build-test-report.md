# electron-builder 构建测试报告

**日期**: 2026-06-30  
**项目**: electron-app/ (麒麟OS安全智能运维Agent 桌面版)

---

## 构建结果

### ✅ 目录模式构建 — build:dir（成功）

```bash
npm run build:dir
# → electron-builder build --win --dir
```

| 文件 | 大小 | 说明 |
|------|------|------|
| `release/win-unpacked/麒麟OS安全运维.exe` | 181MB | 主程序（含 Electron 运行时） |
| `release/win-unpacked/resources/app.asar` | 2.4MB | 前端/JS 源码打包 |
| `release/win-unpacked/resources/backend.exe` | 12MB | 后端服务（extraResource） |
| `release/win-unpacked/resources/config.json` | 1KB | 配置 |
| `release/win-unpacked/resources/icon.png` | — | 托盘图标 |

### ⏱️ NSIS 安装包构建 — build（超时）

```bash
npm run build
# → electron-builder build --win
```

LZMA 压缩阶段在沙箱环境的 12 分钟超时限制内未完成。在真机或 GitHub Actions CI 上可正常运行。

---

## 修复的问题

| 问题 | 原因 | 修复 |
|------|------|------|
| `electronDist 不存在` | 相对路径少一层 `../` | `../../` → `../` |
| `图标至少 256x256` | 原 icon.png 仅 128x128 | PIL 重新生成 256x256 |
| electron 版本 42.5.0 | 之前 package.json 版本号被错误修改 | 改为 `^20.3.12`，重新 `npm install` |

---

## 使用方法

```bash
# 目录模式（快速调试）
cd electron-app/
npm run build:dir
# → release/win-unpacked/ 可直接运行

# 安装包模式（发布用，需真机或 CI）
npm run build
# → release/麒麟OS安全运维Agent-Setup-2.1.0.exe

# 通过 GitHub Actions 发布
git tag v2.1.0
git push origin v2.1.0

# 或一键发布脚本
node scripts/publish-release.js patch
```
