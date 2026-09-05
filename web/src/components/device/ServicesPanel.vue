<script setup lang="ts">
import { computed } from 'vue'
import { Boxes } from 'lucide-vue-next'
import type { Device } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'

const props = defineProps<{ device: Device }>()

interface ServiceRow {
  name: string
  state: string
  enabled?: boolean
  description?: string
}

// The device's AgentReport carries { services: [...] }; rendered
// defensively — the shape is co-owned with Arches-Configuration.
const services = computed<ServiceRow[]>(
  () => (props.device.reported?.services as ServiceRow[] | undefined) ?? [],
)

function stateTone(state: string) {
  return state === 'running' ? 'success' : state === 'failed' ? 'danger' : 'neutral'
}
</script>

<template>
  <div>
    <Card v-if="services.length === 0" class="p-6">
      <div class="flex items-start gap-3">
        <Boxes class="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
        <div>
          <h3 class="text-sm font-semibold">No services reported yet</h3>
          <p class="mt-1 text-sm text-muted-foreground">
            Once the device agent sends an AgentReport, the running services (state, enablement,
            footprint) appear here. HQ renders the report verbatim.
          </p>
        </div>
      </div>
    </Card>
    <Table v-else>
      <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
        <tr>
          <th class="px-4 py-2 font-medium">Service</th>
          <th class="px-4 py-2 font-medium">State</th>
          <th class="px-4 py-2 font-medium">Enabled</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="s in services" :key="s.name" class="border-b border-border last:border-0">
          <td class="px-4 py-2 font-medium">{{ s.name }}</td>
          <td class="px-4 py-2">
            <Badge :tone="stateTone(s.state)" class="capitalize">{{ s.state }}</Badge>
          </td>
          <td class="px-4 py-2 text-muted-foreground">
            {{ s.enabled === undefined ? '—' : s.enabled ? 'yes' : 'no' }}
          </td>
        </tr>
      </tbody>
    </Table>
  </div>
</template>