import api from '@/services/api'

export interface AIQueryResponse {
  conversation_id: string
  message_id: string
  answer: string
  confidence: number
  data_sources: { label: string; data: any }[]
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
  context?: any
  related_alert_id?: string
  feedback_score?: number
  token_usage: number
  model_name?: string
  duration_ms?: number
  created_at?: string
  updated_at?: string
}

export const aiApi = {
  query(question: string, contextAlertId?: string) {
    return api.post<AIQueryResponse>('/ai/query', {
      question,
      context_alert_id: contextAlertId,
    })
  },

  suggest(alertId: string) {
    return api.post<any>('/ai/suggest', { alert_id: alertId })
  },

  playbook(alertIds: string[], scenario?: string) {
    return api.post<any>('/ai/playbook', { alert_ids: alertIds, scenario })
  },

  conversations(page = 1, size = 20) {
    return api.get<any>(`/ai/conversations?page=${page}&size=${size}`)
  },

  conversationDetail(convId: string) {
    return api.get<ConversationDetail>(`/ai/conversations/${convId}`)
  },

  deleteConversation(convId: string) {
    return api.delete<any>(`/ai/conversations/${convId}`)
  },

  feedback(conversationId: string, messageId: string, rating: number, comment?: string) {
    return api.post<any>('/ai/feedback', {
      conversation_id: conversationId,
      message_id: messageId,
      rating,
      comment,
    })
  },
}

export default aiApi