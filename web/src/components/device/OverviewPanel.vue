<script setup lang="ts">
import type { Device } from '@/lib/types'
import Card from '@/components/ui/Card.vue'

const props = defineProps<{ device: Device }>()

const fields = [
  { label: 'Device name', get: () => props.device.name },
  { label: 'Device ID', get: () => props.device.id },
  { label: 'IP address', get: () => props.device.ip_address ?? null },
  { label: 'Hostname', get: () => props.device.hostname ?? null },
  { label: 'Serial', get: () => props.device.serial },
  { label: 'Board revision', get: () => props.device.board_rev },
  { label: 'OS version', get: () => props.device.os_version },
  { label: 'Software version', get: () => props.device.sw_version },
  {
    label: 'Last seen',
    get: () =>
      props.device.last_seen_at ? new Date(props.device.last_seen_at).toLocaleString() : null,
  },
  { label: 'Paired at', get: () => new Date(props.device.created_at).toLocaleString() },
]
</script>

<template>
  <div>
    <!-- Vertical spec list: label left, value right, hairline between rows. -->
    <Card class="overflow-hidden p-0">
      <ul class="divide-y divide-border">
        <li
          v-for="f in fields"
          :key="f.label"
          class="flex items-baseline justify-between gap-6 px-4 py-2.5"
        >
          <span class="shrink-0 text-sm text-muted-foreground">{{ f.label }}</span>
          <span class="min-w-0 truncate text-right font-mono text-sm" :title="f.get() ?? undefined">
            {{ f.get() ?? '—' }}
          </span>
        </li>
      </ul>
      <p class="border-t border-border bg-surface-muted px-4 py-2 text-xs text-muted-foreground">
        IP, hostname, OS and software versions are reported by the device agent when it pairs and
        heartbeats — they are blank until the device comes online.
      </p>
    </Card>
  </div>
</template>