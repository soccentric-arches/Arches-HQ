import type {
  ActiveAlarmListResponse,
  Alarm,
  AlarmRule,
  AuditLogListResponse,
  Backup,
  BackupListResponse,
  ConfigSection,
  Device,
  DeviceAlarm,
  DeviceAlarmListResponse,
  DeviceConfig,
  DeviceCreateResponse,
  DeviceListResponse,
  FaultListResponse,
  LogBundleListResponse,
  RolloutTarget,
  UpdateArtifact,
  UpdateArtifactListResponse,
  UpdateRolloutListResponse,
  User,
  UserRole,
} from './types'

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`/api${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ?? detail
    } catch {
      // response had no JSON body -- fall back to statusText
    }
    throw new ApiError(res.status, detail)
  }
  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ ok: boolean }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    logout: () => request<{ ok: boolean }>('/auth/logout', { method: 'POST' }),
    me: () => request<User>('/auth/me'),
  },
  devices: {
    list: (params: { q?: string; limit?: number; offset?: number } = {}) => {
      const qs = new URLSearchParams()
      if (params.q) qs.set('q', params.q)
      if (params.limit) qs.set('limit', String(params.limit))
      if (params.offset) qs.set('offset', String(params.offset))
      const suffix = qs.toString() ? `?${qs}` : ''
      return request<DeviceListResponse>(`/devices${suffix}`)
    },
    get: (id: string) => request<Device>(`/devices/${id}`),
    create: (name: string) =>
      request<DeviceCreateResponse>('/devices', { method: 'POST', body: JSON.stringify({ name }) }),
    bulkProvision: (names: string[]) =>
      request<{
        items: { device: Device; pairing_token: string | null }[];
      }>('/devices/bulk', { method: 'POST', body: JSON.stringify({ names }) }),
    rename: (id: string, name: string) =>
      request<Device>(`/devices/${id}`, { method: 'PATCH', body: JSON.stringify({ name }) }),
    telemetry: (id: string, since?: string) => {
      const qs = since ? `?since=${encodeURIComponent(since)}` : ''
      return request<Record<string, { recorded_at: string; value: number }[]>>(
        `/devices/${id}/telemetry${qs}`,
      )
    },
    factoryReset: (id: string) =>
      request<{ ok: boolean }>(`/devices/${id}/factory-reset`, { method: 'POST' }),
    disable: (id: string) => request<Device>(`/devices/${id}/disable`, { method: 'POST' }),
    reboot: (id: string) => request<{ ok: boolean }>(`/devices/${id}/reboot`, { method: 'POST' }),
    shutdown: (id: string) =>
      request<{ ok: boolean }>(`/devices/${id}/shutdown`, { method: 'POST' }),
    getConfig: (id: string, section: ConfigSection) =>
      request<DeviceConfig>(`/devices/${id}/config/${section}`),
    putConfig: (id: string, section: ConfigSection, config: Record<string, unknown>) =>
      request<DeviceConfig>(`/devices/${id}/config/${section}`, {
        method: 'PUT',
        body: JSON.stringify({ config }),
      }),
    rotateCredential: (id: string) =>
      request<DeviceCreateResponse>(`/devices/${id}/credential/rotate`, { method: 'POST' }),
    revokeCredential: (id: string) =>
      request<{ ok: boolean }>(`/devices/${id}/credential/revoke`, { method: 'POST' }),
    exportData: (id: string) =>
      request<{ ok: boolean; path: string; size_bytes: number }>(`/devices/${id}/export`, {
        method: 'POST',
      }),
    importData: (id: string) =>
      request<{ ok: boolean; imported: Record<string, number> }>(`/devices/${id}/import`, {
        method: 'POST',
      }),
    downloadExportUrl: (id: string) => `/api/devices/${id}/export/download`,
  },
  updates: {
    listArtifacts: () => request<UpdateArtifactListResponse>('/update/artifacts'),
    createArtifact: (body: Omit<UpdateArtifact, 'id'>) =>
      request<UpdateArtifact>('/update/artifacts', { method: 'POST', body: JSON.stringify(body) }),
    listRollouts: () => request<UpdateRolloutListResponse>('/update/rollouts'),
    createRollout: (body: { artifact_id: string; target: RolloutTarget; device_ids?: string[] }) =>
      request<{ ok: boolean; rollout_id: string; device_count: number }>('/update/rollouts', {
        method: 'POST',
        body: JSON.stringify(body),
      }),
  },
  faults: {
    list: (deviceId: string, since?: string) => {
      const qs = since ? `?since=${encodeURIComponent(since)}` : ''
      return request<FaultListResponse>(`/devices/${deviceId}/faults${qs}`)
    },
  },
  alarms: {
    active: () => request<ActiveAlarmListResponse>('/alarms/active'),
    listForDevice: (deviceId: string, since?: string) => {
      const qs = since ? `?since=${encodeURIComponent(since)}` : ''
      return request<DeviceAlarmListResponse>(`/devices/${deviceId}/alarms${qs}`)
    },
    acknowledge: (id: string) => request<Alarm>(`/alarms/${id}/acknowledge`, { method: 'POST' }),
    resolve: (id: string) => request<Alarm>(`/alarms/${id}/resolve`, { method: 'POST' }),
    clear: (deviceId: string, alarmId: string) =>
      request<DeviceAlarm>(`/devices/${deviceId}/alarms/${alarmId}/clear`, { method: 'POST' }),
  },
  alarmRules: {
    list: () => request<AlarmRule[]>('/alarm-rules'),
    create: (name: string, condition: Record<string, unknown>) =>
      request<AlarmRule>('/alarm-rules', { method: 'POST', body: JSON.stringify({ name, condition }) }),
  },
  logs: {
    list: (deviceId: string) => request<LogBundleListResponse>(`/devices/${deviceId}/logs`),
    downloadUrl: (deviceId: string, bundleId: string) =>
      request<{ download_url: string }>(`/devices/${deviceId}/logs/${bundleId}/download`),
  },
  backups: {
    list: (deviceId: string) => request<BackupListResponse>(`/devices/${deviceId}/backups`),
    takeNow: (deviceId: string) => request<Backup>(`/devices/${deviceId}/backups`, { method: 'POST' }),
    restore: (deviceId: string, backupId: string) =>
      request<{ ok: boolean }>(`/devices/${deviceId}/backups/${backupId}/restore`, { method: 'POST' }),
  },
  users: {
    list: () => request<User[]>('/users'),
    invite: (email: string, role: UserRole, password: string) =>
      request<User>('/users/invite', {
        method: 'POST',
        body: JSON.stringify({ email, role, password }),
      }),
  },
  auditLog: {
    list: (params: { limit?: number; offset?: number } = {}) => {
      const qs = new URLSearchParams()
      if (params.limit) qs.set('limit', String(params.limit))
      if (params.offset) qs.set('offset', String(params.offset))
      const suffix = qs.toString() ? `?${qs}` : ''
      return request<AuditLogListResponse>(`/audit-log${suffix}`)
    },
  },
}
