import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User, LoginResponse } from '@/types'
import api from '@/services/api'
import { needsPasswordChange, clearForcePasswordChange } from '@/stores/forceChange'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)
  const loading = ref(false)

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const res = await api.post<LoginResponse>('/auth/login', {
        username,
        password,
      })
      api.setToken(res.access_token)
      api.setRefreshToken(res.refresh_token)
      user.value = res.user
      isAuthenticated.value = true
      if (res.user.must_change_password) {
        needsPasswordChange.value = true
      }
      localStorage.setItem('token', res.access_token)
      localStorage.setItem('refreshToken', res.refresh_token)
      return true
    } catch (e) {
      console.error('Login failed:', e)
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchCurrentUser() {
    const token = localStorage.getItem('token')
    if (!token) return

    api.setToken(token)
    // 还原刷新令牌，使静默刷新可用
    const refreshToken = localStorage.getItem('refreshToken')
    if (refreshToken) {
      api.setRefreshToken(refreshToken)
    }
    try {
      const res = await api.get<User>('/auth/me')
      user.value = res
      isAuthenticated.value = true
      // 还原登录态时也要检查强制改密标志：若用户上次关掉了改密弹窗，
      // 重新打开应用后必须再次弹出，否则会带着 must_change_password=True
      // 绕过弹窗去操作业务接口，被后端 403 拦截（表现为"保存失败/服务器配置错误"）。
      if (res.must_change_password) {
        needsPasswordChange.value = true
      }
    } catch {
      api.setToken(null)
      api.setRefreshToken(null)
      localStorage.removeItem('token')
      localStorage.removeItem('refreshToken')
    }
  }

  async function logout() {
    const refreshToken = localStorage.getItem('refreshToken')
    try {
      // 通知后端吊销访问令牌与刷新令牌（防重放）
      await api.post('/auth/logout', { refresh_token: refreshToken })
    } catch {
      // 即使后端不可用也执行本地清理
    }
    user.value = null
    isAuthenticated.value = false
    clearForcePasswordChange()
    api.setToken(null)
    api.setRefreshToken(null)
    localStorage.removeItem('token')
    localStorage.removeItem('refreshToken')
  }

  return { user, isAuthenticated, loading, login, fetchCurrentUser, logout }
})