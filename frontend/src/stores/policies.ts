import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Policy, PaginatedResponse } from '@/types'
import api from '@/services/api'

export const usePoliciesStore = defineStore('policies', () => {
  const policies = ref<Policy[]>([])
  const loading = ref(false)

  async function fetchPolicies() {
    loading.value = true
    try {
      const res = await api.get<PaginatedResponse<Policy>>('/policies')
      const items = res.items || res
      // Map backend fields to frontend Policy type
      policies.value = (items as Policy[]).map(p => ({
        ...p,
        created_by: p.created_by || (p.created_by_name ? { id: '', display_name: p.created_by_name } : { id: '', display_name: '系统' }),
        enabled: p.enabled !== undefined ? p.enabled : (p.status === 'enabled'),
      }))
    } catch {
      policies.value = getMockPolicies()
    } finally {
      loading.value = false
    }
  }

  async function togglePolicy(id: string, enabled: boolean) {
    try {
      await api.post(`/policies/${id}/toggle`, { enabled })
      const policy = policies.value.find(p => p.id === id)
      if (policy) policy.enabled = enabled
      return true
    } catch {
      return false
    }
  }

  return { policies, loading, fetchPolicies, togglePolicy }
})

function getMockPolicies(): Policy[] {
  return [
    {
      id: 'policy-01', name: '文件完整性监控', description: '监控关键系统文件变更',
      policy_type: 'file_integrity', policy_type_label: '文件完整性监控',
      version: 3, status: 'enabled', status_label: '已启用',
      target_type: 'all', target_value: [], rules: {},
      priority: 10, enabled: true,
      created_by: { id: 'user-1', display_name: '系统管理员' },
      created_at: '2026-06-01T00:00:00Z', updated_at: '2026-06-20T00:00:00Z',
    },
    {
      id: 'policy-02', name: '进程白名单', description: '允许/禁止特定进程运行',
      policy_type: 'process_whitelist', policy_type_label: '进程白名单',
      version: 2, status: 'enabled', status_label: '已启用',
      target_type: 'all', target_value: [], rules: {},
      priority: 20, enabled: true,
      created_by: { id: 'user-1', display_name: '系统管理员' },
      created_at: '2026-06-02T00:00:00Z', updated_at: '2026-06-18T00:00:00Z',
    },
    {
      id: 'policy-03', name: '网络访问控制', description: '控制网络连接和端口访问',
      policy_type: 'network_firewall', policy_type_label: '网络访问控制',
      version: 5, status: 'enabled', status_label: '已启用',
      target_type: 'tags', target_value: ['production'], rules: {},
      priority: 5, enabled: true,
      created_by: { id: 'user-1', display_name: '系统管理员' },
      created_at: '2026-05-15T00:00:00Z', updated_at: '2026-06-22T00:00:00Z',
    },
    {
      id: 'policy-04', name: '登录安全策略', description: 'SSH和本地登录安全规则',
      policy_type: 'login_policy', policy_type_label: '登录安全策略',
      version: 1, status: 'draft', status_label: '草稿',
      target_type: 'all', target_value: [], rules: {},
      priority: 15, enabled: false,
      created_by: { id: 'user-2', display_name: '安全运维工程师' },
      created_at: '2026-06-21T00:00:00Z', updated_at: '2026-06-21T00:00:00Z',
    },
    {
      id: 'policy-05', name: '漏洞扫描配置', description: '定时漏洞扫描策略',
      policy_type: 'vulnerability_scan', policy_type_label: '漏洞扫描策略',
      version: 2, status: 'disabled', status_label: '已禁用',
      target_type: 'all', target_value: [], rules: {},
      priority: 30, enabled: false,
      created_by: { id: 'user-1', display_name: '系统管理员' },
      created_at: '2026-06-10T00:00:00Z', updated_at: '2026-06-15T00:00:00Z',
    },
    {
      id: 'policy-06', name: '日志审计规则', description: '系统和安全日志采集规则',
      policy_type: 'log_audit', policy_type_label: '日志审计规则',
      version: 4, status: 'enabled', status_label: '已启用',
      target_type: 'all', target_value: [], rules: {},
      priority: 25, enabled: true,
      created_by: { id: 'user-1', display_name: '系统管理员' },
      created_at: '2026-05-20T00:00:00Z', updated_at: '2026-06-19T00:00:00Z',
    },
  ]
}