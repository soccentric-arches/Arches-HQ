<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { RefreshCw } from 'lucide-vue-next'
import { api, ApiError } from '@/lib/api'
import type { ActiveAlarm, Alarm } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'
import Tabs from '@/components/ui/Tabs.vue'
import TabsList from '@/components/ui/TabsList.vue'
import TabsTrigger from '@/components/ui/TabsTrigger.vue'
import TabsContent from '@/components/ui/TabsContent.vue'

const auth = useAuthStore()

// active (device-reported) alarms
const alarms = ref<ActiveAlarm[]>([])
const count = ref(0)
const loading = ref(true)
const error = ref('')

// rule-based alarm history
const history = ref<{ alarm: Alarm; device_name: string }[]>([])
const historyLoading = ref(true)
const ackError = ref('')

function alarmHex(code: number) {
  return `0x${code.toString(16).padStart(8, '0')}`
}

function alarmTone(state: string) {
  return state === 'active' ? 'danger' : state === 'acknowledged' ? 'warning' : 'success'
}

// Severity chips for the five X.733 levels (Task.md C-05). MAJOR and MINOR
// used to have no representation at all.
function severityTone(severity: string) {
  switch (severity) {
    case 'critical':
    case 'major':
      return 'danger'
    case 'minor':
    case 'warning':
      return 'warning'
    default:
      return 'neutral'
  }
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

async function loadHistory(silent = false) {
  if (!silent) historyLoading.value = true
  try {
    const res = await api.alarms.history()
    history.value = res.items
  } catch {
    /* history is best-effort */
  } finally {
    historyLoading.value = false
  }
}

async function ack(a: Alarm) {
  ackError.value = ''
  try {
    await api.alarms.acknowledge(a.id)
    await loadHistory(true)
  } catch (e) {
    ackError.value = e instanceof ApiError ? e.message : 'Acknowledge failed.'
  }
}

async function resolve(a: Alarm) {
  ackError.value = ''
  try {
    await api.alarms.resolve(a.id)
    await loadHistory(true)
  } catch (e) {
    ackError.value = e instanceof ApiError ? e.message : 'Resolve failed.'
  }
}

// Live: poll active alarms every 15s.
let timer: ReturnType<typeof setInterval> | null = null
onMounted(() => {
  load()
  loadHistory()
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
        <p class="text-sm text-muted-foreground">
          Device alarms and rule-based alarm history.
        </p>
      </div>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
        @click="load(); loadHistory(true)"
      >
        <RefreshCw class="h-3.5 w-3.5" /> Refresh
      </button>
    </div>

    <Tabs default-value="active">
      <TabsList>
        <TabsTrigger value="active">Active ({{ count }})</TabsTrigger>
        <TabsTrigger value="rules-history">Rule alarms</TabsTrigger>
      </TabsList>

      <TabsContent value="active">
        <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
        <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
        <Card v-else-if="alarms.length === 0" class="p-6 text-sm text-muted-foreground">
          No active alarms across the fleet.
        </Card>
        <template v-else>
          <Table>
            <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
              <tr>
                <th class="px-4 py-2 font-medium">Device</th>
                <th class="px-4 py-2 font-medium">Code</th>
                <th class="px-4 py-2 font-medium">Domain</th>
                <th class="px-4 py-2 font-medium">Module</th>
                <th class="px-4 py-2 font-medium">Type</th>
                <th class="px-4 py-2 font-medium">Index</th>
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
                <td class="px-4 py-2">{{ a.domain }}</td>
                <td class="px-4 py-2">{{ a.module }}</td>
                <td class="px-4 py-2">{{ a.alarm_type }}</td>
                <td class="px-4 py-2">{{ a.alarm_index }}</td>
                <td class="px-4 py-2">
                  <Badge :tone="severityTone(a.severity)" class="capitalize">{{ a.severity }}</Badge>
                </td>
                <td class="px-4 py-2 text-muted-foreground">{{ new Date(a.triggered_at).toLocaleString() }}</td>
              </tr>
            </tbody>
          </Table>
          <p class="mt-3 text-xs text-muted-foreground">
            Showing the {{ alarms.length }} most recent of {{ count }} active alarms — live, polled
            every 15 s. Acknowledge/resolve per device on its Alarms page.
          </p>
        </template>
      </TabsContent>

      <TabsContent value="rules-history">
        <p v-if="ackError" class="mb-3 text-sm text-danger">{{ ackError }}</p>
        <Card v-if="historyLoading && history.length === 0" class="p-6 text-sm text-muted-foreground">
          Loading…
        </Card>
        <Card v-else-if="history.length === 0" class="p-6 text-sm text-muted-foreground">
          No rule-based alarms recorded.
        </Card>
        <Table v-else>
          <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
            <tr>
              <th class="px-4 py-2 font-medium">Device</th>
              <th class="px-4 py-2 font-medium">State</th>
              <th class="px-4 py-2 font-medium">Triggered</th>
              <th class="px-4 py-2 font-medium">Acknowledged</th>
              <th class="px-4 py-2 font-medium">Resolved</th>
              <th class="px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="h in history" :key="h.alarm.id" class="border-b border-border last:border-0">
              <td class="px-4 py-2 font-medium">{{ h.device_name }}</td>
              <td class="px-4 py-2">
                <Badge :tone="alarmTone(h.alarm.state)" class="capitalize">{{ h.alarm.state }}</Badge>
              </td>
              <td class="px-4 py-2 text-muted-foreground">
                {{ new Date(h.alarm.triggered_at).toLocaleString() }}
              </td>
              <td class="px-4 py-2 text-muted-foreground">
                {{ h.alarm.acknowledged_at ? new Date(h.alarm.acknowledged_at).toLocaleString() : '—' }}
              </td>
              <td class="px-4 py-2 text-muted-foreground">
                {{ h.alarm.resolved_at ? new Date(h.alarm.resolved_at).toLocaleString() : '—' }}
              </td>
              <td class="px-4 py-2 text-right">
                <span v-if="auth.hasRole('operator')" class="flex justify-end gap-2">
                  <Button
                    v-if="h.alarm.state === 'active'"
                    size="sm"
                    variant="secondary"
                    @click="ack(h.alarm)"
                    >Ack</Button
                  >
                  <Button
                    v-if="h.alarm.state !== 'resolved'"
                    size="sm"
                    variant="secondary"
                    @click="resolve(h.alarm)"
                    >Resolve</Button
                  >
                </span>
              </td>
            </tr>
          </tbody>
        </Table>
        <p class="mt-3 text-xs text-muted-foreground">
          Rule-based alarms fire from the rules engine —
          <RouterLink to="/alarm-rules" class="underline hover:text-foreground">manage rules</RouterLink>.
        </p>
      </TabsContent>
    </Tabs>
  </div>
</template>