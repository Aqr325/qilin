/**
 * 麒麟OS 安全运维 Agent - Electron Main Process v3
 *
 * 架构:
 *   start.bat → backend.exe（无窗口服务）+ electron.exe（桌面 UI）
 *   Electron 负责窗口管理、托盘图标、自动更新、系统通知和前端文件服务
 *
 * 变更日志:
 *   v3 (2026-06-28):
 *     - 集成 electron-updater 自动更新
 *     - 新增加更新检查 IPC 通道
 *     - 启动后自动检查更新，新版本后台静默下载
 *     - 下载完成后提示用户重启安装
 *     - 托盘菜单新增更新状态显示
 *   v2 (2026-06-28):
 *     - 移除后端进程启动（由 start.bat 全权负责）
 *     - 新增 IPC 通道集群（window/file/notification/backend-status）
 *     - 后端健康状态主动轮询 + 事件通知
 *     - show-after-ready 模式防止白屏闪烁（FOUC）
 */
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, shell, Notification, ipcMain } = require('electron')
const { autoUpdater } = require('electron-updater')
const path = require('path')
const fs = require('fs')
const http = require('http')

// ════════════════════════════════════════════
// Constants
// ════════════════════════════════════════════
const APP_NAME = '麒麟OS安全运维'
const DEV_MODE = !app.isPackaged
const APP_VERSION = app.getVersion()
const FEEDBACK_EMAIL = 'kylin-secops@honor.cn'

// ─── Paths ───
function getDeliveryRoot() {
  if (DEV_MODE) {
    return path.resolve(__dirname, '..', '麒麟OS安全智能运维Agent_桌面版交付')
  }
  // In packaged app, extraResources sit next to the .exe
  return path.dirname(app.getPath('exe'))
}

function getConfigPath()    { return path.join(getDeliveryRoot(), 'config.json') }
function getIconPath()      { return path.join(getDeliveryRoot(), 'icon.png') }
function getFrontendDir()   { return DEV_MODE ? path.resolve(__dirname, 'frontend') : path.join(process.resourcesPath, 'frontend') }
function getBackendExePath() {
  // 跨平台: Windows 用 backend.exe，Linux/macOS 用 backend
  // 编译脚本会把 Linux 版二进制也复制为 backend.exe（Linux 不
  // 介意 .exe 扩展名），这里优先用平台原生名称，兼容旧包
  const base = path.join(getDeliveryRoot(), 'backend')
  const winPath = base + '.exe'
  if (process.platform === 'win32') return winPath
  // Linux: 优先用 backend（无后缀），fallback 到 backend.exe
  try {
    if (fs.existsSync(base)) return base
  } catch (_) {}
  return winPath
}

// ─── Config ───
let config = {
  backend: { host: '127.0.0.1', port: 8000 },
  desktop: { version: APP_VERSION, backend_ready_timeout_seconds: 60, health_check_interval_seconds: 5 },
  update: { provider: 'github', owner: 'HONOR', repo: 'kylin-secops-desktop', releaseType: 'release' },
}
function loadConfig() {
  try {
    const raw = fs.readFileSync(getConfigPath(), 'utf-8')
    const parsed = JSON.parse(raw)
    if (parsed.backend) config.backend = { ...config.backend, ...parsed.backend }
    if (parsed.desktop) config.desktop = { ...config.desktop, ...parsed.desktop }
    if (parsed.update) config.update = { ...config.update, ...parsed.update }
  } catch (err) {
    console.warn(`[Desktop] Cannot read config.json, using defaults: ${err.message}`)
  }
}
loadConfig()

const BACKEND_PORT = config.backend.port || 8000
const BACKEND_URL = `http://${config.backend.host || '127.0.0.1'}:${BACKEND_PORT}`

// ════════════════════════════════════════════
// State
// ════════════════════════════════════════════
let mainWindow = null
let tray = null
let isQuitting = false
let healthInterval = null
let backendConnected = false

