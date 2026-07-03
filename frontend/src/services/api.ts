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

  setToken(token: string | null) {
    this.token = token
  }

  getToken(): string | null {
    return this.token
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
      const error = await response.json().catch(() => ({ message: '请求失败' }))
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

  // Mock data helper - returns mock data when API is unavailable
  mock<T>(data: T): Promise<T> {
    return new Promise((resolve) => {
      setTimeout(() => resolve(data), 300 + Math.random() * 200)
    })
  }
}

export const api = new ApiService()
export default api
