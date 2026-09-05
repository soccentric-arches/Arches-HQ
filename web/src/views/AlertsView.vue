<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { RefreshCw } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { ActiveAlarm } from '@/lib/types'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'

const alarms = ref<ActiveAlarm[]>([])
const count = ref(0)
const loading = ref(true)
const error = ref('')

function alarmHex(code: number) {
  return `0x${code.toString(16).padStart(8, '0')}`
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const res = await api.alarms.active()
    alarms.value = res.items
    count.value = res.count
  } catch {
    error.value = 'Could not load active alarms.'
  } finally {
    loading.value = false
  }
}

// Live: poll every 15s.
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  load()
  timer = setInterval(() => load(true), 15000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold">Alerts</h1>
        <p class="flex items-center gap-2 text-sm text-muted-foreground">
          <span class="relative flex h-2 w-2">
            <span class="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
            <span class="relative inline-flex h-2 w-2 rounded-full bg-success" />
          </span>
          {{ count }} active across the fleet ·
          <RouterLink to="/alarm-rules" class="underline hover:text-foreground">manage rules</RouterLink>
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
    <Card v-else-if="alarms.length === 0" class="p-6 text-sm text-muted-foreground">
      No active alarms across the fleet.
    </Card>
    <Table v-else>
      <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
        <tr>
          <th class="px-4 py-2 font-medium">Device</th>
          <th class="px-4 py-2 font-medium">Code</th>
          <th class="px-4 py-2 font-medium">Major</th>
          <th class="px-4 py-2 font-medium">Sub</th>
          <th class="px-4 py-2 font-medium">Fault</th>
          <th class="px-4 py-2 font-medium">Severity</th>
          <th class="px-4 py-2 font-medium">Triggered</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="a in alarms" :key="a.id" class="border-b border-border last:border-0">
          <td class="px-4 py-2">
            <RouterLink
              :to="{ name: 'device-detail', params: { id: a.device_id }, query: { section: 'alarms' } }"
              class="font-medium hover:text-accent"
            >
              {{ a.device_name }}
            </RouterLink>
          </td>
          <td class="px-4 py-2 font-mono text-xs">{{ alarmHex(a.alarm_code) }}</td>
          <td class="px-4 py-2">{{ a.major_id }}</td>
          <td class="px-4 py-2">{{ a.sub_section }}</td>
          <td class="px-4 py-2">{{ a.fault_type }}</td>
          <td class="px-4 py-2">{{ a.severity }}</td>
          <td class="px-4 py-2 text-muted-foreground">{{ new Date(a.triggered_at).toLocaleString() }}</td>
        </tr>
      </tbody>
    </Table>
    <p class="mt-3 text-xs text-muted-foreground">
      Showing the {{ alarms.length }} most recent of {{ count }} active alarms. Acknowledge /
      resolve per device on its Alarms page. Rule-based alarm rules are managed
      <RouterLink to="/alarm-rules" class="underline hover:text-foreground">here</RouterLink>.
    </p>
  </div>
</template>