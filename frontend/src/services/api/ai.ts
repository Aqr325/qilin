import api from '@/services/api'

export interface AISuggestResponse {
  actions: { label: string; action: string }[]
  context: { key: string; value: unknown }[]
}

export interface AIPlaybookResponse {
  playbook: string
  steps: { step: number; title: string; description: string; command?: string }[]
  confidence: number
}

export interface ConversationListResponse {
  items: ConversationSummary[]
  total: number
  page: number
  size: number
}

export interface AIFeedbackResponse {
  accepted: boolean
  feedback_id: string
}

export interface AIQueryResponse {
  conversation_id: string
  message_id: string
  answer: string
  confidence: number
  data_sources: { label: string; data: unknown }[]
  suggested_actions: { label: string; action: string }[]
  token_usage: number
  processing_time_ms: number
}

export interface ConversationSummary {
  id: string
  title?: string
  message_count?: number
  last_message?: string
  related_alert_id?: string
  token_usage: number
  created_at?: string
  updated_at?: string
}

export interface ConversationDetail {
  id: string
  title?: string
  messages: { role: string; content: string; created_at?: string }[]
  context?: Record<string, unknown>
  related_alert_id?: string
  feedback_score?: number
  token_usage: number
  model_name?: string
  duration_ms?: number
  created_at?: string
  updated_at?: string
}

export interface ModelConfig {
  id: string
  name: string
  provider: string
  model: string
  api_url?: string
  temperature: number
  max_tokens: number
  system_prompt?: string
  is_active: boolean
  is_default: boolean
  has_api_key: boolean
  api_key?: string
  created_at?: string
  updated_at?: string
}

export interface ModelConfigCreate {
  name: string
  provider: string
  model: string
  api_url?: string
  api_key?: string
  temperature?: number
  max_tokens?: number
  system_prompt?: string
}

export interface ModelConfigUpdate {
  name?: string
  provider?: string
  model?: string
  api_url?: string
  api_key?: string
  temperature?: number
  max_tokens?: number
  system_prompt?: string
  is_active?: boolean
  is_default?: boolean
}

export interface ModelConfigTestResult {
  ok: boolean
  message: string
  latency_ms: number
  model?: string
}

export const aiApi = {
  query(question: string, contextAlertId?: string) {
    return api.post<AIQueryResponse>('/ai/query', {
      question,
      context_alert_id: contextAlertId,
    })
  },

  suggest(alertId: string) {
    return api.post<AISuggestResponse>('/ai/suggest', { alert_id: alertId })
  },

  playbook(alertIds: string[], scenario?: string) {
    return api.post<AIPlaybookResponse>('/ai/playbook', { alert_ids: alertIds, scenario })
  },

  conversations(page = 1, size = 20) {
    return api.get<ConversationListResponse>(`/ai/conversations?page=${page}&size=${size}`)
  },

  conversationDetail(convId: string) {
    return api.get<ConversationDetail>(`/ai/conversations/${convId}`)
  },

  deleteConversation(convId: string) {
    return api.delete<AIFeedbackResponse>(`/ai/conversations/${convId}`)
  },

  feedback(conversationId: string, messageId: string, rating: number, comment?: string) {
    return api.post<AIFeedbackResponse>('/ai/feedback', {
      conversation_id: conversationId,
      message_id: messageId,
      rating,
      comment,
    })
  },

  // Model Config CRUD
  listModelConfigs() {
    return api.get<ModelConfig[]>('/ai/model-configs')
  },

  getModelConfig(id: string) {
    return api.get<ModelConfig>(`/ai/model-configs/${id}`)
  },

  createModelConfig(data: ModelConfigCreate) {
    return api.post<ModelConfig>('/ai/model-configs', data)
  },

  updateModelConfig(id: string, data: ModelConfigUpdate) {
    return api.put<ModelConfig>(`/ai/model-configs/${id}`, data)
  },

  deleteModelConfig(id: string) {
    return api.delete<AIFeedbackResponse>(`/ai/model-configs/${id}`)
  },

  setDefaultModelConfig(id: string) {
    return api.put<ModelConfig>(`/ai/model-configs/${id}/set-default`)
  },

  testModelConfig(data: {
    config_id?: string
    provider?: string
    model?: string
    api_url?: string
    api_key?: string
  }) {
    return api.post<ModelConfigTestResult>('/ai/model-configs/test', data)
  },
}

export default aiApi