// ─── Update State ───
let updateState = {
  checking: false,
  available: false,
  downloading: false,
  progress: 0,
  downloaded: false,
  version: '',
  error: null,
}

// ════════════════════════════════════════════
// Auto Updater
// ════════════════════════════════════════════

function setupAutoUpdater() {
  // ─── Dev mode: never check ───
  if (DEV_MODE) {
    console.log('[Updater] Dev mode, auto-update disabled')
    return
  }

  // Configure updater with repo settings from config
  autoUpdater.setFeedURL({
    provider: config.update?.provider || 'github',
    owner: config.update?.owner || 'HONOR',
    repo: config.update?.repo || 'kylin-secops-desktop',
    releaseType: config.update?.releaseType || 'release',
  })

  autoUpdater.autoDownload = false       // 只检查，不自动下载
  autoUpdater.autoInstallOnAppQuit = true // 退出时安装已下载的更新
  autoUpdater.allowPrerelease = false

  // ─── Event Handlers ───
  autoUpdater.on('checking-for-update', () => {
    console.log('[Updater] Checking for updates...')
    updateState = { ...updateState, checking: true, error: null }
    sendUpdateStatus()
  })

  autoUpdater.on('update-available', (info) => {
    console.log(`[Updater] Update available: v${info.version}`)
    updateState = { ...updateState, checking: false, available: true, version: info.version }
    sendUpdateStatus()
    updateTrayMenu()

    // 通知用户有新版本可用
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-available', {
        version: info.version,
        releaseDate: info.releaseDate,
        releaseNotes: info.releaseNotes,
      })
    }

    // 自动开始下载
    autoUpdater.downloadUpdate()
  })

  autoUpdater.on('update-not-available', (info) => {
    console.log(`[Updater] No update available (current: ${APP_VERSION})`)
    updateState = { ...updateState, checking: false, available: false }
    sendUpdateStatus()
    updateTrayMenu()

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-not-available', { version: APP_VERSION })
    }
  })

  autoUpdater.on('download-progress', (progressObj) => {
    const percent = Math.round(progressObj.percent)
    updateState = { ...updateState, downloading: true, progress: percent }
    sendUpdateStatus()

    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-download-progress', {
        percent,
        bytesPerSecond: progressObj.bytesPerSecond,
        total: progressObj.total,
        transferred: progressObj.transferred,
      })
    }
  })

  autoUpdater.on('update-downloaded', (info) => {
    console.log(`[Updater] Update downloaded: v${info.version}`)
    updateState = { ...updateState, downloading: false, downloaded: true, progress: 100 }
    sendUpdateStatus()
    updateTrayMenu()

    // 通知用户
    if (mainWindow && !mainWindow.isDestroyed()) {
      mainWindow.webContents.send('update-downloaded', { version: info.version })
    }

    // 弹系统通知
    try {
      const notif = new Notification({
        title: `${APP_NAME} - 更新已就绪`,
        body: `v${info.version} 已下载完成。重启应用以安装更新。`,
        icon: getIconPath(),
      })
      notif.on('click', () => {
        if (mainWindow) { mainWindow.show(); mainWindow.focus() }
      })
      notif.show()
    } catch (_) {}
  })

  autoUpdater.on('error', (err) => {
    console.error(`[Updater] Error: ${err.message}`)
    updateState = { ...updateState, checking: false, error: err.message }
    sendUpdateStatus()
    updateTrayMenu()
  })
}

function checkForUpdates() {
  if (DEV_MODE) return
  try {
    autoUpdater.checkForUpdates()
  } catch (err) {
    console.error('[Updater] check error:', err.message)
  }
}

function quitAndInstall() {
  if (updateState.downloaded) {
    setImmediate(() => {
      autoUpdater.quitAndInstall(true, true)
    })
  }
}

function sendUpdateStatus() {
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      mainWindow.webContents.send('update-status', { ...updateState })
    } catch (_) {}
  }
}

