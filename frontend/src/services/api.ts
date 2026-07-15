import { triggerForcePasswordChange } from '@/stores/forceChange'

// Detect Electron environment and use absolute URL
const isElectron = navigator.userAgent.includes('Electron')
const BASE_URL = isElectron ? 'http://127.0.0.1:8001/api/v1' : '/api/v1'

interface RequestOptions {
  method?: string
  body?: any
  headers?: Record<string, string>
}

class ApiService {
  private token: string | null = null
  private refreshToken: string | null = null
  private isRefreshing = false
  private pendingRequests: Array<(token: string) => void> = []

  setToken(token: string | null) {
    this.token = token
  }

  getToken(): string | null {
    return this.token
  }

  setRefreshToken(token: string | null) {
    this.refreshToken = token
  }

  getRefreshToken(): string | null {
    return this.refreshToken
  }

  async request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { method = 'GET', body, headers = {} } = options

    const config: RequestInit = {
      method,
      headers: {
        'Content-Type': 'application/json',
        ...headers,
      },
    }

    if (this.token) {
      (config.headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`
    }

    if (body && method !== 'GET') {
      config.body = JSON.stringify(body)
    }

    const response = await fetch(`${BASE_URL}${path}`, config)

    if (!response.ok) {
      if (response.status === 401 && this.refreshToken && !this.isRefreshing) {
        this.isRefreshing = true
        try {
          const refreshRes = await fetch(`${BASE_URL}/auth/refresh`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh_token: this.refreshToken }),
          })
          if (refreshRes.ok) {
            const refreshData = await refreshRes.json()
            this.token = refreshData.data.access_token
            this.refreshToken = refreshData.data.refresh_token
            // 持久化刷新令牌，避免刷新后丢失
            if (this.refreshToken) {
              localStorage.setItem('refreshToken', this.refreshToken)
            }
            // 重试原请求
            (config.headers as Record<string, string>)['Authorization'] = `Bearer ${this.token}`
            const retryRes = await fetch(`${BASE_URL}${path}`, config)
            if (retryRes.ok) {
              return (await retryRes.json()).data as T
            }
          }
        } catch {
          // 刷新失败
        } finally {
          this.isRefreshing = false
        }
        // 刷新失败后清除token并跳转登录
        this.token = null
        this.refreshToken = null
      }
      const error = await response.json().catch(() => ({ message: '请求失败' }))
      if (
        response.status === 403 &&
        typeof error.detail === 'string' &&
        error.detail.includes('请先修改初始密码')
      ) {
        triggerForcePasswordChange()
      }
      throw new Error(error.detail || error.message || `HTTP ${response.status}`)
    }

    const result = await response.json()
    return result.data as T
  }

  get<T>(path: string): Promise<T> {
    return this.request<T>(path)
  }

  post<T>(path: string, body?: any): Promise<T> {
    return this.request<T>(path, { method: 'POST', body })
  }

  put<T>(path: string, body?: any): Promise<T> {
    return this.request<T>(path, { method: 'PUT', body })
  }

  delete<T>(path: string): Promise<T> {
    return this.request<T>(path, { method: 'DELETE' })
  }
}

export const api = new ApiService()
export default api
