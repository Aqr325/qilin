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
        <button class="btn-primary" @click="openUserDialog()">
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
                    <button class="action-btn" @click="openUserDialog(user)">编辑</button>
                    <button class="action-btn" :class="{ 'text-danger': !user.is_active }" @click="toggleUserStatus(user)">
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
        <button class="btn-primary" @click="openRoleDialog()">新建角色</button>
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
            <button class="action-btn" @click="editRolePermissions(role)">编辑权限</button>
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
            <input v-model="auditKeyword" type="text" placeholder="搜索日志..." class="filter-search" @keyup.enter="searchAuditLogs" />
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
          <div class="table-info">共 {{ systemStore.auditLogsTotal }} 条记录</div>
          <div class="pagination">
            <button
              v-for="p in auditTotalPages"
              :key="p"
              class="page-btn"
              :class="{ active: auditCurrentPage === p }"
              @click="goToAuditPage(p)"
            >
              {{ p }}
            </button>
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

    <!-- User Dialog (Create/Edit) -->
    <Teleport to="body">
      <div v-if="showUserDialog" class="modal-overlay" @click.self="closeUserDialog">
        <div class="modal-dialog">
          <div class="modal-header">
            <h2>{{ editingUser ? '编辑用户' : '新建用户' }}</h2>
            <button class="drawer-close" @click="closeUserDialog">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>用户名</label>
              <input v-model="userForm.username" class="form-input" :disabled="!!editingUser" />
            </div>
            <div class="form-group">
              <label>显示名称</label>
              <input v-model="userForm.display_name" class="form-input" />
            </div>
            <div class="form-group">
              <label>邮箱</label>
              <input v-model="userForm.email" type="email" class="form-input" />
            </div>
            <div v-if="!editingUser" class="form-group">
              <label>初始密码</label>
              <input v-model="userForm.password" type="password" class="form-input" placeholder="至少8位" />
            </div>
            <div class="form-group">
              <label>角色</label>
              <select v-model="userForm.role" class="form-select">
                <option value="admin">系统管理员</option>
                <option value="operator">安全运维员</option>
                <option value="auditor">安全审计员</option>
                <option value="readonly">只读用户</option>
              </select>
            </div>
          </div>
          <div class="modal-footer">
            <button class="action-btn" @click="closeUserDialog">取消</button>
            <button class="btn-primary" @click="saveUser" :disabled="userSaving">
              {{ userSaving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- Role Dialog (Create/Edit Permissions) -->
    <Teleport to="body">
      <div v-if="showRoleDialog" class="modal-overlay" @click.self="closeRoleDialog">
        <div class="modal-dialog" style="max-width:560px;">
          <div class="modal-header">
            <h2>{{ editingRole ? '编辑权限' : '新建角色' }}</h2>
            <button class="drawer-close" @click="closeRoleDialog">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <div v-if="!editingRole" class="form-group">
              <label>角色名称</label>
              <input v-model="roleForm.name" class="form-input" placeholder="英文标识，如：admin" />
            </div>
            <div class="form-group">
              <label>显示名称</label>
              <input v-model="roleForm.display_name" class="form-input" />
            </div>
            <div class="form-group">
              <label>描述</label>
              <textarea v-model="roleForm.description" class="form-textarea" rows="2" placeholder="角色描述"></textarea>
            </div>
            <div class="form-group">
              <label>权限设置</label>
              <div class="perm-grid">
                <label v-for="perm in allPermissions" :key="perm.id" class="perm-checkbox">
                  <input type="checkbox" v-model="roleForm.permissions" :value="perm.id" />
                  <span>{{ perm.label }}</span>
                </label>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="action-btn" @click="closeRoleDialog">取消</button>
            <button class="btn-primary" @click="saveRole" :disabled="roleSaving">
              {{ roleSaving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useSystemStore, type SystemUser } from '@/stores/system'
import { systemApi, type SystemRole } from '@/services/api/system'
import { exportToCSV, timestampSuffix } from '@/utils/csv'
import { showToast } from '@/utils/toast'

defineOptions({ name: 'System' })

const systemStore = useSystemStore()
const activeTab = ref('users')
const auditKeyword = ref('')
const auditCurrentPage = ref(1)
const auditTotalPages = computed(() => Math.max(1, Math.ceil((systemStore.auditLogsTotal || 0) / 20)))

function searchAuditLogs() {
  auditCurrentPage.value = 1
  systemStore.fetchAuditLogs({ keyword: auditKeyword.value, page: 1 })
}

function goToAuditPage(page: number) {
  auditCurrentPage.value = page
  systemStore.fetchAuditLogs({ keyword: auditKeyword.value, page })
}

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
    showToast('系统设置已保存', 'success')
  } catch {
    // Surface the failure so the user knows the edit was not persisted
    showToast('系统设置保存失败，请检查网络或后端服务', 'error')
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

// ── User Dialog ──
const showUserDialog = ref(false)
const editingUser = ref<SystemUser | null>(null)
const userSaving = ref(false)
const userForm = ref({
  username: '',
  display_name: '',
  email: '',
  password: '',
  role: 'readonly',
})

function openUserDialog(user?: any) {
  if (user) {
    editingUser.value = user
    userForm.value = {
      username: user.username,
      display_name: user.display_name,
      email: user.email,
      password: '',
      role: user.role || 'readonly',
    }
  } else {
    editingUser.value = null
    userForm.value = { username: '', display_name: '', email: '', password: '', role: 'readonly' }
  }
  showUserDialog.value = true
}

function closeUserDialog() {
  showUserDialog.value = false
  editingUser.value = null
}

async function saveUser() {
  if (!userForm.value.username || !userForm.value.display_name) {
    showToast('请填写用户名和显示名称', 'warning')
    return
  }
  if (!editingUser.value && (!userForm.value.password || userForm.value.password.length < 8)) {
    showToast('密码长度至少8位', 'warning')
    return
  }
  userSaving.value = true
  try {
    if (editingUser.value) {
      await systemApi.updateUser(editingUser.value.id, {
        display_name: userForm.value.display_name,
        email: userForm.value.email,
        role: userForm.value.role,
      })
    } else {
      await systemApi.createUser({
        username: userForm.value.username,
        display_name: userForm.value.display_name,
        email: userForm.value.email,
        password: userForm.value.password,
        role: userForm.value.role,
      } as any)
    }
    await systemStore.fetchUsers()
    closeUserDialog()
  } catch {
    // API not available, optimistic update
    if (editingUser.value) {
      const u = systemStore.users.find(u => u.id === editingUser.value!.id)
      if (u) {
        u.display_name = userForm.value.display_name
        u.email = userForm.value.email
        u.role = userForm.value.role
        // Also update roles array so the table display reflects the change
        const roleMap: Record<string, { name: string; display_name: string }> = {
          admin: { name: 'admin', display_name: '系统管理员' },
          operator: { name: 'operator', display_name: '安全运维员' },
          auditor: { name: 'auditor', display_name: '安全审计员' },
          readonly: { name: 'readonly', display_name: '只读用户' },
        }
        u.roles = [roleMap[userForm.value.role] || { name: userForm.value.role, display_name: userForm.value.role }]
      }
    } else {
      systemStore.users.push({
        id: 'user-' + Date.now(),
        username: userForm.value.username,
        display_name: userForm.value.display_name,
        email: userForm.value.email,
        role: userForm.value.role,
        is_active: true,
        mfa_enabled: false,
        last_login: undefined,
        created_at: new Date().toISOString(),
      })
    }
    closeUserDialog()
  } finally {
    userSaving.value = false
  }
}

async function toggleUserStatus(user: SystemUser) {
  const newStatus = !user.is_active
  try {
    await systemApi.toggleUserStatus(user.id, newStatus)
    await systemStore.fetchUsers()
  } catch {
    user.is_active = newStatus
  }
}

// ── Role Dialog ──
const showRoleDialog = ref(false)
const editingRole = ref<SystemRole | null>(null)
const roleSaving = ref(false)
const roleForm = ref({
  name: '',
  display_name: '',
  description: '',
  permissions: [] as string[],
})

const allPermissions = [
  { id: 'alert:read', label: '告警查看' },
  { id: 'alert:write', label: '告警处置' },
  { id: 'agent:read', label: 'Agent 查看' },
  { id: 'agent:write', label: 'Agent 管理' },
  { id: 'policy:read', label: '策略查看' },
  { id: 'policy:write', label: '策略配置' },
  { id: 'policy:deploy', label: '策略下发' },
  { id: 'user:write', label: '用户管理' },
  { id: 'role:write', label: '角色管理' },
  { id: 'audit:read', label: '审计日志' },
  { id: 'system:write', label: '系统设置' },
  { id: 'ai:chat', label: 'AI 对话' },
]

function openRoleDialog() {
  editingRole.value = null
  roleForm.value = { name: '', display_name: '', description: '', permissions: [] }
  showRoleDialog.value = true
}

function editRolePermissions(role: SystemRole) {
  editingRole.value = role
  roleForm.value = {
    name: role.name,
    display_name: role.display_name,
    description: role.description,
    permissions: role.permissions || [],
  }
  showRoleDialog.value = true
}

function closeRoleDialog() {
  showRoleDialog.value = false
  editingRole.value = null
}

async function saveRole() {
  if (!roleForm.value.display_name) {
    showToast('请填写角色显示名称', 'warning')
    return
  }
  if (!editingRole.value && !roleForm.value.name) {
    showToast('请填写角色名称', 'warning')
    return
  }
  roleSaving.value = true
  try {
    if (editingRole.value) {
      await systemApi.updateRole(editingRole.value.id, {
        display_name: roleForm.value.display_name,
        description: roleForm.value.description,
        permission_ids: roleForm.value.permissions,
      })
    } else {
      await systemApi.createRole({
        name: roleForm.value.name,
        display_name: roleForm.value.display_name,
        description: roleForm.value.description,
        permission_ids: roleForm.value.permissions,
      })
    }
    await systemStore.fetchRoles()
    closeRoleDialog()
  } catch {
    // API not available, optimistic update
    if (editingRole.value) {
      const r = systemStore.roles.find(r => r.id === editingRole.value!.id)
      if (r) {
        r.display_name = roleForm.value.display_name
        r.description = roleForm.value.description
        r.permission_count = roleForm.value.permissions.length
      }
    } else {
      systemStore.roles.push({
        id: 'role-' + Date.now(),
        name: roleForm.value.name,
        display_name: roleForm.value.display_name,
        description: roleForm.value.description,
        permission_count: roleForm.value.permissions.length,
        permissions: roleForm.value.permissions,
      })
    }
    closeRoleDialog()
  } finally {
    roleSaving.value = false
  }
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

/* ── Dialogs ── */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.6);
  z-index: var(--z-modal);
  display: flex;
  align-items: center;
  justify-content: center;
}

.modal-dialog {
  width: 440px;
  max-width: 90vw;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 16px;
  box-shadow: var(--shadow-xl);
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5);
  border-bottom: 1px solid var(--color-border-default);
}

.modal-header h2 {
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

.modal-body { padding: var(--space-5); }
.modal-footer {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
  padding: var(--space-5);
  border-top: 1px solid var(--color-border-default);
}

.form-group { margin-bottom: var(--space-4); }
.form-group label {
  display: block;
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.form-input {
  height: 38px;
  width: 100%;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
}

.form-input:focus { border-color: var(--color-accent-500); }
.form-input:disabled { opacity: 0.5; cursor: not-allowed; }

.form-select {
  height: 38px;
  width: 100%;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
}

.form-select:focus { border-color: var(--color-accent-500); }
.form-select option { background: var(--color-bg-surface); color: var(--color-text-primary); }

.form-textarea {
  width: 100%;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
  resize: vertical;
}

.form-textarea:focus { border-color: var(--color-accent-500); }

/* Permission Grid */
.perm-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-4);
  max-height: 200px;
  overflow-y: auto;
  padding: var(--space-3);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  background: var(--color-bg-elevated);
}

.perm-checkbox {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  cursor: pointer;
}

.perm-checkbox input[type="checkbox"] {
  accent-color: var(--color-accent-500);
  width: 14px;
  height: 14px;
}
</style>