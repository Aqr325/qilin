import type { Policy, PaginatedResponse } from '@/types'
import api from '@/services/api'

export const policiesApi = {
  list(params?: Record<string, string>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : ''
    return api.get<PaginatedResponse<Policy>>(`/policies${query}`)
  },

  detail(id: string) {
    return api.get<Policy>(`/policies/${id}`)
  },

  create(data: Partial<Policy>) {
    return api.post<Policy>('/policies', data)
  },

  update(id: string, data: Partial<Policy>) {
    return api.put<Policy>(`/policies/${id}`, data)
  },

  delete(id: string) {
    return api.delete(`/policies/${id}`)
  },

  toggle(id: string, enabled: boolean) {
    return api.post<Policy>(`/policies/${id}/toggle`, { enabled })
  },

  deploy(id: string, agentIds?: string[], force = false) {
    return api.post(`/policies/${id}/deploy`, { agent_ids: agentIds, force })
  },

  deployStatus(id: string) {
    return api.get(`/policies/${id}/deploy-status`)
  },

  versions(id: string) {
    return api.get(`/policies/${id}/versions`)
  },

  validate(rules: any) {
    return api.post('/policies/validate', { rules })
  },
}