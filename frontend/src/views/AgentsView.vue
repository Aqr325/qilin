<template>
  <div class="agents-view">
    <div class="page-header">
      <div class="page-header-left">
        <h1>Agent 管理</h1>
        <p>监控和管理所有已部署 Agent 的运行状态</p>
      </div>
      <div class="page-header-right">
        <button class="btn-primary" @click="showUpgradeDialog = true">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px;">
            <path d="M7 1v8M3 5l4 4 4-4"/>
          </svg>
          批量升级
        </button>
      </div>
    </div>

    <!-- Status Overview -->
    <div class="agent-stats-grid">
      <div class="mini-stat-card">
        <div class="mini-stat-dot online"></div>
        <div class="mini-stat-value">{{ agentsStore.stats.online }}</div>
        <div class="mini-stat-label">在线</div>
      </div>
      <div class="mini-stat-card">
        <div class="mini-stat-dot offline"></div>
        <div class="mini-stat-value">{{ agentsStore.stats.offline }}</div>
        <div class="mini-stat-label">离线</div>
      </div>
      <div class="mini-stat-card">
        <div class="mini-stat-dot error"></div>
        <div class="mini-stat-value">{{ agentsStore.stats.error }}</div>
        <div class="mini-stat-label">异常</div>
      </div>
      <div class="mini-stat-card">
        <div class="mini-stat-dot pending"></div>
        <div class="mini-stat-value">{{ agentsStore.stats.pending }}</div>
        <div class="mini-stat-label">等待</div>
      </div>
      <div class="mini-stat-card">
        <div style="width:8px;height:8px;border-radius:2px;background:var(--chart-color-6);"></div>
        <div class="mini-stat-value">{{ agentsStore.stats.avgCpu }}%</div>
        <div class="mini-stat-label">平均CPU</div>
      </div>
      <div class="mini-stat-card">
        <div style="width:8px;height:8px;border-radius:2px;background:var(--color-medium);"></div>
        <div class="mini-stat-value">{{ agentsStore.stats.avgMem }}%</div>
        <div class="mini-stat-label">平均内存</div>
      </div>
    </div>

    <!-- Agent List -->
    <div class="chart-card">
      <div class="alert-table-wrap">
        <table class="alert-table">
          <thead>
            <tr>
              <th>Agent</th>
              <th>IP 地址</th>
              <th>状态</th>
              <th>CPU</th>
              <th>内存</th>
              <th>磁盘</th>
              <th>版本</th>
              <th>系统</th>
              <th>标签</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="agent in agentsStore.agents" :key="agent.id" @click="showAgentDetail(agent)" style="cursor:pointer;">
              <td>
                <span class="agent-name-row">
                  <span :class="['status-pulse', agent.status]"></span>
                  <span class="alert-name">{{ agent.hostname }}</span>
                </span>
              </td>
              <td class="mono-cell">{{ agent.ip_address }}</td>
              <td><span :class="['status-tag', agentStatusTag(agent.status)]"><span class="dot"></span>{{ statusLabel(agent.status) }}</span></td>
              <td>
                <div class="progress-mini">
                  <div class="progress-bar" :class="cpuBarClass(agent.cpu_usage)" :style="{ width: agent.cpu_usage + '%' }"></div>
                </div>
                <span class="progress-text">{{ agent.cpu_usage }}%</span>
              </td>
              <td>
                <div class="progress-mini">
                  <div class="progress-bar" :class="memBarClass(agent.memory_usage)" :style="{ width: agent.memory_usage + '%' }"></div>
                </div>
                <span class="progress-text">{{ agent.memory_usage }}%</span>
              </td>
              <td>
                <div class="progress-mini">
                  <div class="progress-bar" :class="diskBarClass(agent.disk_usage)" :style="{ width: agent.disk_usage + '%' }"></div>
                </div>
                <span class="progress-text">{{ agent.disk_usage }}%</span>
              </td>
              <td class="mono-cell">{{ agent.agent_version }}</td>
              <td class="mono-cell">{{ agent.os_version }}</td>
              <td>
                <span v-for="tag in (agent.tags || [])" :key="tag" class="tag-pill">{{ tag }}</span>
              </td>
              <td @click.stop>
                <div class="action-group">
                  <button class="action-btn" @click="restartAgent(agent)">重启</button>
                  <button class="action-btn" @click="showAgentDetail(agent)">详情</button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- Detail Drawer -->
    <Teleport to="body">
      <div v-if="detailAgent" class="drawer-overlay" @click.self="closeDetail">
        <div class="drawer">
          <div class="drawer-header">
            <h2>{{ detailAgent.hostname }}</h2>
            <button class="drawer-close" @click="closeDetail">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="drawer-body">
            <div class="detail-section">
              <h3>基本信息</h3>
              <div class="detail-row"><span class="detail-label">Agent ID</span><span class="detail-value mono">{{ detailAgent.agent_id }}</span></div>
              <div class="detail-row"><span class="detail-label">IP 地址</span><span class="detail-value mono">{{ detailAgent.ip_address }}</span></div>
              <div class="detail-row"><span class="detail-label">状态</span><span :class="['status-tag', agentStatusTag(detailAgent.status)]"><span class="dot"></span>{{ statusLabel(detailAgent.status) }}</span></div>
              <div class="detail-row"><span class="detail-label">操作系统</span><span class="detail-value">{{ detailAgent.os_version }}</span></div>
              <div class="detail-row"><span class="detail-label">Agent 版本</span><span class="detail-value mono">{{ detailAgent.agent_version }}</span></div>
              <div class="detail-row"><span class="detail-label">CPU 核心</span><span class="detail-value">{{ detailAgent.cpu_cores }} 核</span></div>
              <div class="detail-row"><span class="detail-label">总内存</span><span class="detail-value">{{ formatMemory(detailAgent.memory_total) }}</span></div>
              <div class="detail-row"><span class="detail-label">进程数</span><span class="detail-value">{{ detailAgent.processes_total }}</span></div>
              <div class="detail-row"><span class="detail-label">最后心跳</span><span class="detail-value mono">{{ formatTime(detailAgent.last_heartbeat) }}</span></div>
            </div>

            <div class="detail-section">
              <h3>资源使用</h3>
              <div class="detail-row">
                <span class="detail-label">CPU 使用率</span>
                <div style="flex:1;margin:0 12px;">
                  <div class="progress-mini"><div class="progress-bar" :class="cpuBarClass(detailAgent.cpu_usage)" :style="{ width: detailAgent.cpu_usage + '%' }"></div></div>
                </div>
                <span class="detail-value mono">{{ detailAgent.cpu_usage }}%</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">内存使用率</span>
                <div style="flex:1;margin:0 12px;">
                  <div class="progress-mini"><div class="progress-bar" :class="memBarClass(detailAgent.memory_usage)" :style="{ width: detailAgent.memory_usage + '%' }"></div></div>
                </div>
                <span class="detail-value mono">{{ detailAgent.memory_usage }}%</span>
              </div>
              <div class="detail-row">
                <span class="detail-label">磁盘使用率</span>
                <div style="flex:1;margin:0 12px;">
                  <div class="progress-mini"><div class="progress-bar" :class="diskBarClass(detailAgent.disk_usage)" :style="{ width: detailAgent.disk_usage + '%' }"></div></div>
                </div>
                <span class="detail-value mono">{{ detailAgent.disk_usage }}%</span>
              </div>
            </div>

            <div class="detail-section">
              <h3>标签</h3>
              <div style="display:flex;flex-wrap:wrap;gap:6px;">
                <span v-for="tag in (detailAgent.tags || [])" :key="tag" class="tag-pill">{{ tag }}</span>
                <span v-if="!detailAgent.tags?.length" class="text-muted">无标签</span>
              </div>
            </div>

            <div class="detail-actions">
              <button class="btn-primary" @click="restartAgent(detailAgent)">远程重启</button>
              <button class="action-btn" @click="deployPolicyToAgent(detailAgent)">策略下发</button>
              <button class="action-btn" @click="openUpgradeDialogForAgent(detailAgent)">远程升级</button>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Upgrade Dialog -->
    <Teleport to="body">
      <div v-if="showUpgradeDialog" class="modal-overlay" @click.self="showUpgradeDialog = false">
        <div class="modal-dialog">
          <div class="modal-header">
            <h2>批量升级 Agent</h2>
            <button class="drawer-close" @click="showUpgradeDialog = false">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>目标版本</label>
              <select v-model="upgradeVersion" class="filter-select" style="width:100%;">
                <option value="" disabled>请选择版本</option>
                <option v-for="v in availableVersions" :key="v" :value="v">v{{ v }}</option>
              </select>
            </div>
            <div class="form-group">
              <label>升级范围</label>
              <div class="radio-group">
                <label class="radio-label"><input type="radio" v-model="upgradeScope" value="selected" checked /> 已选 Agent</label>
                <label class="radio-label"><input type="radio" v-model="upgradeScope" value="all" /> 所有 Agent</label>
                <label class="radio-label"><input type="radio" v-model="upgradeScope" value="online" /> 仅在线 Agent</label>
              </div>
            </div>
            <div class="form-group">
              <label>灰度比例</label>
              <div style="display:flex;align-items:center;gap:12px;">
                <input type="range" v-model.number="grayPercent" min="10" max="100" step="10" style="flex:1;accent-color:var(--color-accent-500);" />
                <span class="mono">{{ grayPercent }}%</span>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="action-btn" @click="showUpgradeDialog = false">取消</button>
            <button class="btn-primary" @click="startUpgrade">开始升级</button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Deploy Policy Dialog -->
    <Teleport to="body">
      <div v-if="showDeployPolicyDialog" class="modal-overlay" @click.self="closeDeployPolicyDialog">
        <div class="modal-dialog">
          <div class="modal-header">
            <h2>策略下发</h2>
            <button class="drawer-close" @click="closeDeployPolicyDialog">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <p style="font-size:var(--text-body-sm);color:var(--color-text-secondary);margin-bottom:var(--space-4);">
              将策略下发到 Agent：
              <span class="mono" style="color:var(--color-accent-500);">{{ deployAgent?.hostname }}</span>
            </p>
            <div class="form-group">
              <label>选择策略</label>
              <select v-model="deployPolicyForm.policyId" class="filter-select" style="width:100%;">
                <option value="">请选择策略</option>
                <option v-for="p in policyList" :key="p.id" :value="p.id">{{ p.name }}</option>
              </select>
            </div>
            <div class="form-group">
              <label class="radio-label" style="display:flex;align-items:center;gap:8px;">
                <input type="checkbox" v-model="deployPolicyForm.force" style="accent-color:var(--color-accent-500);" />
                强制下发（覆盖已有策略）
              </label>
            </div>
          </div>
          <div class="modal-footer">
            <button class="action-btn" @click="closeDeployPolicyDialog">取消</button>
            <button class="btn-primary" @click="confirmDeployPolicy" :disabled="deploying">
              {{ deploying ? '下发中...' : '确认下发' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAgentsStore } from '@/stores/agents'

defineOptions({ name: 'Agents' })
import { policiesApi } from '@/services/api/policies'
import { showToast } from '@/utils/toast'
import type { Agent, Policy } from '@/types'

const agentsStore = useAgentsStore()

const detailAgent = ref<Agent | null>(null)
const showUpgradeDialog = ref(false)
const upgradeVersion = ref('')
const upgradeScope = ref('selected')
const grayPercent = ref(30) // 保留合理默认值，生产环境应改为配置项

const availableVersions = computed(() => {
  const versions = new Set(agentsStore.agents.map(a => a.agent_version).filter(Boolean))
  return Array.from(versions).sort().reverse()
})

// Policy list for deploy dialog
const policyList = ref<Policy[]>([])
const deploying = ref(false)

function statusLabel(s: string) {
  const map: Record<string, string> = { online: '在线', offline: '离线', error: '异常', upgrading: '升级中', pending: '等待' }
  return map[s] || s
}

function agentStatusTag(s: string) {
  const map: Record<string, string> = {
    online: 'status-resolved',
    offline: 'status-pending',
    error: 'status-pending',
    upgrading: 'status-progress',
    pending: 'status-pending',
  }
  return map[s] || 'status-pending'
}

function cpuBarClass(v: number | undefined) { const n = v ?? 0; return n > 80 ? 'bar-critical' : n > 60 ? 'bar-warn' : 'bar-ok' }
function memBarClass(v: number | undefined) { const n = v ?? 0; return n > 80 ? 'bar-critical' : n > 60 ? 'bar-warn' : 'bar-ok' }
function diskBarClass(v: number | undefined) { const n = v ?? 0; return n > 85 ? 'bar-critical' : n > 70 ? 'bar-warn' : 'bar-ok' }

function formatMemory(mb?: number) {
  if (!mb) return '-'
  return mb >= 1024 ? `${(mb / 1024).toFixed(1)} GB` : `${mb} MB`
}

function formatTime(iso?: string) {
  if (!iso) return '--'
  return new Date(iso).toLocaleString('zh-CN')
}

function showAgentDetail(agent: Agent) {
  detailAgent.value = agent
}

function closeDetail() {
  detailAgent.value = null
}

function restartAgent(agent: Agent) {
  // confirm() is kept for confirmation dialogs
  if (confirm(`确认远程重启 ${agent.hostname} 的 Agent 服务？`)) {
    agentsStore.restartAgent(agent.agent_id)
  }
}

async function startUpgrade() {
  if (!upgradeVersion.value) {
    showToast('请选择升级版本', 'warning')
    return
  }
  try {
    const targetAgents = upgradeScope.value === 'selected'
      ? agentsStore.agents.filter(a => a.status !== 'offline' && a.status !== 'error').map(a => a.agent_id)
      : upgradeScope.value === 'online'
        ? agentsStore.agents.filter(a => a.status === 'online').map(a => a.agent_id)
        : agentsStore.agents.map(a => a.agent_id)

    if (targetAgents.length === 0) {
      showToast('没有可升级的 Agent', 'warning')
      return
    }
    await agentsStore.upgradeAgents(targetAgents, upgradeVersion.value)
    showToast(`已向 ${targetAgents.length} 个 Agent 下发升级任务 v${upgradeVersion.value}`, 'success')
    showUpgradeDialog.value = false
    await agentsStore.fetchAgents()
  } catch {
    showToast('升级任务下发失败', 'error')
  }
}

// ── Policy Deploy to Agent ──
const showDeployPolicyDialog = ref(false)
const deployAgent = ref<Agent | null>(null)
const deployPolicyForm = ref({
  policyId: '',
  force: false,
})

function deployPolicyToAgent(agent: Agent) {
  deployAgent.value = agent
  deployPolicyForm.value = { policyId: '', force: false }
  showDeployPolicyDialog.value = true
}

function closeDeployPolicyDialog() {
  showDeployPolicyDialog.value = false
  deployAgent.value = null
}

async function confirmDeployPolicy() {
  if (!deployPolicyForm.value.policyId || !deployAgent.value) {
    showToast('请选择要下发的策略', 'warning')
    return
  }
  deploying.value = true
  try {
    await policiesApi.deploy(deployPolicyForm.value.policyId, [deployAgent.value.agent_id], deployPolicyForm.value.force)
    showToast(`策略已成功下发到 Agent「${deployAgent.value.hostname}」`, 'success')
  } catch {
    showToast('策略下发失败，请检查后端服务', 'error')
  } finally {
    deploying.value = false
    closeDeployPolicyDialog()
  }
}

function openUpgradeDialogForAgent(agent: Agent) {
  upgradeScope.value = 'selected'
  // Set selected agents to just this one for the upgrade
  upgradeVersion.value = agent.agent_version === '3.2.1' ? '3.2.0' : '3.2.1'
  showUpgradeDialog.value = true
}

async function loadPolicies() {
  try {
    const res = await policiesApi.list()
    policyList.value = res.items
  } catch {
    // 真实数据失败：显示空状态，绝不使用假数据
    policyList.value = []
    showToast('策略列表加载失败，请检查后端服务', 'error')
  }
}

onMounted(() => {
  agentsStore.fetchAgents()
  loadPolicies()
})
</script>

<style scoped>
.page-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:var(--space-6); }
.page-header-left h1 { font-size:var(--text-h1); font-weight:var(--font-weight-bold); color:var(--color-text-primary); margin-bottom:var(--space-1); }
.page-header-left p { font-size:var(--text-body); color:var(--color-text-tertiary); }
.page-header-right { flex-shrink:0; }

