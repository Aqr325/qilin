<template>
  <div class="system-view">
    <div class="page-header">
      <div class="page-header-left">
        <h1>系统管理</h1>
        <p>用户管理、角色权限配置与操作审计</p>
      </div>
    </div>

    <!-- Tabs -->
    <div class="tab-bar">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        :class="['tab-btn', { active: activeTab === tab.key }]"
        @click="activeTab = tab.key"
      >
        {{ tab.label }}
      </button>
    </div>

    <!-- Users Tab -->
    <div v-if="activeTab === 'users'" class="tab-content">
      <div class="section-header">
        <h2 class="section-title">用户管理</h2>
        <button class="btn-primary">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px;">
            <path d="M7 1v12M1 7h12"/>
          </svg>
          新建用户
        </button>
      </div>
      <div class="chart-card">
        <div class="alert-table-wrap">
          <table class="alert-table">
            <thead>
              <tr>
                <th>用户名</th>
                <th>显示名称</th>
                <th>邮箱</th>
                <th>角色</th>
                <th>状态</th>
                <th>MFA</th>
                <th>最后登录</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="user in systemStore.users" :key="user.id">
                <td><span class="alert-name mono">{{ user.username }}</span></td>
                <td>{{ user.display_name }}</td>
                <td class="mono-cell">{{ user.email }}</td>
                <td><span class="role-tag">{{ (user.roles?.length ? user.roles.map(r => r.display_name || r.name).join(', ') : user.role) || '—' }}</span></td>
                <td>
                  <span :class="['badge', user.is_active ? 'badge-low' : 'badge-medium']">
                    {{ user.is_active ? '启用' : '禁用' }}
                  </span>
                </td>
                <td>
                  <span :class="['badge', user.mfa_enabled ? 'badge-info' : 'badge-medium']">
                    {{ user.mfa_enabled ? '已启用' : '未启用' }}
                  </span>
                </td>
                <td class="mono-cell time-cell">{{ formatTime(user.last_login) }}</td>
                <td>
                  <div class="action-group">
                    <button class="action-btn">编辑</button>
                    <button class="action-btn" :class="{ 'text-danger': !user.is_active }">
                      {{ user.is_active ? '禁用' : '启用' }}
                    </button>
                  </div>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Roles Tab -->
    <div v-if="activeTab === 'roles'" class="tab-content">
      <div class="section-header">
        <h2 class="section-title">角色权限</h2>
        <button class="btn-primary">新建角色</button>
      </div>
      <div class="roles-grid">
        <div v-for="role in systemStore.roles" :key="role.id" class="role-card">
          <div class="role-card-header">
            <div class="role-avatar" :class="'role-' + role.name">{{ role.display_name.charAt(0) }}</div>
            <div>
              <div class="role-name">{{ role.display_name }}</div>
              <div class="role-badge">{{ role.name }}</div>
            </div>
            <div class="role-perm-count">{{ role.permission_count }} 权限</div>
          </div>
          <p class="role-desc">{{ role.description }}</p>
          <div class="role-actions">
            <button class="action-btn">编辑权限</button>
          </div>
        </div>
      </div>

      <div class="section-header" style="margin-top:var(--space-8);">
        <h2 class="section-title">权限矩阵</h2>
      </div>
      <div class="chart-card">
        <div class="alert-table-wrap">
          <table class="alert-table perm-table">
            <thead>
              <tr>
                <th>权限</th>
                <th>系统管理员</th>
                <th>安全运维员</th>
                <th>安全审计员</th>
                <th>只读用户</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="row in permMatrix" :key="row.action">
                <td class="perm-action">{{ row.action }}</td>
                <td v-for="(val, idx) in row.roles" :key="idx">
                  <span :class="['perm-dot', val ? 'perm-yes' : 'perm-no']"></span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- Audit Logs Tab -->
    <div v-if="activeTab === 'audit'" class="tab-content">
      <div class="section-header">
        <h2 class="section-title">操作审计日志</h2>
        <div style="display:flex;gap:var(--space-3);">
          <div class="search-input-wrap">
            <svg class="search-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
              <circle cx="7" cy="7" r="4.5"/><path d="M10.5 10.5L14 14"/>
            </svg>
            <input v-model="auditKeyword" type="text" placeholder="搜索日志..." class="filter-search" />
          </div>
          <button class="action-btn" @click="exportAuditLogs">
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px;">
              <path d="M2 4h10M2 7h10M2 10h7"/>
            </svg>
            导出
          </button>
        </div>
      </div>
      <div class="chart-card">
        <div class="alert-table-wrap">
          <table class="alert-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>操作人</th>
                <th>操作</th>
                <th>资源类型</th>
                <th>资源名称</th>
                <th>来源 IP</th>
                <th>结果</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="log in systemStore.auditLogs" :key="log.id">
                <td class="mono-cell time-cell">{{ formatTime(log.created_at) }}</td>
                <td><span class="alert-name">{{ log.username }}</span></td>
                <td><span class="action-label">{{ actionLabel(log.action) }}</span></td>
                <td class="mono-cell">{{ log.resource_type }}</td>
                <td>{{ log.resource_name || '-' }}</td>
                <td class="mono-cell">{{ log.ip_address || '-' }}</td>
                <td>
                  <span :class="['badge', log.result === 'success' ? 'badge-low' : 'badge-critical']">
                    {{ log.result === 'success' ? '成功' : '失败' }}
                  </span>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
        <div class="table-footer">
          <div class="table-info">共 {{ systemStore.auditLogs.length }} 条记录</div>
          <div class="pagination">
            <button class="page-btn active">1</button>
            <button class="page-btn">2</button>
            <button class="page-btn">3</button>
          </div>
        </div>
      </div>
    </div>

    <!-- Settings Tab -->
    <div v-if="activeTab === 'settings'" class="tab-content">
      <div class="section-header">
        <h2 class="section-title">系统设置</h2>
        <button class="btn-primary" @click="saveSettings" :disabled="settingsLoading">
          {{ settingsLoading ? '保存中...' : '保存设置' }}
        </button>
      </div>
      <div class="chart-card">
        <div class="settings-grid">
          <div class="setting-item">
            <label class="setting-label">密码最小长度</label>
            <input v-model.number="settingsForm.password_min_length" type="number" min="8" max="32" class="setting-input" />
          </div>
          <div class="setting-item">
            <label class="setting-label">密码过期天数</label>
            <input v-model.number="settingsForm.password_expire_days" type="number" min="30" max="365" class="setting-input" />
          </div>
          <div class="setting-item">
            <label class="setting-label">会话超时（分钟）</label>
            <input v-model.number="settingsForm.session_timeout_minutes" type="number" min="15" max="1440" class="setting-input" />
          </div>
          <div class="setting-item">
            <label class="setting-label">告警自动解决（小时）</label>
            <input v-model.number="settingsForm.alert_auto_resolve_hours" type="number" min="1" max="720" class="setting-input" />
          </div>
          <div class="setting-item">
            <label class="setting-label">心跳超时（秒）</label>
            <input v-model.number="settingsForm.heartbeat_timeout_seconds" type="number" min="10" max="120" class="setting-input" />
          </div>
          <div class="setting-item">
            <label class="setting-label">最大登录尝试</label>
            <input v-model.number="settingsForm.max_login_attempts" type="number" min="3" max="20" class="setting-input" />
          </div>
          <div class="setting-item">
            <label class="setting-label">锁定持续时间（分钟）</label>
            <input v-model.number="settingsForm.lockout_duration_minutes" type="number" min="1" max="1440" class="setting-input" />
          </div>
          <div class="setting-item toggle-item">
            <label class="setting-label">AI 自动分析</label>
            <label class="toggle-switch">
              <input type="checkbox" v-model="settingsForm.ai_auto_analysis" />
              <span class="toggle-slider"></span>
            </label>
          </div>
          <div class="setting-item toggle-item">
            <label class="setting-label">通知推送</label>
            <label class="toggle-switch">
              <input type="checkbox" v-model="settingsForm.notification_enabled" />
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useSystemStore } from '@/stores/system'
import { systemApi } from '@/services/api/system'
import { exportToCSV, timestampSuffix } from '@/utils/csv'

