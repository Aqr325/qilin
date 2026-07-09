<template>
  <div class="ai-view">
    <div class="ai-sidebar">
      <div class="ai-sidebar-header">
        <button class="btn-new-chat" @click="aiStore.newChat()">
          <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;">
            <path d="M7 1v12M1 7h12"/>
          </svg>
          新建对话
        </button>
        <button class="btn-settings" @click="openSettings" title="模型配置">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:18px;height:18px;">
            <circle cx="9" cy="9" r="2.5"/>
            <path d="M9 1.5v2M9 14.5v2M1.5 9h2M14.5 9h2M3.4 3.4l1.4 1.4M13.2 13.2l1.4 1.4M3.4 14.6l1.4-1.4M13.2 4.8l1.4-1.4"/>
          </svg>
        </button>
      </div>

      <div class="ai-conv-list">
        <div
          v-for="conv in aiStore.conversations"
          :key="conv.id"
          :class="['conv-item', { active: aiStore.currentConversation?.id === conv.id }]"
          @click="aiStore.loadConversation(conv.id)"
        >
          <div class="conv-title">{{ conv.title || '未命名对话' }}</div>
          <div class="conv-meta">
            <span>{{ conv.message_count || 0 }} 条消息</span>
            <button class="conv-delete" @click.stop="aiStore.deleteConversation(conv.id)" title="删除">
              <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.2" stroke-linecap="round" style="width:12px;height:12px;">
                <path d="M2 4h10M4.5 4V3a1 1 0 0 1 1-1h3a1 1 0 0 1 1 1v1M5.5 7v3M8.5 7v3M3 4l.7 7.5a1 1 0 0 0 1 .5h4.6a1 1 0 0 0 1-.5L11 4"/>
              </svg>
            </button>
          </div>
        </div>
        <div v-if="aiStore.conversations.length === 0 && !aiStore.loading" class="conv-empty">
          暂无历史对话
        </div>
      </div>
    </div>

    <div class="ai-main">
      <div class="ai-messages" ref="messagesRef">
        <div v-if="aiStore.messages.length === 0" class="ai-welcome">
          <div class="welcome-icon">
            <svg viewBox="0 0 40 40" fill="none">
              <circle cx="20" cy="20" r="18" stroke="var(--color-accent-500)" stroke-width="1.5" opacity="0.3"/>
              <circle cx="20" cy="20" r="10" stroke="var(--color-accent-500)" stroke-width="1.5"/>
              <circle cx="20" cy="20" r="4" fill="var(--color-accent-500)" opacity="0.4"/>
            </svg>
          </div>
          <h2>AI 安全运维助手</h2>
          <p>使用自然语言与运维系统交互，查询告警信息、分析安全事件、生成处置策略</p>
          <div class="model-indicator" v-if="defaultModel" @click="openSettings">
            <span class="model-dot" :class="defaultModel.is_active ? 'active' : 'inactive'"></span>
            <span class="model-name">{{ defaultModel.name }}</span>
            <span class="model-provider">{{ providerLabel(defaultModel.provider) }}</span>
            <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" style="width:12px;height:12px;">
              <path d="M3 5l4 4 4-4"/>
            </svg>
          </div>
          <div class="welcome-suggestions">
            <div class="suggestion-chip" @click="sendQuick('最近有哪些严重告警？')">最近有哪些严重告警？</div>
            <div class="suggestion-chip" @click="sendQuick('分析当前的系统安全态势')">分析当前的系统安全态势</div>
            <div class="suggestion-chip" @click="sendQuick('有多少Agent在线？')">有多少Agent在线？</div>
            <div class="suggestion-chip" @click="sendQuick('生成一份安全巡检报告')">生成一份安全巡检报告</div>
          </div>
        </div>

        <div v-for="(msg, idx) in aiStore.messages" :key="idx" :class="['msg', msg.role === 'user' ? 'msg-user' : 'msg-ai']">
          <div class="msg-avatar">
            <svg v-if="msg.role === 'user'" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:16px;height:16px;">
              <circle cx="9" cy="6" r="3"/><path d="M3 16c0-3.3 2.7-6 6-6s6 2.7 6 6"/>
            </svg>
            <svg v-else viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:16px;height:16px;">
              <circle cx="9" cy="9" r="6"/><circle cx="9" cy="9" r="2" fill="currentColor" opacity="0.4"/>
            </svg>
          </div>
          <div class="msg-bubble">
            <div v-if="msg.role === 'ai'" class="msg-content" v-html="sanitizeHtml(renderMarkdown(msg.content))"></div>
            <div v-else class="msg-content">{{ msg.content }}</div>
            <div v-if="msg.created_at" class="msg-time">{{ formatTime(msg.created_at) }}</div>
          </div>
        </div>

        <div v-if="aiStore.sending" class="msg msg-ai">
          <div class="msg-avatar">
            <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:16px;height:16px;">
              <circle cx="9" cy="9" r="6"/><circle cx="9" cy="9" r="2" fill="currentColor" opacity="0.4"/>
            </svg>
          </div>
          <div class="msg-bubble">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
          </div>
        </div>

        <div v-if="aiStore.error" class="msg msg-ai">
          <div class="msg-avatar">
            <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:16px;height:16px;">
              <circle cx="9" cy="9" r="6"/><circle cx="9" cy="9" r="2" fill="currentColor" opacity="0.4"/>
            </svg>
          </div>
          <div class="msg-bubble msg-error">{{ aiStore.error }}</div>
        </div>
      </div>

      <div class="ai-input-bar">
        <div class="current-model" @click="openSettings" v-if="defaultModel" :title="'点击切换模型'">
          <span class="model-dot-sm" :class="defaultModel.is_active ? 'active' : 'inactive'"></span>
          <span class="model-name-sm">{{ defaultModel.name }}</span>
        </div>
        <input
          v-model="inputText"
          type="text"
          placeholder="输入运维问题，例如：查看最近的告警..."
          class="ai-input"
          @keydown.enter="handleSend"
          :disabled="aiStore.sending"
        />
        <button class="btn-send" @click="handleSend" :disabled="!inputText.trim() || aiStore.sending">
          <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="width:16px;height:16px;">
            <path d="M3 9h12M10 4l5 5-5 5"/>
          </svg>
        </button>
      </div>
    </div>

    <!-- ── Settings Drawer ── -->
    <Teleport to="body">
      <div v-if="showSettings" class="settings-overlay" @click.self="closeSettings">
        <div class="settings-drawer">
          <div class="settings-header">
            <h2>模型配置</h2>
            <div class="settings-header-actions">
              <button class="btn-add-model" @click="openModelDialog()">
                <svg viewBox="0 0 14 14" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" style="width:14px;height:14px;">
                  <path d="M7 1v12M1 7h12"/>
                </svg>
                新增模型
              </button>
              <button class="settings-close" @click="closeSettings">
                <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5">
                  <path d="M4 4l10 10M14 4l-10 10"/>
                </svg>
              </button>
            </div>
          </div>

          <div class="settings-body">
            <div v-if="aiStore.modelConfigLoading" class="settings-empty">加载中...</div>
            <div v-else-if="aiStore.modelConfigs.length === 0" class="settings-empty">
              <div class="empty-icon">
                <svg viewBox="0 0 40 40" fill="none" stroke="var(--color-text-tertiary)" stroke-width="1.5">
                  <rect x="6" y="6" width="28" height="28" rx="4"/>
                  <path d="M14 20h12M20 14v12"/>
                </svg>
              </div>
              <p>暂无模型配置</p>
              <p class="empty-hint">添加 OpenAI、Anthropic、Ollama 等模型，让 AI 助手更强大</p>
            </div>
            <div v-else class="model-list">
              <div
                v-for="config in aiStore.modelConfigs"
                :key="config.id"
                :class="['model-card', { default: config.is_default }]"
              >
                <div class="model-card-header">
                  <div class="model-card-title">
                    <span class="model-badge" :class="providerClass(config.provider)">
                      {{ providerLabel(config.provider) }}
                    </span>
                    <span class="model-card-name">{{ config.name }}</span>
                    <span class="model-card-model">{{ config.model }}</span>
                  </div>
                  <div class="model-card-badges">
                    <span v-if="config.is_default" class="badge-default">默认</span>
                    <span v-if="config.is_active" class="badge-active">已启用</span>
                    <span v-else class="badge-inactive">已禁用</span>
                  </div>
                </div>

                <div class="model-card-details">
                  <div class="detail-row">
                    <span class="detail-label">温度</span>
                    <span class="detail-value">{{ config.temperature }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">最大 Token</span>
                    <span class="detail-value">{{ config.max_tokens }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">API 地址</span>
                    <span class="detail-value detail-truncate">{{ config.api_url || '使用默认地址' }}</span>
                  </div>
                  <div class="detail-row">
                    <span class="detail-label">API Key</span>
                    <span class="detail-value detail-key">{{ config.has_api_key ? '●●●●●●●●（已配置）' : '未设置' }}</span>
                  </div>
                </div>

                <div class="model-card-actions">
                  <button class="action-btn" @click="openModelDialog(config)">编辑</button>
                  <button v-if="!config.is_default" class="action-btn" @click="setDefault(config.id)">设为默认</button>
                  <button class="action-btn action-toggle" :class="{ disabled: !config.is_active }" @click="toggleActive(config)">
                    {{ config.is_active ? '禁用' : '启用' }}
                  </button>
                  <button class="action-btn action-delete" @click="deleteModel(config)">删除</button>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- ── Model Dialog ── -->
    <Teleport to="body">
      <div v-if="showModelDialog" class="modal-overlay" @click.self="closeModelDialog">
        <div class="modal-dialog">
          <div class="modal-header">
            <h2>{{ editingConfig ? '编辑模型配置' : '新增模型配置' }}</h2>
            <button class="drawer-close" @click="closeModelDialog">
              <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5"><path d="M4 4l10 10M14 4l-10 10"/></svg>
            </button>
          </div>
          <div class="modal-body">
            <div class="form-group">
              <label>配置名称</label>
              <input v-model="configForm.name" class="form-input" placeholder="如：GPT-4-turbo" />
            </div>
            <div class="form-group">
              <label>提供商</label>
              <select v-model="configForm.provider" class="form-select" @change="onProviderChange">
                <option value="openai">OpenAI</option>
                <option value="anthropic">Anthropic</option>
                <option value="ollama">Ollama</option>
                <option value="custom">自定义</option>
              </select>
            </div>
            <div class="form-group">
              <label>模型标识</label>
              <input v-model="configForm.model" class="form-input" placeholder="如：gpt-4-turbo、claude-3-5-sonnet" />
            </div>
            <div class="form-group">
              <label>API 地址 <span class="label-hint">{{ configForm.provider === 'custom' ? '（自定义必须填写）' : '（可选，默认使用官方地址）' }}</span></label>
              <input
                v-model="configForm.api_url"
                class="form-input"
                :placeholder="configForm.provider === 'custom' ? '如：https://apihub.agnes-ai.com/v1' : (configForm.provider === 'ollama' ? '如：http://localhost:11434/v1' : '留空使用官方地址')"
                :disabled="configForm.provider !== 'custom' && configForm.provider !== 'ollama'"
              />
            </div>
            <div class="form-group">
              <label>API Key <span class="label-hint">{{ configForm.provider === 'custom' ? '（自定义必须填写）' : '（可选）' }}</span></label>
              <input v-model="configForm.api_key" type="password" class="form-input" placeholder="sk-..." />
            </div>
            <div class="form-row">
              <div class="form-group">
                <label>温度 (0.0-2.0)</label>
                <input v-model.number="configForm.temperature" type="number" step="0.1" min="0" max="2" class="form-input" />
              </div>
              <div class="form-group">
                <label>最大 Token</label>
                <input v-model.number="configForm.max_tokens" type="number" min="1" max="128000" class="form-input" />
              </div>
            </div>
            <div class="form-group">
              <label>系统提示词 <span class="label-hint">（可选）</span></label>
              <textarea v-model="configForm.system_prompt" class="form-textarea" rows="3" placeholder="你是一个安全运维助手，帮助用户分析系统安全状态..."></textarea>
            </div>
          </div>
          <div class="modal-footer">
            <button class="action-btn" @click="closeModelDialog">取消</button>
            <button class="btn-primary" @click="saveConfig" :disabled="configSaving">
              {{ configSaving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, nextTick } from 'vue'
import { showToast } from '@/utils/toast'
import { useAIStore } from '@/stores/ai'
import { marked } from 'marked'
import { sanitizeHtml } from '../utils/sanitize'

defineOptions({ name: 'AI' })

const aiStore = useAIStore()
const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)

// Settings panel
const showSettings = ref(false)
const showModelDialog = ref(false)
const editingConfig = ref<any>(null)
const configSaving = ref(false)
const configForm = ref({
  name: '',
  provider: 'openai',
  model: 'gpt-4-turbo',
  api_url: '',
  api_key: '',
  temperature: 0.7,
  max_tokens: 4096,
  system_prompt: '',
})

const defaultModel = computed(() => aiStore.getDefaultModel())

function providerLabel(provider: string): string {
  const map: Record<string, string> = {
    openai: 'OpenAI',
    anthropic: 'Anthropic',
    ollama: 'Ollama',
    custom: '自定义',
  }
  return map[provider] || provider
}

function providerClass(provider: string): string {
  const map: Record<string, string> = {
    openai: 'provider-openai',
    anthropic: 'provider-anthropic',
    ollama: 'provider-ollama',
    custom: 'provider-custom',
  }
  return map[provider] || 'provider-custom'
}

async function openSettings() {
  await aiStore.fetchModelConfigs()
  showSettings.value = true
}

function closeSettings() {
  showSettings.value = false
}

function openModelDialog(config?: any) {
  if (config) {
    editingConfig.value = config
    configForm.value = {
      name: config.name,
      provider: config.provider,
      model: config.model,
      api_url: config.api_url || '',
      api_key: '',
      temperature: config.temperature,
      max_tokens: config.max_tokens,
      system_prompt: config.system_prompt || '',
    }
  } else {
    editingConfig.value = null
    configForm.value = {
      name: '',
      provider: 'openai',
      model: 'gpt-4-turbo',
      api_url: '',
      api_key: '',
      temperature: 0.7,
      max_tokens: 4096,
      system_prompt: '',
    }
  }
  showModelDialog.value = true
}

function closeModelDialog() {
  showModelDialog.value = false
  editingConfig.value = null
}

function onProviderChange() {
  const modelMap: Record<string, string> = {
    openai: 'gpt-4-turbo',
    anthropic: 'claude-3-5-sonnet',
    ollama: 'qwen2.5:7b',
    custom: '',
  }
  configForm.value.model = modelMap[configForm.value.provider] || configForm.value.model
  // 切换提供商时清空 API 地址，让用户自己填写
  if (configForm.value.provider === 'custom') {
    configForm.value.api_url = ''
  }
}

async function saveConfig() {
  if (!configForm.value.name || !configForm.value.model) {
    showToast('请填写配置名称和模型标识', 'warning')
    return
  }
  // 自定义提供商必须填写 API 地址
  if (configForm.value.provider === 'custom' && !configForm.value.api_url) {
    showToast('自定义提供商必须填写 API 地址', 'warning')
    return
  }
  // 自定义提供商必须填写 API Key
  if (configForm.value.provider === 'custom' && !configForm.value.api_key) {
    showToast('自定义提供商必须填写 API Key', 'warning')
    return
  }
  configSaving.value = true
  try {
    const payload = {
      name: configForm.value.name,
      provider: configForm.value.provider,
      model: configForm.value.model,
      api_url: configForm.value.api_url || undefined,
      api_key: configForm.value.api_key || undefined,
      temperature: configForm.value.temperature,
      max_tokens: configForm.value.max_tokens,
      system_prompt: configForm.value.system_prompt || undefined,
    }
    if (editingConfig.value) {
      await aiStore.updateModelConfig(editingConfig.value.id, payload)
      showToast('模型配置已更新', 'success')
    } else {
      await aiStore.createModelConfig(payload)
      showToast('模型配置已添加', 'success')
    }
    closeModelDialog()
  } catch (e: any) {
    showToast(e.message || '保存失败', 'error')
  } finally {
    configSaving.value = false
  }
}

async function setDefault(id: string) {
  await aiStore.setDefaultModelConfig(id)
}

async function toggleActive(config: any) {
  try {
    await aiStore.updateModelConfig(config.id, { is_active: !config.is_active })
    showToast(config.is_active ? '已禁用模型' : '已启用模型', 'success')
  } catch (e: any) {
    showToast(e.message || '操作失败', 'error')
  }
}

async function deleteModel(config: any) {
  if (config.is_default) {
    showToast('无法删除默认模型，请先设置其他模型为默认', 'warning')
    return
  }
  // confirm() is kept for confirmation dialogs
  if (!confirm(`确认删除模型配置「${config.name}」？`)) return
  try {
    await aiStore.deleteModelConfig(config.id)
    showToast('模型配置已删除', 'success')
  } catch (e: any) {
    showToast(e.message || '删除失败', 'error')
  }
}

async function handleSend() {
  const text = inputText.value.trim()
  if (!text || aiStore.sending) return
  inputText.value = ''
  await aiStore.sendMessage(text)
  scrollToBottom()
}

async function sendQuick(text: string) {
  if (aiStore.sending) return
  await aiStore.sendMessage(text)
  scrollToBottom()
}

function scrollToBottom() {
  nextTick(() => {
    if (messagesRef.value) {
      messagesRef.value.scrollTop = messagesRef.value.scrollHeight
    }
  })
}

function formatTime(iso?: string) {
  if (!iso) return ''
  const d = new Date(iso)
  return d.toLocaleString('zh-CN')
}

function renderMarkdown(content: string): string {
  return marked(content, { breaks: true }) as string
}

onMounted(() => {
  aiStore.fetchConversations()
  aiStore.fetchModelConfigs()
})
</script>

<style scoped>
.ai-view {
  display: flex;
  height: calc(100vh - var(--layout-topbar-height) - var(--space-12));
  gap: var(--space-4);
  position: relative;
}

/* ── Sidebar ── */
.ai-sidebar {
  width: 240px;
  min-width: 240px;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  overflow: hidden;
}

.ai-sidebar-header {
  padding: var(--space-4);
  border-bottom: 1px solid var(--color-border-subtle);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.btn-new-chat {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: rgba(0, 188, 212, 0.1);
  border: 1px solid rgba(0, 188, 212, 0.2);
  border-radius: 8px;
  color: var(--color-accent-500);
  font-size: var(--text-body-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-new-chat:hover {
  background: rgba(0, 188, 212, 0.18);
}

.btn-settings {
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
  transition: all 0.2s;
}
.btn-settings:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.ai-conv-list {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-2);
}

.conv-item {
  padding: var(--space-3);
  border-radius: 8px;
  cursor: pointer;
  margin-bottom: 2px;
  transition: all 0.2s;
}
.conv-item:hover { background: var(--color-bg-hover); }
.conv-item.active { background: rgba(0, 188, 212, 0.1); }

.conv-title {
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
  margin-bottom: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.conv-meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
}

.conv-delete {
  background: none;
  border: none;
  color: var(--color-text-tertiary);
  cursor: pointer;
  padding: 2px;
  border-radius: 4px;
  opacity: 0;
  transition: all 0.2s;
}
.conv-item:hover .conv-delete { opacity: 1; }
.conv-delete:hover { color: var(--color-critical); background: rgba(244,67,54,0.1); }

.conv-empty {
  text-align: center;
  padding: var(--space-8) var(--space-4);
  color: var(--color-text-tertiary);
  font-size: var(--text-caption);
}

/* ── Main ── */
.ai-main {
  flex: 1;
  display: flex;
  flex-direction: column;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  overflow: hidden;
}

.ai-messages {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-6);
}

.ai-welcome {
  text-align: center;
  padding: var(--space-12) var(--space-6);
  max-width: 480px;
  margin: 0 auto;
}

.welcome-icon {
  margin-bottom: var(--space-4);
}

.ai-welcome h2 {
  font-size: var(--text-h2);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-3);
}

.ai-welcome p {
  color: var(--color-text-tertiary);
  line-height: 1.6;
  margin-bottom: var(--space-6);
}

.model-indicator {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 20px;
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  cursor: pointer;
  margin-bottom: var(--space-6);
  transition: all 0.2s;
}
.model-indicator:hover {
  border-color: var(--color-accent-500);
  color: var(--color-accent-500);
}
.model-indicator .model-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.model-indicator .model-dot.active { background: var(--color-success); }
.model-indicator .model-dot.inactive { background: var(--color-text-tertiary); }
.model-indicator .model-name {
  color: var(--color-text-primary);
  font-weight: var(--font-weight-medium);
}

.welcome-suggestions {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  justify-content: center;
}

.suggestion-chip {
  padding: var(--space-2) var(--space-4);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 20px;
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}
.suggestion-chip:hover {
  border-color: var(--color-accent-500);
  color: var(--color-accent-500);
  background: rgba(0, 188, 212, 0.06);
}

/* ── Messages ── */
.msg {
  display: flex;
  gap: var(--space-3);
  margin-bottom: var(--space-5);
  max-width: 85%;
}

.msg-user {
  flex-direction: row-reverse;
  margin-left: auto;
}

.msg-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  background: var(--color-bg-elevated);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border-subtle);
}

