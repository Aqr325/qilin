<template>
  <div class="dashboard">
    <div class="page-header">
      <div class="page-header-left">
        <h1>安全态势总览</h1>
        <p>实时监控系统安全状态与 Agent 运行状况</p>
      </div>
      <div class="page-header-right">
        <div class="page-header-time">{{ time }}</div>
        <div class="page-header-date">{{ date }}</div>
      </div>
    </div>

    <!-- KPI Cards -->
    <div class="metric-grid">
      <div class="metric-card card-critical">
        <div class="metric-card-label">告警总数</div>
        <div class="metric-card-value">{{ overview.total_alerts.toLocaleString() }}</div>
        <div class="metric-card-trend trend-bad">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10L7 4L11 10"/></svg>
          {{ overview.alert_trend_percent }}%
        </div>
      </div>
      <div class="metric-card card-accent">
        <div class="metric-card-label">活跃 Agent</div>
        <div class="metric-card-value">{{ overview.active_agents }}</div>
        <div class="metric-card-trend trend-good">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10L7 4L11 10"/></svg>
          {{ overview.agent_trend_percent }}%
        </div>
        <div style="font-size:var(--text-body-sm);color:var(--color-text-secondary);margin-top:2px;">/ {{ overview.total_agents }} 台</div>
      </div>
      <div class="metric-card card-high">
        <div class="metric-card-label">高危事件</div>
        <div class="metric-card-value">{{ overview.high_severity_alerts }}</div>
        <div class="metric-card-trend trend-good">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 4L7 10L11 4"/></svg>
          {{ Math.abs(overview.high_trend_percent ?? 0) }}%
        </div>
      </div>
      <div class="metric-card card-success">
        <div class="metric-card-label">系统健康度</div>
        <div class="metric-card-value">{{ (overview.health_score ?? 0).toFixed(1) }}%</div>
        <div class="metric-card-trend trend-good">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M3 10L7 4L11 10"/></svg>
          {{ overview.health_trend_percent }}%
        </div>
      </div>
    </div>

    <!-- Trend Chart -->
    <section class="chart-section">
      <div class="chart-card">
        <div class="chart-card-header">
          <span class="chart-card-title">威胁趋势（近7天）</span>
          <div class="chart-card-legend">
            <span class="legend-item"><span class="legend-dot" style="background:#FF3B5C;"></span>严重</span>
            <span class="legend-item"><span class="legend-dot" style="background:#FF6D00;"></span>高危</span>
            <span class="legend-item"><span class="legend-dot" style="background:#FFC107;"></span>中危</span>
          </div>
        </div>
        <div class="chart-wrapper">
          <canvas ref="trendChartRef"></canvas>
        </div>
      </div>
    </section>

    <!-- Two-column: Doughnut + Agent Health -->
    <div class="two-col-grid">
      <div class="chart-card">
        <div class="chart-card-header">
          <span class="chart-card-title">告警分布</span>
        </div>
        <div class="chart-wrapper">
          <canvas ref="doughnutChartRef"></canvas>
        </div>
      </div>

      <div class="chart-card">
        <div class="chart-card-header">
          <span class="chart-card-title">Agent 健康状态</span>
          <span style="font-size:var(--text-caption);color:var(--color-text-tertiary);">共 {{ agentHealthTotal }} 台</span>
        </div>
        <div class="agent-status-list">
          <div v-for="item in agentHealthItems" :key="item.label" class="agent-status-item">
            <div class="agent-status-header">
              <div class="agent-status-left">
                <span :class="['agent-status-dot', item.statusClass]"></span>
                <span class="agent-status-label">{{ item.label }}</span>
              </div>
              <span class="agent-status-count">{{ item.count }} 台</span>
            </div>
            <div class="agent-status-bar-wrap">
              <div class="agent-status-bar" :class="item.statusClass" :style="{ width: item.percent + '%' }"></div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Recent Alerts -->
    <section class="alert-table-section chart-card">
      <div class="chart-card-header">
        <span class="chart-card-title">最新告警</span>
        <div style="display:flex;gap:var(--space-3);align-items:center;">
          <span style="font-size:var(--text-caption);color:var(--color-text-tertiary);">{{ refreshSeconds }}s 前更新</span>
          <span class="legend-item"><span class="legend-dot" style="background:var(--color-status-online);border-radius:50%;"></span></span>
        </div>
      </div>
      <div class="alert-table-wrap">
        <table class="alert-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>告警名称</th>
              <th>来源</th>
              <th>严重度</th>
              <th>状态</th>
              <th>Agent</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="alert in recentAlerts" :key="alert.id">
              <td class="time-cell">{{ formatTime(alert.created_at) }}</td>
              <td><span class="alert-name">{{ alert.title }}</span></td>
              <td>{{ alert.source_ip || '-' }}</td>
              <td><span :class="['badge', severityClass(alert.severity)]">{{ alert.severity_label }}</span></td>
              <td><span :class="['status-tag', statusClass(alert.status)]"><span class="dot"></span>{{ alert.status_label }}</span></td>
              <td class="mono-cell">{{ alert.agent_id }}</td>
              <td><button class="action-btn" @click="viewAlert(alert)">查看</button></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="table-footer">
        <div class="table-info">显示 1-{{ Math.min(recentAlerts.length, 6) }} 条，共 {{ alertsStore.total }} 条</div>
        <div class="pagination">
          <button class="page-btn" :disabled="alertsStore.page <= 1" @click="prevPage">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M8 3L4 7L8 11"/></svg>
          </button>
          <button class="page-btn active">{{ alertsStore.page }}</button>
          <button class="page-btn" @click="nextPage">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M6 3L10 7L6 11"/></svg>
          </button>
        </div>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, nextTick, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useDashboardStore } from '@/stores/dashboard'
