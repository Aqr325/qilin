import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'
import { systemApi } from '@/services/api/system'
import type { AuditLog } from '@/types'
import type { SystemUser, SystemRole } from '@/services/api/system'

export const useSystemStore = defineStore('system', () => {
  const users = ref<SystemUser[]>([])
  const roles = ref<SystemRole[]>([])
  const auditLogs = ref<AuditLog[]>([])
  const auditLogsTotal = ref(0)
  const loading = ref(false)

  async function fetchUsers() {
    loading.value = true
    try {
      const res = await systemApi.users()
      const items = res.items ?? []
      // Map backend roles array to simple role string
      users.value = items.map(u => ({
        ...u,
        role: u.roles?.[0]?.name ?? '',
        is_active: u.is_active !== undefined ? u.is_active : true,
        mfa_enabled: u.mfa_enabled ?? false,
      }))
    } catch (e) {
      console.warn('Failed to fetch users, showing empty list:', e)
      users.value = []
    } finally {
      loading.value = false
    }
  }

  async function fetchRoles() {
    try {
      const res = await api.get<any>('/system/roles')
      // Backend returns list of roles directly
      const items = res.data?.items ?? res.items ?? res.data ?? res
      roles.value = (Array.isArray(items) ? items : []).map((r: any) => ({
        id: r.id,
        name: r.name,
        display_name: r.display_name,
        description: r.description ?? '',
        permission_count: r.permissions?.length ?? r.permission_count ?? 0,
        permissions: (r.permissions ?? []).map((p: any) => p.id ?? p.permission ?? p),
      }))
    } catch (e) {
      console.warn('Failed to fetch roles, showing empty list:', e)
      roles.value = []
    }
  }

  async function fetchAuditLogs(params?: { keyword?: string; page?: number }) {
    loading.value = true
    try {
      const query = new URLSearchParams()
      if (params?.keyword) query.set('keyword', params.keyword)
      if (params?.page) query.set('page', String(params.page))
      query.set('size', '20')
      const qs = query.toString()
      const res = await api.get<any>(`/system/audit-logs${qs ? '?' + qs : ''}`)
      auditLogs.value = res.items || res
      auditLogsTotal.value = res.total ?? (Array.isArray(res.items || res) ? (res.items || res).length : 0)
    } catch (e) {
      console.warn('Failed to fetch audit logs, showing empty list:', e)
      auditLogs.value = []
      auditLogsTotal.value = 0
    } finally {
      loading.value = false
    }
  }

  return { users, roles, auditLogs, auditLogsTotal, loading, fetchUsers, fetchRoles, fetchAuditLogs }
})