.msg-user .msg-avatar {
  background: rgba(0, 188, 212, 0.12);
  color: var(--color-accent-500);
}

.msg-bubble {
  padding: var(--space-3) var(--space-4);
  border-radius: 12px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  line-height: 1.6;
  font-size: var(--text-body-sm);
  color: var(--color-text-primary);
  white-space: pre-wrap;
  word-break: break-word;
}

.msg-user .msg-bubble {
  background: rgba(0, 188, 212, 0.08);
  border-color: rgba(0, 188, 212, 0.15);
}

.msg-error {
  color: var(--color-critical) !important;
  border-color: rgba(244,67,54,0.2) !important;
}

.msg-content :deep(pre) {
  background: #0D1117;
  border: 1px solid var(--color-border-default);
  border-radius: 8px;
  padding: var(--space-4);
  overflow-x: auto;
  font-size: var(--text-mono-sm);
  line-height: 1.6;
  margin: var(--space-3) 0;
}

.msg-content :deep(code) {
  background: rgba(0,0,0,0.3);
  padding: 1px 5px;
  border-radius: 4px;
  font-size: var(--text-mono-sm);
  font-family: var(--font-family-mono);
}

.msg-content :deep(pre code) {
  background: none;
  padding: 0;
  border-radius: 0;
}

