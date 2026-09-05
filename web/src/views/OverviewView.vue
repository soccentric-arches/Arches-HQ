<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Activity, BellRing, PackageOpen, RefreshCw, Satellite } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { AuditLogEntry, Device, UpdateRollout } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'

const auth = useAuthStore()

const devices = ref<Device[]>([])
const rollouts = ref<UpdateRollout[]>([])
const activeAlarms = ref<{ id: string; device_id: string; device_name: string; alarm_code: number; triggered_at: string }[]>([])
const activeAlarmsCount = ref(0)
const recentActivity = ref<AuditLogEntry[]>([])
const loading = ref(true)
const error = ref('')

const stats = computed(() => ({
  total: devices.value.length,
  online: devices.value.filter((d) => d.online).length,
  offline: devices.value.filter((d) => !d.online).length,
  pending: devices.value.filter((d) => d.pairing_state === 'pending').length,
}))

// Version spread: group by the agent-reported software version (fallback OS).
const versionSpread = computed(() => {
  const counts = new Map<string, number>()
  for (const d of devices.value) {
    const key = d.sw_version ?? d.os_version ?? 'not reported'
    counts.set(key, (counts.get(key) ?? 0) + 1)
  }
  return [...counts.entries()].sort((a, b) => b[1] - a[1])
})

// Platform family breakdown — fleet devices are named <platform>-0001.
const platformFamilies = computed(() => {
  const map = new Map<string, { total: number; online: number }>()
  for (const d of devices.value) {
    const family = d.name.split('-')[0] || 'other'
    const entry = map.get(family) ?? { total: 0, online: 0 }
    entry.total += 1
    if (d.online) entry.online += 1
    map.set(family, entry)
  }
  return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0]))
})

// Fleet status donut geometry.
const donut = computed(() => {
  const { online, offline, pending, total } = stats.value
  const segments: { label: string; count: number; color: string; offset: number }[] = []
  let acc = 25 // start at 12 o'clock
  for (const [label, count, color] of [
    ['Online', online, 'var(--color-success)'],
    ['Offline', offline, 'var(--color-border-strong)'],
    ['Awaiting pairing', pending, 'var(--color-warning)'],
  ] as const) {
    const pct = total ? (count / total) * 100 : 0
    segments.push({ label, count, color, offset: acc })
    acc += pct
  }
  return { segments, total }
})

const activeRollouts = computed(() => rollouts.value.filter((r) => r.status === 'in_progress'))

const glanceDevices = computed(() =>
  [...devices.value]
    .sort((a, b) => Number(b.online) - Number(a.online) || a.name.localeCompare(b.name))
    .slice(0, 8),
)

function familyLabel(family: string) {
  return family.charAt(0).toUpperCase() + family.slice(1)
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const jobs: Promise<unknown>[] = [
      api.devices.list({ limit: 200 }).then((d) => (devices.value = d.items)),
      api.updates.listRollouts().then((r) => (rollouts.value = r.items)),
      api.alarms.active().then((a) => {
        activeAlarms.value = a.items
        activeAlarmsCount.value = a.count
      }),
    ]
    if (auth.hasRole('admin')) {
      jobs.push(api.auditLog.list({ limit: 6 }).then((a) => (recentActivity.value = a.items)))
    }
    await Promise.all(jobs)
  } catch {
    error.value = 'Could not load fleet data.'
  } finally {
    loading.value = false
  }
}

