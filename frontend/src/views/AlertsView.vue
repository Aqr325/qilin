<template>
  <div class="alerts-view">
    <div class="page-header">
      <div class="page-header-left">
        <h1>告警管理</h1>
        <p>监控、分析和处置安全告警事件</p>
      </div>
      <div class="page-header-right">
        <button class="btn-primary" @click="exportAlerts">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px;">
            <path d="M7 1v12M1 7h12"/>
          </svg>
          导出告警
        </button>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="alert-stats-grid">
      <div class="stat-card">
        <div class="stat-card-icon pending-icon">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="9" r="7"/><path d="M9 5v4l3 2"/></svg>
        </div>
        <div class="stat-card-info">
          <div class="stat-card-value">{{ alertsStore.pendingCount }}</div>
          <div class="stat-card-label">待处理</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card-icon progress-icon">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="9" r="7"/><path d="M9 5v4l3 2"/></svg>
        </div>
        <div class="stat-card-info">
          <div class="stat-card-value">{{ alertsStore.inProgressCount }}</div>
          <div class="stat-card-label">处理中</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card-icon new-icon">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="9" r="7"/><path d="M9 5v4l3 2"/></svg>
        </div>
        <div class="stat-card-info">
          <div class="stat-card-value">{{ alertsStore.todayNewCount }}</div>
          <div class="stat-card-label">今日新增</div>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card-icon resolved-icon">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><circle cx="9" cy="9" r="7"/><path d="M5 9l3 3 5-5"/></svg>
        </div>
        <div class="stat-card-info">
          <div class="stat-card-value">{{ alertsStore.resolvedCount }}</div>
          <div class="stat-card-label">已处置</div>
        </div>
      </div>
    </div>

    <!-- Filters -->
    <div class="filter-bar">
      <div class="filter-group">
        <select v-model="severityFilter" @change="applyFilter('severity', severityFilter)" class="filter-select">
          <option value="">全部严重度</option>
          <option value="critical">致命</option>
          <option value="high">高危</option>
          <option value="medium">中危</option>
          <option value="low">低危</option>
        </select>
        <select v-model="statusFilter" @change="applyFilter('status', statusFilter)" class="filter-select">
          <option value="">全部状态</option>
          <option value="new">待处理</option>
          <option value="acknowledged">处理中</option>
          <option value="investigating">调查中</option>
          <option value="resolved">已处置</option>
          <option value="false_positive">误报</option>
        </select>
        <select v-model="alertTypeFilter" @change="applyFilter('type', alertTypeFilter)" class="filter-select">
          <option value="">全部类型</option>
          <option value="login_monitor">登录行为异常</option>
          <option value="process_monitor">进程异常</option>
          <option value="network_monitor">网络连接异常</option>
          <option value="file_monitor">文件监控告警</option>
          <option value="privilege_escalation">提权告警</option>
          <option value="malware">恶意软件</option>
        </select>
      </div>
      <div class="filter-actions">
        <div class="search-input-wrap">
          <svg class="search-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>
          </svg>
          <input v-model="keywordFilter" type="text" placeholder="搜索告警名称、来源IP..." class="filter-search" @keyup.enter="applyFilter('keyword', keywordFilter)" />
        </div>
      </div>
    </div>

    <!-- Batch actions -->
    <div v-if="alertsStore.selectedAlerts.size > 0" class="batch-bar">
      <span class="batch-info">已选择 {{ alertsStore.selectedAlerts.size }} 条</span>
      <button class="action-btn" @click="batchAction('resolved')">标记已处置</button>
      <button class="action-btn" @click="batchAction('acknowledged')">确认处理</button>
      <button class="action-btn" @click="batchAction('false_positive')">标记误报</button>
      <button class="action-btn" style="margin-left:auto;" @click="alertsStore.clearSelection()">取消选择</button>
    </div>

    <!-- Alert Table -->
    <div class="chart-card">
      <div class="alert-table-wrap">
        <table class="alert-table">
          <thead>
            <tr>
              <th style="width:36px;">
                <input type="checkbox" :checked="allSelected" @change="alertsStore.toggleSelectAll()" style="accent-color:var(--color-accent-500);" />
              </th>
              <th>序号</th>
              <th>告警名称</th>
              <th>严重度</th>
              <th>类型</th>
              <th>状态</th>
              <th>MITRE ATT&CK</th>
              <th>Agent</th>
              <th>时间</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="alert in alertsStore.alerts" :key="alert.id" @click="showDetail(alert)" style="cursor:pointer;">
              <td @click.stop>
                <input type="checkbox" :checked="alertsStore.selectedAlerts.has(alert.id)" @change="alertsStore.toggleSelect(alert.id)" style="accent-color:var(--color-accent-500);" />
              </td>
              <td class="mono-cell">{{ alert.alert_seq }}</td>
              <td><span class="alert-name">{{ alert.title }}</span></td>
              <td><span :class="['badge', severityBadge(alert.severity)]">{{ alert.severity_label }}</span></td>
              <td><span class="type-label">{{ alert.alert_type_label }}</span></td>
              <td><span :class="['status-tag', statusTag(alert.status)]"><span class="dot"></span>{{ alert.status_label }}</span></td>
              <td>
                <span v-if="alert.mitre_technique_id" class="mitre-tag">{{ alert.mitre_technique_id }}</span>
                <span v-else class="text-muted">-</span>
              </td>
              <td class="mono-cell">{{ alert.agent_id }}</td>
              <td class="mono-cell time-cell">{{ formatTime(alert.created_at) }}</td>
              <td @click.stop>
                <button class="action-btn" @click="showDetail(alert)">详情</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="table-footer">
        <div class="table-info">{{ alertsStore.total }} 条记录，第 {{ alertsStore.page }} 页</div>
        <div class="pagination">
          <button class="page-btn" :disabled="alertsStore.page <= 1" @click="changePage(alertsStore.page - 1)">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M8 3L4 7L8 11"/></svg>
          </button>
          <button class="page-btn active">{{ alertsStore.page }}</button>
          <button class="page-btn" @click="changePage(alertsStore.page + 1)">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M6 3L10 7L6 11"/></svg>
          </button>
        </div>
      </div>
    </div>

    <!-- Alert Detail Drawer -->
    <Teleport to="body">
      <div v-if="detailAlert" class="drawer-overlay" @click.self="closeDetail">
        <div class="drawer">
          <div class="drawer-header">
            <h2>{{ detailAlert.title }}</h2>
            <button class="drawer-close" @click="closeDetail">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="drawer-body">
            <div class="detail-section">
              <div class="detail-row">
                <span class="detail-label">告警序号</span>
                <span class="detail-value mono">#{{ detailAlert.alert_seq }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">严重度</span>
                <span :class="['badge', severityBadge(detailAlert.severity)]">{{ detailAlert.severity_label }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">状态</span>
                <span :class="['status-tag', statusTag(detailAlert.status)]"><span class="dot"></span>{{ detailAlert.status_label }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">类型</span>
                <span>{{ detailAlert.alert_type_label }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">MITRE ATT&CK</span>
                <span v-if="detailAlert.mitre_technique_id">{{ detailAlert.mitre_technique_id }} - {{ detailAlert.mitre_technique_name }}</span>
                <span v-else class="text-muted">未映射</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">来源 Agent</span>
                <span class="mono">{{ detailAlert.agent_id }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">来源 IP</span>
                <span class="mono">{{ detailAlert.source_ip || '-' }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">首次检测</span>
                <span class="mono">{{ formatTime(detailAlert.first_detected_at) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">最后检测</span>
                <span class="mono">{{ formatTime(detailAlert.last_detected_at) }}</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">聚合次数</span>
                <span>{{ detailAlert.alert_count }}</span>
              </div>
            </div>

            <div class="detail-section">
              <h3>描述</h3>
              <p class="detail-desc">{{ detailAlert.description }}</p>
            </div>

            <div class="detail-actions">
              <button class="btn-primary" @click="changeDetailStatus('acknowledged')">确认处理</button>
              <button class="action-btn" @click="changeDetailStatus('resolved')">标记已处置</button>
              <button class="action-btn" @click="changeDetailStatus('false_positive')">标记误报</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAlertsStore } from '@/stores/alerts'
import { showToast } from '@/utils/toast'

defineOptions({ name: 'Alerts' })
import type { Alert, AlertStatus } from '@/types'
import { exportToCSV, timestampSuffix } from '@/utils/csv'
import { alertsApi } from '@/services/api/alerts'

const alertsStore = useAlertsStore()

const severityFilter = ref('')
const statusFilter = ref('')
const alertTypeFilter = ref('')
const keywordFilter = ref('')

const detailAlert = ref<Alert | null>(null)

const allSelected = computed(() => {
  return alertsStore.alerts.length > 0 && alertsStore.selectedAlerts.size === alertsStore.alerts.length
})

function severityBadge(s: string) {
  return `badge-${s}`
}

function statusTag(s: string) {
  const map: Record<string, string> = {
    new: 'status-pending',
    acknowledged: 'status-progress',
    investigating: 'status-progress',
    resolved: 'status-resolved',
    false_positive: 'status-resolved',
    closed: 'status-resolved',
  }
  return map[s] || 'status-pending'
}

function formatTime(iso: string) {
  if (!iso) return '--'
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour12: false, month: '2-digit', day: '2-digit' })
}

function applyFilter(key: string, val: string) {
  alertsStore.setFilter(key, val)
}

function changePage(p: number) {
  alertsStore.page = p
  alertsStore.fetchAlerts()
}

async function batchAction(status: string) {
  const ids = Array.from(alertsStore.selectedAlerts)
  try {
    await alertsApi.batchStatus(ids, status)
    // Server confirmed → reconcile store (drops the local override)
    for (const id of ids) alertsStore.setAlertStatus(id, status as AlertStatus, true)
    alertsStore.clearSelection()
    await alertsStore.fetchStats()
  } catch {
    // API unavailable → keep optimistic edit; override survives background re-fetch
    for (const id of ids) alertsStore.setAlertStatus(id, status as AlertStatus, false)
    alertsStore.clearSelection()
  }
}

async function showDetail(alert: Alert) {
  try {
    const detail = await alertsApi.detail(alert.id)
    detailAlert.value = detail
  } catch {
    // API not available, use summary
    detailAlert.value = alert
  }
}

function closeDetail() {
  detailAlert.value = null
}

async function changeDetailStatus(status: string) {
  if (!detailAlert.value) return
  const id = detailAlert.value.id
  try {
    await alertsApi.updateStatus(id, status)
    // Server confirmed → reconcile store and clear override
    alertsStore.setAlertStatus(id, status as AlertStatus, true)
    closeDetail()
    // Refresh stats
    await alertsStore.fetchStats()
  } catch {
    // API unavailable → keep optimistic edit; override survives background re-fetch
    alertsStore.setAlertStatus(id, status as AlertStatus, false)
    closeDetail()
  }
}

async function exportAlerts() {
  const columns = [
    { key: 'alert_seq', label: '告警编号' },
    { key: 'title', label: '告警标题' },
    { key: 'alert_type', label: '类型' },
    { key: 'severity', label: '严重级别' },
    { key: 'status', label: '状态' },
    { key: 'source_ip', label: '来源IP' },
    { key: 'created_at', label: '创建时间' },
  ]
  try {
    // 从后端拉取完整告警集合后再导出（而非仅当前分页）
    const res = await alertsApi.list({ page: '1', size: '100000' })
    const rows = res.items ?? []
    if (rows.length === 0) {
      showToast('暂无可导出的告警数据', 'warning')
      return
    }
    exportToCSV(rows, columns, `告警导出_${timestampSuffix()}.csv`)
  } catch {
    showToast('告警导出失败，请检查后端服务', 'error')
  }
}

onMounted(() => {
  alertsStore.fetchAlerts()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-6);
}

.page-header-left h1 {
  font-size: var(--text-h1);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.page-header-left p {
  font-size: var(--text-body);
  color: var(--color-text-tertiary);
}

.page-header-right {
  flex-shrink: 0;
}

.alert-stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-5);
  margin-bottom: var(--space-6);
}

.stat-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-5);
  display: flex;
  align-items: center;
  gap: var(--space-4);
  transition: all 0.25s ease;
}

.stat-card:hover {
  border-color: rgba(0, 188, 212, 0.15);
  box-shadow: var(--shadow-card-hover);
}

.stat-card-icon {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.stat-card-icon svg {
  width: 20px;
  height: 20px;
}

.pending-icon { background: rgba(255, 59, 92, 0.12); color: var(--color-critical); }
.progress-icon { background: rgba(68, 138, 255, 0.12); color: var(--color-info); }
.new-icon { background: rgba(255, 193, 7, 0.12); color: var(--color-medium); }
.resolved-icon { background: rgba(0, 200, 83, 0.12); color: var(--color-low); }

.stat-card-value {
  font-size: var(--text-h2);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  font-family: var(--font-family-mono);
}

.stat-card-label {
  font-size: var(--text-body-sm);
  color: var(--color-text-tertiary);
}

.filter-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
  gap: var(--space-4);
}

.filter-group {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.filter-select {
  height: 34px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
  cursor: pointer;
  transition: border-color 0.2s ease;
  min-width: 120px;
}

.filter-select:focus {
  border-color: var(--color-accent-500);
}

.filter-select option {
  background: var(--color-bg-surface);
  color: var(--color-text-primary);
}

.filter-actions {
  display: flex;
  gap: var(--space-3);
}

.search-input-wrap {
  position: relative;
}

.search-input-wrap .search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 14px;
  height: 14px;
  color: var(--color-text-tertiary);
  pointer-events: none;
}

.filter-search {
  height: 34px;
  width: 200px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: 0 var(--space-3) 0 30px;
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
  transition: all 0.2s ease;
}

.filter-search:focus {
  border-color: var(--color-accent-500);
  box-shadow: var(--glow-accent);
}

.batch-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: rgba(0, 188, 212, 0.08);
  border: 1px solid rgba(0, 188, 212, 0.2);
  border-radius: 8px;
  margin-bottom: var(--space-4);
}