import { useAlertsStore } from '@/stores/alerts'
import Chart from 'chart.js/auto'

defineOptions({ name: 'Dashboard' })
import { showToast } from '@/utils/toast'
import type { Alert } from '@/types'

const router = useRouter()
const store = useDashboardStore()
const alertsStore = useAlertsStore()

const trendChartRef = ref<HTMLCanvasElement | null>(null)
const doughnutChartRef = ref<HTMLCanvasElement | null>(null)
const refreshSeconds = ref(0)

let trendChart: any = null
let doughnutChart: any = null

const overview = computed(() => store.overview)
const agentHealthTotal = computed(() => store.agentHealth.online + store.agentHealth.offline + store.agentHealth.error + store.agentHealth.pending)

const agentHealthItems = computed(() => {
  const total = agentHealthTotal.value || 1
  return [
    { label: '在线', count: store.agentHealth.online, statusClass: 'online', percent: (store.agentHealth.online / total * 100).toFixed(1) },
    { label: '离线', count: store.agentHealth.offline, statusClass: 'offline', percent: (store.agentHealth.offline / total * 100).toFixed(1) },
    { label: '异常', count: store.agentHealth.error, statusClass: 'error', percent: (store.agentHealth.error / total * 100).toFixed(1) },
    { label: '等待', count: store.agentHealth.pending, statusClass: 'pending', percent: (store.agentHealth.pending / total * 100).toFixed(1) },
  ]
})

const recentAlerts = computed(() => alertsStore.alerts.slice(0, 6))

// Clock
const time = ref('')
const date = ref('')
let clockTimer: ReturnType<typeof setInterval>
let refreshTimer: ReturnType<typeof setInterval>

function updateClock() {
  const now = new Date()
  time.value = now.toLocaleTimeString('zh-CN', { hour12: false })
  const days = ['日', '一', '二', '三', '四', '五', '六']
  date.value = `${now.getFullYear()}年${String(now.getMonth() + 1).padStart(2, '0')}月${String(now.getDate()).padStart(2, '0')}日 星期${days[now.getDay()]}`
}

function formatTime(iso: string) {
  if (!iso) return '--:--:--'
  const d = new Date(iso)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}

function severityClass(s: string) {
  return `badge-${s}`
}