const systemStore = useSystemStore()
const activeTab = ref('users')
const auditKeyword = ref('')

const tabs = [
  { key: 'users', label: '用户管理' },
  { key: 'roles', label: '角色权限' },
  { key: 'audit', label: '审计日志' },
  { key: 'settings', label: '系统设置' },
]

// ── Settings ──
const settingsForm = ref({
  password_min_length: 12,
  password_expire_days: 90,
  session_timeout_minutes: 60,
  alert_auto_resolve_hours: 72,
  heartbeat_timeout_seconds: 30,
  max_login_attempts: 5,
  lockout_duration_minutes: 15,
  ai_auto_analysis: true,
  notification_enabled: true,
})
const settingsLoading = ref(false)

async function fetchSettings() {
  try {
    const res = await systemApi.settings()
    Object.assign(settingsForm.value, res)
  } catch {
    // use defaults
  }
}

async function saveSettings() {
  settingsLoading.value = true
  try {
    await systemApi.updateSettings(settingsForm.value)
  } catch {
    // silently fail
  } finally {
    settingsLoading.value = false
  }
}

function exportAuditLogs() {
  const columns = [
    { key: 'created_at', label: '时间' },
    { key: 'username', label: '操作人' },
    { key: 'action', label: '操作' },
    { key: 'resource_type', label: '资源类型' },
    { key: 'resource_name', label: '资源名称' },
    { key: 'ip_address', label: '来源 IP' },
    { key: 'result', label: '结果' },
  ]
  exportToCSV(systemStore.auditLogs, columns, `审计日志导出_${timestampSuffix()}.csv`)
}

