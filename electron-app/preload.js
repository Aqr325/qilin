/**
 * 麒麟OS 安全运维 - Preload Script
 * 
 * 在渲染进程和主进程之间建立安全的 IPC 桥接。
 * 仅暴露最小必需的 API，遵守 contextIsolation 安全策略。
 *
 * IPC Channels (renderer → main):
 *   window-minimize     - 最小化窗口
 *   window-maximize     - 最大化/还原切换
 *   window-close        - 关闭窗口（隐藏到托盘）
 *   backend-status      - 获取后端健康状态
 *   open-file-dialog    - 打开文件选择对话框
 *   show-notification   - 显示系统通知
 *   check-for-updates   - 手动触发更新检查
 *   get-update-status   - 获取当前更新状态
 *   install-update      - 重启安装已下载的更新
 *
 * IPC Channels (main → renderer):
 *   backend-connected      - 后端连接成功
 *   backend-disconnected   - 后端断开连接
 *   backend-error          - 后端错误
 *   app-version            - 应用版本号
 *   update-available       - 有新版本可用
 *   update-not-available   - 已是最新版本
 *   update-download-progress - 下载进度
 *   update-downloaded      - 更新已下载
 *   update-status          - 更新状态同步
 */

const { contextBridge, ipcRenderer } = require('electron')

// ─────────────────────────────────────────
// Backend URL helper
// NOTE: In preload, we cannot read config.json directly (no fs).
// The renderer should use getBackendUrl via a dedicated IPC if
// the port needs to be dynamic. For now, default to 8000 but
// main.js respects config.json.
// ─────────────────────────────────────────
function getBackendPort() {
  try {
    // Try to read from localStorage (set by renderer on boot)
    const cached = localStorage.getItem('backend_port')
    return cached ? parseInt(cached, 10) : 8000
  } catch {
    return 8000
  }
}

// ─────────────────────────────────────────
// 安全暴露给渲染进程的 API
// ─────────────────────────────────────────
contextBridge.exposeInMainWorld('electronAPI', {
  // ─── Platform / App Info ───
  platform: process.platform,
  isDesktop: true,
  appName: '麒麟OS安全运维',

  versions: Object.freeze({
    node: process.versions.node,
    electron: process.versions.electron,
    chrome: process.versions.chrome,
  }),

  // ─── Backend Connection ───
  getBackendUrl: () => `http://127.0.0.1:${getBackendPort()}`,
  getBackendPort: () => getBackendPort(),

  // 主动查询后端健康状态
  checkBackendHealth: async () => {
    try {
      const port = getBackendPort()
      const res = await ipcRenderer.invoke('backend-status')
      return { connected: res?.connected ?? false, port, timestamp: Date.now() }
    } catch {
      return { connected: false, port: getBackendPort(), timestamp: Date.now() }
    }
  },

  // ─── Window Controls ───
  minimizeWindow: () => ipcRenderer.send('window-minimize'),
  maximizeWindow: () => ipcRenderer.send('window-maximize'),
  closeWindow: () => ipcRenderer.send('window-close'),

  // ─── File Dialog ───
  openFileDialog: async (options) => {
    try {
      return await ipcRenderer.invoke('open-file-dialog', options)
    } catch (err) {
      console.error('[Preload] File dialog error:', err)
      return { canceled: true, filePaths: [] }
    }
  },

  // ─── System Notification ───
  showNotification: (title, body) => {
    ipcRenderer.send('show-notification', { title, body })
  },

  // ─── Event Subscriptions (安全的事件监听) ───
  // 监听后端连接状态变化
  onBackendConnected: (callback) => {
    const handler = (_event, data) => callback(data)
    ipcRenderer.on('backend-connected', handler)
    // 返回清理函数
    return () => ipcRenderer.removeListener('backend-connected', handler)
  },

  onBackendDisconnected: (callback) => {
    const handler = (_event, data) => callback(data)
    ipcRenderer.on('backend-disconnected', handler)
    return () => ipcRenderer.removeListener('backend-disconnected', handler)
  },

  onBackendError: (callback) => {
    const handler = (_event, data) => callback(data)
    ipcRenderer.on('backend-error', handler)
    return () => ipcRenderer.removeListener('backend-error', handler)
  },

  // 监听窗口状态变化（最大化/还原）
  onWindowMaximizedChange: (callback) => {
    const handler = (_event, isMaximized) => callback(isMaximized)
    ipcRenderer.on('window-maximized-change', handler)
    return () => ipcRenderer.removeListener('window-maximized-change', handler)
  },

  // 监听应用版本更新
  onAppVersion: (callback) => {
    const handler = (_event, version) => callback(version)
    ipcRenderer.on('app-version', handler)
    return () => ipcRenderer.removeListener('app-version', handler)
  },

  // ─── Auto Update API ───
  getAppVersion: async () => {
    try { return await ipcRenderer.invoke('get-app-version') }
    catch { return 'unknown' }
  },

  checkForUpdates: async () => {
    try { return await ipcRenderer.invoke('check-for-updates') }
    catch { return { error: true } }
  },

  getUpdateStatus: async () => {
    try { return await ipcRenderer.invoke('get-update-status') }
    catch { return { checking: false, available: false } }
  },

  installUpdate: () => {
    ipcRenderer.send('install-update')
  },

  // 监听更新事件
  onUpdateAvailable: (callback) => {
    const handler = (_event, info) => callback(info)
    ipcRenderer.on('update-available', handler)
    return () => ipcRenderer.removeListener('update-available', handler)
  },

  onUpdateNotAvailable: (callback) => {
    const handler = (_event, info) => callback(info)
    ipcRenderer.on('update-not-available', handler)
    return () => ipcRenderer.removeListener('update-not-available', handler)
  },

  onUpdateDownloadProgress: (callback) => {
    const handler = (_event, progress) => callback(progress)
    ipcRenderer.on('update-download-progress', handler)
    return () => ipcRenderer.removeListener('update-download-progress', handler)
  },

  onUpdateDownloaded: (callback) => {
    const handler = (_event, info) => callback(info)
    ipcRenderer.on('update-downloaded', handler)
    return () => ipcRenderer.removeListener('update-downloaded', handler)
  },

  onUpdateStatus: (callback) => {
    const handler = (_event, status) => callback(status)
    ipcRenderer.on('update-status', handler)
    return () => ipcRenderer.removeListener('update-status', handler)
  },
})
