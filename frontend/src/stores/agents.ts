import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Agent, PaginatedResponse } from '@/types'
import api from '@/services/api'

export const useAgentsStore = defineStore('agents', () => {
  const agents = ref<Agent[]>([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = ref(20)
  const loading = ref(false)
  const selectedAgentId = ref<string | null>(null)

  const stats = ref({
    online: 5,
    offline: 1,
    error: 0,
    pending: 2,
    total: 8,
    avgCpu: 42.5,
    avgMem: 65.3,
  })

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
    } catch {
      agents.value = getMockAgents()
      total.value = 12
    } finally {
      loading.value = false
    }
  }

  async function upgradeAgents(agentIds: string[], version: string) {
    try {
      await api.post('/agents/upgrade', { agent_ids: agentIds, version })
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

  return {
    agents, total, page, pageSize, loading, selectedAgentId, stats,
    fetchAgents, upgradeAgents, restartAgent,
  }
})

function getMockAgents(): Agent[] {
  return [
    { id: '1', agent_id: 'kylin-node-01', hostname: 'kylin-node-01', ip_address: '192.168.1.1', os_version: 'Kylin V10 SP1', agent_version: '3.2.0', status: 'online', cpu_usage: 45.2, memory_usage: 50.0, memory_total: 16384, disk_usage: 64.0, cpu_cores: 8, processes_total: 245, last_heartbeat: '2026-06-23T20:00:00Z', tags: ['production', 'web-server'] },
    { id: '2', agent_id: 'kylin-node-02', hostname: 'kylin-node-02', ip_address: '192.168.1.2', os_version: 'Kylin V10 SP1', agent_version: '3.2.0', status: 'online', cpu_usage: 23.4, memory_usage: 35.2, memory_total: 32768, disk_usage: 45.0, cpu_cores: 16, processes_total: 312, last_heartbeat: '2026-06-23T20:00:00Z', tags: ['production', 'database'] },
    { id: '3', agent_id: 'kylin-node-03', hostname: 'kylin-node-03', ip_address: '192.168.1.3', os_version: 'Kylin V10 SP1', agent_version: '3.1.9', status: 'online', cpu_usage: 12.8, memory_usage: 28.6, memory_total: 8192, disk_usage: 55.0, cpu_cores: 4, processes_total: 178, last_heartbeat: '2026-06-23T20:00:00Z', tags: ['staging'] },
    { id: '4', agent_id: 'kylin-node-04', hostname: 'kylin-node-04', ip_address: '192.168.1.4', os_version: 'Kylin V10 SP1', agent_version: '3.2.0', status: 'online', cpu_usage: 67.1, memory_usage: 78.4, memory_total: 16384, disk_usage: 82.0, cpu_cores: 8, processes_total: 401, last_heartbeat: '2026-06-23T20:00:00Z', tags: ['production', 'web-server'] },
    { id: '5', agent_id: 'kylin-node-05', hostname: 'kylin-node-05', ip_address: '192.168.1.5', os_version: 'Kylin V10 SP1', agent_version: '3.2.0', status: 'error', cpu_usage: 92.3, memory_usage: 88.1, memory_total: 8192, disk_usage: 94.0, cpu_cores: 4, processes_total: 523, last_heartbeat: '2026-06-23T19:55:00Z', tags: ['production', 'cache'] },
    { id: '6', agent_id: 'kylin-node-06', hostname: 'kylin-node-06', ip_address: '192.168.1.6', os_version: 'Kylin V10 SP1', agent_version: '3.1.8', status: 'offline', cpu_usage: 0, memory_usage: 0, memory_total: 16384, disk_usage: 0, cpu_cores: 8, processes_total: 0, last_heartbeat: '2026-06-23T18:30:00Z', tags: ['production', 'worker'] },
    { id: '7', agent_id: 'kylin-node-07', hostname: 'kylin-node-07', ip_address: '192.168.1.7', os_version: 'Kylin V10 SP1', agent_version: '3.2.1', status: 'online', cpu_usage: 34.5, memory_usage: 55.3, memory_total: 32768, disk_usage: 38.0, cpu_cores: 16, processes_total: 267, last_heartbeat: '2026-06-23T20:00:00Z', tags: ['production', 'database'] },
    { id: '8', agent_id: 'kylin-node-08', hostname: 'kylin-node-08', ip_address: '192.168.1.8', os_version: 'Kylin V10 SP1', agent_version: '3.2.0', status: 'upgrading', cpu_usage: 55.0, memory_usage: 62.0, memory_total: 16384, disk_usage: 50.0, cpu_cores: 8, processes_total: 198, last_heartbeat: '2026-06-23T19:58:00Z', tags: ['staging'] },
    { id: '9', agent_id: 'kylin-node-09', hostname: 'kylin-node-09', ip_address: '192.168.1.9', os_version: 'Kylin V10 SP1', agent_version: '3.2.0', status: 'online', cpu_usage: 15.6, memory_usage: 32.4, memory_total: 8192, disk_usage: 44.0, cpu_cores: 4, processes_total: 156, last_heartbeat: '2026-06-23T20:00:00Z', tags: ['development'] },
    { id: '10', agent_id: 'kylin-node-10', hostname: 'kylin-node-10', ip_address: '192.168.1.10', os_version: 'Kylin V10 SP1', agent_version: '3.2.0', status: 'pending', cpu_usage: 8.2, memory_usage: 22.0, memory_total: 16384, disk_usage: 30.0, cpu_cores: 8, processes_total: 89, last_heartbeat: '2026-06-23T19:50:00Z', tags: ['development'] },
  ]
}