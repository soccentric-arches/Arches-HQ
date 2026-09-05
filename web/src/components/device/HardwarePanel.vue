<script setup lang="ts">
import { computed } from 'vue'
import { Cpu } from 'lucide-vue-next'
import type { Device } from '@/lib/types'
import Card from '@/components/ui/Card.vue'

const props = defineProps<{ device: Device }>()

// AgentReport.hardware: { soc, memory, storage[], radios[], peripherals[], sensors[] }
const hardware = computed<Record<string, unknown> | null>(
  () => (props.device.reported?.hardware as Record<string, unknown> | undefined) ?? null,
)

const entries = computed<[string, string][]>(() => {
  if (!hardware.value) return []
  return Object.entries(hardware.value)
    .filter(([, v]) => v !== null && v !== undefined)
    .map(([k, v]) => [k, typeof v === 'string' ? v : JSON.stringify(v)])
})

const reported = computed(() =>
  [
    ['Serial', props.device.serial],
    ['Board revision', props.device.board_rev],
  ] as [string, string | null][],
)
</script>

<template>
  <div class="space-y-4">
    <Card class="p-4">
      <h3 class="text-sm font-semibold">Reported hardware identity</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        Populated from the device's board manifest when it pairs.
      </p>
      <dl class="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        <div v-for="[label, value] in reported" :key="label">
          <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">{{ label }}</dt>
          <dd class="mt-0.5 truncate font-mono">{{ value ?? '—' }}</dd>
        </div>
      </dl>
    </Card>

    <Card v-if="entries.length" class="p-4">
      <h3 class="text-sm font-semibold">Hardware inventory</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        From the device's latest AgentReport — what is actually installed.
      </p>
      <dl class="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        <div v-for="[key, value] in entries" :key="key">
          <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {{ key.replaceAll('_', ' ') }}
          </dt>
          <dd class="mt-0.5 break-all font-mono text-xs">{{ value }}</dd>
        </div>
      </dl>
    </Card>

    <Card v-else class="p-4">
      <div class="flex items-start gap-3">
        <Cpu class="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        <div>
          <h3 class="text-sm font-semibold">Inventory not yet reported</h3>
          <p class="mt-1 text-sm text-muted-foreground">
            SoC, memory, storage, radios (WiFi / GNSS) and peripherals appear here once the device
            agent sends its hardware inventory in an AgentReport.
          </p>
        </div>
      </div>
    </Card>
  </div>
</template>