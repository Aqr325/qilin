import type { Agent, PaginatedResponse } from '@/types'
import api from '@/services/api'

export const agentsApi = {
  list(params?: Record<string, string>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : ''
    return api.get<PaginatedResponse<Agent>>(`/agents${query}`)
  },

  stats() {
    return api.get<{ online: number; offline: number; error: number; total: number }>('/agents/stats')
  },

  detail(id: string) {
    return api.get<Agent>(`/agents/${id}`)
  },

  metrics(id: string) {
    return api.get(`/agents/${id}/metrics`)
  },

  upgrade(agentIds: string[], version: string, packageUrl = '') {
    return api.post('/agents/upgrade', { agent_ids: agentIds, version, package_url: packageUrl })
  },

  restart(id: string) {
    return api.post<{ task_id: string }>(`/agents/${id}/restart`)
  },
}
