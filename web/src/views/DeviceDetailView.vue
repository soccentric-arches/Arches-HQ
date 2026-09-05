<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ChevronRight } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { Device } from '@/lib/types'
import DeviceSidebar, { DEVICE_SECTION_GROUPS } from '@/components/device/DeviceSidebar.vue'
import OverviewPanel from '@/components/device/OverviewPanel.vue'
import MonitoringPanel from '@/components/device/MonitoringPanel.vue'
import TelemetryPanel from '@/components/device/TelemetryPanel.vue'
import AlarmsPanel from '@/components/device/AlarmsPanel.vue'
import FaultsPanel from '@/components/device/FaultsPanel.vue'
import LogsPanel from '@/components/device/LogsPanel.vue'
import SettingsPanel from '@/components/device/SettingsPanel.vue'
import PowerPanel from '@/components/device/PowerPanel.vue'
import TimeSyncPanel from '@/components/device/TimeSyncPanel.vue'
import NetworkPanel from '@/components/device/NetworkPanel.vue'
import ServicesPanel from '@/components/device/ServicesPanel.vue'
import CloudPanel from '@/components/device/CloudPanel.vue'
import BackupsPanel from '@/components/device/BackupsPanel.vue'
import OTAPanel from '@/components/device/OTAPanel.vue'
import SecurityPanel from '@/components/device/SecurityPanel.vue'
import HardwarePanel from '@/components/device/HardwarePanel.vue'

const props = defineProps<{ id: string }>()

const device = ref<Device | null>(null)
const loading = ref(true)
const error = ref('')

const route = useRoute()
const router = useRouter()

const allSections = DEVICE_SECTION_GROUPS.flatMap((g) => g.items)

// The active device section is reflected in the URL (?section=…) so each
// pane stays deep-linkable.
const active = computed(() => {
  const value = route.query.section
  return typeof value === 'string' && allSections.some((s) => s.value === value)
    ? value
    : 'overview'
})

function selectSection(value: string) {
  router.replace({ query: { ...route.query, section: value } })
}

onMounted(async () => {
  try {
    device.value = await api.devices.get(props.id)
  } catch {
    error.value = 'Device not found.'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="grid gap-6 lg:grid-cols-[15rem_minmax(0,1fr)]">
    <!-- Device sidebar: everything device-scoped lives here. -->
    <DeviceSidebar v-if="device" :device="device" :active="active" @select="selectSection" />

    <section class="min-w-0">
      <nav class="mb-4 flex items-center gap-1 text-sm text-muted-foreground" aria-label="Breadcrumb">
        <RouterLink to="/" class="hover:text-foreground">Devices</RouterLink>
        <ChevronRight class="h-3.5 w-3.5" />
        <span v-if="device" class="truncate font-medium text-foreground">{{ device.name }}</span>
      </nav>

      <div v-if="loading" class="text-sm text-muted-foreground">Loading…</div>
      <div v-else-if="error" class="text-sm text-danger">{{ error }}</div>
      <template v-else-if="device">
        <OverviewPanel v-if="active === 'overview'" :device="device" />
        <MonitoringPanel v-else-if="active === 'monitoring'" :device-id="device.id" />
        <TelemetryPanel v-else-if="active === 'telemetry'" :device-id="device.id" />
        <AlarmsPanel v-else-if="active === 'alarms'" :device-id="device.id" />
        <FaultsPanel v-else-if="active === 'faults'" :device-id="device.id" />
        <LogsPanel v-else-if="active === 'logs'" :device-id="device.id" />
        <SettingsPanel v-else-if="active === 'settings'" :device="device" @updated="device = $event" />
        <PowerPanel v-else-if="active === 'power'" :device="device" @updated="device = $event" />
        <TimeSyncPanel v-else-if="active === 'time-sync'" :device-id="device.id" />
        <NetworkPanel v-else-if="active === 'network'" :device-id="device.id" />
        <ServicesPanel v-else-if="active === 'services'" :device="device" />
        <CloudPanel v-else-if="active === 'cloud'" :device="device" />
        <BackupsPanel v-else-if="active === 'backup'" :device="device" />
        <OTAPanel v-else-if="active === 'ota'" :device="device" />
        <SecurityPanel v-else-if="active === 'security'" :device-id="device.id" />
        <HardwarePanel v-else-if="active === 'hardware'" :device="device" />
      </template>
    </section>
  </div>
</template>