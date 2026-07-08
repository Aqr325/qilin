import { defineStore } from 'pinia'
import { ref } from 'vue'
import api from '@/services/api'
import type { AuditLog } from '@/types'

export interface SystemUser {
  id: string
  username: string
  display_name: string
  email: string
  role: string
  roles?: { name: string; display_name: string }[]
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

export const useSystemStore = defineStore('system', () => {
  const users = ref<SystemUser[]>([])
  const roles = ref<SystemRole[]>([])
  const auditLogs = ref<AuditLog[]>([])
  const loading = ref(false)

  async function fetchUsers() {
    loading.value = true
    try {
      const res = await api.get<any>('/system/users')
      const items = res.items || res
      // Map backend roles array to simple role string
      users.value = (items as any[]).map(u => ({
        ...u,
        role: u.roles?.[0]?.name ?? u.roles?.[0]?.id ?? '',
        is_active: u.is_active !== undefined ? u.is_active : true,
        mfa_enabled: u.mfa_enabled ?? false,
      }))
    } catch {
      users.value = getMockUsers()
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
    } catch {
      roles.value = getMockRoles()
    }
  }

  async function fetchAuditLogs() {
    loading.value = true
    try {
      const res = await api.get<any>('/system/audit-logs')
      auditLogs.value = res.items || res
    } catch {
      auditLogs.value = getMockAuditLogs()
    } finally {
      loading.value = false
    }
  }

  return { users, roles, auditLogs, loading, fetchUsers, fetchRoles, fetchAuditLogs }
})

function getMockUsers(): SystemUser[] {
  return [
    { id: 'user-1', username: 'admin', display_name: '赵明远', email: 'admin@kylinos.cn', role: '管理员', is_active: true, mfa_enabled: true, last_login: '2026-06-23T19:00:00Z', created_at: '2026-01-01T00:00:00Z' },
    { id: 'user-2', username: 'operator', display_name: '李运维', email: 'ops@kylinos.cn', role: '运维员', is_active: true, mfa_enabled: false, last_login: '2026-06-23T15:30:00Z', created_at: '2026-02-15T00:00:00Z' },
    { id: 'user-3', username: 'auditor', display_name: '王审计', email: 'audit@kylinos.cn', role: '审计员', is_active: true, mfa_enabled: true, last_login: '2026-06-22T09:00:00Z', created_at: '2026-03-01T00:00:00Z' },
    { id: 'user-4', username: 'zhangsan', display_name: '张三', email: 'zhangsan@kylinos.cn', role: '运维员', is_active: true, mfa_enabled: false, last_login: '2026-06-23T11:00:00Z', created_at: '2026-04-10T00:00:00Z' },
    { id: 'user-5', username: 'lisi', display_name: '李四', email: 'lisi@kylinos.cn', role: '只读用户', is_active: false, mfa_enabled: false, last_login: '2026-06-10T08:00:00Z', created_at: '2026-04-15T00:00:00Z' },
    { id: 'user-6', username: 'wangwu', display_name: '王五', email: 'wangwu@kylinos.cn', role: '审计员', is_active: true, mfa_enabled: true, last_login: '2026-06-23T14:00:00Z', created_at: '2026-05-01T00:00:00Z' },
  ]
}

function getMockRoles(): SystemRole[] {
  const allPerms = ['alert:read', 'alert:write', 'agent:read', 'agent:write', 'policy:read', 'policy:write', 'policy:deploy', 'user:write', 'role:write', 'audit:read', 'system:write', 'ai:chat']
  return [
    { id: 'role-1', name: 'admin', display_name: '系统管理员', description: '系统完全控制权限，包括用户管理、策略配置、系统设置', permission_count: allPerms.length, permissions: allPerms },
    { id: 'role-2', name: 'operator', display_name: '安全运维员', description: '日常安全运维操作，告警处置、Agent管理、策略查看', permission_count: 6, permissions: ['alert:read', 'alert:write', 'agent:read', 'agent:write', 'policy:read', 'ai:chat'] },
    { id: 'role-3', name: 'auditor', display_name: '安全审计员', description: '审计日志查看、报表导出、合规检查', permission_count: 4, permissions: ['alert:read', 'agent:read', 'policy:read', 'audit:read'] },
    { id: 'role-4', name: 'readonly', display_name: '只读用户', description: '仅可查看仪表盘和告警信息，无操作权限', permission_count: 2, permissions: ['alert:read', 'agent:read'] },
  ]
}

function getMockAuditLogs(): AuditLog[] {
  return [
    { id: 1, user_id: 'user-1', username: 'admin', action: 'update', resource_type: 'policy', resource_id: 'policy-03', resource_name: '网络访问控制', detail: { before: { enabled: false }, after: { enabled: true } }, ip_address: '192.168.1.100', result: 'success', created_at: '2026-06-23T19:30:00Z' },
    { id: 2, user_id: 'user-2', username: 'operator', action: 'update', resource_type: 'alert', resource_id: 'alert-003', resource_name: '异常网络连接', detail: { status_change: 'new → acknowledged' }, ip_address: '192.168.1.101', result: 'success', created_at: '2026-06-23T19:25:00Z' },
    { id: 3, user_id: 'user-1', username: 'admin', action: 'create', resource_type: 'user', resource_id: 'user-6', resource_name: '王五', detail: { role: 'auditor' }, ip_address: '192.168.1.100', result: 'success', created_at: '2026-06-23T18:00:00Z' },
    { id: 4, user_id: 'user-1', username: 'admin', action: 'create', resource_type: 'policy', resource_id: 'policy-04', resource_name: '登录安全策略', detail: { policy_type: 'login_policy' }, ip_address: '192.168.1.100', result: 'success', created_at: '2026-06-23T16:00:00Z' },
    { id: 5, user_id: 'user-2', username: 'operator', action: 'update', resource_type: 'agent', resource_id: 'kylin-node-07', resource_name: 'kylin-node-07', detail: { tags_added: ['monitoring'] }, ip_address: '192.168.1.101', result: 'success', created_at: '2026-06-23T15:30:00Z' },
    { id: 6, user_id: 'user-1', username: 'admin', action: 'delete', resource_type: 'user', resource_id: 'user-5', resource_name: '李四', detail: { reason: '离职', error: '用户当前有活跃会话' }, ip_address: '192.168.1.100', result: 'failure', created_at: '2026-06-23T14:00:00Z' },
  ]
}