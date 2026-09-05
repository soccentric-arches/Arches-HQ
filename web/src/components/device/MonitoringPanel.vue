<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { api } from '@/lib/api'
import Card from '@/components/ui/Card.vue'

const props = defineProps<{ deviceId: string }>()

interface Point {
  recorded_at: string
  value: number
}

const POLL_MS = 5000

const series = ref<Record<string, Point[]>>({})
const loading = ref(true)
const error = ref('')
const updatedAt = ref<string | null>(null)
let timer: ReturnType<typeof setInterval> | null = null

// Render a sparkline for the most recent `take` points.
function sparklinePath(points: Point[], width = 240, height = 48): string {
  const recent = points.slice(-40)
  if (recent.length < 2) return ''
  const values = recent.map((p) => p.value)
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  return recent
    .map((p, i) => {
      const x = (i / (recent.length - 1)) * width
      const y = height - ((p.value - min) / span) * height
      return `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`
    })
    .join(' ')
}

async function load(silent = false) {
  if (!silent) loading.value = true
  try {
    series.value = await api.devices.telemetry(props.deviceId)
    error.value = ''
    updatedAt.value = new Date().toLocaleTimeString()
  } catch {
    if (!silent) error.value = 'Could not load device metrics.'
  } finally {
    loading.value = false
  }
}

onMounted(() => {
  load()
  timer = setInterval(() => load(true), POLL_MS)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <p class="flex items-center gap-2 text-xs text-muted-foreground">
        <span v-if="!error && updatedAt" class="relative flex h-2 w-2">
          <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
          <span class="relative inline-flex h-2 w-2 rounded-full bg-success" />
        </span>
        <span v-else class="h-2 w-2 rounded-full bg-border-strong" />
        <template v-if="updatedAt">Live — updated {{ updatedAt }}</template>
        <template v-else>Live — waiting for data</template>
      </p>
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
    <Card v-else-if="Object.keys(series).length === 0" class="p-6 text-sm text-muted-foreground">
      The device has not reported any metrics yet. Resource usage (CPU, memory, disk, …) appears
      here as soon as the agent starts sending telemetry.
    </Card>
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      <Card v-for="(points, metric) in series" :key="metric" class="p-4">
        <div class="mb-2 flex items-baseline justify-between gap-2">
          <span class="truncate text-sm font-medium capitalize">{{ metric }}</span>
          <span class="font-mono text-sm text-muted-foreground">{{ points.at(-1)?.value.toFixed(1) }}</span>
        </div>
        <svg viewBox="0 0 240 48" class="h-12 w-full" preserveAspectRatio="none">
          <path :d="sparklinePath(points)" fill="none" stroke="var(--color-accent)" stroke-width="2" />
        </svg>
        <p class="mt-1 text-xs text-muted-foreground">{{ points.length }} samples in window</p>
      </Card>
    </div>
  </div>
</template>