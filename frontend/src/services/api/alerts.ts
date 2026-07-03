import type { Alert, PaginatedResponse } from '@/types'
import api from '@/services/api'

export const alertsApi = {
  list(params?: Record<string, string>) {
    const query = params ? '?' + new URLSearchParams(params).toString() : ''
    return api.get<PaginatedResponse<Alert>>(`/alerts${query}`)
  },

  stats() {
    return api.get<{
      pending: number; in_progress: number; today_new: number; resolved: number
    }>('/alerts/stats')
  },

  detail(id: string) {
    return api.get<Alert>(`/alerts/${id}`)
  },

  updateStatus(id: string, status: string, comment?: string) {
    return api.put<Alert>(`/alerts/${id}/status`, { status, comment })
  },

  batchStatus(alertIds: string[], status: string, comment?: string) {
    return api.post('/alerts/batch/status', { alert_ids: alertIds, status, comment })
  },

  assign(id: string, assigneeId: string) {
    return api.post<Alert>(`/alerts/${id}/assign`, { assignee_id: assigneeId })
  },

  mitreMatrix() {
    return api.get('/alerts/mitre-matrix')
  },

  export(format: string) {
    return api.get(`/alerts/export?format=${format}`)
  },
}
