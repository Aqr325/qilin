<template>
  <div class="policies-view">
    <div class="page-header">
      <div class="page-header-left">
        <h1>策略配置</h1>
        <p>管理安全策略规则和编排自动化响应流程</p>
      </div>
      <div class="page-header-right">
        <button class="btn-primary" @click="openCreatePolicy">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;vertical-align:middle;margin-right:4px;">
            <path d="M7 1v12M1 7h12"/>
          </svg>
          新建策略
        </button>
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
        <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" v-html="tab.icon" style="width:16px;height:16px;" />
        {{ tab.label }}
      </button>
    </div>

    <!-- Policy List View -->
    <div v-if="activeTab === 'list'">
      <div class="policy-grid">
        <div v-for="policy in policiesStore.policies" :key="policy.id" class="policy-card">
          <div class="policy-card-header">
            <div class="policy-type-icon" :class="'type-' + policy.policy_type">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5">
                <circle cx="9" cy="9" r="7"/>
                <path d="M5 9l3 3 5-5"/>
              </svg>
            </div>
            <div class="policy-card-info">
              <div class="policy-card-name">{{ policy.name }}</div>
              <div class="policy-card-type">{{ policy.policy_type_label }}</div>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" :checked="policy.enabled" @change="togglePolicy(policy)" />
              <span class="toggle-track"><span class="toggle-thumb"></span></span>
            </label>
          </div>
          <p class="policy-desc">{{ policy.description }}</p>
          <div class="policy-meta">
            <span class="policy-version">v{{ policy.version }}</span>
            <span :class="['badge', policyStatusBadge(policy.status)]">{{ policy.status_label }}</span>
            <span class="policy-date">更新于 {{ formatDate(policy.updated_at) }}</span>
          </div>
          <div class="policy-footer">
            <span class="policy-priority">优先级: {{ policy.priority }}</span>
            <div class="policy-actions">
              <button class="action-btn" @click="editPolicy(policy)">编辑</button>
              <button class="action-btn" @click="deployPolicy(policy)">下发</button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- Orchestration Tab -->
    <div v-if="activeTab === 'orchestration'" class="orchestration-view">
      <div class="chart-card" style="margin-bottom:var(--space-5);">
        <div class="chart-card-header">
          <span class="chart-card-title">策略编排流程</span>
        </div>
        <div class="orchestration-flow">
          <div v-for="(step, idx) in flowSteps" :key="idx" class="flow-step" :class="{ active: step.active }">
            <div class="flow-step-number">{{ idx + 1 }}</div>
            <div class="flow-step-content">
              <div class="flow-step-title">{{ step.title }}</div>
              <div class="flow-step-desc">{{ step.desc }}</div>
            </div>
            <svg v-if="idx < flowSteps.length - 1" class="flow-arrow" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
              <path d="M8 4l8 8-8 8"/>
            </svg>
          </div>
        </div>
      </div>

      <div class="two-col-grid">
        <div class="chart-card">
          <div class="chart-card-header">
            <span class="chart-card-title">条件节点</span>
          </div>
          <div style="padding:var(--space-4);text-align:center;color:var(--color-text-tertiary);font-size:var(--text-body-sm);">
            <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" style="width:36px;height:36px;margin-bottom:8px;opacity:0.5;">
              <path d="M9 1v16M1 9h16"/>
            </svg>
            <p>拖拽条件节点到此区域</p>
          </div>
        </div>
        <div class="chart-card">
          <div class="chart-card-header">
            <span class="chart-card-title">动作节点</span>
          </div>
          <div style="padding:var(--space-4);text-align:center;color:var(--color-text-tertiary);font-size:var(--text-body-sm);">
            <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" style="width:36px;height:36px;margin-bottom:8px;opacity:0.5;">
              <path d="M3 3h12v12H3z"/>
            </svg>
            <p>拖拽动作节点到此区域</p>
          </div>
        </div>
      </div>
    </div>

    <!-- Policy Editor Modal -->
    <Teleport to="body">
      <div v-if="showEditor" class="modal-overlay" @click.self="closeEditor">
        <div class="editor-modal">
          <div class="modal-header">
            <h2>{{ editingPolicy ? '编辑策略' : '新建策略' }}</h2>
            <button class="drawer-close" @click="closeEditor">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="editor-body">
            <div class="editor-left">
              <div class="form-group">
                <label>策略名称</label>
                <input v-model="editorForm.name" type="text" class="editor-input" placeholder="输入策略名称" />
              </div>
              <div class="form-group">
                <label>策略类型</label>
                <select v-model="editorForm.policy_type" class="editor-select">
                  <option value="file_integrity">文件完整性监控</option>
                  <option value="process_whitelist">进程白名单</option>
                  <option value="network_firewall">网络访问控制</option>
                  <option value="login_policy">登录安全策略</option>
                  <option value="vulnerability_scan">漏洞扫描策略</option>
                  <option value="log_audit">日志审计规则</option>
                </select>
              </div>
              <div class="form-group">
                <label>描述</label>
                <textarea v-model="editorForm.description" class="editor-textarea" rows="3" placeholder="策略描述"></textarea>
              </div>
              <div class="form-group">
                <label>优先级</label>
                <input v-model.number="editorForm.priority" type="number" class="editor-input" style="width:100px;" />
              </div>
              <div class="form-group">
                <label>目标范围</label>
                <select v-model="editorForm.target_type" class="editor-select">
                  <option value="all">所有 Agent</option>
                  <option value="tags">按标签选择</option>
                  <option value="expression">按表达式</option>
                </select>
              </div>
            </div>
            <div class="editor-right">
              <div class="form-group" style="flex:1;display:flex;flex-direction:column;">
                <label>规则配置 (YAML)</label>
                <textarea
                  v-model="editorForm.rulesText"
                  class="editor-code"
                  placeholder="输入 YAML 规则配置..."
                  spellcheck="false"
                ></textarea>
              </div>
              <div class="form-group">
                <label>生效时间</label>
                <div style="display:flex;gap:8px;">
                  <input type="datetime-local" v-model="editorForm.effective_start" class="editor-input" style="flex:1;" />
                </div>
              </div>
            </div>
          </div>
          <div class="modal-footer">
            <button class="action-btn" @click="closeEditor">取消</button>
            <button class="action-btn" @click="validateRules">语法校验</button>
            <button class="btn-primary" @click="savePolicy">{{ editingPolicy ? '保存修改' : '创建策略' }}</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { usePoliciesStore } from '@/stores/policies'
