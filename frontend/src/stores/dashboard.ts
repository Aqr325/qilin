import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { DashboardOverview, DashboardOverviewBackend, AlertTrend, AgentHealthDistribution } from '@/types'
import api from '@/services/api'

export const useDashboardStore = defineStore('dashboard', () => {
  const overview = ref<DashboardOverview>({
    total_alerts: 0, active_alerts: 0, critical_alerts: 0, resolved_alerts: 0,
    total_agents: 0, online_agents: 0, offline_agents: 0, active_policies: 0,
    alerts_today: 0, resolved_today: 0,
    avg_response_time_hours: null, alert_trend: null,
    active_agents: 0, high_severity_alerts: 0, health_score: 100,
    alert_trend_percent: 0, agent_trend_percent: 0,
    high_trend_percent: 0, health_trend_percent: 0,
  })
  const alertTrend = ref<AlertTrend[]>([])
  const agentHealth = ref<AgentHealthDistribution>({
    online: 0, offline: 0, error: 0, pending: 0,
  })
  const loading = ref(false)

const criticalCount = ref(0)
const highCount = ref(0)
const mediumCount = ref(0)
const lowCount = ref(0)

  async function fetchOverview() {
    loading.value = true
    try {
      const res = await api.get<DashboardOverviewBackend>('/dashboard/overview')
      // Map backend fields to what the template expects
      overview.value = {
        ...res,
        active_agents: res.online_agents ?? 0,
        high_severity_alerts: res.critical_alerts ?? 0,
        health_score: res.total_alerts > 0
          ? Math.round((1 - res.active_alerts / (res.total_alerts + res.active_alerts)) * 100)
          : 100,
        // 趋势百分比 — 暂无历史对比数据，初始为0
        alert_trend_percent: 0,
        agent_trend_percent: 0,
        high_trend_percent: 0,
        health_trend_percent: 0,
      }
      // Update agent health from overview
      agentHealth.value = {
        online: res.online_agents ?? 0,
        offline: res.offline_agents ?? 0,
        error: 0,
        pending: (res.total_agents ?? 0) - (res.online_agents ?? 0) - (res.offline_agents ?? 0),
      }
      criticalCount.value = res.critical_alerts ?? 0
      highCount.value = res.high_alerts ?? 0
      mediumCount.value = res.medium_alerts ?? 0
      lowCount.value = res.low_alerts ?? 0
    } catch {
      // Use mock defaults — already set
    } finally {
      loading.value = false
    }
  }

  async function fetchAlertTrend() {
    try {
      const res = await api.get<AlertTrend[]>('/dashboard/alert-trend?days=7')
      // Backend returns TrendData: { labels, datasets } — transform to AlertTrend[]
      if (res && typeof res === 'object' && 'labels' in res && 'datasets' in res) {
        const labels = (res as any).labels as string[]
        const datasets = (res as any).datasets as Array<{ label: string; data: number[] }>
        const buildMap = (label: string): number[] => {
          const ds = datasets.find(d => d.label === label)
          return ds?.data ?? labels.map(() => 0)
        }
        alertTrend.value = labels.map(date => ({
          date: (() => {
            // Robust date conversion: handle YYYY-MM-DD format
            const parts = date.split('-')
            if (parts.length >= 3 && parts[1] && parts[2]) {
              return `${parts[1]}/${parts[2]}`
            }
            return date
          })(),
          critical: buildMap('critical'),
          high: buildMap('high'),
          medium: buildMap('medium'),
          low: buildMap('low'),
        })).map((item, i) => ({
          date: item.date,
          critical: item.critical[i] || 0,
          high: item.high[i] || 0,
          medium: item.medium[i] || 0,
          low: item.low[i] || 0,
        }))
      } else {
        alertTrend.value = Array.isArray(res) ? res : []
      }
    } catch (e) {
      console.warn('Failed to fetch alert trend, showing empty trend:', e)
      alertTrend.value = []
    }
  }

  return {
    overview, alertTrend, agentHealth, loading,
    criticalCount, highCount, mediumCount, lowCount,
    fetchOverview, fetchAlertTrend,
  }
})
