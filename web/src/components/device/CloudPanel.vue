<script setup lang="ts">
import { computed } from 'vue'
import { Cloud, CloudOff } from 'lucide-vue-next'
import type { Device } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'

const props = defineProps<{ device: Device }>()

const status = computed<{ label: string; tone: 'success' | 'danger'; detail: string }>(() => ({
  label: props.device.online ? 'Connected' : 'Disconnected',
  tone: props.device.online ? 'success' : 'danger',
  detail: props.device.online
    ? 'The device holds an open outbound link to HQ; presence = liveness.'
    : props.device.last_seen_at
      ? `Last seen ${new Date(props.device.last_seen_at).toLocaleString()}`
      : 'The device has never connected.',
}))

const identity = computed(() => [
  ['Agent version', props.device.agent_version],
  ['OS version', props.device.os_version],
  ['Software version', props.device.sw_version],
  ['IP address', props.device.ip_address],
  ['Hostname', props.device.hostname],
] as [string, string | null][])
</script>

<template>
  <div class="space-y-4">
    <Card class="flex items-center gap-4 p-4">
      <span
        class="flex h-10 w-10 shrink-0 items-center justify-center rounded-md"
        :class="device.online ? 'bg-success-muted text-success' : 'bg-danger-muted text-danger'"
      >
        <component :is="device.online ? Cloud : CloudOff" class="h-5 w-5" />
      </span>
      <div class="min-w-0">
        <p class="flex items-center gap-2 text-sm font-semibold">
          {{ status.label }}
          <Badge :tone="status.tone" class="capitalize">{{ device.pairing_state }}</Badge>
        </p>
        <p class="mt-0.5 truncate text-sm text-muted-foreground">{{ status.detail }}</p>
      </div>
    </Card>

    <Card class="p-4">
      <h3 class="text-sm font-semibold">Link details</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        Reported by the device agent on heartbeat and in its AgentReport.
      </p>
      <dl class="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        <div v-for="[label, value] in identity" :key="label">
          <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">{{ label }}</dt>
          <dd class="mt-0.5 truncate font-mono">{{ value ?? '—' }}</dd>
        </div>
      </dl>
    </Card>
  </div>
</template>