function statusClass(s: string) {
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

function viewAlert(alert: Alert) {
  router.push('/alerts')
}

function prevPage() {
  if (alertsStore.page > 1) {
    alertsStore.page--
    alertsStore.fetchAlerts()
  }
}

function nextPage() {
  alertsStore.page++
  alertsStore.fetchAlerts()
}

// Chart initialization
function initCharts() {
  if (trendChartRef.value) {
    const ctx = trendChartRef.value.getContext('2d')
    if (ctx) {
      trendChart = new Chart(ctx, {
        type: 'line',
        data: {
          labels: store.alertTrend.map(t => t.date),
          datasets: [
            {
              label: '严重告警',
              data: store.alertTrend.map(t => t.critical),
              borderColor: '#FF3B5C',
              backgroundColor: 'rgba(255, 59, 92, 0.08)',
              borderWidth: 2,
              pointRadius: 3,
              pointHoverRadius: 5,
              pointBackgroundColor: '#FF3B5C',
              tension: 0.35,
              fill: true,
            },
            {
              label: '高危告警',
              data: store.alertTrend.map(t => t.high),
              borderColor: '#FF6D00',
              backgroundColor: 'rgba(255, 109, 0, 0.06)',
              borderWidth: 2,
              pointRadius: 3,
              pointHoverRadius: 5,
              pointBackgroundColor: '#FF6D00',
              tension: 0.35,
              fill: true,
            },
            {
              label: '中危告警',
              data: store.alertTrend.map(t => t.medium),
              borderColor: '#FFC107',
              backgroundColor: 'rgba(255, 193, 7, 0.05)',
              borderWidth: 2,
              pointRadius: 3,
              pointHoverRadius: 5,
              pointBackgroundColor: '#FFC107',
              tension: 0.35,
              fill: true,
            },
          ],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 1200, easing: 'easeOutQuart' },
          interaction: { intersect: false, mode: 'index' },
          plugins: {
            legend: { display: false },
            tooltip: {
              backgroundColor: '#1C2128',
              titleColor: '#E8ECF0',
              bodyColor: '#9BA3B0',
              borderColor: '#2C3540',
              borderWidth: 1,
              padding: 10,
              cornerRadius: 8,
            },
          },
          scales: {
            x: {
              grid: { color: 'rgba(44, 53, 64, 0.5)', drawBorder: false },
              ticks: { color: '#5C6673' },
            },
            y: {
              beginAtZero: true,
              grid: { color: 'rgba(44, 53, 64, 0.5)', drawBorder: false },
              ticks: { color: '#5C6673', stepSize: 10 },
            },
          },
        },
      })
    }
  }

  if (doughnutChartRef.value) {
    const ctx = doughnutChartRef.value.getContext('2d')
    if (ctx) {
      const data = [store.criticalCount, store.highCount, store.mediumCount, store.lowCount]
      doughnutChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
          labels: ['严重', '高危', '中危', '低危'],
          datasets: [{
            data,
            backgroundColor: ['#FF3B5C', '#FF6D00', '#FFC107', '#00C853'],
            borderColor: '#14181F',
            borderWidth: 3,
            hoverOffset: 6,
          }],
        },
        options: {
          responsive: true,
          maintainAspectRatio: false,
          animation: { duration: 1000, easing: 'easeOutBounce', animateRotate: true },
          cutout: '62%',
          plugins: {
            legend: {
              position: 'bottom',
              labels: {
                color: '#9BA3B0',
                font: { size: 11 },
                padding: 14,
                usePointStyle: true,
                pointStyle: 'circle',
                generateLabels: function(chart: any) {
                  const data = chart.data
                  return data.labels.map((label: string, i: number) => ({
                    text: `${label} ${data.datasets[0].data[i]}`,
                    fillStyle: data.datasets[0].backgroundColor[i],
                    strokeStyle: data.datasets[0].backgroundColor[i],
                    hidden: false,
                    index: i,
                  }))
                },
              },
            },
            tooltip: {
              backgroundColor: '#1C2128',
              titleColor: '#E8ECF0',
              bodyColor: '#9BA3B0',
              borderColor: '#2C3540',
              borderWidth: 1,
              padding: 10,
              cornerRadius: 8,
            },
          },
        },
      })
    }
  }
}

// Watch for data changes and update charts
watch(() => store.alertTrend, (newTrend) => {
  if (trendChart && newTrend.length > 0) {
    trendChart.data.labels = newTrend.map(t => t.date)
    trendChart.data.datasets[0].data = newTrend.map(t => t.critical)
    trendChart.data.datasets[1].data = newTrend.map(t => t.high)
    trendChart.data.datasets[2].data = newTrend.map(t => t.medium)
    trendChart.update('active')
  }
}, { deep: true })

watch(() => [store.criticalCount, store.highCount, store.mediumCount, store.lowCount], () => {
  if (doughnutChart) {
    doughnutChart.data.datasets[0].data = [store.criticalCount, store.highCount, store.mediumCount, store.lowCount]
    doughnutChart.update('active')
  }
}, { deep: true })

onMounted(async () => {
  updateClock()
  clockTimer = setInterval(updateClock, 1000)
  refreshTimer = setInterval(() => { refreshSeconds.value++ }, 1000)

  await Promise.all([
    store.fetchOverview(),
    store.fetchAlertTrend(),
    alertsStore.fetchAlerts(),
  ])

  await nextTick()
  initCharts()
})

onUnmounted(() => {
  clearInterval(clockTimer)
  clearInterval(refreshTimer)
  if (trendChart) trendChart.destroy()
  if (doughnutChart) doughnutChart.destroy()
})
</script>

<style scoped>
.page-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  margin-bottom: var(--space-6);
  animation: fadeInUp 0.5s ease;
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
  text-align: right;
  flex-shrink: 0;
}

.page-header-time {
  font-family: var(--font-family-mono);
  font-size: var(--text-mono);
  color: var(--color-text-secondary);
  letter-spacing: 0.5px;
}

