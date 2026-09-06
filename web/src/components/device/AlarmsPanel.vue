<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { api, ApiError } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import type { DeviceAlarm } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'

const props = defineProps<{ deviceId: string }>()
const auth = useAuthStore()

const alarms = ref<DeviceAlarm[]>([])
const loading = ref(true)
const error = ref('')
const busy = ref(false)
const LIVE_WINDOW_HOURS = 24

// Time series: alarms per hour over the live window, bucketed client-side
// from the device-scoped feed.
function hourlyCounts(): { hour: string; count: number }[] {
  const buckets = new Map<string, number>()
  const now = Date.now()
  for (let i = 23; i >= 0; i--) {
    const d = new Date(now - i * 3600_000)
    buckets.set(d.toISOString().slice(0, 13), 0)
  }
  for (const a of alarms.value) {
    const key = a.triggered_at.slice(0, 13)
    if (buckets.has(key)) buckets.set(key, (buckets.get(key) ?? 0) + 1)
  }
  return [...buckets.entries()].map(([hour, count]) => ({ hour, count }))
}

const counts = ref<{ hour: string; count: number }[]>([])
const maxCount = ref(1)

function refreshChart() {
  counts.value = hourlyCounts()
  maxCount.value = Math.max(1, ...counts.value.map((c) => c.count))
}

const sinceIso = () => new Date(Date.now() - LIVE_WINDOW_HOURS * 3600_000).toISOString()

function alarmTone(state: string) {
  return state === 'active' ? 'danger' : state === 'acknowledged' ? 'warning' : 'success'
}

// Severity chips for the five X.733 levels (Task.md C-05). MAJOR and MINOR
// used to have no representation at all.
function severityTone(severity: string) {
  switch (severity) {
    case 'critical':
      return 'danger'
    case 'major':
      return 'danger'
    case 'minor':
      return 'warning'
    case 'warning':
      return 'warning'
    default:
      return 'neutral'
  }
}

// Render a packed alarm_code as a hex string, e.g. 0x10410007.
function alarmCodeHex(code: number) {
  return `0x${code.toString(16).padStart(8, '0')}`
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const res = await api.alarms.listForDevice(props.deviceId, sinceIso())
    alarms.value = res.items
    refreshChart()
  } catch {
    error.value = 'Could not load alarms.'
  } finally {
    loading.value = false
  }
}

async function clear(alarm: DeviceAlarm) {
  busy.value = true
  try {
    await api.alarms.clear(props.deviceId, alarm.id)
    await load(true)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Could not clear alarm.'
  } finally {
    busy.value = false
  }
}

// Real-time view: poll the feed on an interval.
let timer: ReturnType<typeof setInterval> | null = null

watch(
  () => props.deviceId,
  () => load(),
)
onMounted(() => {
  load()
  timer = setInterval(() => load(true), 10000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <p class="flex items-center gap-2 text-xs text-muted-foreground">
        <span class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
          <span class="relative inline-flex h-2 w-2 rounded-full bg-success" />
        </span>
        Live — device-reported alarms, last {{ LIVE_WINDOW_HOURS }}h
      </p>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
        @click="load()"
      >
        <RefreshCw class="h-3.5 w-3.5" /> Refresh
      </button>
    </div>

    <!-- time series: alarms per hour -->
    <Card v-if="!loading" class="mb-4 p-4">
      <h3 class="text-sm font-semibold">Alarms per hour (last 24h)</h3>
      <div class="mt-3 flex h-20 items-end gap-1">
        <div v-for="c in counts" :key="c.hour" class="group relative flex-1">
          <div
            class="w-full rounded-t-sm bg-accent/70 transition-colors group-hover:bg-accent"
            :style="{ height: `${Math.max(4, (c.count / maxCount) * 76)}px` }"
          />
          <span
            class="pointer-events-none absolute -top-5 left-1/2 hidden -translate-x-1/2 text-[10px] text-muted-foreground group-hover:block"
          >
            {{ c.count }}
          </span>
        </div>
      </div>
      <div class="mt-1 flex justify-between text-[10px] text-muted-foreground">
        <span>-24h</span>
        <span>now</span>
      </div>
    </Card>

    <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
    <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <Card v-else-if="alarms.length === 0" class="p-6 text-sm text-muted-foreground">
      No alarms reported in the last {{ LIVE_WINDOW_HOURS }} hours.
    </Card>
    <Table v-else>
      <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
        <tr>
          <th class="px-4 py-2 font-medium">Code</th>
          <th class="px-4 py-2 font-medium">Domain</th>
          <th class="px-4 py-2 font-medium">Module</th>
          <th class="px-4 py-2 font-medium">Type</th>
          <th class="px-4 py-2 font-medium">Index</th>
          <th class="px-4 py-2 font-medium">Severity</th>
          <th class="px-4 py-2 font-medium">State</th>
          <th class="px-4 py-2 font-medium">Triggered</th>
          <th class="px-4 py-2 font-medium"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in alarms" :key="a.id" class="border-b border-border last:border-0">
          <td class="px-4 py-2 font-mono text-xs">{{ alarmCodeHex(a.alarm_code) }}</td>
          <td class="px-4 py-2">{{ a.domain }}</td>
          <td class="px-4 py-2">{{ a.module }}</td>
          <td class="px-4 py-2">{{ a.alarm_type }}</td>
          <td class="px-4 py-2">{{ a.alarm_index }}</td>
          <td class="px-4 py-2">
            <Badge :tone="severityTone(a.severity)" class="capitalize">{{ a.severity }}</Badge>
          </td>
          <td class="px-4 py-2">
            <Badge :tone="alarmTone(a.state)" class="capitalize">{{ a.state }}</Badge>
          </td>
          <td class="px-4 py-2 text-muted-foreground">{{ new Date(a.triggered_at).toLocaleString() }}</td>
          <td class="px-4 py-2 text-right">
            <Button
              v-if="auth.hasRole('operator') && a.state !== 'resolved'"
              size="sm"
              variant="secondary"
              :disabled="busy"
              @click="clear(a)"
              >Clear</Button
            >
          </td>
        </tr>
      </tbody>
    </Table>
  </div>
</template>