.msg-content :deep(p) {
  margin: var(--space-2) 0;
  line-height: 1.7;
}

.msg-content :deep(ul), .msg-content :deep(ol) {
  padding-left: var(--space-5);
  margin: var(--space-2) 0;
}

.msg-content :deep(li) {
  margin: var(--space-1) 0;
}

.msg-content :deep(h1), .msg-content :deep(h2), .msg-content :deep(h3), .msg-content :deep(h4) {
  margin: var(--space-4) 0 var(--space-2);
  color: var(--color-text-primary);
}

.msg-content :deep(blockquote) {
  border-left: 3px solid var(--color-accent-500);
  padding-left: var(--space-4);
  margin: var(--space-3) 0;
  color: var(--color-text-secondary);
  background: rgba(0, 188, 212, 0.05);
  border-radius: 0 4px 4px 0;
  padding: var(--space-3) var(--space-4);
}

.msg-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: var(--space-3) 0;
  font-size: var(--text-body-sm);
}

.msg-content :deep(th), .msg-content :deep(td) {
  border: 1px solid var(--color-border-default);
  padding: var(--space-2) var(--space-3);
  text-align: left;
}

.msg-content :deep(th) {
  background: var(--color-bg-elevated);
  font-weight: var(--font-weight-semibold);
}

