/**
 * 麒麟OS 安全运维 Agent - Electron Main Process
 * 
 * 统一桌面程序: Electron 主程序 + Vue 3 前端 + PyInstaller 后端
 * 
 * 打包结构:
 *   kylin-secops-desktop/
 *   ├── kylin-secops-desktop.exe (Electron)
 *   └── resources/
 *       ├── frontend/ (Vue 3 dist)
 *       ├── backend.exe (PyInstaller 后端)
 *       ├── config.json
 *       ├── icon.png
 *       └── kylin_secops.db
 */
const { app, BrowserWindow, Tray, Menu, nativeImage, dialog, shell } = require('electron')
const path = require('path')
const { spawn, spawnSync } = require('child_process')
const fs = require('fs')
const http = require('http')

// ════════════════════════════════════════════
// Constants
// ════════════════════════════════════════════
const APP_NAME = '麒麟OS安全运维'
const BACKEND_PORT = 8001
const BACKEND_URL = `http://127.0.0.1:${BACKEND_PORT}`
const DEV_MODE = !app.isPackaged

// ════════════════════════════════════════════
// Path Resolution
// ════════════════════════════════════════════
function getResourcesPath() {
  if (DEV_MODE) {
    // Dev: __dirname is desktop/, resources are in desktop/resources/
    return path.join(__dirname, 'resources')
  }
  // Packaged: resources are in process.resourcesPath
  return process.resourcesPath
}

function getConfigPath() {
  return path.join(getResourcesPath(), 'config.json')
}

function getBackendExePath() {
  return path.join(getResourcesPath(), 'backend.exe')
}

function getFrontendPath() {
  if (DEV_MODE) {
    return path.join(__dirname, 'frontend')
  }
  // Packaged: frontend is in resources/frontend/
  return path.join(getResourcesPath(), 'frontend')
}

// ════════════════════════════════════════════
// State
// ════════════════════════════════════════════
let mainWindow = null
let tray = null
let backendProcess = null
let isQuitting = false

// ════════════════════════════════════════════
// Backend Process Management
// ════════════════════════════════════════════
function startBackend() {
  const backendExe = getBackendExePath()

  console.log(`[Desktop] Backend exe: ${backendExe}`)
  console.log(`[Desktop] Dev mode: ${DEV_MODE}`)

  // Resolve seed password from config.json and inject it as the KYLIN_SEED_PASSWORD
  // env var when spawning the backend. This ensures first-time DB initialization
  // uses a known, user-visible default credential instead of an invisible random
  // password (which would lock the user out of their own desktop install).
  let seedPassword = ''
  try {
    const cfgPath = getConfigPath()
    if (fs.existsSync(cfgPath)) {
      const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf-8'))
      seedPassword = cfg.seed_password || (cfg.backend && cfg.backend.seed_password) || ''
    }
  } catch (e) {
    console.error('[Desktop] Failed to read seed_password from config:', e.message)
  }

  if (DEV_MODE && !fs.existsSync(backendExe)) {
    console.log('[Desktop] Backend exe not found in dev, assuming Python dev server is running')
    return Promise.resolve()
  }

  if (!fs.existsSync(backendExe)) {
    console.log(`[Desktop] Backend exe not found at: ${backendExe}`)
    console.log(`[Desktop] Resources path: ${getResourcesPath()}`)
    return Promise.resolve()
  }

  return new Promise((resolve) => {
    try {
      console.log('[Desktop] Starting backend process...')

      backendProcess = spawn(backendExe, [], {
        cwd: getResourcesPath(),
        stdio: ['ignore', 'pipe', 'pipe'],
        env: {
          ...process.env,
          PYTHONUNBUFFERED: '1',
          ...(seedPassword ? { KYLIN_SEED_PASSWORD: seedPassword } : {}),
        },
        windowsHide: true,
      })

      backendProcess.stdout.on('data', (data) => {
        const msg = data.toString()
        console.log(`[Backend] ${msg.trim()}`)
        if (msg.includes('Uvicorn running') || msg.includes('Application startup complete')) {
          console.log('[Desktop] Backend is ready!')
          resolve()
        }
      })

      backendProcess.stderr.on('data', (data) => {
        const msg = data.toString()
        console.error(`[Backend:err] ${msg.trim()}`)
        if (msg.includes('Uvicorn running') || msg.includes('Application startup complete')) {
          resolve()
        }
      })

      backendProcess.on('error', (err) => {
        console.error('[Desktop] Failed to start backend:', err.message)
        resolve()
      })

      backendProcess.on('exit', (code) => {
        console.log(`[Desktop] Backend exited with code ${code}`)
        backendProcess = null
        // Auto-restart backend if it crashed unexpectedly (max 3 retries)
        if (code !== 0 && code !== null) {
          const restartCount = (global.__backendRestartCount || 0) + 1
          global.__backendRestartCount = restartCount
          if (restartCount <= 3) {
            console.log(`[Desktop] Restarting backend (attempt ${restartCount}/3)...`)
            setTimeout(() => startBackendInternal(), 1000)
          } else {
            console.error('[Desktop] Backend crashed 3 times, giving up.')
          }
        }
      })

      // Timeout fallback
      setTimeout(() => {
        console.log('[Desktop] Backend startup timeout, proceeding...')
        if (mainWindow && !mainWindow.isDestroyed()) {
          mainWindow.webContents.send('backend-timeout')
        }
        resolve()
      }, 15000)
    } catch (err) {
      console.error('[Desktop] Backend spawn error:', err.message)
      resolve()
    }
  })
}

