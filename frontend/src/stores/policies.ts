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
    } catch (e) {
      console.warn('Failed to fetch policies, showing empty list:', e)
      policies.value = []
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