.msg-content :deep(a) {
  color: var(--color-accent-500);
  text-decoration: underline;
}

.msg-content :deep(hr) {
  border: none;
  border-top: 1px solid var(--color-border-subtle);
  margin: var(--space-4) 0;
}

.msg-time {
  font-size: var(--text-label);
  color: var(--color-text-tertiary);
  margin-top: var(--space-1);
  text-align: right;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}
.typing-indicator span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--color-text-tertiary);
  animation: typing 1.2s infinite ease-in-out;
}
.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }
@keyframes typing {
  0%, 60%, 100% { opacity: 0.3; transform: scale(0.8); }
  30% { opacity: 1; transform: scale(1); }
}

/* ── Input ── */
.ai-input-bar {
  display: flex;
  gap: var(--space-3);
  padding: var(--space-4);
  border-top: 1px solid var(--color-border-subtle);
  background: var(--color-bg-surface);
  align-items: center;
}

.current-model {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.2s;
}
.current-model:hover {
  border-color: var(--color-accent-500);
  color: var(--color-accent-500);
}
.current-model .model-dot-sm {
  width: 6px;
  height: 6px;
  border-radius: 50%;
}
.current-model .model-dot-sm.active { background: var(--color-success); }
.current-model .model-dot-sm.inactive { background: var(--color-text-tertiary); }

