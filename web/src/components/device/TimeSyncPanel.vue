<script setup lang="ts">
import { computed } from 'vue'
import { Clock, Globe, RadioTower, Satellite } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import { useDeviceConfig } from '@/lib/useDeviceConfig'

const props = defineProps<{ deviceId: string }>()

const TIME_SOURCES = [
  { value: 'ntp', label: 'NTP', hint: 'Network time protocol servers' },
  { value: 'ptp', label: 'PTP', hint: 'Precision time protocol (hardware timestamping)' },
  { value: 'gnss', label: 'GNSS', hint: 'Satellite time (GPS / GLONASS / …)' },
  { value: 'manual', label: 'Manual', hint: 'Operator sets the clock by hand' },
]

const CONSTELLATIONS = ['gps', 'glonass', 'galileo', 'beidou']

const cfg = useDeviceConfig(props.deviceId, 'time')

const mode = computed(() => (cfg.config.value.mode as string) ?? 'ntp')
const ntpServers = computed({
  get: () => ((cfg.config.value.ntp_servers as string[]) ?? []).join(', '),
  set: (v: string) => cfg.set('ntp_servers', v.split(',').map((s) => s.trim()).filter(Boolean)),
})
const timezone = computed({
  get: () => (cfg.config.value.timezone as string) ?? 'UTC',
  set: (v: string) => cfg.set('timezone', v),
})
const constellations = computed(() => (cfg.config.value.gnss as string[]) ?? [])

function pickMode(m: string) {
  cfg.set('mode', m)
}

function toggleConstellation(c: string) {
  const next = constellations.value.includes(c)
    ? constellations.value.filter((x) => x !== c)
    : [...constellations.value, c]
  cfg.set('gnss', next)
}
</script>

<template>
  <div class="space-y-4">
    <Card class="p-4">
      <h3 class="flex items-center gap-2 text-sm font-semibold">
        <Clock class="h-4 w-4 text-muted-foreground" /> Time source
      </h3>
      <p class="mt-1 text-sm text-muted-foreground">
        Where the device gets its clock. Saved as desired state; the device applies it and reports
        back sync status.
      </p>
      <div class="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
        <button
          v-for="t in TIME_SOURCES"
          :key="t.value"
          type="button"
          class="rounded-md border p-3 text-left transition-colors"
          :class="
            mode === t.value
              ? 'border-accent bg-accent-muted'
              : 'border-border hover:bg-surface-muted'
          "
          @click="pickMode(t.value)"
        >
          <p class="text-sm font-medium">{{ t.label }}</p>
          <p class="mt-0.5 text-xs text-muted-foreground">{{ t.hint }}</p>
        </button>
      </div>
    </Card>

    <Card v-if="mode === 'ntp'" class="p-4">
      <h3 class="text-sm font-semibold">NTP servers</h3>
      <p class="mt-1 text-sm text-muted-foreground">Comma-separated host or IP list.</p>
      <Input v-model="ntpServers" placeholder="pool.ntp.org, time.google.com" class="mt-3 max-w-lg" />
    </Card>

    <Card v-if="mode === 'gnss'" class="p-4">
      <h3 class="flex items-center gap-2 text-sm font-semibold">
        <Satellite class="h-4 w-4 text-muted-foreground" /> Constellations
      </h3>
      <p class="mt-1 text-sm text-muted-foreground">Which satellite systems the receiver should use.</p>
      <div class="mt-3 flex flex-wrap gap-2">
        <button
          v-for="c in CONSTELLATIONS"
          :key="c"
          type="button"
          class="rounded-full border px-3 py-1 text-xs font-medium uppercase transition-colors"
          :class="
            constellations.includes(c)
              ? 'border-accent bg-accent-muted text-accent'
              : 'border-border text-muted-foreground hover:bg-surface-muted'
          "
          @click="toggleConstellation(c)"
        >
          {{ c }}
        </button>
      </div>
      <p class="mt-3 flex items-center gap-2 text-xs text-muted-foreground">
        <RadioTower class="h-3.5 w-3.5" /> PTP profile settings ship with the device agent's time
        daemon.
      </p>
    </Card>

    <Card class="p-4">
      <h3 class="flex items-center gap-2 text-sm font-semibold">
        <Globe class="h-4 w-4 text-muted-foreground" /> Timezone
      </h3>
      <Input v-model="timezone" placeholder="UTC" class="mt-3 max-w-xs" />
    </Card>

    <div class="flex items-center gap-3">
      <Button size="sm" :disabled="cfg.saving.value || !cfg.dirty.value" @click="cfg.save()">
        {{ cfg.saving.value ? 'Saving…' : 'Save & apply' }}
      </Button>
      <span v-if="cfg.error.value" class="text-sm text-danger">{{ cfg.error.value }}</span>
      <span v-else-if="!cfg.dirty.value && cfg.savedAt.value" class="text-xs text-muted-foreground">
        Desired state saved — the device applies it on its next sync.
      </span>
    </div>
  </div>
</template>