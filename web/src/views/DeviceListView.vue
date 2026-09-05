<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { Download, Upload } from 'lucide-vue-next'
import { api, ApiError } from '@/lib/api'
import { connectDeviceStatusSocket } from '@/lib/deviceStatusSocket'
import type { Device } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Dialog from '@/components/ui/Dialog.vue'
import Input from '@/components/ui/Input.vue'
import Table from '@/components/ui/Table.vue'

const auth = useAuthStore()
const devices = ref<Device[]>([])
const q = ref('')
const loading = ref(true)
const error = ref('')

const addOpen = ref(false)
const newName = ref('')
const creating = ref(false)
const createError = ref('')
const pairingToken = ref<string | null>(null)

// ── column sorting (client-side) ─────────────────────────────────────────
const sortKey = ref<'name' | 'online' | 'pairing_state' | 'last_seen_at'>('name')
const sortAsc = ref(true)

function setSort(key: (typeof sortKey)['value']) {
  if (sortKey.value === key) sortAsc.value = !sortAsc.value
  else {
    sortKey.value = key
    sortAsc.value = true
  }
}

const filteredDevices = computed(() => {
  const query = q.value.trim().toLowerCase()
  const rows = query ? devices.value.filter((d) => d.name.toLowerCase().includes(query)) : devices.value
  const dir = sortAsc.value ? 1 : -1
  return [...rows].sort((a, b) => {
    switch (sortKey.value) {
      case 'online':
        return (Number(b.online) - Number(a.online)) * dir
      case 'pairing_state':
        return a.pairing_state.localeCompare(b.pairing_state) * dir
      case 'last_seen_at':
        return (
          (new Date(a.last_seen_at ?? 0).getTime() - new Date(b.last_seen_at ?? 0).getTime()) * dir
        )
      default:
        return a.name.localeCompare(b.name) * dir
    }
  })
})

