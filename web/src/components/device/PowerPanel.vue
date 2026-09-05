<script setup lang="ts">
import { ref } from 'vue'
import { api, ApiError } from '@/lib/api'
import type { Device } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Dialog from '@/components/ui/Dialog.vue'

const props = defineProps<{ device: Device }>()
const emit = defineEmits<{ updated: [Device] }>()
const auth = useAuthStore()

const busy = ref(false)
const message = ref('')
// 'system-reset' has no agent verb yet; the rest are real HQ commands.
type ConfirmKind = 'reboot' | 'shutdown' | 'system-reset' | 'factory-reset' | 'disable'
const confirmKind = ref<ConfirmKind | null>(null)

const labels: Record<ConfirmKind, string> = {
  reboot: 'Reboot this device?',
  shutdown: 'Shut down this device?',
  'system-reset': 'System reset this device?',
  'factory-reset': 'Factory reset this device?',
  disable: 'Disable this device?',
}

const descriptions: Record<ConfirmKind, string> = {
  reboot: 'The device will restart. It drops offline for the duration and reconnects automatically.',
  shutdown: 'The device will power off. Someone with physical access must start it again.',
  'system-reset': 'Services and state are reset; network identity and pairing are kept.',
  'factory-reset': 'The device will wipe local state and require re-pairing.',
  disable: 'HQ will refuse this device\'s connection immediately, even with a valid credential.',
}

async function confirmAction() {
  if (!confirmKind.value) return
  busy.value = true
  try {
    switch (confirmKind.value) {
      case 'reboot':
        await api.devices.reboot(props.device.id)
        message.value = 'Reboot queued — delivered on the device\'s next heartbeat.'
        break
      case 'shutdown':
        await api.devices.shutdown(props.device.id)
        message.value = 'Shutdown queued — delivered on the device\'s next heartbeat.'
        break
      case 'factory-reset':
        await api.devices.factoryReset(props.device.id)
        message.value = 'Factory reset queued — delivered on the device\'s next heartbeat.'
        break
      case 'disable': {
        const updated = await api.devices.disable(props.device.id)
        emit('updated', updated)
        message.value = 'Device disabled.'
        break
      }
      default:
        message.value = 'Not yet supported: the agent protocol does not expose this verb yet.'
    }
  } catch (e) {
    message.value = e instanceof ApiError ? e.message : 'Action failed.'
  } finally {
    busy.value = false
    confirmKind.value = null
  }
}
</script>

<template>
  <div class="space-y-4">
    <p v-if="message" class="text-sm text-muted-foreground">{{ message }}</p>

    <Card class="p-4">
      <h3 class="text-sm font-semibold">Power</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        Control the device power state. Commands are queued and delivered when the device next
        heartbeats.
      </p>
      <div class="mt-3 flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" :disabled="!device.online" @click="confirmKind = 'reboot'">
          Reboot
        </Button>
        <Button
          size="sm"
          variant="secondary"
          :disabled="!device.online"
          @click="confirmKind = 'shutdown'"
        >
          Shut down
        </Button>
      </div>
      <p v-if="!device.online" class="mt-3 text-xs text-muted-foreground">
        The device is offline — commands queue up and are delivered when it reconnects.
      </p>
    </Card>

    <Card class="p-4">
      <h3 class="text-sm font-semibold">Reset</h3>
      <p class="mt-1 text-sm text-muted-foreground">
        Recover a misbehaving device. All actions here are logged to the audit log and cannot be
        undone by HQ.
      </p>
      <div class="mt-3 flex flex-wrap gap-2">
        <Button
          size="sm"
          variant="secondary"
          :disabled="!device.online"
          @click="confirmKind = 'system-reset'"
        >
          System reset
        </Button>
        <Button
          v-if="auth.hasRole('admin')"
          size="sm"
          variant="destructive"
          @click="confirmKind = 'factory-reset'"
        >
          Factory reset
        </Button>
        <Button
          v-if="auth.hasRole('admin')"
          size="sm"
          variant="destructive"
          :disabled="device.pairing_state === 'disabled'"
          @click="confirmKind = 'disable'"
        >
          Disable device
        </Button>
      </div>
      <Badge v-if="device.pairing_state === 'disabled'" tone="danger" class="mt-3">
        Currently disabled
      </Badge>
    </Card>

    <Dialog :open="confirmKind !== null" @update:open="(v) => !v && (confirmKind = null)">
      <template #default="{ close }">
        <h2 class="text-base font-semibold">
          {{ confirmKind ? labels[confirmKind] : '' }}
        </h2>
        <p class="mt-2 text-sm text-muted-foreground">
          {{ confirmKind ? descriptions[confirmKind] : '' }}
        </p>
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="secondary" @click="close(); confirmKind = null">Cancel</Button>
          <Button
            variant="destructive"
            :disabled="busy || confirmKind === 'system-reset'"
            @click="confirmAction(); close()"
          >
            Confirm
          </Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>