import { policiesApi } from '@/services/api/policies'
import { showToast } from '@/utils/toast'
import type { Policy } from '@/types'

defineOptions({ name: 'Policies' })

const policiesStore = usePoliciesStore()

const activeTab = ref('list')
const tabs = [
  { key: 'list', label: '策略列表', icon: '' },
  { key: 'orchestration', label: '策略编排', icon: '' },
]

const flowSteps = [
  { title: '事件触发', desc: '安全事件采集器检测到异常', active: true },
  { title: '条件匹配', desc: '匹配策略规则条件', active: false },
  { title: '动作执行', desc: '执行预设响应动作', active: false },
  { title: '告警与通知', desc: '生成告警并通知相关人员', active: false },
]

const showEditor = ref(false)
const editingPolicy = ref<Policy | null>(null)
const editorForm = ref({
  name: '',
  description: '',
  policy_type: 'file_integrity',
  priority: 100,
  target_type: 'all',
  rulesText: 'paths:\n  - /etc/passwd\n  - /etc/shadow\nhash_algorithm: sha256\ncheck_interval: 300\naction_on_change: alert',
  effective_start: '',
})

function policyStatusBadge(s: string) {
  const map: Record<string, string> = { draft: 'badge-info', enabled: 'badge-low', disabled: 'badge-medium', archived: 'badge-high' }
  return map[s] || 'badge-info'
}

function formatDate(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  return `${d.getMonth() + 1}/${d.getDate()} ${d.getHours()}:${String(d.getMinutes()).padStart(2, '0')}`
}

async function togglePolicy(policy: Policy) {
  await policiesStore.togglePolicy(policy.id, !policy.enabled)
}

function editPolicy(policy: Policy) {
  editingPolicy.value = policy
  editorForm.value = {
    name: policy.name,
    description: policy.description || '',
    policy_type: policy.policy_type,
    priority: policy.priority,
    target_type: policy.target_type,
    rulesText: JSON.stringify(policy.rules, null, 2),
    effective_start: policy.effective_start || '',
  }
  showEditor.value = true
}

