<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { Fault } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'

const props = defineProps<{ deviceId: string }>()

const faults = ref<Fault[]>([])
const loading = ref(true)
const error = ref('')
const LIVE_WINDOW_HOURS = 24

// Time series: faults per hour over the live window.
const counts = ref<{ hour: string; count: number }[]>([])
const maxCount = ref(1)

function refreshChart() {
  const buckets = new Map<string, number>()
  const now = Date.now()
  for (let i = 23; i >= 0; i--) {
    const d = new Date(now - i * 3600_000)
    buckets.set(d.toISOString().slice(0, 13), 0)
  }
  for (const f of faults.value) {
    const key = f.raised_at.slice(0, 13)
    if (buckets.has(key)) buckets.set(key, (buckets.get(key) ?? 0) + 1)
  }
  counts.value = [...buckets.entries()].map(([hour, count]) => ({ hour, count }))
  maxCount.value = Math.max(1, ...counts.value.map((c) => c.count))
}

const sinceIso = () => new Date(Date.now() - LIVE_WINDOW_HOURS * 3600_000).toISOString()

function severityTone(sev: string) {
  return sev === 'critical' ? 'danger' : sev === 'warn' ? 'warning' : 'neutral'
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const res = await api.faults.list(props.deviceId, sinceIso())
    faults.value = res.items
    refreshChart()
  } catch {
    error.value = 'Could not load faults.'
  } finally {
    loading.value = false
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
        Live — hardware faults, last {{ LIVE_WINDOW_HOURS }}h
      </p>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
        @click="load()"
      >
        <RefreshCw class="h-3.5 w-3.5" /> Refresh
      </button>
    </div>

    <!-- time series: faults per hour -->
    <Card v-if="!loading" class="mb-4 p-4">
      <h3 class="text-sm font-semibold">Faults per hour (last 24h)</h3>
      <div class="mt-3 flex h-20 items-end gap-1">
        <div v-for="c in counts" :key="c.hour" class="group relative flex-1">
          <div
            class="w-full rounded-t-sm bg-danger/60 transition-colors group-hover:bg-danger"
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
    <Card v-else-if="faults.length === 0" class="p-6 text-sm text-muted-foreground">
      No faults reported in the last {{ LIVE_WINDOW_HOURS }} hours.
    </Card>
    <Table v-else>
      <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
        <tr>
          <th class="px-4 py-2 font-medium">Code</th>
          <th class="px-4 py-2 font-medium">Severity</th>
          <th class="px-4 py-2 font-medium">Message</th>
          <th class="px-4 py-2 font-medium">Raised</th>
          <th class="px-4 py-2 font-medium">Cleared</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="f in faults" :key="f.id" class="border-b border-border last:border-0">
          <td class="px-4 py-2 font-mono text-xs">{{ f.code }}</td>
          <td class="px-4 py-2">
            <Badge :tone="severityTone(f.severity)" class="capitalize">{{ f.severity }}</Badge>
          </td>
          <td class="max-w-72 truncate px-4 py-2" :title="f.message">{{ f.message }}</td>
          <td class="px-4 py-2 text-muted-foreground">{{ new Date(f.raised_at).toLocaleString() }}</td>
          <td class="px-4 py-2 text-muted-foreground">
            {{ f.cleared_at ? new Date(f.cleared_at).toLocaleString() : '—' }}
          </td>
        </tr>
      </tbody>
    </Table>
  </div>
</template>