const permMatrix = [
  { action: '告警查看', roles: [true, true, true, true] },
  { action: '告警处置', roles: [true, true, false, false] },
  { action: 'Agent 查看', roles: [true, true, true, true] },
  { action: 'Agent 管理', roles: [true, true, false, false] },
  { action: '策略配置', roles: [true, true, false, false] },
  { action: '策略下发', roles: [true, true, false, false] },
  { action: '用户管理', roles: [true, false, false, false] },
  { action: '角色管理', roles: [true, false, false, false] },
  { action: '审计日志', roles: [true, false, true, false] },
  { action: '系统设置', roles: [true, false, false, false] },
  { action: 'AI 对话', roles: [true, true, false, false] },
]

function actionLabel(action: string) {
  const map: Record<string, string> = {
    create: '创建', update: '更新', delete: '删除',
    action: '操作', login: '登录', export: '导出',
  }
  return map[action] || action
}

function formatTime(iso?: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

onMounted(async () => {
  await Promise.all([
    systemStore.fetchUsers(),
    systemStore.fetchRoles(),
    systemStore.fetchAuditLogs(),
    fetchSettings(),
  ])
})
</script>

<style scoped>
.page-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:var(--space-6); }
.page-header-left h1 { font-size:var(--text-h1); font-weight:var(--font-weight-bold); color:var(--color-text-primary); margin-bottom:var(--space-1); }
.page-header-left p { font-size:var(--text-body); color:var(--color-text-tertiary); }

.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-border-default);
}

.tab-btn {
  padding: var(--space-3) var(--space-5);
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-text-tertiary);
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover { color: var(--color-text-secondary); background: var(--color-bg-hover); }
.tab-btn.active { color: var(--color-accent-500); border-bottom-color: var(--color-accent-500); }

