import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Alert, AlertSeverity, AlertStatus, PaginatedResponse } from '@/types'
import api from '@/services/api'

export const useAlertsStore = defineStore('alerts', () => {
  const alerts = ref<Alert[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const filterSeverity = ref<AlertSeverity | ''>('')
  const filterStatus = ref<AlertStatus | ''>('')
  const filterAgent = ref('')
  const filterType = ref('')
  const searchKeyword = ref('')
  const selectedAlerts = ref<Set<string>>(new Set())

  // ── Edit-override guard ──
  // Alerts are fetched in the background (30s polling + Dashboard remount). To keep
  // user edits from being clobbered by a re-fetch before/while they are persisted,
  // we remember locally-edited statuses and re-apply them after every fetch.
  const dirtyAlerts = ref<Set<string>>(new Set())
  const localStatus = new Map<string, { status: AlertStatus; status_label: string }>()

  const statusLabelMap: Record<string, string> = {
    acknowledged: '处理中', resolved: '已处置', false_positive: '误报',
    new: '待处理', investigating: '调查中', closed: '已关闭',
  }

  function applyLocalOverrides() {
    for (const id of dirtyAlerts.value) {
      const override = localStatus.get(id)
      if (!override) continue
      const a = alerts.value.find(x => x.id === id)
      if (a) {
        a.status = override.status
        a.status_label = override.status_label
      }
    }
  }

  // Single source of truth for status edits.
  // confirmed=true → server acknowledged the change, drop the override.
  // confirmed=false → optimistic only (API failed), keep override so polls can't revert it.
  function setAlertStatus(id: string, status: AlertStatus, confirmed: boolean) {
    const status_label = statusLabelMap[status] || status
    localStatus.set(id, { status, status_label })
    if (confirmed) {
      dirtyAlerts.value.delete(id)
    } else {
      dirtyAlerts.value = new Set(dirtyAlerts.value).add(id)
    }
    const a = alerts.value.find(x => x.id === id)
    if (a) {
      a.status = status
      a.status_label = status_label
    }
  }

  // Stats
const pendingCount = ref(0)
const inProgressCount = ref(0)
const todayNewCount = ref(0)
const resolvedCount = ref(0)

  async function fetchAlerts() {
    loading.value = true
    try {
      const params = new URLSearchParams()
      params.set('page', String(page.value))
      params.set('size', String(pageSize.value))
      if (filterSeverity.value) params.set('severity', filterSeverity.value)
      if (filterStatus.value) params.set('status', filterStatus.value)
      if (filterAgent.value) params.set('agent_id', filterAgent.value)
      if (filterType.value) params.set('alert_type', filterType.value)
      if (searchKeyword.value) params.set('keyword', searchKeyword.value)

      const res = await api.get<PaginatedResponse<Alert>>(`/alerts?${params.toString()}`)
      alerts.value = res.items
      total.value = res.total

      // Re-apply any locally edited statuses so background re-fetches
      // (polling / Dashboard remount) never revert the user's changes.
      applyLocalOverrides()

      // Also fetch stats
      await fetchStats()
    } catch (e) {
      console.warn('Failed to fetch alerts, showing empty list:', e)
      alerts.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const res = await api.get<{
        total: number; new_count: number; critical_count: number; resolved_count: number;
        by_severity: Record<string, number>; by_status: Record<string, number>
      }>('/alerts/stats')
      pendingCount.value = res.by_status?.new ?? res.new_count ?? 0
      inProgressCount.value = res.by_status?.acknowledged ?? 0
      todayNewCount.value = res.new_count ?? 0
      resolvedCount.value = res.resolved_count ?? 0
    } catch (e) {
      console.warn('Failed to fetch alert stats:', e)
    }
  }

  async function batchUpdateStatus(alertIds: string[], status: AlertStatus, comment?: string) {
    try {
      await api.post('/alerts/batch/status', { alert_ids: alertIds, status, comment })
      selectedAlerts.value.clear()
      await fetchAlerts()
      return true
    } catch {
      return false
    }
  }

  function toggleSelect(alertId: string) {
    const newSet = new Set(selectedAlerts.value)
    if (newSet.has(alertId)) {
      newSet.delete(alertId)
    } else {
      newSet.add(alertId)
    }
    selectedAlerts.value = newSet
  }

  function toggleSelectAll() {
    if (selectedAlerts.value.size === alerts.value.length) {
      selectedAlerts.value.clear()
    } else {
      selectedAlerts.value = new Set(alerts.value.map(a => a.id))
    }
  }

  function setFilter(key: string, value: string) {
    page.value = 1
    switch (key) {
      case 'severity': filterSeverity.value = value as AlertSeverity; break
      case 'status': filterStatus.value = value as AlertStatus; break
      case 'agent': filterAgent.value = value; break
      case 'type': filterType.value = value; break
      case 'keyword': searchKeyword.value = value; break
    }
    fetchAlerts()
  }

  // Auto refresh
  let pollTimer: ReturnType<typeof setInterval> | null = null

  function startPolling() {
    pollTimer = setInterval(() => {
      fetchAlerts()
    }, 30000)
  }

  function stopPolling() {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }

  function clearSelection() {
    selectedAlerts.value = new Set<string>()
  }

  return {
    alerts, total, page, pageSize, loading,
    filterSeverity, filterStatus, filterAgent, searchKeyword,
    selectedAlerts,
    pendingCount, inProgressCount, todayNewCount, resolvedCount,
    fetchAlerts, fetchStats, batchUpdateStatus, toggleSelect, toggleSelectAll, setFilter,
    setAlertStatus,
    startPolling, stopPolling, clearSelection,
  }
})