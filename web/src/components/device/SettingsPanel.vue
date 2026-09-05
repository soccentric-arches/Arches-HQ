<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { KeyRound } from 'lucide-vue-next'
import { api, ApiError } from '@/lib/api'
import type { Device } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { useDeviceConfig } from '@/lib/useDeviceConfig'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'

const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ updated: [Device] }>()
const auth = useAuthStore()

// --- rename ---
const name = ref(props.device.name)
const savingName = ref(false)
const nameError = ref('')
const nameSaved = ref(false)

// --- desired system config (hostname is applied device-side) ---
const sys = useDeviceConfig(props.device.id, 'system')
const hostname = computed({
  get: () => (sys.config.value.hostname as string) ?? props.device.hostname ?? '',
  set: (v: string) => sys.set('hostname', v),
})

async function saveName() {
  const trimmed = name.value.trim()
  if (!trimmed || trimmed === props.device.name) return
  savingName.value = true
  nameError.value = ''
  nameSaved.value = false
  try {
    const updated = await api.devices.rename(props.device.id, trimmed)
    emit('updated', updated)
    nameSaved.value = true
  } catch (e) {
    nameError.value = e instanceof ApiError ? e.message : 'Could not rename device.'
  } finally {
    savingName.value = false
  }
}

// --- pairing credential ---
const rotating = ref(false)
const newToken = ref<string | null>(null)
const credError = ref('')

async function rotateCredential() {
  rotating.value = true
  credError.value = ''
  try {
    const res = await api.devices.rotateCredential(props.device.id)
    newToken.value = res.pairing_token
  } catch (e) {
    credError.value = e instanceof ApiError ? e.message : 'Could not rotate credential.'
  } finally {
    rotating.value = false
  }
}

async function revokeCredential() {
  if (!confirm('Revoke this device credential? The device must re-pair to connect again.')) return
  rotating.value = true
  credError.value = ''
  try {
    await api.devices.revokeCredential(props.device.id)
    newToken.value = null
  } catch (e) {
    credError.value = e instanceof ApiError ? e.message : 'Could not revoke credential.'
  } finally {
    rotating.value = false
  }
}

// --- export / import (per-device SQLite) ---
const exporting = ref(false)
const importing = ref(false)
const exportInfo = ref<{ path: string; size_bytes: number } | null>(null)
const storeError = ref('')
const importedMsg = ref('')

async function exportDevice() {
  exporting.value = true
  storeError.value = ''
  importedMsg.value = ''
  try {
    const res = await api.devices.exportData(props.device.id)
    exportInfo.value = { path: res.path, size_bytes: res.size_bytes }
  } catch (e) {
    storeError.value = e instanceof ApiError ? e.message : 'Export failed.'
  } finally {
    exporting.value = false
  }
}

async function importDevice() {
  if (
    !confirm('Restore rows from the stored SQLite file? Only rows missing in the database are added.')
  )
    return
  importing.value = true
  storeError.value = ''
  importedMsg.value = ''
  try {
    const res = await api.devices.importData(props.device.id)
    const parts = Object.entries(res.imported)
      .filter(([, n]) => n > 0)
      .map(([k, n]) => `${n} ${k}`)
    importedMsg.value = parts.length
      ? `Restored: ${parts.join(', ')}.`
      : 'Nothing to restore — already up to date.'
  } catch (e) {
    storeError.value = e instanceof ApiError ? e.message : 'Import failed.'
  } finally {
    importing.value = false
  }
}

function downloadExport() {
  window.open(api.devices.downloadExportUrl(props.device.id), '_blank')
}

const identity = [
  { label: 'Device ID', get: () => props.device.id },
  { label: 'Serial', get: () => props.device.serial ?? '—' },
  { label: 'Board revision', get: () => props.device.board_rev ?? '—' },
]

watch(
  () => props.device.name,
  (v) => (name.value = v),
)
</script>

