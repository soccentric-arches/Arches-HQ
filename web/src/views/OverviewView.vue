<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Activity, BellRing, PackageOpen, RefreshCw, Satellite } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { Device, UpdateRollout } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'


const devices = ref<Device[]>([])
const rollouts = ref<UpdateRollout[]>([])
const activeAlarms = ref(0)
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

const activeRollouts = computed(() => rollouts.value.filter((r) => r.status === 'in_progress'))

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const [d, r, a] = await Promise.all([
      api.devices.list({ limit: 200 }),
      api.updates.listRollouts(),
      api.alarms.active(),
    ])
    devices.value = d.items
    rollouts.value = r.items
    activeAlarms.value = a.count
  } catch {
    error.value = 'Could not load fleet data.'
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold">Fleet overview</h1>
        <p class="text-sm text-muted-foreground">Health across every platform family.</p>
      </div>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
        @click="load(true)"
      >
        <RefreshCw class="h-3.5 w-3.5" /> Refresh
      </button>
    </div>

    <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
    <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <template v-else>
      <div class="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <RouterLink to="/" class="contents">
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
            <p class="mt-2 text-2xl font-semibold" :class="activeAlarms > 0 ? 'text-danger' : ''">
              {{ activeAlarms }}
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

      <div class="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card class="p-4">
          <h3 class="text-sm font-semibold">Software version spread</h3>
          <p class="mt-1 text-xs text-muted-foreground">
            Grouped by the agent-reported software version.
          </p>
          <ul class="mt-3 space-y-2">
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
          <h3 class="text-sm font-semibold">Recent rollouts</h3>
          <p v-if="rollouts.length === 0" class="mt-2 text-sm text-muted-foreground">
            No rollouts yet — start one from a device's OTA page.
          </p>
          <ul v-else class="mt-3 space-y-2">
            <li v-for="r in rollouts.slice(0, 6)" :key="r.id" class="flex items-center justify-between gap-2 text-sm">
              <span class="min-w-0 truncate">v{{ r.artifact_version }} · {{ r.devices.length }} device(s)</span>
              <Badge :tone="r.status === 'completed' ? 'success' : r.status === 'failed' ? 'danger' : 'warning'" class="capitalize">
                {{ r.status.replace('_', ' ') }}
              </Badge>
            </li>
          </ul>
        </Card>
      </div>
    </template>
  </div>
</template>