<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { api } from '@/lib/api'
import { useAuthStore } from '@/stores/auth'
import type { Alarm, Fault } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'

const props = defineProps<{ deviceId: string }>()
const auth = useAuthStore()

const faults = ref<Fault[]>([])
const alarms = ref<Alarm[]>([])
const loading = ref(true)

function severityTone(sev: string) {
  return sev === 'critical' ? 'danger' : sev === 'warn' ? 'warning' : 'neutral'
}
function alarmTone(state: string) {
  return state === 'active' ? 'danger' : state === 'acknowledged' ? 'warning' : 'success'
}

async function load() {
  loading.value = true
  const [f, a] = await Promise.all([
    api.faults.list(props.deviceId),
    api.alarms.listForDevice(props.deviceId),
  ])
  faults.value = f.items
  alarms.value = a.items
  loading.value = false
}

async function acknowledge(id: string) {
  await api.alarms.acknowledge(id)
  await load()
}
async function resolve(id: string) {
  await api.alarms.resolve(id)
  await load()
}

watch(() => props.deviceId, load)
onMounted(load)
</script>

<template>
  <div v-if="loading" class="text-sm text-muted-foreground">Loading…</div>
  <div v-else class="grid grid-cols-1 gap-6 lg:grid-cols-2">
    <div>
      <h3 class="mb-2 text-sm font-semibold">Alarms</h3>
      <Card v-if="alarms.length === 0" class="p-4 text-sm text-muted-foreground">No alarms.</Card>
      <div v-else class="space-y-2">
        <Card v-for="a in alarms" :key="a.id" class="flex items-center justify-between p-3">
          <div class="flex items-center gap-2">
            <Badge :tone="alarmTone(a.state)">{{ a.state }}</Badge>
            <span class="text-sm text-muted-foreground">{{ new Date(a.triggered_at).toLocaleString() }}</span>
          </div>
          <div v-if="auth.hasRole('operator')" class="flex gap-2">
            <Button v-if="a.state === 'active'" size="sm" variant="secondary" @click="acknowledge(a.id)"
              >Acknowledge</Button
            >
            <Button v-if="a.state !== 'resolved'" size="sm" variant="secondary" @click="resolve(a.id)"
              >Resolve</Button
            >
          </div>
        </Card>
      </div>
    </div>

    <div>
      <h3 class="mb-2 text-sm font-semibold">Faults (raw feed)</h3>
      <Card v-if="faults.length === 0" class="p-4 text-sm text-muted-foreground">No faults reported.</Card>
      <div v-else class="space-y-2">
        <Card v-for="f in faults" :key="f.id" class="p-3">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <Badge :tone="severityTone(f.severity)">{{ f.severity }}</Badge>
              <span class="text-sm font-medium">{{ f.code }}</span>
            </div>
            <span class="text-xs text-muted-foreground">{{ new Date(f.raised_at).toLocaleString() }}</span>
          </div>
          <p v-if="f.message" class="mt-1 text-sm text-muted-foreground">{{ f.message }}</p>
          <p class="mt-1 text-xs text-muted-foreground">
            {{ f.cleared_at ? `Cleared ${new Date(f.cleared_at).toLocaleString()}` : 'Still active' }}
          </p>
        </Card>
      </div>
    </div>
  </div>
</template>