// ── CSV export (client-side, current fleet) ──────────────────────────────
function exportCsv() {
  const header = [
    'name',
    'serial',
    'ip_address',
    'hostname',
    'os_version',
    'sw_version',
    'pairing_state',
    'online',
    'last_seen_at',
    'device_id',
  ]
  const escape = (v: unknown) => {
    const s = v === null || v === undefined ? '' : String(v)
    return /[",\n]/.test(s) ? `"${s.replaceAll('"', '""')}"` : s
  }
  const lines = devices.value.map((d) =>
    [d.name, d.serial, d.ip_address, d.hostname, d.os_version, d.sw_version, d.pairing_state, d.online, d.last_seen_at, d.id]
      .map(escape)
      .join(','),
  )
  const blob = new Blob([[header.join(','), ...lines].join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `arches-hq-devices-${new Date().toISOString().slice(0, 10)}.csv`
  a.click()
  URL.revokeObjectURL(url)
}

// ── bulk enrollment (manufacturing / staging flow) ───────────────────────
const bulkOpen = ref(false)
const bulkNames = ref('')
const bulkBusy = ref(false)
const bulkError = ref('')
const bulkTokens = ref<{ name: string; token: string }[]>([])

async function bulkEnroll() {
  const names = bulkNames.value
    .split('\n')
    .map((n) => n.trim())
    .filter(Boolean)
  if (names.length === 0) return
  bulkBusy.value = true
  bulkError.value = ''
  try {
    const res = await api.devices.bulkProvision(names)
    bulkTokens.value = res.items
      .filter((i) => i.pairing_token)
      .map((i) => ({ name: i.device.name, token: i.pairing_token as string }))
    bulkNames.value = ''
    await load()
  } catch (e) {
    bulkError.value = e instanceof ApiError ? e.message : 'Bulk enrollment failed.'
  } finally {
    bulkBusy.value = false
  }
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.devices.list({ q: q.value || undefined })
    devices.value = res.items
  } catch {
    error.value = 'Could not load devices.'
  } finally {
    loading.value = false
  }
}

async function handleCreate() {
  if (!newName.value.trim()) return
  creating.value = true
  createError.value = ''
  try {
    const res = await api.devices.create(newName.value.trim())
    pairingToken.value = res.pairing_token
    newName.value = ''
    await load()
    if (!res.pairing_token) addOpen.value = false
  } catch (e) {
    createError.value = e instanceof ApiError ? e.message : 'Could not create device.'
  } finally {
    creating.value = false
  }
}

function closeAddDialog() {
  addOpen.value = false
  pairingToken.value = null
  createError.value = ''
}

let closeSocket: (() => void) | null = null

onMounted(() => {
  load()
  closeSocket = connectDeviceStatusSocket((event) => {
    const device = devices.value.find((d) => d.id === event.device_id)
    if (device) {
      device.online = event.online
      device.last_seen_at = event.last_seen_at
    }
  })
})

onUnmounted(() => closeSocket?.())
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <h1 class="text-xl font-semibold">Devices</h1>
      <div class="flex gap-2">
        <Button variant="secondary" @click="exportCsv" title="Export the current fleet as CSV">
          <Download class="h-3.5 w-3.5" /> CSV
        </Button>
        <Button
          v-if="auth.hasRole('operator')"
          variant="secondary"
          @click="bulkOpen = true; bulkTokens = []"
        >
          <Upload class="h-3.5 w-3.5" /> Bulk enroll
        </Button>
        <Button v-if="auth.hasRole('operator')" @click="addOpen = true">Add device</Button>
      </div>
    </div>

    <Input v-model="q" placeholder="Search by name…" class="mb-4 max-w-xs" @keyup.enter="load" />

    <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
    <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <Card v-else-if="filteredDevices.length === 0" class="p-6 text-sm text-muted-foreground">
      No devices yet.
    </Card>
    <Table v-else>
      <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
        <tr>
          <th class="cursor-pointer px-4 py-2 font-medium" @click="setSort('name')">
            Name {{ sortKey === 'name' ? (sortAsc ? '↑' : '↓') : '' }}
          </th>
          <th class="cursor-pointer px-4 py-2 font-medium" @click="setSort('online')">
            Status {{ sortKey === 'online' ? (sortAsc ? '↑' : '↓') : '' }}
          </th>
          <th class="cursor-pointer px-4 py-2 font-medium" @click="setSort('pairing_state')">
            Pairing {{ sortKey === 'pairing_state' ? (sortAsc ? '↑' : '↓') : '' }}
          </th>
          <th class="cursor-pointer px-4 py-2 font-medium" @click="setSort('last_seen_at')">
            Last seen {{ sortKey === 'last_seen_at' ? (sortAsc ? '↑' : '↓') : '' }}
          </th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="d in filteredDevices"
          :key="d.id"
          class="cursor-pointer border-b border-border last:border-0 hover:bg-surface-muted"
        >
          <td class="px-4 py-2">
            <RouterLink :to="{ name: 'device-detail', params: { id: d.id } }" class="font-medium">
              {{ d.name }}
            </RouterLink>
          </td>
          <td class="px-4 py-2">
            <Badge :tone="d.online ? 'success' : 'neutral'">{{ d.online ? 'Online' : 'Offline' }}</Badge>
          </td>
          <td class="px-4 py-2">
            <Badge :tone="d.pairing_state === 'authorized' ? 'accent' : 'neutral'">{{
              d.pairing_state
            }}</Badge>
          </td>
          <td class="px-4 py-2 text-muted-foreground">
            {{ d.last_seen_at ? new Date(d.last_seen_at).toLocaleString() : '—' }}
          </td>
        </tr>
      </tbody>
    </Table>

    <!-- add device -->
    <Dialog v-model:open="addOpen">
      <template #default="{ close }">
        <div v-if="pairingToken">
          <h2 class="text-base font-semibold">Pairing token</h2>
          <p class="mt-1 text-sm text-muted-foreground">
            Enter this into the device's WebConfig HQ section. It will not be shown again.
          </p>
          <code class="mt-3 block break-all rounded-md bg-surface-muted p-3 text-sm">{{ pairingToken }}</code>
          <Button class="mt-4 w-full" @click="closeAddDialog(); close()">Done</Button>
        </div>
        <div v-else>
          <h2 class="text-base font-semibold">Add device</h2>
          <Input v-model="newName" placeholder="Device name" class="mt-4" @keyup.enter="handleCreate" />
          <p v-if="createError" class="mt-2 text-sm text-danger">{{ createError }}</p>
          <div class="mt-4 flex justify-end gap-2">
            <Button variant="secondary" @click="close">Cancel</Button>
            <Button :disabled="creating" @click="handleCreate">{{ creating ? 'Creating…' : 'Create' }}</Button>
          </div>
        </div>
      </template>
    </Dialog>

    <!-- bulk enrollment -->
    <Dialog v-model:open="bulkOpen">
      <template #default="{ close }">
        <div v-if="bulkTokens.length">
          <h2 class="text-base font-semibold">Enrollment tokens</h2>
          <p class="mt-1 text-sm text-muted-foreground">
            Enter each token into the device's WebConfig HQ section. They will not be shown again —
            copy them now.
          </p>
          <div class="mt-3 max-h-64 overflow-y-auto rounded-md border border-border">
            <div
              v-for="t in bulkTokens"
              :key="t.name"
              class="flex items-center justify-between gap-3 border-b border-border px-3 py-2 last:border-0"
            >
              <span class="shrink-0 text-sm font-medium">{{ t.name }}</span>
              <code class="truncate font-mono text-xs text-muted-foreground">{{ t.token }}</code>
            </div>
          </div>
          <Button
            class="mt-4 w-full"
            @click="
              bulkOpen = false;
              bulkTokens = [];
              bulkError = '';
            "
            >Done</Button
          >
        </div>
        <div v-else>
          <h2 class="text-base font-semibold">Bulk enroll devices</h2>
          <p class="mt-1 text-sm text-muted-foreground">
            One device name per line (e.g. from your manufacturing list). Each becomes a pending
            device with its own single-use pairing token.
          </p>
          <textarea
            v-model="bulkNames"
            rows="6"
            placeholder="acadia-0001&#10;acadia-0002&#10;zion-0001"
            class="mt-3 w-full rounded-md border border-border bg-surface p-3 font-mono text-xs"
          />
          <p v-if="bulkError" class="mt-2 text-sm text-danger">{{ bulkError }}</p>
          <div class="mt-4 flex justify-end gap-2">
            <Button variant="secondary" @click="close">Cancel</Button>
            <Button :disabled="bulkBusy || !bulkNames.trim()" @click="bulkEnroll">
              {{ bulkBusy ? 'Enrolling…' : 'Enroll' }}
            </Button>
          </div>
        </div>
      </template>
    </Dialog>
  </div>
</template>