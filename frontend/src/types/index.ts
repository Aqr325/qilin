export interface User {
  id: string
  username: string
  display_name: string
  email: string
  phone?: string
  roles: Role[]
  permissions: string[]
  is_active: boolean
  is_locked: boolean
  mfa_enabled: boolean
  last_login_at?: string
  created_at: string
}

export interface Role {
  id: string
  name: string
  display_name: string
  description?: string
  is_system: boolean
  permissions?: string[]
}

export interface LoginRequest {
  username: string
  password: string
  mfa_code?: string
}

export interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
  user: User
}

export interface Agent {
  id: string
  agent_id: string
  hostname: string
  ip_address: string
  os_version: string
  agent_version: string
  status: AgentStatus
  cpu_usage?: number
  memory_usage?: number
  memory_total: number
  total_memory?: number
  disk_usage?: number
  cpu_cores: number
  processes_total?: number
  last_heartbeat?: string
  tags: string[]
  uptime?: number
  registered_at?: string
}

export type AgentStatus = 'online' | 'offline' | 'error' | 'upgrading' | 'pending'

export interface Alert {
  id: string
  alert_seq: number
  agent_id: string
  hostname: string
  alert_type: string
  alert_type_label: string
  severity: AlertSeverity
  severity_label: string
  title: string
  description: string
  status: AlertStatus
  status_label: string
  source_ip?: string
  mitre_technique_id?: string
  mitre_tactic?: string
  mitre_technique_name?: string
  assignee?: { id: string; display_name: string }
  assigned_at?: string
  suppressed: boolean
  correlation_count: number
  first_detected_at: string
  last_detected_at: string
  alert_count: number
  resolved_at?: string
  created_at: string
}

export type AlertSeverity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type AlertStatus = 'new' | 'acknowledged' | 'investigating' | 'resolved' | 'false_positive' | 'closed'

export interface Policy {
  id: string
  name: string
  description?: string
  policy_type: PolicyType
  policy_type_label: string
  version: number
  status: PolicyStatus
  status_label: string
  target_type: string
  target_value: string[]
  rules: any
  priority: number
  effective_start?: string
  effective_end?: string
  created_by: { id: string; display_name: string }
  created_at: string
  updated_at: string
  enabled: boolean
}

export type PolicyType =
  | 'file_integrity'
  | 'process_whitelist'
  | 'network_firewall'
  | 'login_policy'
  | 'vulnerability_scan'
  | 'log_audit'

export type PolicyStatus = 'draft' | 'enabled' | 'disabled' | 'archived'

export interface AuditLog {
  id: number
  user_id: string
  username: string
  action: string
  resource_type: string
  resource_id?: string
  resource_name?: string
  detail: any
  ip_address?: string
  result: string
  created_at: string
}

export interface DashboardOverview {
  total_alerts: number
  active_alerts: number
  critical_alerts: number
  resolved_alerts: number
  total_agents: number
  online_agents: number
  offline_agents: number
  active_policies: number
  alerts_today: number
  resolved_today: number
  avg_response_time_hours: number | null
  alert_trend: any | null
  // Computed / derived by store to match template expectations
  active_agents?: number
  high_severity_alerts?: number
  health_score?: number
  alert_trend_percent?: number
  agent_trend_percent?: number
  high_trend_percent?: number
  health_trend_percent?: number
}

export interface AlertTrend {
  date: string
  critical: number
  high: number
  medium: number
  low: number
}

export interface AgentHealthDistribution {
  online: number
  offline: number
  error: number
  pending: number
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  size: number
  total_pages: number
}

export interface ApiResponse<T> {
  code: number
  message: string
  data: T
  request_id: string
}