.agent-stats-grid {
  display: grid;
  grid-template-columns: repeat(6, 1fr);
  gap: var(--space-4);
  margin-bottom: var(--space-6);
}

.mini-stat-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  text-align: center;
}

.mini-stat-dot {
  width: 10px;
  height: 10px;
  border-radius: 50%;
}

.mini-stat-dot.online { background: var(--color-status-online); }
.mini-stat-dot.offline { background: var(--color-status-offline); }
.mini-stat-dot.error { background: var(--color-status-error); }
.mini-stat-dot.pending { background: var(--color-status-pending); }

.mini-stat-value {
  font-size: var(--text-h3);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  font-family: var(--font-family-mono);
}

.mini-stat-label {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
}

.chart-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-5);
}

.alert-table-wrap { overflow-x: auto; }

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

.agent-name-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.status-pulse {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.status-pulse.online { background: var(--color-status-online); box-shadow: 0 0 6px var(--color-status-online); }
.status-pulse.offline { background: var(--color-status-offline); }
.status-pulse.error {
  background: var(--color-status-error);
  box-shadow: 0 0 6px var(--color-status-error);
  animation: pulseRing 2s ease-in-out infinite;
}
.status-pulse.upgrading { background: var(--color-status-pending); }
.status-pulse.pending { background: var(--color-status-pending); }

.alert-name { color: var(--color-text-primary); font-weight: var(--font-weight-medium); }

.progress-mini {
  width: 80px;
  height: 4px;
  background: var(--color-bg-elevated);
  border-radius: 2px;
  overflow: hidden;
  display: inline-block;
  vertical-align: middle;
}

.progress-bar {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}

.bar-ok { background: var(--color-low); }
.bar-warn { background: var(--color-medium); }
.bar-critical { background: var(--color-critical); }

.progress-text {
  font-family: var(--font-family-mono);
  font-size: var(--text-mono-sm);
  color: var(--color-text-tertiary);
  margin-left: 6px;
}

.mono-cell { font-family: var(--font-family-mono); font-size: var(--text-mono-sm); }

.tag-pill {
  display: inline-block;
  padding: 1px 6px;
  background: rgba(0, 188, 212, 0.1);
  color: var(--color-accent-500);
  border-radius: 4px;
  font-size: var(--text-label);
  margin: 1px;
}

.action-group { display: flex; gap: 4px; }

/* Drawer */
.drawer-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:var(--z-modal); display:flex; justify-content:flex-end; }
.drawer { width:460px; max-width:100vw; height:100%; background:var(--color-bg-surface); border-left:1px solid var(--color-border-default); display:flex; flex-direction:column; animation:slideInRight 0.25s ease; }
@keyframes slideInRight { from{transform:translateX(100%)} to{transform:translateX(0)} }
.drawer-header { display:flex; align-items:center; justify-content:space-between; padding:var(--space-5); border-bottom:1px solid var(--color-border-default); }
.drawer-header h2 { font-size:var(--text-h3); font-weight:var(--font-weight-semibold); color:var(--color-text-primary); }
.drawer-close { width:32px;height:32px;display:flex;align-items:center;justify-content:center;border-radius:8px;border:none;background:transparent;color:var(--color-text-secondary);cursor:pointer; }
.drawer-close:hover { background:var(--color-bg-hover); color:var(--color-text-primary); }
.drawer-close svg { width:18px;height:18px; }
.drawer-body { flex:1; overflow-y:auto; padding:var(--space-5); }
.detail-section { margin-bottom:var(--space-6); }
.detail-section h3 { font-size:var(--text-h4); font-weight:var(--font-weight-semibold); color:var(--color-text-primary); margin-bottom:var(--space-3); }
.detail-row { display:flex; justify-content:space-between; align-items:center; padding:var(--space-2) 0; border-bottom:1px solid var(--color-border-subtle); }
.detail-row:last-child { border-bottom:none; }
.detail-label { color:var(--color-text-tertiary); font-size:var(--text-body-sm); }
.detail-value { color:var(--color-text-primary); font-size:var(--text-body-sm); font-weight:var(--font-weight-medium); }
.detail-actions { display:flex; gap:var(--space-3); padding-top:var(--space-4); border-top:1px solid var(--color-border-default); }
.text-muted { color:var(--color-text-tertiary); }

