/**
 * 麒麟OS 安全运维 - Preload Script
 * 安全地暴露有限的 API 给渲染进程
 */

const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('electronAPI', {
  // Platform info
  platform: process.platform,
  versions: {
    node: process.versions.node,
    electron: process.versions.electron,
    chrome: process.versions.chrome,
  },

  // App info
  isDesktop: true,
  appName: '麒麟OS安全运维',

  // IPC helpers
  getBackendUrl: () => 'http://127.0.0.1:8001',

  // 订阅主进程事件（如后端启动超时降级）
  onBackendTimeout: (callback) => {
    ipcRenderer.on('backend-timeout', (_event, ...args) => callback(...args))
  },
})