.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
}

.section-title {
  font-size: var(--text-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
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

.alert-name { color: var(--color-text-primary); font-weight: var(--font-weight-medium); }
.mono-cell { font-family: var(--font-family-mono); font-size: var(--text-mono-sm); }
.time-cell { white-space: nowrap; }
.mono { font-family: var(--font-family-mono); }

.action-group { display: flex; gap: 4px; }
.text-danger { color: var(--color-critical); }

.role-tag {
  display: inline-block;
  padding: 1px 8px;
  background: rgba(124, 77, 255, 0.12);
  color: var(--color-accent-purple);
  border-radius: 4px;
  font-size: var(--text-caption);
  font-weight: var(--font-weight-medium);
}

.action-label {
  font-size: var(--text-body-sm);
  color: var(--color-text-primary);
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
}

.filter-search:focus { border-color: var(--color-accent-500); }

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4) 0;
}

.table-info { font-size: var(--text-caption); color: var(--color-text-tertiary); }

.pagination { display: flex; align-items: center; gap: 2px; }

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
}

.page-btn:hover { background: var(--color-bg-hover); color: var(--color-text-primary); border-color: var(--color-border-default); }
.page-btn.active { background: rgba(0, 188, 212, 0.12); border-color: var(--color-accent-500); color: var(--color-accent-500); }

/* Roles Grid */
.roles-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-5);
}

.role-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-5);
  transition: all 0.25s ease;
}

.role-card:hover { border-color: rgba(0, 188, 212, 0.15); box-shadow: var(--shadow-card-hover); }

.role-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.role-avatar {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-h4);
  font-weight: var(--font-weight-bold);
  color: #fff;
  flex-shrink: 0;
}

.role-admin { background: linear-gradient(135deg, var(--color-critical), #D32F2F); }
.role-operator { background: linear-gradient(135deg, var(--color-accent-500), var(--color-accent-600)); }
.role-auditor { background: linear-gradient(135deg, var(--color-accent-purple), #651FFF); }
.role-readonly { background: linear-gradient(135deg, var(--color-text-tertiary), #455A64); }

.role-name { font-size: var(--text-h4); font-weight: var(--font-weight-semibold); color: var(--color-text-primary); }

.role-badge {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  font-family: var(--font-family-mono);
}

.role-perm-count {
  margin-left: auto;
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  background: var(--color-bg-elevated);
  padding: 2px 8px;
  border-radius: 4px;
}

.role-desc {
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-4);
  line-height: 1.5;
}

.role-actions { padding-top: var(--space-3); border-top: 1px solid var(--color-border-subtle); }

/* Permission Matrix */
.perm-table tbody td { text-align: center; }
.perm-action {
  color: var(--color-text-primary) !important;
  font-weight: var(--font-weight-medium);
  text-align: left !important;
}

.perm-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.perm-yes { background: var(--color-low); }
.perm-no { background: var(--color-bg-elevated); }

/* ── Settings ── */
.settings-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-5);
}

.setting-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.setting-label {
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.setting-input {
  height: 36px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
  max-width: 200px;
}

.setting-input:focus { border-color: var(--color-accent-500); }

.toggle-item {
  flex-direction: row;
  align-items: center;
  justify-content: space-between;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
  cursor: pointer;
}

.toggle-switch input { opacity: 0; width: 0; height: 0; }

.toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 22px;
  transition: all 0.3s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 2px;
  bottom: 2px;
  background: var(--color-text-tertiary);
  border-radius: 50%;
  transition: all 0.3s;
}

.toggle-switch input:checked + .toggle-slider {
  background: rgba(0, 188, 212, 0.2);
  border-color: var(--color-accent-500);
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(18px);
  background: var(--color-accent-500);
}

@media (max-width: 768px) {
  .roles-grid { grid-template-columns: 1fr; }
}
</style>