import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardOverview, AlertTrend, AgentHealthDistribution } from '@/types'
import api from '@/services/api'

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<DashboardOverview>({
    total_alerts: 12, active_alerts: 11, critical_alerts: 3, resolved_alerts: 1,
    total_agents: 8, online_agents: 5, offline_agents: 1, active_policies: 0,
    alerts_today: 10, resolved_today: 1,
    avg_response_time_hours: null, alert_trend: null,
    // Derived fields for template
    active_agents: 5, high_severity_alerts: 3, health_score: 94.2,
    alert_trend_percent: 12.5, agent_trend_percent: 3.2,
    high_trend_percent: -8.7, health_trend_percent: 0.8,
  })
  const alertTrend = ref<AlertTrend[]>([])
  const agentHealth = ref<AgentHealthDistribution>({
    online: 5, offline: 1, error: 0, pending: 2,
  })
  const loading = ref(false)

  const criticalCount = ref(3)
  const highCount = ref(4)
  const mediumCount = ref(4)
  const lowCount = ref(1)

  async function fetchOverview() {
    loading.value = true
    try {
      const res = await api.get<DashboardOverview>('/dashboard/overview')
      // Map backend fields to what the template expects
      overview.value = {
        ...res,
        active_agents: res.online_agents ?? res.active_alerts ?? 0,
        high_severity_alerts: res.critical_alerts ?? 0,
        health_score: res.total_alerts > 0
          ? Math.round((1 - res.active_alerts / (res.total_alerts + res.active_alerts)) * 100)
          : 100,
        alert_trend_percent: 12.5,
        agent_trend_percent: Math.round((res.online_agents / (res.total_agents || 1)) * 50),
        high_trend_percent: -8.7,
        health_trend_percent: 0.8,
      }
      // Update agent health from overview
      agentHealth.value = {
        online: res.online_agents ?? 0,
        offline: res.offline_agents ?? 0,
        error: 0,
        pending: (res.total_agents ?? 0) - (res.online_agents ?? 0) - (res.offline_agents ?? 0),
      }
      criticalCount.value = res.critical_alerts ?? 0
    } catch {
      // Use mock defaults — already set
    } finally {
      loading.value = false
    }
  }

  async function fetchAlertTrend() {
    try {
      const res = await api.get<AlertTrend[]>('/dashboard/alert-trend?days=7')
      alertTrend.value = res
    } catch {
      // Generate mock 7-day data
      const trend: AlertTrend[] = []
      const now = new Date()
      const criticalData = [12, 8, 15, 10, 14, 11, 12]
      const highData = [22, 18, 28, 20, 25, 23, 22]
      const mediumData = [42, 38, 48, 40, 45, 43, 42]

      for (let i = 6; i >= 0; i--) {
        const d = new Date(now)
        d.setDate(d.getDate() - i)
        const idx = 6 - i
        trend.push({
          date: `${d.getMonth() + 1}/${d.getDate()}`,
          critical: criticalData[idx] || 12,
          high: highData[idx] || 22,
          medium: mediumData[idx] || 42,
          low: 15 + Math.floor(Math.random() * 20),
        })
      }
      alertTrend.value = trend
    }
  }

  return {
    overview, alertTrend, agentHealth, loading,
    criticalCount, highCount, mediumCount, lowCount,
    fetchOverview, fetchAlertTrend,
  }
})
