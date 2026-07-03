import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { User } from '@/types'
import api from '@/services/api'

export const useAuthStore = defineStore('auth', () => {
  const user = ref<User | null>(null)
  const isAuthenticated = ref(false)
  const loading = ref(false)

  async function login(username: string, password: string) {
    loading.value = true
    try {
      const res = await api.post<{ access_token: string; user: User }>('/auth/login', {
        username,
        password,
      })
      api.setToken(res.access_token)
      user.value = res.user
      isAuthenticated.value = true
      localStorage.setItem('token', res.access_token)
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
    try {
      const res = await api.get<User>('/auth/me')
      user.value = res
      isAuthenticated.value = true
    } catch {
      api.setToken(null)
      localStorage.removeItem('token')
    }
  }

  function logout() {
    user.value = null
    isAuthenticated.value = false
    api.setToken(null)
    localStorage.removeItem('token')
  }

  return { user, isAuthenticated, loading, login, fetchCurrentUser, logout }
})