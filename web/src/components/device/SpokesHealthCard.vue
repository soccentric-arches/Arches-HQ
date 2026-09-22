<script setup lang="ts">
import { computed } from 'vue'
import { Activity, CircleAlert, CircleCheck, CirclePause } from 'lucide-vue-next'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'
import type { Device, SpokeStatus } from '@/lib/types'

// Device health and per-spoke status, from the fields the device's periodic
// AgentReport promotes onto the device row (Task.md F-05). Before this panel
// existed a spoke could restart for a week with nothing on any screen.
const props = defineProps<{ device: Device }>()

const spokes = computed<SpokeStatus[]>(() => {
  const raw = props.device.spoke_status
  if (!raw) return []
  if (Array.isArray(raw)) return raw as SpokeStatus[]
  return Object.entries(raw).map(([name, v]) => {
    const rec = (v ?? {}) as Record<string, unknown>
    return {
      name,
      state: String(rec.state ?? 'unknown'),
      live: typeof rec.live === 'boolean' ? rec.live : undefined,
      restarts: typeof rec.restarts === 'number' ? rec.restarts : undefined,
    }
  })
})

const scorePct = computed(() => {
  const s = props.device.health_score
  return s === null || s === undefined ? null : Math.round(s * 100)
})

function scoreTone(pct: number | null) {
  if (pct === null) return 'neutral'
  return pct >= 80 ? 'success' : pct >= 50 ? 'warning' : 'danger'
}

function spokeTone(state: string) {
  switch (state) {
    case 'ready':
      return 'success'
    case 'degraded':
    case 'starting':
      return 'warning'
    case 'stopped':
    case 'hung':
      return 'danger'
    default:
      return 'neutral'
  }
}

function spokeIcon(state: string) {
  switch (state) {
    case 'ready':
      return CircleCheck
    case 'degraded':
    case 'starting':
      return CirclePause
    default:
      return CircleAlert
  }
}

const unhealthy = computed(() => spokes.value.filter((s) => s.state !== 'ready'))
</script>

<template>
  <Card class="p-5">
    <div class="mb-3 flex items-center justify-between">
      <h3 class="flex items-center gap-2 text-sm font-medium">
        <Activity class="h-4 w-4 text-muted-foreground" /> Instrumentation health
      </h3>
      <Badge v-if="scorePct !== null" :tone="scoreTone(scorePct)">{{ scorePct }} / 100</Badge>
      <Badge v-else tone="neutral">no report yet</Badge>
    </div>

    <p v-if="spokes.length === 0" class="text-xs text-muted-foreground">
      The device has not pushed a spoke report yet. It appears here after the first
      AgentReport arrives over the device link.
    </p>

    <template v-else>
      <p v-if="unhealthy.length" class="mb-3 text-xs text-warning">
        {{ unhealthy.length }} of {{ spokes.length }} spokes not ready —
        {{ unhealthy.map((s) => s.name).join(', ') }}
      </p>
      <ul class="grid gap-1.5 text-sm sm:grid-cols-2">
        <li
          v-for="s in spokes"
          :key="s.name"
          class="flex items-center justify-between rounded-md border border-border px-2.5 py-1.5"
        >
          <span class="flex items-center gap-2 font-mono text-xs">
            <component :is="spokeIcon(s.state)" class="h-3.5 w-3.5" :class="spokeTone(s.state) === 'danger' ? 'text-danger' : spokeTone(s.state) === 'warning' ? 'text-warning' : 'text-success'" />
            {{ s.name }}
          </span>
          <span class="flex items-center gap-2">
            <span v-if="s.restarts" class="text-xs text-muted-foreground">↻ {{ s.restarts }}</span>
            <Badge :tone="spokeTone(s.state)" class="capitalize">{{ s.state }}</Badge>
          </span>
        </li>
      </ul>
    </template>
  </Card>
</template>