/* Modal */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:var(--z-modal); display:flex; align-items:center; justify-content:center; }
.modal-dialog { width:480px; max-width:90vw; background:var(--color-bg-surface); border:1px solid var(--color-border-default); border-radius:16px; box-shadow:var(--shadow-xl); }
.modal-header { display:flex; align-items:center; justify-content:space-between; padding:var(--space-5); border-bottom:1px solid var(--color-border-default); }
.modal-header h2 { font-size:var(--text-h3); font-weight:var(--font-weight-semibold); color:var(--color-text-primary); }
.modal-body { padding:var(--space-5); }
.modal-footer { display:flex; gap:var(--space-3); justify-content:flex-end; padding:var(--space-5); border-top:1px solid var(--color-border-default); }
.form-group { margin-bottom:var(--space-5); }
.form-group label { display:block; font-size:var(--text-body-sm); font-weight:var(--font-weight-medium); color:var(--color-text-secondary); margin-bottom:var(--space-2); }
.radio-group { display:flex; flex-direction:column; gap:var(--space-2); }
.radio-label { display:flex; align-items:center; gap:var(--space-2); font-size:var(--text-body-sm); color:var(--color-text-primary); cursor:pointer; }
.radio-label input[type="radio"] { accent-color:var(--color-accent-500); }
.filter-select { height:34px; background:var(--color-bg-elevated); border:1px solid var(--color-border-subtle); border-radius:8px; padding:0 var(--space-3); color:var(--color-text-primary); font-size:var(--text-body-sm); font-family:inherit; outline:none; }
.filter-select:focus { border-color:var(--color-accent-500); }

@media (max-width: 1200px) {
  .agent-stats-grid { grid-template-columns: repeat(3, 1fr); }
}

@media (max-width: 768px) {
  .agent-stats-grid { grid-template-columns: repeat(2, 1fr); }
}
</style>