// ════════════════════════════════════════════
// Backend Health Monitor
// ════════════════════════════════════════════

function checkBackendHealth() {
  return new Promise((resolve) => {
    const req = http.get(`${BACKEND_URL}/health`, (res) => resolve(res.statusCode === 200))
    req.on('error', () => resolve(false))
    req.setTimeout(3000, () => { req.destroy(); resolve(false) })
    req.end()
  })
}

function setBackendConnected(connected) {
  if (backendConnected === connected) return
  backendConnected = connected
  updateTrayMenu()
  updateTrayTooltip()
  if (mainWindow && !mainWindow.isDestroyed()) {
    try {
      mainWindow.webContents.send(connected ? 'backend-connected' : 'backend-disconnected', {
        connected, port: BACKEND_PORT, timestamp: Date.now(),
      })
    } catch (_) {}
  }
}

function startHealthMonitor() {
  checkBackendHealth().then((ok) => setBackendConnected(ok))
  healthInterval = setInterval(async () => {
    const ok = await checkBackendHealth()
    setBackendConnected(ok)
  }, 5000)
}

function stopHealthMonitor() {
  if (healthInterval) { clearInterval(healthInterval); healthInterval = null }
}

// ════════════════════════════════════════════
// IPC Handlers
// ════════════════════════════════════════════

function registerIpcHandlers() {
  // ─── Window Controls ───
  ipcMain.on('window-minimize', () => mainWindow?.minimize())
  ipcMain.on('window-maximize', () => {
    mainWindow?.isMaximized() ? mainWindow.unmaximize() : mainWindow?.maximize()
  })
  ipcMain.on('window-close', () => mainWindow?.hide())

  // ─── Backend Status ───
  ipcMain.handle('backend-status', async () => ({
    connected: await checkBackendHealth(), port: BACKEND_PORT,
  }))

  // ─── File Dialog ───
  ipcMain.handle('open-file-dialog', async (_event, options) => {
    if (!mainWindow) return { canceled: true, filePaths: [] }
    return dialog.showOpenDialog(mainWindow, {
      title: options?.title || '选择文件',
      properties: options?.properties || ['openFile'],
      filters: options?.filters || [{ name: '所有文件', extensions: ['*'] }],
    })
  })

  // ─── System Notification ───
  ipcMain.on('show-notification', (_event, { title, body }) => {
    try {
      const notification = new Notification({ title: title || APP_NAME, body: body || '', icon: getIconPath() })
      notification.on('click', () => { mainWindow?.show(); mainWindow?.focus() })
      notification.show()
    } catch (err) { console.warn('[Desktop] Notification error:', err.message) }
  })

  // ─── Auto Updater ───
  ipcMain.handle('check-for-updates', async () => {
    if (DEV_MODE) return { disabled: true }
    checkForUpdates()
    return { checking: true }
  })

  ipcMain.handle('get-update-status', async () => updateState)

  ipcMain.on('install-update', () => {
    quitAndInstall()
  })

  // ─── App Info ───
  ipcMain.handle('get-app-version', async () => APP_VERSION)
}

// ════════════════════════════════════════════
// Window Management
// ════════════════════════════════════════════

function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1400, height: 900,
    minWidth: 1024, minHeight: 700,
    title: APP_NAME,
    icon: getIconPath(),
    backgroundColor: '#0f1923',
    show: false,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true, nodeIntegration: false, sandbox: false,
    },
  })

  // ─── Load Frontend ───
  const indexPath = path.join(getFrontendDir(), 'index.html')
  if (fs.existsSync(indexPath)) {
    mainWindow.loadFile(indexPath)
  } else if (DEV_MODE) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    mainWindow.loadURL(BACKEND_URL)
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
    mainWindow.webContents.send('app-version', APP_VERSION)

    // 窗口显示后检查更新（延迟几秒让应用先渲染完成）
    setTimeout(() => checkForUpdates(), 5000)
  })

  mainWindow.on('closed', () => { mainWindow = null })
  mainWindow.on('close', (event) => {
    if (!isQuitting) { event.preventDefault(); mainWindow.hide(); return false }
  })
  mainWindow.on('maximize', () => mainWindow?.webContents.send('window-maximized-change', true))
  mainWindow.on('unmaximize', () => mainWindow?.webContents.send('window-maximized-change', false))
  mainWindow.webContents.setWindowOpenHandler(({ url }) => { shell.openExternal(url); return { action: 'deny' } })
}

