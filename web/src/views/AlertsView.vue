<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
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

// ---- Correlated alarm timeline (Task.md F-08) --------------------------------
// X.733 escalation chains: alarms whose `correlated` arrays reference each
// other render as ONE group instead of N flat rows. An alarm joins a group
// when its own code appears in another alarm's correlated list, or it lists
// another displayed alarm's code. Group label is the highest-severity member
// plus the escalation rule of its catalog entry, when the code is catalogued.
interface CorrelationGroup {
  codes: number[]
  members: ActiveAlarm[]
}

const SEVERITY_RANK: Record<string, number> = { info: 0, warning: 1, minor: 2, major: 3, critical: 4 }

const correlationGroups = computed(() => {
  const byCode = new Map<number, ActiveAlarm>()
  for (const a of alarms.value) byCode.set(a.alarm_code, a)

  const union = new Map<ActiveAlarm, Set<ActiveAlarm>>()
  const find = (x: ActiveAlarm): Set<ActiveAlarm> => {
    let s = union.get(x)
    if (!s) {
      s = new Set([x])
      union.set(x, s)
    }
    return s
  }
  const join = (a: ActiveAlarm, b: ActiveAlarm) => {
    const sa = find(a)
    const sb = find(b)
    for (const m of sb) sa.add(m)
    for (const m of sa) union.set(m, sa)
  }
  for (const a of alarms.value) {
    for (const c of a.correlated ?? []) {
      const peer = byCode.get(c)
      if (peer && peer !== a) join(a, peer)
    }
  }

  const seen = new Set<ActiveAlarm>()
  const groups: CorrelationGroup[] = []
  for (const a of alarms.value) {
    if (seen.has(a)) continue
    const members = [...find(a)]
    if (members.length < 2) continue
    for (const m of members) seen.add(m)
    groups.push({
      codes: members.map((m) => m.alarm_code),
      members: members.sort(
        (x, y) => (SEVERITY_RANK[y.severity] ?? 0) - (SEVERITY_RANK[x.severity] ?? 0)
      ),
    })
  }
  return groups
})

const soloAlarms = computed(() => alarms.value.filter((a) => !correlationGroups.value.some((g) => g.members.includes(a))))

function groupHeadline(g: CorrelationGroup) {
  const head = g.members[0]
  const label = head.name || alarmHex(head.alarm_code)
  return g.members.length === 2
    ? `${label} + 1 correlated alarm`
    : `${label} + ${g.members.length - 1} correlated alarms`
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
          <!-- Correlated chains first (Task.md F-08): an escalation chain is
               one story, not N rows. -->
          <div v-for="g in correlationGroups" :key="g.codes.join('-')" class="mb-4">
            <Card class="p-4">
              <div class="mb-2 flex items-center gap-2">
                <Badge tone="danger">escalation chain</Badge>
                <span class="text-sm font-medium">{{ groupHeadline(g) }}</span>
              </div>
              <ul class="divide-y divide-border">
                <li
                  v-for="m in g.members"
                  :key="m.id"
                  class="flex items-center justify-between gap-4 py-1.5 text-sm"
                >
                  <span class="flex min-w-0 items-center gap-2">
                    <Badge :tone="severityTone(m.severity)" class="capitalize">{{ m.severity }}</Badge>
                    <span class="truncate font-mono text-xs">{{ m.name || alarmHex(m.alarm_code) }}</span>
                    <span class="truncate text-xs text-muted-foreground">on {{ m.device_name }}</span>
                  </span>
                  <span class="text-xs text-muted-foreground">{{ new Date(m.triggered_at).toLocaleString() }}</span>
                </li>
              </ul>
            </Card>
          </div>

          <Table>
            <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
              <tr>
                <th class="px-4 py-2 font-medium">Device</th>
                <th class="px-4 py-2 font-medium">Alarm</th>
                <th class="px-4 py-2 font-medium">Code</th>
                <th class="px-4 py-2 font-medium">Severity</th>
                <th class="px-4 py-2 font-medium">Triggered</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="a in soloAlarms" :key="a.id" class="border-b border-border last:border-0">
                <td class="px-4 py-2">
                  <RouterLink
                    :to="{ name: 'device-detail', params: { id: a.device_id }, query: { section: 'alarms' } }"
                    class="font-medium hover:text-accent"
                  >
                    {{ a.device_name }}
                  </RouterLink>
                </td>
                <td class="px-4 py-2 text-xs">{{ a.name || '—' }}</td>
                <td class="px-4 py-2 font-mono text-xs">{{ alarmHex(a.alarm_code) }}</td>
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