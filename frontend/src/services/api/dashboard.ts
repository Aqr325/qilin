import type { DashboardOverview, AlertTrend } from '@/types'
import api from '@/services/api'

export const dashboardApi = {
  overview() {
    return api.get<DashboardOverview>('/dashboard/overview')
  },

  alertTrend(days = 7) {
    return api.get<AlertTrend[]>(`/dashboard/alert-trend?days=${days}`)
  },

  agentHeatmap(hours = 24) {
    return api.get(`/dashboard/agent-heatmap?hours=${hours}`)
  },

  topAlerts(limit = 10) {
    return api.get(`/dashboard/top-alerts?limit=${limit}`)
  },
}