.batch-info {
  font-size: var(--text-body-sm);
  color: var(--color-accent-500);
  font-weight: var(--font-weight-medium);
}

.chart-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-5);
}

.alert-table-wrap {
  overflow-x: auto;
}

.alert-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-body-sm);
}

.alert-table thead th {
  padding: var(--space-3) var(--space-4);
  text-align: left;
  font-weight: var(--font-weight-medium);
  color: var(--color-text-tertiary);
  font-size: var(--text-caption);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  border-bottom: 1px solid var(--color-border-default);
  white-space: nowrap;
}

.alert-table tbody tr {
  border-bottom: 1px solid var(--color-border-subtle);
  transition: background 0.2s ease;
}

.alert-table tbody tr:last-child { border-bottom: none; }
.alert-table tbody tr:hover { background: var(--color-bg-hover); }

.alert-table tbody td {
  padding: var(--space-3) var(--space-4);
  color: var(--color-text-secondary);
  vertical-align: middle;
}

.alert-name {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
}

.type-label {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

.mitre-tag {
  display: inline-block;
  padding: 1px 6px;
  background: rgba(124, 77, 255, 0.12);
  color: var(--color-accent-purple);
  border-radius: 4px;
  font-family: var(--font-family-mono);
  font-size: var(--text-mono-sm);
}

.mono-cell, .mono {
  font-family: var(--font-family-mono);
  font-size: var(--text-mono-sm);
}

.time-cell { white-space: nowrap; }
.text-muted { color: var(--color-text-tertiary); }

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4) 0;
}