.page-header-date {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-5);
  margin-bottom: var(--space-6);
  animation: fadeInUp 0.5s ease 0.1s both;
}

.metric-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-5);
  position: relative;
  overflow: hidden;
  transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.metric-card:hover {
  border-color: rgba(0, 188, 212, 0.15);
  box-shadow: var(--shadow-card-hover);
  transform: translateY(-2px);
}

.metric-card::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 3px;
  border-radius: 12px 12px 0 0;
}

.card-critical::before { background: var(--color-critical); }
.card-accent::before { background: var(--color-accent-500); }
.card-high::before { background: var(--color-high); }
.card-success::before { background: var(--color-low); }

.metric-card-label {
  font-size: var(--text-body-sm);
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-2);
  font-weight: var(--font-weight-medium);
}

.metric-card-value {
  font-size: var(--text-display);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  line-height: 1.1;
  margin-bottom: var(--space-2);
  font-family: var(--font-family-mono), var(--font-family-zh);
  letter-spacing: -0.5px;
}

.metric-card-trend {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
}

.metric-card-trend svg {
  width: 14px;
  height: 14px;
}

.trend-good { color: var(--color-low); }
.trend-bad { color: var(--color-critical); }

.chart-section {
  margin-bottom: var(--space-6);
  animation: fadeInUp 0.5s ease 0.2s both;
}

.chart-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-5);
  transition: border-color 0.25s cubic-bezier(0.4, 0, 0.2, 1), box-shadow 0.25s cubic-bezier(0.4, 0, 0.2, 1);
}

.chart-card:hover {
  border-color: rgba(0, 188, 212, 0.12);
  box-shadow: var(--shadow-card-hover);
}

.chart-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-5);
}

.chart-card-title {
  font-size: var(--text-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.chart-card-legend {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.legend-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
}

.legend-dot {
  width: 8px;
  height: 8px;
  border-radius: 2px;
  flex-shrink: 0;
}

.chart-wrapper {
  position: relative;
  width: 100%;
  height: 260px;
}

.two-col-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-5);
  margin-bottom: var(--space-6);
  animation: fadeInUp 0.5s ease 0.3s both;
}

.two-col-grid .chart-wrapper {
  height: 220px;
}

.agent-status-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.agent-status-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.agent-status-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.agent-status-left {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.agent-status-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
  flex-shrink: 0;
  position: relative;
}

.agent-status-dot.online { background: var(--color-status-online); }
.agent-status-dot.offline { background: var(--color-status-offline); }
.agent-status-dot.error { background: var(--color-status-error); }
.agent-status-dot.pending { background: var(--color-status-pending); }

.agent-status-label {
  font-size: var(--text-body-sm);
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
}

.agent-status-count {
  font-size: var(--text-body);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  font-family: var(--font-family-mono);
}

.agent-status-bar-wrap {
  width: 100%;
  height: 6px;
  background: var(--color-bg-elevated);
  border-radius: 3px;
  overflow: hidden;
}

.agent-status-bar {
  height: 100%;
  border-radius: 3px;
  transition: width 1s ease;
}

.agent-status-bar.online { background: var(--color-status-online); }
.agent-status-bar.offline { background: var(--color-status-offline); }
.agent-status-bar.error { background: var(--color-status-error); }
.agent-status-bar.pending { background: var(--color-status-pending); }

.alert-table-section {
  animation: fadeInUp 0.5s ease 0.4s both;
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

.alert-table tbody tr:last-child {
  border-bottom: none;
}

.alert-table tbody tr:hover {
  background: var(--color-bg-hover);
}

.alert-table tbody td {
  padding: var(--space-3) var(--space-4);
  color: var(--color-text-secondary);
  vertical-align: middle;
}

.alert-table tbody td .alert-name {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
}

.time-cell {
  font-family: var(--font-family-mono);
  font-size: var(--text-mono-sm);
  white-space: nowrap;
}

.mono-cell {
  font-family: var(--font-family-mono);
  font-size: var(--text-mono-sm);
}

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  border-top: 1px solid var(--color-border-subtle);
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

.page-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
  border-color: var(--color-border-default);
}

.page-btn.active {
  background: rgba(0, 188, 212, 0.12);
  border-color: var(--color-accent-500);
  color: var(--color-accent-500);
}

.page-btn svg {
  width: 14px;
  height: 14px;
}

@media (max-width: 1200px) {
  .metric-grid { grid-template-columns: repeat(2, 1fr); }
  .two-col-grid { grid-template-columns: 1fr; }
}

@media (max-width: 768px) {
  .metric-grid { grid-template-columns: 1fr; }
  .chart-card-legend { display: none; }
  .page-header { flex-direction: column; gap: var(--space-3); }
  .page-header-right { text-align: left; }
}
</style>