// ════════════════════════════════════════════
// System Tray
// ════════════════════════════════════════════

function getTrayIcon() {
  const iconPath = getIconPath()
  const img = fs.existsSync(iconPath) ? nativeImage.createFromPath(iconPath) : nativeImage.createEmpty()
  return img.resize({ width: 16, height: 16 })
}

function updateTrayTooltip() {
  if (!tray) return
  let tooltip = `${APP_NAME} v${APP_VERSION}`
  if (updateState.available) tooltip += ` | 更新可用: v${updateState.version}`
  if (updateState.downloading) tooltip += ` | 下载中 ${updateState.progress}%`
  if (updateState.downloaded) tooltip += ` | 更新已下载，重启安装`
  tooltip += ` | 后端: ${backendConnected ? '已连接' : '未连接'}`
  tray.setToolTip(tooltip)
}

function updateTrayMenu() {
  if (!tray) return

  // ─── 更新状态行 ───
  let updateLabel
  if (updateState.checking) { updateLabel = '检查更新...' }
  else if (updateState.downloading) { updateLabel = `下载更新 ${updateState.progress}%` }
  else if (updateState.downloaded) { updateLabel = `重启安装 v${updateState.version}` }
  else if (updateState.available) { updateLabel = `新版本 v${updateState.version} 可用` }
  else if (updateState.error) { updateLabel = `更新出错: ${updateState.error.substring(0, 30)}` }
  else { updateLabel = '已是最新版本' }

  const connectedLabel = `后端: ${backendConnected ? '● 已连接' : '○ 未连接'}`

  const contextMenu = Menu.buildFromTemplate([
    { label: '打开窗口', click: () => { mainWindow?.show(); mainWindow?.focus() } },
    { type: 'separator' },
    { label: connectedLabel, enabled: false },
    { type: 'separator' },
    {
      label: updateLabel,
      click: () => {
        if (updateState.downloaded) { quitAndInstall() }
        else if (!updateState.checking) { checkForUpdates() }
      },
    },
    { type: 'separator' },
    { label: `v${APP_VERSION}`, enabled: false },
    { type: 'separator' },
    {
      label: '退出',
      click: () => { isQuitting = true; app.quit() },
    },
  ])
  tray.setContextMenu(contextMenu)
}

function createTray() {
  tray = new Tray(getTrayIcon())
  tray.setToolTip(`${APP_NAME} v${APP_VERSION}`)
  updateTrayMenu()
  tray.on('double-click', () => { mainWindow?.show(); mainWindow?.focus() })
}

// ════════════════════════════════════════════
// App Lifecycle
// ════════════════════════════════════════════

app.whenReady().then(async () => {
  console.log(`[Desktop] ${APP_NAME} v${APP_VERSION} starting... (dev=${DEV_MODE})`)

  // 初始化自动更新
  setupAutoUpdater()

  // 注册 IPC
  registerIpcHandlers()

  // 创建窗口和托盘
  createWindow()
  createTray()

  // 启动后端健康监控
  startHealthMonitor()

  console.log('[Desktop] Electron UI ready')
})

app.on('window-all-closed', () => { /* stay in tray */ })
app.on('before-quit', () => { isQuitting = true; stopHealthMonitor() })
app.on('activate', () => { mainWindow === null ? createWindow() : mainWindow.show() })