<template>
  <div class="space-y-4">
    <Card class="p-4">
      <h3 class="text-sm font-semibold">Device name</h3>
      <p class="mt-1 text-sm text-muted-foreground">Shown across HQ; must be unique per tenant.</p>
      <div class="mt-3 flex max-w-md items-center gap-2">
        <Input v-model="name" placeholder="Device name" @keyup.enter="saveName" />
        <Button
          size="sm"
          :disabled="savingName || !name.trim() || name.trim() === device.name"
          @click="saveName"
        >
          {{ savingName ? 'Saving…' : 'Save' }}
        </Button>
      </div>
      <p v-if="nameError" class="mt-2 text-sm text-danger">{{ nameError }}</p>
      <p v-else-if="nameSaved" class="mt-2 text-sm text-success">Name updated.</p>
    </Card>

    <Card class="p-4">
      <h3 class="text-sm font-semibold">Identity</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        Device ID and serial are immutable. Hostname is desired state — saved here and applied
        device-side by the agent.
      </p>
      <dl class="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
        <div v-for="f in identity" :key="f.label">
          <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {{ f.label }}
          </dt>
          <dd class="mt-0.5 truncate font-mono">{{ f.get() }}</dd>
        </div>
        <div>
          <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Pairing</dt>
          <dd class="mt-0.5">
            <Badge :tone="device.pairing_state === 'authorized' ? 'success' : 'neutral'" class="capitalize">
              {{ device.pairing_state }}
            </Badge>
          </dd>
        </div>
      </dl>
      <div class="mt-4 max-w-md">
        <label class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Hostname (desired)
        </label>
        <div class="mt-1 flex gap-2">
          <Input v-model="hostname" placeholder="sensor-1.local" @keyup.enter="sys.save()" />
          <Button
            size="sm"
            variant="secondary"
            :disabled="sys.saving.value || !sys.dirty.value"
            @click="sys.save()"
          >
            {{ sys.saving.value ? 'Saving…' : 'Apply' }}
          </Button>
        </div>
        <span v-if="sys.error.value" class="mt-1 text-sm text-danger">{{ sys.error.value }}</span>
      </div>
    </Card>

    <Card v-if="auth.hasRole('admin')" class="p-4">
      <h3 class="text-sm font-semibold">Export &amp; import (per-device SQLite)</h3>
      <p class="mt-1 max-w-2xl text-sm text-muted-foreground">
        The device's data lives in its own folder under the storage root
        (<code class="font-mono text-xs">storage/devices/&lt;id&gt;/device.sqlite</code>).
        Export mirrors the database into that file — easy to back up or copy off the server;
        import restores rows that are missing.
      </p>
      <div class="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" :disabled="exporting" @click="exportDevice">
          {{ exporting ? 'Exporting…' : 'Export now' }}
        </Button>
        <Button
          v-if="exportInfo"
          size="sm"
          variant="secondary"
          @click="downloadExport"
        >
          Download .sqlite
        </Button>
        <Button size="sm" variant="secondary" :disabled="importing" @click="importDevice">
          {{ importing ? 'Importing…' : 'Restore from export' }}
        </Button>
      </div>
      <p v-if="exportInfo" class="mt-2 text-xs text-muted-foreground">
        Written to <code class="font-mono">{{ exportInfo.path }}</code>
        ({{ (exportInfo.size_bytes / 1024).toFixed(1) }} KB)
      </p>
      <p v-if="importedMsg" class="mt-2 text-sm text-success">{{ importedMsg }}</p>
      <p v-if="storeError" class="mt-2 text-sm text-danger">{{ storeError }}</p>
    </Card>

    <Card v-if="auth.hasRole('admin')" class="p-4">
      <div class="flex items-start justify-between gap-4">
        <div>
          <h3 class="flex items-center gap-2 text-sm font-semibold">
            <KeyRound class="h-4 w-4 text-muted-foreground" /> Pairing credential
          </h3>
          <p class="mt-1 max-w-lg text-sm text-muted-foreground">
            Rotate to issue a fresh single-use pairing token, or revoke to cut the device off
            immediately. Both actions are written to the audit log.
          </p>
        </div>
        <div class="flex shrink-0 gap-2">
          <Button size="sm" variant="secondary" :disabled="rotating" @click="rotateCredential">
            Rotate
          </Button>
          <Button
            size="sm"
            variant="destructive"
            :disabled="rotating"
            @click="revokeCredential"
          >
            Revoke
          </Button>
        </div>
      </div>
      <p v-if="credError" class="mt-2 text-sm text-danger">{{ credError }}</p>
      <div v-if="newToken" class="mt-3">
        <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          New pairing token — shown once
        </p>
        <code class="mt-1 block break-all rounded-md bg-surface-muted p-3 text-sm">
          {{ newToken }}
        </code>
      </div>
    </Card>
  </div>
</template>