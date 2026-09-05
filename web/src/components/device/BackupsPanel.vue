<script setup lang="ts">
import { onMounted, onUnmounted, ref, watch } from 'vue'
import { api, ApiError } from '@/lib/api'
import type { Backup, Device } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'

const props = defineProps<{ device: Device }>()
const auth = useAuthStore()

const backups = ref<Backup[]>([])
const loading = ref(true)
const busy = ref(false)
const message = ref('')

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

async function load() {
  try {
    const res = await api.backups.list(props.device.id)
    backups.value = res.items
  } catch {
    message.value = 'Could not load backups.'
  } finally {
    loading.value = false
  }
}

async function takeBackup() {
  busy.value = true
  try {
    await api.backups.takeNow(props.device.id)
    message.value = 'Backup requested — delivered on the device\'s next heartbeat.'
    await load()
  } catch (e) {
    message.value = e instanceof ApiError ? e.message : 'Backup request failed.'
  } finally {
    busy.value = false
  }
}

async function restore(backupId: string) {
  busy.value = true
  try {
    await api.backups.restore(props.device.id, backupId)
    message.value = 'Restore requested — delivered on the device\'s next heartbeat.'
  } catch (e) {
    message.value = e instanceof ApiError ? e.message : 'Restore request failed.'
  } finally {
    busy.value = false
  }
}

// Poll lightly so rows appear once the device uploads the blob.
let timer: ReturnType<typeof setInterval> | null = null

watch(
  () => props.device.id,
  () => {
    loading.value = true
    load()
  },
)
onMounted(() => {
  load()
  timer = setInterval(load, 15000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
</script>

<template>
  <div>
    <div class="mb-3 flex items-center justify-between">
      <p class="text-xs text-muted-foreground">
        Device backups stored in HQ object storage. Restoring pushes the image back to the device.
      </p>
      <Button v-if="auth.hasRole('operator')" size="sm" :disabled="busy" @click="takeBackup">
        Take backup now
      </Button>
    </div>

    <p v-if="message" class="mb-3 text-sm text-muted-foreground">{{ message }}</p>

    <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
    <Card v-else-if="backups.length === 0" class="p-6 text-sm text-muted-foreground">
      No backups yet. Take one manually, or schedule it from the device agent.
    </Card>
    <Table v-else>
      <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
        <tr>
          <th class="px-4 py-2 font-medium">Created</th>
          <th class="px-4 py-2 font-medium">Size</th>
          <th class="px-4 py-2 font-medium">Restored</th>
          <th class="px-4 py-2 font-medium"></th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="b in backups" :key="b.id" class="border-b border-border last:border-0">
          <td class="px-4 py-2">{{ new Date(b.created_at).toLocaleString() }}</td>
          <td class="px-4 py-2 text-muted-foreground">{{ formatBytes(b.size_bytes) }}</td>
          <td class="px-4 py-2 text-muted-foreground">
            {{ b.restored_at ? new Date(b.restored_at).toLocaleString() : '—' }}
          </td>
          <td class="px-4 py-2 text-right">
            <Button
              v-if="auth.hasRole('admin')"
              size="sm"
              variant="secondary"
              :disabled="busy"
              @click="restore(b.id)"
              >Restore</Button
            >
          </td>
        </tr>
      </tbody>
    </Table>
  </div>
</template>