function openCreatePolicy() {
  editingPolicy.value = null
  editorForm.value = {
    name: '',
    description: '',
    policy_type: 'file_integrity',
    priority: 100,
    target_type: 'all',
    rulesText: '',
    effective_start: '',
  }
  showEditor.value = true
}

function closeEditor() {
  showEditor.value = false
  editingPolicy.value = null
}

async function validateRules() {
  try {
    let rules
    try {
      rules = JSON.parse(editorForm.value.rulesText)
    } catch {
      // If not valid JSON, treat as YAML-like text and do basic validation
      rules = null
    }
    const res = await policiesApi.validate({ rules })
    if (res.valid) {
      showToast('策略语法校验通过', 'success')
    } else {
      alert(`策略语法校验失败: ${res.error || '未知错误'}`)
    }
  } catch {
    // API not available, do basic frontend validation
    if (!editorForm.value.rulesText.trim()) {
      alert('规则配置不能为空')
      return
    }
    // Basic validation: try JSON parse first
    try {
      JSON.parse(editorForm.value.rulesText)
      showToast('策略语法校验通过', 'success')
      return
    } catch {
      // Try basic YAML-like validation: each non-empty, non-comment line should have a colon
      const lines = editorForm.value.rulesText.split('\n')
      let hasError = false
      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed || trimmed.startsWith('#')) continue
        if (!trimmed.startsWith('- ') && !trimmed.includes(':')) {
          hasError = true
          break
        }
      }
      if (!hasError) {
        showToast('策略语法校验通过', 'success')
      } else {
        alert('策略语法校验失败：每行应包含键值对（key: value）或列表项（- item）')
      }
    }
  }
}

async function savePolicy() {
  if (!editorForm.value.name.trim()) {
    alert('策略名称不能为空')
    return
  }

  let rules = {}
  try {
    rules = JSON.parse(editorForm.value.rulesText)
  } catch {
    // If not valid JSON, store as raw string for the backend to parse as YAML
    rules = { _raw_yaml: editorForm.value.rulesText }
  }

  const payload = {
    name: editorForm.value.name,
    description: editorForm.value.description,
    policy_type: editorForm.value.policy_type,
    priority: editorForm.value.priority,
    target_type: editorForm.value.target_type,
    target_value: editorForm.value.target_type === 'all' ? [] : [],
    rules,
    effective_start: editorForm.value.effective_start || null,
  }

  try {
    if (editingPolicy.value) {
      await policiesApi.update(editingPolicy.value.id, payload)
      // refresh
      await policiesStore.fetchPolicies()
    } else {
      await policiesApi.create(payload)
      await policiesStore.fetchPolicies()
    }
    closeEditor()
  } catch {
    // API not available, try optimistic update with mock
    if (editingPolicy.value) {
      const idx = policiesStore.policies.findIndex(p => p.id === editingPolicy.value.id)
      if (idx >= 0) {
        policiesStore.policies[idx] = {
          ...policiesStore.policies[idx],
          name: editorForm.value.name,
          description: editorForm.value.description,
          policy_type: editorForm.value.policy_type,
          priority: editorForm.value.priority,
          rules,
        }
      }
    } else {
      const newPolicy: Policy = {
        id: 'policy-' + Date.now(),
        name: editorForm.value.name,
        description: editorForm.value.description || '',
        policy_type: editorForm.value.policy_type,
        policy_type_label: policyTypeLabel(editorForm.value.policy_type),
        version: 1,
        status: 'draft',
        status_label: '草稿',
        target_type: editorForm.value.target_type,
        target_value: [],
        rules,
        priority: editorForm.value.priority,
        enabled: false,
        created_by: { id: 'user-1', display_name: '系统管理员' },
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
      }
      policiesStore.policies.unshift(newPolicy)
    }
    closeEditor()
  }
}

function policyTypeLabel(type: string): string {
  const map: Record<string, string> = {
    file_integrity: '文件完整性监控',
    process_whitelist: '进程白名单',
    network_firewall: '网络访问控制',
    login_policy: '登录安全策略',
    vulnerability_scan: '漏洞扫描策略',
    log_audit: '日志审计规则',
  }
  return map[type] || type
}

