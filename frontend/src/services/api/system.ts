import type { PaginatedResponse } from '@/types'
import api from '@/services/api'

export interface SystemUser {
  id: string
  username: string
  display_name: string
  email: string
  phone?: string
  role: string
  is_active: boolean
  mfa_enabled: boolean
  last_login?: string
  created_at: string
}

export interface SystemRole {
  id: string
  name: string
  display_name: string
  description: string
  permission_count: number
  permissions: string[]
}

export const systemApi = {
  users(params?: Record<string, string>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : ''
    return api.get<PaginatedResponse<SystemUser>>(`/system/users${query}`)
  },

  createUser(data: Partial<SystemUser>) {
    return api.post<SystemUser>('/system/users', data)
  },

  updateUser(id: string, data: Partial<SystemUser>) {
    return api.put<SystemUser>(`/system/users/${id}`, data)
  },

  toggleUserStatus(id: string, isActive: boolean) {
    return api.put(`/system/users/${id}/status`, { is_active: isActive })
  },

  roles() {
    return api.get<any[]>('/system/roles')
  },

  roleDetail(id: string) {
    return api.get<any>(`/system/roles/${id}`)
  },

  createRole(data: any) {
    return api.post('/system/roles', data)
  },

  updateRole(id: string, data: any) {
    return api.put(`/system/roles/${id}`, data)
  },

  auditLogs(params?: Record<string, string>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : ''
    return api.get<PaginatedResponse<any>>(`/system/audit-logs${query}`)
  },

  settings() {
    return api.get('/system/settings')
  },

  updateSettings(data: any) {
    return api.put('/system/settings', data)
  },
}