.table-info {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
}

.pagination {
  display: flex;
  align-items: center;
  gap: 2px;
}

.page-btn {
  min-width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-text-tertiary);
  font-size: var(--text-caption);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.15s ease;
}

.page-btn:hover { background: var(--color-bg-hover); color: var(--color-text-primary); border-color: var(--color-border-default); }
.page-btn.active { background: rgba(0, 188, 212, 0.12); border-color: var(--color-accent-500); color: var(--color-accent-500); }
.page-btn svg { width: 14px; height: 14px; }

/* Drawer */
.drawer-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: var(--z-modal);
  display: flex;
  justify-content: flex-end;
}

.drawer {
  width: 480px;
  max-width: 100vw;
  height: 100%;
  background: var(--color-bg-surface);
  border-left: 1px solid var(--color-border-default);
  display: flex;
  flex-direction: column;
  animation: slideInRight 0.25s ease;
}

@keyframes slideInRight {
  from { transform: translateX(100%); }
  to { transform: translateX(0); }
}

.drawer-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5);
  border-bottom: 1px solid var(--color-border-default);
}

.drawer-header h2 {
  font-size: var(--text-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.drawer-close {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--color-text-secondary);
  cursor: pointer;
}

.drawer-close:hover { background: var(--color-bg-hover); color: var(--color-text-primary); }
.drawer-close svg { width: 18px; height: 18px; }

.drawer-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
}

.detail-section {
  margin-bottom: var(--space-6);
}

.detail-section h3 {
  font-size: var(--text-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-3);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-2) 0;
  border-bottom: 1px solid var(--color-border-subtle);
}

.detail-row:last-child { border-bottom: none; }

.detail-label {
  color: var(--color-text-tertiary);
  font-size: var(--text-body-sm);
}

.detail-value {
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
}

.detail-desc {
  color: var(--color-text-secondary);
  font-size: var(--text-body);
  line-height: 1.6;
}

.detail-actions {
  display: flex;
  gap: var(--space-3);
  padding-top: var(--space-4);
  border-top: 1px solid var(--color-border-default);
}

@media (max-width: 1200px) {
  .alert-stats-grid { grid-template-columns: repeat(2, 1fr); }
}

@media (max-width: 768px) {
  .alert-stats-grid { grid-template-columns: 1fr; }
  .filter-bar { flex-direction: column; align-items: stretch; }
  .filter-group { flex-wrap: wrap; }
  .drawer { width: 100vw; }
}
</style>