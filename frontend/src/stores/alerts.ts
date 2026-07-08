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
  const pendingCount = ref(42)
  const inProgressCount = ref(18)
  const todayNewCount = ref(7)
  const resolvedCount = ref(156)

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
    } catch {
      // Use mock data when API unavailable
      alerts.value = getMockAlerts()
      total.value = 42
      // Keep existing hardcoded stats
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
    } catch {
      // Keep existing values
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

function getMockAlerts(): Alert[] {
  return [
    {
      id: 'alert-001', alert_seq: 10245, agent_id: 'kylin-node-01', hostname: 'kylin-node-01',
      alert_type: 'login_monitor', alert_type_label: '登录行为异常',
      severity: 'critical', severity_label: '致命',
      title: '检测到SSH暴力破解攻击', description: 'kylin-node-01 在5分钟内收到 156 次 SSH 登录失败尝试',
      status: 'new', status_label: '待处理',
      mitre_technique_id: 'T1110', mitre_tactic: 'TA0006', mitre_technique_name: '暴力破解',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T19:55:00Z', last_detected_at: '2026-06-23T20:00:00Z',
      alert_count: 1, created_at: '2026-06-23T20:00:01Z', source_ip: '192.168.1.100',
    },
    {
      id: 'alert-002', alert_seq: 10244, agent_id: 'kylin-node-07', hostname: 'kylin-node-07',
      alert_type: 'process_monitor', alert_type_label: '进程异常告警',
      severity: 'high', severity_label: '高危',
      title: '可疑进程启动', description: '检测到非白名单进程 /tmp/evil.sh 启动',
      status: 'new', status_label: '待处理',
      mitre_technique_id: 'T1059', mitre_tactic: 'TA0002', mitre_technique_name: '命令和脚本解释器',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T19:50:00Z', last_detected_at: '2026-06-23T19:50:00Z',
      alert_count: 1, created_at: '2026-06-23T19:50:01Z', source_ip: '192.168.1.203',
    },
    {
      id: 'alert-003', alert_seq: 10243, agent_id: 'kylin-node-12', hostname: 'kylin-node-12',
      alert_type: 'network_monitor', alert_type_label: '网络连接异常',
      severity: 'medium', severity_label: '中危',
      title: '异常网络连接', description: 'kylin-node-12 与已知恶意IP 45.33.32.156 建立连接',
      status: 'acknowledged', status_label: '处理中',
      mitre_technique_id: 'T1071', mitre_tactic: 'TA0011', mitre_technique_name: '应用层协议',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T19:45:00Z', last_detected_at: '2026-06-23T19:45:00Z',
      alert_count: 1, created_at: '2026-06-23T19:45:01Z', source_ip: '10.0.12.45',
    },
    {
      id: 'alert-004', alert_seq: 10242, agent_id: 'kylin-node-05', hostname: 'kylin-node-05',
      alert_type: 'file_monitor', alert_type_label: '文件监控告警',
      severity: 'low', severity_label: '低危',
      title: '文件完整性变更', description: '/etc/passwd 文件发生变更',
      status: 'resolved', status_label: '已处置',
      mitre_technique_id: 'T1078', mitre_tactic: 'TA0003', mitre_technique_name: '有效账户',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T19:40:00Z', last_detected_at: '2026-06-23T19:40:00Z',
      alert_count: 1, created_at: '2026-06-23T19:40:01Z', source_ip: '192.168.2.88',
    },
    {
      id: 'alert-005', alert_seq: 10241, agent_id: 'kylin-node-01', hostname: 'kylin-node-01',
      alert_type: 'login_monitor', alert_type_label: '登录行为异常',
      severity: 'critical', severity_label: '致命',
      title: 'SSH 暴力破解', description: 'kylin-node-01 检测到持续的SSH暴力破解攻击',
      status: 'acknowledged', status_label: '处理中',
      mitre_technique_id: 'T1110', mitre_tactic: 'TA0006', mitre_technique_name: '暴力破解',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T19:35:00Z', last_detected_at: '2026-06-23T19:35:00Z',
      alert_count: 1, created_at: '2026-06-23T19:35:01Z', source_ip: '10.0.0.19',
    },
    {
      id: 'alert-006', alert_seq: 10240, agent_id: 'kylin-node-09', hostname: 'kylin-node-09',
      alert_type: 'anomaly', alert_type_label: '行为异常告警',
      severity: 'high', severity_label: '高危',
      title: 'Agent 心跳超时', description: 'kylin-node-09 超过 30 秒未上报心跳',
      status: 'resolved', status_label: '已处置',
      mitre_technique_id: 'T1499', mitre_tactic: 'TA0040', mitre_technique_name: '端点拒绝服务',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T19:30:00Z', last_detected_at: '2026-06-23T19:30:00Z',
      alert_count: 1, created_at: '2026-06-23T19:30:01Z', source_ip: '192.168.3.12',
    },
    {
      id: 'alert-007', alert_seq: 10239, agent_id: 'kylin-node-03', hostname: 'kylin-node-03',
      alert_type: 'privilege_escalation', alert_type_label: '提权告警',
      severity: 'critical', severity_label: '致命',
      title: '检测到可疑sudo提权操作', description: "用户 'devops' 在非预期时间执行sudo命令",
      status: 'new', status_label: '待处理',
      mitre_technique_id: 'T1548.003', mitre_tactic: 'TA0004', mitre_technique_name: '滥用权限提升',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T19:25:00Z', last_detected_at: '2026-06-23T19:25:00Z',
      alert_count: 1, created_at: '2026-06-23T19:25:01Z',
    },
    {
      id: 'alert-008', alert_seq: 10238, agent_id: 'kylin-node-15', hostname: 'kylin-node-15',
      alert_type: 'malware', alert_type_label: '恶意软件告警',
      severity: 'critical', severity_label: '致命',
      title: '检测到已知恶意软件签名', description: '文件 /usr/bin/.systemd 匹配已知恶意软件签名',
      status: 'investigating', status_label: '调查中',
      mitre_technique_id: 'T1204', mitre_tactic: 'TA0002', mitre_technique_name: '用户执行',
      suppressed: false, correlation_count: 1,
      first_detected_at: '2026-06-23T18:55:00Z', last_detected_at: '2026-06-23T19:00:00Z',
      alert_count: 2, created_at: '2026-06-23T18:55:01Z',
    },
  ]
}