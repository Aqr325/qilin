/**
 * 轻量级 Toast 通知工具
 * 用于替换浏览器 alert()，提供更好的用户体验
 */

interface ToastOption {
  message: string
  type?: 'success' | 'error' | 'warning' | 'info'
  duration?: number
}

let toastContainer: HTMLDivElement | null = null

function ensureContainer() {
  if (!toastContainer) {
    toastContainer = document.createElement('div')
    toastContainer.className = 'toast-container'
    toastContainer.style.cssText = `
      position: fixed; top: 20px; right: 20px; z-index: 9999;
      display: flex; flex-direction: column; gap: 8px;
      max-width: 360px;
    `
    document.body.appendChild(toastContainer)
  }
  return toastContainer
}

export function toast(option: string | ToastOption) {
  const opts = typeof option === 'string' ? { message: option, type: 'info' } : option
  const { message, type = 'info', duration = 3000 } = opts

  const el = document.createElement('div')
  const colors = {
    success: '#10b981', error: '#ef4444', warning: '#f59e0b', info: '#06b6d4'
  }
  const icons = { success: '✓', error: '✕', warning: '⚠', info: 'ℹ' }

  el.className = `toast toast-${type}`
  el.style.cssText = `
    display: flex; align-items: center; gap: 10px;
    padding: 12px 16px; border-radius: 8px;
    background: rgba(15, 23, 42, 0.95); color: #e2e8f0;
    font-size: 13px; border-left: 3px solid ${colors[type]};
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
    animation: toast-in 0.25s ease;
  `
  el.innerHTML = `<span style="color:${colors[type]};font-weight:bold">${icons[type]}</span><span>${message}</span>`

  ensureContainer().appendChild(el)
  setTimeout(() => {
    el.style.animation = 'toast-out 0.2s ease forwards'
    setTimeout(() => el.remove(), 200)
  }, duration)
}

// Add animation styles
const style = document.createElement('style')
style.textContent = `
  @keyframes toast-in { from { opacity: 0; transform: translateX(20px); } to { opacity: 1; transform: translateX(0); } }
  @keyframes toast-out { from { opacity: 1; transform: translateX(0); } to { opacity: 0; transform: translateX(20px); } }
`
document.head.appendChild(style)

// Export a simple wrapper for quick use
export function showToast(msg: string, type?: 'success' | 'error' | 'warning' | 'info') {
  toast({ message: msg, type })
}