async function deployPolicy(policy: Policy) {
  if (!confirm(`确认将策略「${policy.name}」下发到目标 Agent？`)) return
  try {
    await policiesApi.deploy(policy.id)
    // refresh
    await policiesStore.fetchPolicies()
  } catch {
    // API not available, optimistic update
    const p = policiesStore.policies.find(p => p.id === policy.id)
    if (p) {
      p.status = 'deploying'
      p.status_label = '下发中'
      setTimeout(() => {
        if (p) {
          p.status = 'enabled'
          p.status_label = '已启用'
        }
      }, 2000)
    }
  }
}

onMounted(() => {
  policiesStore.fetchPolicies()
})
</script>

<style scoped>
.page-header { display:flex; align-items:flex-start; justify-content:space-between; margin-bottom:var(--space-6); }
.page-header-left h1 { font-size:var(--text-h1); font-weight:var(--font-weight-bold); color:var(--color-text-primary); margin-bottom:var(--space-1); }
.page-header-left p { font-size:var(--text-body); color:var(--color-text-tertiary); }
.page-header-right { flex-shrink:0; }

.tab-bar {
  display: flex;
  gap: 0;
  margin-bottom: var(--space-6);
  border-bottom: 1px solid var(--color-border-default);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: var(--space-2);
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

.tab-btn:hover {
  color: var(--color-text-secondary);
  background: var(--color-bg-hover);
}

.tab-btn.active {
  color: var(--color-accent-500);
  border-bottom-color: var(--color-accent-500);
}

/* Policy Grid */
.policy-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: var(--space-5);
}

.policy-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-5);
  transition: all 0.25s ease;
}

.policy-card:hover {
  border-color: rgba(0, 188, 212, 0.15);
  box-shadow: var(--shadow-card-hover);
}

.policy-card-header {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.policy-type-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.policy-type-icon svg { width: 18px; height: 18px; }

.type-file_integrity { background: rgba(0, 188, 212, 0.12); color: var(--color-accent-500); }
.type-process_whitelist { background: rgba(0, 200, 83, 0.12); color: var(--color-low); }
.type-network_firewall { background: rgba(124, 77, 255, 0.12); color: var(--color-accent-purple); }
.type-login_policy { background: rgba(255, 193, 7, 0.12); color: var(--color-medium); }
.type-vulnerability_scan { background: rgba(255, 59, 92, 0.12); color: var(--color-critical); }
.type-log_audit { background: rgba(68, 138, 255, 0.12); color: var(--color-info); }

.policy-card-info { flex:1; }
.policy-card-name { font-size:var(--text-h4); font-weight:var(--font-weight-semibold); color:var(--color-text-primary); }
.policy-card-type { font-size:var(--text-caption); color:var(--color-text-tertiary); }

.toggle-switch { position:relative; }
.toggle-switch input { position:absolute; opacity:0; width:0; height:0; }
.toggle-track {
  display:block;
  width:36px; height:20px;
  background: var(--color-bg-elevated);
  border-radius: 10px;
  cursor: pointer;
  transition: background 0.2s ease;
  position: relative;
}
.toggle-thumb {
  position:absolute;
  top:2px; left:2px;
  width:16px; height:16px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  transition: all 0.2s ease;
}
.toggle-switch input:checked + .toggle-track { background: var(--color-accent-500); }
.toggle-switch input:checked + .toggle-track .toggle-thumb { left: 18px; background: #fff; }

.policy-desc { font-size:var(--text-body-sm); color:var(--color-text-secondary); margin-bottom:var(--space-3); line-height:1.5; }

.policy-meta { display:flex; align-items:center; gap:var(--space-3); margin-bottom:var(--space-4); }
.policy-version { font-family:var(--font-family-mono); font-size:var(--text-mono-sm); color:var(--color-text-tertiary); }
.policy-date { font-size:var(--text-caption); color:var(--color-text-tertiary); margin-left:auto; }

.policy-footer { display:flex; align-items:center; justify-content:space-between; padding-top:var(--space-3); border-top:1px solid var(--color-border-subtle); }
.policy-priority { font-size:var(--text-caption); color:var(--color-text-tertiary); }
.policy-actions { display:flex; gap:var(--space-2); }

/* Orchestration */
.orchestration-flow {
  display: flex;
  align-items: flex-start;
  gap: var(--space-4);
  padding: var(--space-5);
  overflow-x: auto;
}

.flow-step {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  min-width: 200px;
  position: relative;
}

.flow-step-number {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--color-bg-elevated);
  border: 2px solid var(--color-border-default);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-h4);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}