function stopBackend() {
  const proc = backendProcess
  if (!proc) return
  console.log('[Desktop] Stopping backend...')
  try {
    const pid = proc.pid
    if (pid) {
      if (process.platform === 'win32') {
        // 同步终止（spawnSync 会等待 taskkill 完成再返回），避免 Electron 抢先退出
        // 导致 backend.exe 子进程被孤儿化、文件锁不释放（下次覆盖升级会失败）。
        spawnSync('taskkill', ['/pid', String(pid), '/f', '/t'], { windowsHide: true })
      } else {
        try { proc.kill('SIGTERM') } catch (e) { /* ignore */ }
      }
    }
  } catch (err) {
    console.error('[Desktop] Error stopping backend:', err.message)
  } finally {
    backendProcess = null
  }
}

function waitForBackend(maxRetries = 40) {
  return new Promise((resolve) => {
    let retries = 0
    function check() {
      const req = http.get(`${BACKEND_URL}/health`, (res) => {
        if (res.statusCode === 200) resolve()
        else if (retries < maxRetries) { retries++; setTimeout(check, 500) }
        else resolve()
      })
      req.on('error', () => {
        if (retries < maxRetries) { retries++; setTimeout(check, 500) }
        else resolve()
      })
      req.end()
    }
    check()
  })
}

// ════════════════════════════════════════════
// Window Management
// ════════════════════════════════════════════
function createWindow() {
  const iconPath = path.join(getResourcesPath(), 'icon.png')
  let windowIcon = undefined
  if (fs.existsSync(iconPath)) {
    windowIcon = iconPath
  }

  mainWindow = new BrowserWindow({
    width: 1400,
    height: 900,
    minWidth: 1024,
    minHeight: 700,
    title: APP_NAME,
    icon: windowIcon,
    webPreferences: {
      preload: path.join(__dirname, 'preload.js'),
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
      webSecurity: true,
    },
    show: false,
    backgroundColor: '#0f1923',
  })

  const frontendPath = getFrontendPath()
  console.log(`[Desktop] Frontend path: ${frontendPath}`)

  if (fs.existsSync(path.join(frontendPath, 'index.html'))) {
    mainWindow.loadFile(path.join(frontendPath, 'index.html'))
  } else if (DEV_MODE) {
    mainWindow.loadURL('http://localhost:5173')
  } else {
    // Last resort: backend serves the frontend
    mainWindow.loadURL(BACKEND_URL)
  }

  mainWindow.once('ready-to-show', () => {
    mainWindow.show()
  })

  mainWindow.on('closed', () => {
    mainWindow = null
  })

  mainWindow.on('close', (event) => {
    if (!isQuitting) {
      event.preventDefault()
      mainWindow.hide()
      return false
    }
  })

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url)
    return { action: 'deny' }
  })
}

// ════════════════════════════════════════════
// System Tray
// ════════════════════════════════════════════
function createTray() {
  const iconPath = path.join(getResourcesPath(), 'icon.png')
  let trayIcon
  if (fs.existsSync(iconPath)) {
    const img = nativeImage.createFromPath(iconPath)
    trayIcon = img.resize({ width: 16, height: 16 })
  } else {
    trayIcon = nativeImage.createEmpty()
  }

  tray = new Tray(trayIcon)
  tray.setToolTip(APP_NAME)

  const contextMenu = Menu.buildFromTemplate([
    { label: '打开窗口', click: () => { mainWindow && mainWindow.show() && mainWindow.focus() } },
    { type: 'separator' },
    {
      label: '退出', click: () => {
        isQuitting = true
        stopBackend()
        app.quit()
      }
    },
  ])
  tray.setContextMenu(contextMenu)
  tray.on('double-click', () => { mainWindow && mainWindow.show() && mainWindow.focus() })
}

// ════════════════════════════════════════════
// Single Instance Lock
// ════════════════════════════════════════════
const gotTheLock = app.requestSingleInstanceLock()
if (!gotTheLock) {
  console.log(`[Desktop] Another instance is already running, quitting.`)
  app.quit()
}

// ════════════════════════════════════════════
// App Lifecycle
// ════════════════════════════════════════════
app.whenReady().then(async () => {
  console.log(`[Desktop] ${APP_NAME} starting... (dev=${DEV_MODE})`)
  console.log(`[Desktop] Resources: ${getResourcesPath()}`)

  // Start backend silently
  await startBackend()

  // Wait for backend health
  try {
    await waitForBackend(40)
    console.log('[Desktop] Backend is healthy')
  } catch (err) {
    console.warn('[Desktop] Backend health check timeout:', err.message)
  }

  createWindow()
  createTray()
})

app.on('window-all-closed', () => {
  // Keep running in tray
})

app.on('before-quit', (event) => {
  if (!isQuitting) {
    isQuitting = true
    // 阻止 Electron 立即退出：先同步杀掉后端子进程树，待 OS 释放 backend.exe 文件锁后，
    // 再真正退出，确保进程无残留、下次覆盖升级不会被锁。
    event.preventDefault()
    stopBackend()
    setTimeout(() => {
      app.quit()
    }, 300)
  }
})

app.on('activate', () => {
  if (mainWindow === null) createWindow()
  else mainWindow.show()
})