.ai-input {
  flex: 1;
  height: 42px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 10px;
  padding: 0 var(--space-4);
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
}
.ai-input:focus { border-color: var(--color-accent-500); }
.ai-input:disabled { opacity: 0.5; }

.btn-send {
  width: 42px;
  height: 42px;
  border-radius: 10px;
  border: none;
  background: var(--color-accent-500);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: all 0.2s;
  flex-shrink: 0;
}
.btn-send:hover { background: var(--color-accent-600); }
.btn-send:disabled { opacity: 0.4; cursor: not-allowed; }

/* ── Settings Drawer ── */
.settings-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  z-index: var(--z-modal);
}

.settings-drawer {
  position: absolute;
  right: 0;
  top: 0;
  width: 480px;
  max-width: 90vw;
  height: 100%;
  background: var(--color-bg-surface);
  border-left: 1px solid var(--color-border-default);
  display: flex;
  flex-direction: column;
  box-shadow: -8px 0 32px rgba(0, 0, 0, 0.15);
}

.settings-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5);
  border-bottom: 1px solid var(--color-border-subtle);
}

.settings-header h2 {
  font-size: var(--text-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.settings-header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.btn-add-model {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-3);
  background: rgba(0, 188, 212, 0.1);
  border: 1px solid rgba(0, 188, 212, 0.2);
  border-radius: 8px;
  color: var(--color-accent-500);
  font-size: var(--text-body-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-add-model:hover {
  background: rgba(0, 188, 212, 0.18);
}

.settings-close {
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
.settings-close:hover { background: var(--color-bg-hover); }
.settings-close svg { width: 18px; height: 18px; }

.settings-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
}

.settings-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: var(--space-12) var(--space-6);
  color: var(--color-text-tertiary);
  text-align: center;
}

.empty-icon { margin-bottom: var(--space-4); }
.settings-empty p:first-of-type { color: var(--color-text-secondary); font-weight: var(--font-weight-medium); }
.empty-hint { font-size: var(--text-caption); color: var(--color-text-tertiary); margin-top: var(--space-1); }

/* Model List */
.model-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.model-card {
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 12px;
  padding: var(--space-4);
  transition: all 0.2s;
}
.model-card.default {
  border-color: var(--color-accent-500);
  background: rgba(0, 188, 212, 0.04);
}
.model-card:hover {
  border-color: var(--color-border-default);
}

.model-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.model-card-title {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.model-badge {
  font-size: var(--text-label);
  padding: 2px 6px;
  border-radius: 4px;
  background: var(--color-bg-hover);
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-medium);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.model-badge.provider-openai { background: #007aff20; color: #007aff; }
.model-badge.provider-anthropic { background: #ff900020; color: #ff9000; }
.model-badge.provider-ollama { background: #30d15820; color: #30d158; }
.model-badge.provider-custom { background: #af52de20; color: #af52de; }

.model-card-name {
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.model-card-model {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}

.model-card-badges {
  display: flex;
  gap: var(--space-1);
}

.badge-default {
  font-size: var(--text-label);
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(0, 188, 212, 0.15);
  color: var(--color-accent-500);
  font-weight: var(--font-weight-medium);
}

.badge-active {
  font-size: var(--text-label);
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(48, 209, 88, 0.15);
  color: var(--color-success);
}

.badge-inactive {
  font-size: var(--text-label);
  padding: 2px 6px;
  border-radius: 4px;
  background: rgba(255, 149, 0, 0.15);
  color: #ff9500;
}

.model-card-details {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2) var(--space-3);
  padding: var(--space-3) 0;
  border-top: 1px solid var(--color-border-subtle);
  border-bottom: 1px solid var(--color-border-subtle);
  margin-bottom: var(--space-3);
}

.detail-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: var(--text-caption);
}

.detail-label {
  color: var(--color-text-tertiary);
}

.detail-value {
  color: var(--color-text-secondary);
  font-family: var(--font-mono);
}

.detail-truncate {
  max-width: 120px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.detail-key {
  letter-spacing: 1px;
}

.model-card-actions {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.action-btn {
  flex: 1;
  min-width: 0;
  padding: var(--space-2) var(--space-2);
  background: var(--color-bg-hover);
  border: 1px solid var(--color-border-subtle);
  border-radius: 6px;
  color: var(--color-text-secondary);
  font-size: var(--text-caption);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s;
}
.action-btn:hover {
  background: var(--color-bg-surface);
  border-color: var(--color-border-default);
  color: var(--color-text-primary);
}

.action-toggle.disabled {
  opacity: 0.5;
}

.action-delete {
  color: var(--color-critical) !important;
}
.action-delete:hover {
  background: rgba(244, 67, 54, 0.1) !important;
  border-color: rgba(244, 67, 54, 0.2) !important;
  color: var(--color-critical) !important;
}

/* ── Dialog ── */
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
  width: 520px;
  max-width: 90vw;
  max-height: 85vh;
  overflow-y: auto;
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

.form-group { margin-bottom: var(--space-4); }
.form-group label {
  display: block;
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-secondary);
  margin-bottom: var(--space-2);
}

.label-hint {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  font-weight: var(--font-weight-normal);
  margin-left: var(--space-1);
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

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.modal-footer {
  display: flex;
  gap: var(--space-3);
  justify-content: flex-end;
  padding: var(--space-5);
  border-top: 1px solid var(--color-border-default);
}

.btn-primary {
  padding: var(--space-2) var(--space-5);
  background: var(--color-accent-500);
  border: none;
  border-radius: 8px;
  color: #fff;
  font-size: var(--text-body-sm);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s;
}
.btn-primary:hover { background: var(--color-accent-600); }
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }

@media (max-width: 768px) {
  .settings-drawer { width: 100%; max-width: 100vw; }
  .form-row { grid-template-columns: 1fr; }
  .model-card-details { grid-template-columns: 1fr; }
}
</style>