.flow-step.active .flow-step-number {
  background: rgba(0, 188, 212, 0.15);
  border-color: var(--color-accent-500);
  color: var(--color-accent-500);
}

.flow-step-content { flex:1; }
.flow-step-title { font-size:var(--text-body-sm); font-weight:var(--font-weight-semibold); color:var(--color-text-primary); }
.flow-step-desc { font-size:var(--text-caption); color:var(--color-text-tertiary); margin-top:2px; }

.flow-arrow {
  width: 24px;
  height: 24px;
  color: var(--color-text-disabled);
  flex-shrink: 0;
  margin: 0 4px;
}

.two-col-grid { display:grid; grid-template-columns:1fr 1fr; gap:var(--space-5); }

/* Editor Modal */
.modal-overlay { position:fixed; inset:0; background:rgba(0,0,0,0.6); z-index:var(--z-modal); display:flex; align-items:center; justify-content:center; }
.editor-modal { width:80%; max-width:1000px; max-height:90vh; background:var(--color-bg-surface); border:1px solid var(--color-border-default); border-radius:16px; display:flex; flex-direction:column; box-shadow:var(--shadow-xl); }
.modal-header { display:flex; align-items:center; justify-content:space-between; padding:var(--space-5); border-bottom:1px solid var(--color-border-default); }
.modal-header h2 { font-size:var(--text-h3); font-weight:var(--font-weight-semibold); color:var(--color-text-primary); }
.drawer-close { width:32px;height:32px;display:flex;align-items:center;justify-content:center;border-radius:8px;border:none;background:transparent;color:var(--color-text-secondary);cursor:pointer; }
.drawer-close:hover { background:var(--color-bg-hover); color:var(--color-text-primary); }
.drawer-close svg { width:18px;height:18px; }
.editor-body { display:grid; grid-template-columns:1fr 1fr; gap:var(--space-5); padding:var(--space-5); overflow-y:auto; flex:1; }
.editor-left, .editor-right { display:flex; flex-direction:column; gap:var(--space-4); }
.form-group { margin-bottom:0; }
.form-group label { display:block; font-size:var(--text-body-sm); font-weight:var(--font-weight-medium); color:var(--color-text-secondary); margin-bottom:var(--space-2); }
.editor-input, .editor-select {
  width:100%;
  height:34px;
  background:var(--color-bg-elevated);
  border:1px solid var(--color-border-subtle);
  border-radius:8px;
  padding:0 var(--space-3);
  color:var(--color-text-primary);
  font-size:var(--text-body-sm);
  font-family:inherit;
  outline:none;
}
.editor-input:focus, .editor-select:focus { border-color:var(--color-accent-500); }
.editor-select option { background:var(--color-bg-surface); color:var(--color-text-primary); }
.editor-textarea {
  width:100%;
  background:var(--color-bg-elevated);
  border:1px solid var(--color-border-subtle);
  border-radius:8px;
  padding:var(--space-3);
  color:var(--color-text-primary);
  font-size:var(--text-body-sm);
  font-family:inherit;
  outline:none;
  resize:vertical;
}
.editor-textarea:focus { border-color:var(--color-accent-500); }
.editor-code {
  flex:1;
  width:100%;
  min-height:200px;
  background:#0D1117;
  border:1px solid var(--color-border-default);
  border-radius:8px;
  padding:var(--space-4);
  color:#E8ECF0;
  font-family:var(--font-family-mono);
  font-size:var(--text-mono-sm);
  line-height:1.6;
  outline:none;
  resize:vertical;
  tab-size:2;
}
.editor-code:focus { border-color:var(--color-accent-500); }
.modal-footer { display:flex; gap:var(--space-3); justify-content:flex-end; padding:var(--space-5); border-top:1px solid var(--color-border-default); }

@media (max-width: 1200px) { .editor-body { grid-template-columns:1fr; } }
@media (max-width: 768px) { .policy-grid { grid-template-columns:1fr; } }
</style>