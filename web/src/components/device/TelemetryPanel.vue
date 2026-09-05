<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { api } from '@/lib/api'
import Card from '@/components/ui/Card.vue'

const props = defineProps<{ deviceId: string }>()

interface Point {
  recorded_at: string
  value: number
}

// Time range for the series, and whether to keep refreshing live.
const RANGES = [
  { label: '1h', hours: 1 },
  { label: '6h', hours: 6 },
  { label: '24h', hours: 24 },
  { label: '7d', hours: 24 * 7 },
]
const rangeHours = ref(24)
const live = ref(true)
const POLL_MS = 5000

const series = ref<Record<string, Point[]>>({})
const loading = ref(true)
const error = ref('')

let timer: ReturnType<typeof setInterval> | null = null

function sparklinePath(points: Point[], width = 240, height = 48): string {
  const recent = points.slice(-60)
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
    const since = new Date(Date.now() - rangeHours.value * 3600_000).toISOString()
    series.value = await api.devices.telemetry(props.deviceId, since)
    error.value = ''
  } catch {
    if (!silent) error.value = 'Could not load telemetry.'
  } finally {
    loading.value = false
  }
}

function manageTimer() {
  if (timer) {
    clearInterval(timer)
    timer = null
  }
  if (live.value) timer = setInterval(() => load(true), POLL_MS)
}

watch(
  () => props.deviceId,
  () => load(),
)
watch(rangeHours, () => load())
watch(live, manageTimer)
onMounted(() => {
  load()
  manageTimer()
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <div class="flex gap-1">
        <button
          v-for="r in RANGES"
          :key="r.label"
          type="button"
          class="rounded-full border px-3 py-1 text-xs font-medium transition-colors"
          :class="
            rangeHours === r.hours
              ? 'border-accent bg-accent-muted text-accent'
              : 'border-border text-muted-foreground hover:bg-surface-muted'
          "
          @click="rangeHours = r.hours"
        >
          {{ r.label }}
        </button>
      </div>
      <label class="flex items-center gap-2 text-xs text-muted-foreground">
        <input v-model="live" type="checkbox" class="accent-[var(--color-accent)]" />
        Live ({{ POLL_MS / 1000 }}s)
      </label>
    </div>

    <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
    <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <Card v-else-if="Object.keys(series).length === 0" class="p-6 text-sm text-muted-foreground">
      No telemetry in this window. The device agent reports numeric metrics as it runs.
    </Card>
    <div v-else class="grid grid-cols-1 gap-4 sm:grid-cols-2">
      <Card v-for="(points, metric) in series" :key="metric" class="p-4">
        <div class="mb-2 flex items-baseline justify-between gap-2">
          <span class="truncate text-sm font-medium capitalize">{{ metric }}</span>
          <span class="font-mono text-sm text-muted-foreground">
            {{ points.at(-1)?.value.toFixed(1) }}
          </span>
        </div>
        <svg viewBox="0 0 240 48" class="h-16 w-full" preserveAspectRatio="none">
          <path :d="sparklinePath(points)" fill="none" stroke="var(--color-accent)" stroke-width="2" />
        </svg>
        <p class="mt-1 text-xs text-muted-foreground">
          {{ points.length }} samples in window
          <span v-if="points[0]" class="block">
            since {{ new Date(points[0]?.recorded_at ?? '').toLocaleString() }}
          </span>
        </p>
      </Card>
    </div>
  </div>
</template>