<script lang="ts">
import {
  Activity,
  BellRing,
  Boxes,
  Cloud,
  Cpu,
  Clock,
  DatabaseBackup,
  Gauge,
  LineChart,
  Network,
  PackageOpen,
  Power,
  ScrollText,
  Settings,
  ShieldCheck,
  TriangleAlert,
} from 'lucide-vue-next'
import type { SidebarNavItem } from '@/components/ui/SidebarNav.vue'

export interface DeviceSectionGroup {
  label: string
  items: SidebarNavItem[]
}

// The device menu: everything device-scoped lives in this sidebar, grouped
// by concern. Section values are the `?section=` deep links.
export const DEVICE_SECTION_GROUPS: DeviceSectionGroup[] = [
  {
    label: 'Overview',
    items: [
      { value: 'overview', label: 'Device info', icon: Gauge },
      { value: 'monitoring', label: 'Monitoring', icon: Activity },
    ],
  },
  {
    label: 'Data',
    items: [
      { value: 'telemetry', label: 'Telemetry', icon: LineChart },
      { value: 'alarms', label: 'Alarms', icon: BellRing },
      { value: 'faults', label: 'Faults', icon: TriangleAlert },
      { value: 'logs', label: 'Logs', icon: ScrollText },
    ],
  },
  {
    label: 'System',
    items: [
      { value: 'settings', label: 'Settings', icon: Settings },
      { value: 'power', label: 'Power & Control', icon: Power },
      { value: 'time-sync', label: 'Time & Sync', icon: Clock },
    ],
  },
  {
    label: 'Network',
    items: [
      { value: 'network', label: 'Network', icon: Network },
      { value: 'services', label: 'Services', icon: Boxes },
      { value: 'cloud', label: 'Cloud Connectivity', icon: Cloud },
    ],
  },
  {
    label: 'Maintenance',
    items: [
      { value: 'backup', label: 'Backup & Restore', icon: DatabaseBackup },
      { value: 'ota', label: 'OTA Updates', icon: PackageOpen },
      { value: 'security', label: 'Security', icon: ShieldCheck },
      { value: 'hardware', label: 'Hardware', icon: Cpu },
    ],
  },
]
</script>

<script setup lang="ts">
import type { Device } from '@/lib/types'
import SidebarNav from '@/components/ui/SidebarNav.vue'

defineProps<{ device: Device; active: string }>()

const emit = defineEmits<{ select: [string] }>()
</script>

<template>
  <aside
    class="h-fit rounded-lg border border-border bg-surface p-3 lg:sticky lg:top-[4.5rem] lg:max-h-[calc(100vh-5.5rem)] lg:overflow-y-auto"
  >
    <div class="px-2 pt-1">
      <p class="truncate text-sm font-semibold">{{ device.name }}</p>
      <p class="mt-1 flex items-center gap-1.5 text-xs text-muted-foreground">
        <span
          class="h-1.5 w-1.5 rounded-full"
          :class="device.online ? 'bg-success' : 'bg-border-strong'"
        />
        {{ device.online ? 'Online' : 'Offline' }}
      </p>
    </div>

    <template v-for="group in DEVICE_SECTION_GROUPS" :key="group.label">
      <div class="my-3 border-t border-border" />
      <SidebarNav
        :label="group.label"
        :items="group.items"
        :model-value="active"
        @update:model-value="emit('select', $event)"
      />
    </template>
  </aside>
</template>