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
            <div class="msg-content">{{ msg.content }}</div>
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
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, nextTick } from 'vue'
import { useAIStore } from '@/stores/ai'

const aiStore = useAIStore()
const inputText = ref('')
const messagesRef = ref<HTMLElement | null>(null)

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

onMounted(() => {
  aiStore.fetchConversations()
})
</script>

<style scoped>
.ai-view {
  display: flex;
  height: calc(100vh - var(--layout-topbar-height) - var(--space-12));
  gap: var(--space-4);
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
}

.btn-new-chat {
  width: 100%;
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
}

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
</style>