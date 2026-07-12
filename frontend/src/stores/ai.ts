import { defineStore } from 'pinia'
import { ref } from 'vue'
import aiApi, { type AIQueryResponse, type ConversationSummary, type ConversationDetail, type ModelConfig, type ModelConfigTestResult } from '@/services/api/ai'

export const useAIStore = defineStore('ai', () => {
  const conversations = ref<ConversationSummary[]>([])
  const currentConversation = ref<ConversationDetail | null>(null)
  const messages = ref<{ role: string; content: string; created_at?: string }[]>([])
  const loading = ref(false)
  const sending = ref(false)
  const error = ref('')
  const modelConfigs = ref<ModelConfig[]>([])
  const modelConfigLoading = ref(false)

  async function fetchConversations() {
    try {
      const res = await aiApi.conversations()
      conversations.value = res.items ?? []
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

  async function fetchModelConfigs() {
    modelConfigLoading.value = true
    try {
      const res = await aiApi.listModelConfigs()
      const items = Array.isArray(res) ? res : (res as { items?: ModelConfig[] }).items ?? []
      modelConfigs.value = items
    } catch {
      modelConfigs.value = []
    } finally {
      modelConfigLoading.value = false
    }
  }

  async function createModelConfig(data: any) {
    try {
      await aiApi.createModelConfig(data)
      await fetchModelConfigs()
    } catch (e: any) {
      throw e
    }
  }

  async function updateModelConfig(id: string, data: any) {
    try {
      await aiApi.updateModelConfig(id, data)
      await fetchModelConfigs()
    } catch (e: any) {
      throw e
    }
  }

  async function deleteModelConfig(id: string) {
    try {
      await aiApi.deleteModelConfig(id)
      modelConfigs.value = modelConfigs.value.filter(c => c.id !== id)
    } catch (e: any) {
      throw e
    }
  }

  async function setDefaultModelConfig(id: string) {
    try {
      await aiApi.setDefaultModelConfig(id)
      await fetchModelConfigs()
    } catch (e: any) {
      throw e
    }
  }

  function getDefaultModel() {
    return modelConfigs.value.find(c => c.is_default && c.is_active) || modelConfigs.value[0] || null
  }

  async function testModelConfig(data: {
    config_id?: string
    provider?: string
    model?: string
    api_url?: string
    api_key?: string
  }): Promise<ModelConfigTestResult> {
    const res = await aiApi.testModelConfig(data)
    return res as unknown as ModelConfigTestResult
  }

  return {
    conversations,
    currentConversation,
    messages,
    loading,
    sending,
    error,
    modelConfigs,
    modelConfigLoading,
    fetchConversations,
    loadConversation,
    sendMessage,
    deleteConversation,
    sendFeedback,
    newChat,
    fetchModelConfigs,
    createModelConfig,
    updateModelConfig,
    deleteModelConfig,
    setDefaultModelConfig,
    getDefaultModel,
    testModelConfig,
  }
})