// Live: refresh every 30s.
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  load()
  timer = setInterval(() => load(true), 30000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold">Fleet overview</h1>
        <p class="flex items-center gap-2 text-sm text-muted-foreground">
          <span class="relative flex h-2 w-2">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
            <span class="relative inline-flex h-2 w-2 rounded-full bg-success" />
          </span>
          Live — refreshes every 30 s
        </p>
      </div>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
        @click="load()"
      >
        <RefreshCw class="h-3.5 w-3.5" /> Refresh
      </button>
    </div>

    <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
    <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <template v-else>
      <!-- stat cards -->
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <RouterLink :to="{ name: 'devices' }" class="contents">
          <Card class="p-4 transition-colors hover:bg-surface-muted">
            <p class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <Satellite class="h-3.5 w-3.5" /> Devices
            </p>
            <p class="mt-2 text-2xl font-semibold">{{ stats.total }}</p>
            <p class="mt-1 text-xs text-muted-foreground">
              {{ stats.online }} online · {{ stats.offline }} offline
            </p>
          </Card>
        </RouterLink>
        <RouterLink to="/deployments" class="contents">
          <Card class="p-4 transition-colors hover:bg-surface-muted">
            <p class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <PackageOpen class="h-3.5 w-3.5" /> Deployments
            </p>
            <p class="mt-2 text-2xl font-semibold">{{ activeRollouts.length }}</p>
            <p class="mt-1 text-xs text-muted-foreground">rollouts in progress</p>
          </Card>
        </RouterLink>
        <RouterLink to="/alarm-rules" class="contents">
          <Card class="p-4 transition-colors hover:bg-surface-muted">
            <p class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              <BellRing class="h-3.5 w-3.5" /> Active alarms
            </p>
            <p class="mt-2 text-2xl font-semibold" :class="activeAlarmsCount > 0 ? 'text-danger' : ''">
              {{ activeAlarmsCount }}
            </p>
            <p class="mt-1 text-xs text-muted-foreground">across the fleet</p>
          </Card>
        </RouterLink>
        <Card class="p-4">
          <p class="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            <Activity class="h-3.5 w-3.5" /> Pairing queue
          </p>
          <p class="mt-2 text-2xl font-semibold">{{ stats.pending }}</p>
          <p class="mt-1 text-xs text-muted-foreground">devices awaiting pairing</p>
        </Card>
      </div>

      <!-- donut + platform families -->
      <div class="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card class="p-4">
          <h3 class="text-sm font-semibold">Fleet status</h3>
          <div class="mt-3 flex items-center gap-6">
            <svg viewBox="0 0 36 36" class="h-28 w-28 shrink-0 -rotate-90">
              <circle cx="18" cy="18" r="15.9155" fill="none" stroke="var(--color-surface-muted)" stroke-width="4" />
              <circle
                v-for="s in donut.segments"
                :key="s.label"
                cx="18"
                cy="18"
                r="15.9155"
                fill="none"
                :stroke="s.color"
                stroke-width="4"
                :stroke-dasharray="`${s.count && donut.total ? (s.count / donut.total) * 100 : 0} ${100}`"
                :stroke-dashoffset="s.offset"
              />
            </svg>
            <ul class="min-w-0 flex-1 space-y-2 text-sm">
              <li v-for="s in donut.segments" :key="s.label" class="flex items-center justify-between gap-2">
                <span class="flex items-center gap-2 text-muted-foreground">
                  <span class="h-2 w-2 shrink-0 rounded-full" :style="{ background: s.color }" />
                  {{ s.label }}
                </span>
                <span class="font-medium">{{ s.count }}</span>
              </li>
              <li class="flex items-center justify-between gap-2 border-t border-border pt-2">
                <span class="text-muted-foreground">Total</span>
                <span class="font-semibold">{{ donut.total }}</span>
              </li>
            </ul>
          </div>

          <h4 class="mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Software version spread
          </h4>
          <ul class="mt-2 space-y-2">
            <li v-for="[version, count] in versionSpread" :key="version" class="text-sm">
              <div class="flex items-center justify-between">
                <span class="truncate font-mono text-xs">{{ version }}</span>
                <Badge tone="neutral">{{ count }}</Badge>
              </div>
              <div class="mt-1 h-1.5 w-full rounded-full bg-surface-muted">
                <div
                  class="h-1.5 rounded-full bg-accent"
                  :style="{ width: `${(count / stats.total) * 100}%` }"
                />
              </div>
            </li>
          </ul>
        </Card>

        <Card class="p-4">
          <h3 class="text-sm font-semibold">Platform families</h3>
          <p class="mt-1 text-xs text-muted-foreground">Online per platform family.</p>
          <ul class="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <li v-for="[family, s] in platformFamilies" :key="family" class="rounded-md border border-border px-3 py-2">
              <div class="flex items-center justify-between gap-2 text-sm">
                <span class="truncate font-medium">{{ familyLabel(family) }}</span>
                <Badge :tone="s.online > 0 ? 'success' : 'neutral'">
                  {{ s.online }}/{{ s.total }}
                </Badge>
              </div>
              <div class="mt-1.5 h-1 w-full rounded-full bg-surface-muted">
                <div
                  class="h-1 rounded-full"
                  :class="s.online > 0 ? 'bg-success' : 'bg-border-strong'"
                  :style="{ width: `${s.total ? (s.online / s.total) * 100 : 0}%` }"
                />
              </div>
            </li>
          </ul>
        </Card>
      </div>

      <!-- devices at a glance + alarms/activity -->
      <div class="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card class="p-4">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold">Devices at a glance</h3>
            <RouterLink :to="{ name: 'devices' }" class="text-xs text-muted-foreground hover:text-foreground">
              View all →
            </RouterLink>
          </div>
          <p v-if="glanceDevices.length === 0" class="mt-3 text-sm text-muted-foreground">
            No devices yet.
          </p>
          <ul v-else class="mt-3 divide-y divide-border">
            <li v-for="d in glanceDevices" :key="d.id">
              <RouterLink
                :to="{ name: 'device-detail', params: { id: d.id } }"
                class="flex items-center justify-between gap-3 py-2 text-sm hover:text-accent"
              >
                <span class="flex min-w-0 items-center gap-2">
                  <span
                    class="h-1.5 w-1.5 shrink-0 rounded-full"
                    :class="d.online ? 'bg-success' : 'bg-border-strong'"
                  />
                  <span class="truncate font-medium">{{ d.name }}</span>
                </span>
                <span class="shrink-0 text-xs text-muted-foreground">
                  {{ d.sw_version ?? d.os_version ?? d.last_seen_at ? new Date(d.last_seen_at ?? d.created_at).toLocaleDateString() : 'never seen' }}
                </span>
              </RouterLink>
            </li>
          </ul>
        </Card>

        <Card class="p-4">
          <h3 class="text-sm font-semibold">Latest active alarms</h3>
          <p v-if="activeAlarms.length === 0" class="mt-3 text-sm text-muted-foreground">
            No active alarms across the fleet.
          </p>
          <ul v-else class="mt-3 divide-y divide-border">
            <li v-for="a in activeAlarms.slice(0, 5)" :key="a.id">
              <RouterLink
                :to="{ name: 'device-detail', params: { id: a.device_id }, query: { section: 'alarms' } }"
                class="flex items-center justify-between gap-2 py-2 text-sm hover:text-accent"
              >
                <span class="min-w-0 truncate">
                  <span class="font-medium">{{ a.device_name }}</span>
                  <span class="ml-2 font-mono text-xs text-muted-foreground">
                    0x{{ a.alarm_code.toString(16).padStart(8, '0') }}
                  </span>
                </span>
                <span class="shrink-0 text-xs text-muted-foreground">
                  {{ new Date(a.triggered_at).toLocaleTimeString() }}
                </span>
              </RouterLink>
            </li>
          </ul>
        </Card>
      </div>

      <!-- recent activity (admin) -->
      <Card v-if="auth.hasRole('admin') && recentActivity.length" class="mt-4 p-4">
        <div class="flex items-center justify-between">
          <h3 class="text-sm font-semibold">Recent activity</h3>
          <RouterLink to="/audit-log" class="text-xs text-muted-foreground hover:text-foreground">
            Full audit log →
          </RouterLink>
        </div>
        <ul class="mt-3 divide-y divide-border">
          <li v-for="e in recentActivity" :key="e.id" class="flex items-center justify-between gap-3 py-2 text-sm">
            <span class="min-w-0 truncate font-mono text-xs">{{ e.action }}</span>
            <span class="shrink-0 text-xs text-muted-foreground">
              {{ new Date(e.created_at).toLocaleString() }}
            </span>
          </li>
        </ul>
      </Card>
    </template>
  </div>
</template>