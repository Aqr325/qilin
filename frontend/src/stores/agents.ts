import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Agent, PaginatedResponse, AgentHealthScore } from '@/types'
import api from '@/services/api'
import { agentsApi } from '@/services/api/agents'

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agent[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const selectedAgentId = ref<string | null>(null)

  // Health score cache keyed by agent_id
  const healthScores = ref<Record<string, AgentHealthScore>>({})

  const stats = ref({
    online: 0,
    offline: 0,
    error: 0,
    pending: 0,
    total: 0,
    avgCpu: 0,
    avgMem: 0,
  })

  // Local machine (backend host) status
  const localStatus = ref<Record<string, any>>({})

  async function fetchLocalStatus() {
    try {
      const res = await api.get<any>('/system/local-status')
      localStatus.value = res
    } catch {
      localStatus.value = {}
    }
  }

  async function fetchAgents() {
    loading.value = true
    try {
      const res = await api.get<PaginatedResponse<Agent>>(`/agents?page=${page.value}&size=${pageSize.value}`)
      // Map backend fields: total_memory -> memory_total
      agents.value = res.items.map((a: any) => ({
        ...a,
        memory_total: a.total_memory ?? a.memory_total ?? 0,
        cpu_usage: a.cpu_usage ?? 0,
        memory_usage: a.memory_usage ?? 0,
        disk_usage: a.disk_usage ?? 0,
        processes_total: a.processes_total ?? 0,
        health_score: a.health_score ?? null,
        last_status_change: a.last_status_change ?? null,
      }))
      total.value = res.total

      // Update stats from real data
      const online = agents.value.filter(a => a.status === 'online').length
      const offline = agents.value.filter(a => a.status === 'offline').length
      const error = agents.value.filter(a => a.status === 'error').length
      const pending = agents.value.filter(a => a.status === 'pending' || a.status === 'upgrading').length
      const cpuVals = agents.value.filter(a => a.cpu_usage && a.cpu_usage > 0).map(a => a.cpu_usage!)
      const memVals = agents.value.filter(a => a.memory_usage && a.memory_usage > 0).map(a => a.memory_usage!)
      stats.value = {
        online, offline, error, pending,
        total: total.value,
        avgCpu: cpuVals.length ? Math.round(cpuVals.reduce((a, b) => a + b, 0) / cpuVals.length * 10) / 10 : 0,
        avgMem: memVals.length ? Math.round(memVals.reduce((a, b) => a + b, 0) / memVals.length * 10) / 10 : 0,
      }
    } catch (e) {
      console.warn('Failed to fetch agents, showing empty list:', e)
      agents.value = []
      total.value = 0
    } finally {
      loading.value = false
    }
  }

  async function fetchHealthScore(agentId: string) {
    try {
      const res = await agentsApi.getHealthScore(agentId)
      healthScores.value[agentId] = res
    } catch (e) {
      console.warn(`Failed to fetch health score for ${agentId}:`, e)
    }
  }

  async function upgradeAgents(agentIds: string[], version: string, packageUrl = '') {
    try {
      await api.post('/agents/upgrade', { agent_ids: agentIds, version, package_url: packageUrl })
      return true
    } catch {
      return false
    }
  }

  async function restartAgent(agentId: string) {
    try {
      await api.post(`/agents/${agentId}/restart`)
      return true
    } catch {
      return false
    }
  }

  async function batchRestartAgent(agentIds: string[]) {
    try {
      const res = await agentsApi.batchRestart({ agent_ids: agentIds })
      return res.data?.task_ids ?? []
    } catch {
      return []
    }
  }

  return {
    agents, total, page, pageSize, loading, selectedAgentId,
    healthScores,
    localStatus,
    stats,
    fetchAgents, fetchHealthScore, fetchLocalStatus,
    upgradeAgents, restartAgent, batchRestartAgent,
  }
})
