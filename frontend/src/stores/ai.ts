import { defineStore } from 'pinia'
import { ref } from 'vue'
import aiApi, { type AIQueryResponse, type ConversationSummary, type ConversationDetail } from '@/services/api/ai'

export const useAIStore = defineStore('ai', () => {
  const conversations = ref<ConversationSummary[]>([])
  const currentConversation = ref<ConversationDetail | null>(null)
  const messages = ref<{ role: string; content: string; created_at?: string }[]>([])
  const loading = ref(false)
  const sending = ref(false)
  const error = ref('')

  async function fetchConversations() {
    try {
      const res = await aiApi.conversations()
      conversations.value = (res as any).items || []
    } catch {
      conversations.value = []
    }
  }

  async function loadConversation(convId: string) {
    loading.value = true
    error.value = ''
    try {
      const detail = await aiApi.conversationDetail(convId)
      currentConversation.value = detail
      messages.value = detail.messages || []
    } catch (e: any) {
      error.value = e.message || '加载对话失败'
      messages.value = []
    } finally {
      loading.value = false
    }
  }

  async function sendMessage(question: string) {
    sending.value = true
    error.value = ''

    // Optimistic: add user message
    messages.value.push({ role: 'user', content: question })

    try {
      const res = await aiApi.query(question)

      // Add AI response
      messages.value.push({
        role: 'assistant',
        content: res.answer,
      })

      // Refresh conversation list
      await fetchConversations()

      return res
    } catch (e: any) {
      error.value = e.message || '发送失败'
      messages.value.push({
        role: 'assistant',
        content: `抱歉，请求失败了：${error.value}`,
      })
      return null
    } finally {
      sending.value = false
    }
  }

  async function deleteConversation(convId: string) {
    try {
      await aiApi.deleteConversation(convId)
      conversations.value = conversations.value.filter(c => c.id !== convId)
      if (currentConversation.value?.id === convId) {
        currentConversation.value = null
        messages.value = []
      }
    } catch (e: any) {
      error.value = e.message || '删除失败'
    }
  }

  async function sendFeedback(messageId: string, rating: number, comment?: string) {
    if (!currentConversation.value) return
    try {
      await aiApi.feedback(currentConversation.value.id, messageId, rating, comment)
    } catch {
      // silently fail
    }
  }

  function newChat() {
    currentConversation.value = null
    messages.value = []
    error.value = ''
  }

  return {
    conversations,
    currentConversation,
    messages,
    loading,
    sending,
    error,
    fetchConversations,
    loadConversation,
    sendMessage,
    deleteConversation,
    sendFeedback,
    newChat,
  }
})