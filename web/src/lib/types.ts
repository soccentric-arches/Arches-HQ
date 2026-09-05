export type UserRole = 'viewer' | 'operator' | 'admin'
export type PairingState = 'pending' | 'authorized' | 'disabled' | 'revoked'

export interface Page {
  total: number
  limit: number
  offset: number
}

export interface User {
  id: string
  email: string
  role: UserRole
  created_at: string
}

export interface Device {
  id: string
  name: string
  pairing_state: PairingState
  online: boolean
  last_seen_at: string | null
  serial: string | null
  board_rev: string | null
  // Agent-reported identity (Arches-Configuration); null until the device pairs.
  ip_address?: string | null
  hostname?: string | null
  os_version?: string | null
  sw_version?: string | null
  // From the heartbeat frame; null until first connect.
  agent_version?: string | null
  // AgentReport state dump: hardware inventory, services, network status.
  reported?: Record<string, unknown> | null
  created_at: string
}

export type ConfigSection = 'system' | 'time' | 'network' | 'security'

export interface DeviceConfig {
  device_id: string
  section: ConfigSection
  config: Record<string, unknown>
  updated_at: string
}

export interface DeviceGroup {
  id: string
  name: string
  device_ids: string[]
}

export interface DeviceListResponse {
  items: Device[]
  page: Page
}

export interface DeviceCreateResponse {
  device: Device
  pairing_token: string | null
}

export interface AuditLogEntry {
  id: string
  actor_user_id: string | null
  action: string
  target_device_id: string | null
  payload: Record<string, unknown>
  created_at: string
}

export interface AuditLogListResponse {
  items: AuditLogEntry[]
  page: Page
}

export type FaultSeverity = 'info' | 'warn' | 'critical'

export interface Fault {
  id: string
  device_id: string
  code: string
  severity: FaultSeverity
  message: string
  raised_at: string
  cleared_at: string | null
}

export interface FaultListResponse {
  items: Fault[]
  page: Page
}

export type AlarmState = 'active' | 'acknowledged' | 'resolved'

export interface Alarm {
  id: string
  alarm_rule_id: string
  device_id: string
  state: AlarmState
  triggered_at: string
  acknowledged_at: string | null
  resolved_at: string | null
}

export interface AlarmListResponse {
  items: Alarm[]
  page: Page
}

// Device-reported 4-byte alarm from the `alarms` table (GET /devices/{id}/alarms).
// `alarm_code` is the packed big-endian uint32 (byte0=major_id, byte1=sub_section,
// byte2=fault_type, byte3=severity), e.g. 0x01020304 -> (1, 2, 3, 4).
export interface DeviceAlarm {
  id: string
  device_id: string
  major_id: number
  sub_section: number
  fault_type: number
  severity: number
  alarm_code: number
  state: AlarmState
  triggered_at: string
  resolved_at: string | null
}

export interface DeviceAlarmListResponse {
  items: DeviceAlarm[]
  page: Page
}

export interface ActiveAlarm {
  id: string
  device_id: string
  device_name: string
  major_id: number
  sub_section: number
  fault_type: number
  severity: number
  alarm_code: number
  state: 'active' | 'acknowledged' | 'resolved'
  triggered_at: string
}

export interface ActiveAlarmListResponse {
  count: number
  items: ActiveAlarm[]
}

export interface AlarmRule {
  id: string
  name: string
  condition: Record<string, unknown>
  notify_channels: Record<string, unknown>
  enabled: boolean
}

export interface LogBundle {
  id: string
  device_id: string
  size_bytes: number
  uploaded_at: string
  time_range_start: string
  time_range_end: string
}

export interface LogBundleListResponse {
  items: LogBundle[]
  page: Page
}

export interface Backup {
  id: string
  device_id: string
  size_bytes: number
  created_at: string
  restored_at: string | null
}

export interface BackupListResponse {
  items: Backup[]
  page: Page
}

export type RolloutTarget = 'all' | 'device_group' | 'specific_devices'
export type RolloutStatus = 'pending' | 'in_progress' | 'completed' | 'failed'
export type DeviceRolloutStatus = 'pending' | 'applying' | 'succeeded' | 'failed'

export interface UpdateArtifact {
  id: string
  version: string
  target_board_rev: string
  storage_url: string
  checksum_sha256: string
}

export interface UpdateArtifactListResponse {
  items: UpdateArtifact[]
  page: Page
}

export interface UpdateRolloutDevice {
  device_id: string
  status: DeviceRolloutStatus
  applied_at: string | null
  error: string | null
}

export interface UpdateRollout {
  id: string
  artifact_id: string
  artifact_version: string
  target: RolloutTarget
  status: RolloutStatus
  started_at: string | null
  completed_at: string | null
  devices: UpdateRolloutDevice[]
}

export interface UpdateRolloutListResponse {
  items: UpdateRollout[]
  page: Page
}
