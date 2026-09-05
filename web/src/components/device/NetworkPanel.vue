<script setup lang="ts">
import { computed, ref } from 'vue'
import { Cable, Plus, Trash2, Wifi } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import Tabs from '@/components/ui/Tabs.vue'
import TabsList from '@/components/ui/TabsList.vue'
import TabsTrigger from '@/components/ui/TabsTrigger.vue'
import TabsContent from '@/components/ui/TabsContent.vue'
import { useDeviceConfig } from '@/lib/useDeviceConfig'

const props = defineProps<{ deviceId: string }>()

const cfg = useDeviceConfig(props.deviceId, 'network')

// ---- wired ----
const wiredDhcp = computed({
  get: () => ((cfg.config.value.wired_dhcp as boolean) ?? true),
  set: (v: boolean) => cfg.set('wired_dhcp', v),
})
const wiredIp = computed({
  get: () => (cfg.config.value.wired_ip as string) ?? '',
  set: (v: string) => cfg.set('wired_ip', v),
})
const wiredGateway = computed({
  get: () => (cfg.config.value.wired_gateway as string) ?? '',
  set: (v: string) => cfg.set('wired_gateway', v),
})
const wiredDns = computed({
  get: () => (cfg.config.value.wired_dns as string) ?? '',
  set: (v: string) => cfg.set('wired_dns', v),
})

// ---- wireless (5 GHz) ----
const wifiSsid = computed({
  get: () => (cfg.config.value.wifi_ssid as string) ?? '',
  set: (v: string) => cfg.set('wifi_ssid', v),
})
const wifiPsk = ref('')
function saveWifiPsk() {
  if (wifiPsk.value.trim()) {
    cfg.set('wifi_psk', wifiPsk.value.trim())
    wifiPsk.value = ''
  }
}
const wifiBand = computed({
  get: () => (cfg.config.value.wifi_band as string) ?? '5g',
  set: (v: string) => cfg.set('wifi_band', v),
})

// ---- wireguard tunnels ----
interface WgTunnel {
  name: string
  endpoint: string
  public_key: string
  allowed_ips: string
}
const tunnels = computed<WgTunnel[]>(() => (cfg.config.value.wireguard as WgTunnel[]) ?? [])

function addTunnel() {
  cfg.set('wireguard', [...tunnels.value, { name: '', endpoint: '', public_key: '', allowed_ips: '' }])
}
function removeTunnel(i: number) {
  cfg.set('wireguard', tunnels.value.filter((_, idx) => idx !== i))
}
function updateTunnel(i: number, key: keyof WgTunnel, value: string | undefined) {
  cfg.set(
    'wireguard',
    tunnels.value.map((t, idx) => (idx === i ? { ...t, [key]: value ?? '' } : t)),
  )
}
</script>

<template>
  <div>
    <Tabs default-value="wired">
      <TabsList>
        <TabsTrigger value="wired">Wired</TabsTrigger>
        <TabsTrigger value="wireless">Wireless 5 GHz</TabsTrigger>
        <TabsTrigger value="wireguard">WireGuard</TabsTrigger>
      </TabsList>

      <TabsContent value="wired">
        <Card class="p-4">
          <h3 class="flex items-center gap-2 text-sm font-semibold">
            <Cable class="h-4 w-4 text-muted-foreground" /> Wired interface
          </h3>
          <label class="mt-3 flex items-center gap-2 text-sm">
            <input v-model="wiredDhcp" type="checkbox" class="accent-[var(--color-accent)]" />
            Use DHCP
          </label>
          <div v-if="!wiredDhcp" class="mt-3 grid max-w-lg grid-cols-1 gap-3 sm:grid-cols-3">
            <Input v-model="wiredIp" placeholder="IP address (10.0.0.10/24)" />
            <Input v-model="wiredGateway" placeholder="Gateway" />
            <Input v-model="wiredDns" placeholder="DNS" />
          </div>
        </Card>
      </TabsContent>

      <TabsContent value="wireless">
        <Card class="p-4">
          <h3 class="flex items-center gap-2 text-sm font-semibold">
            <Wifi class="h-4 w-4 text-muted-foreground" /> Wireless station
          </h3>
          <div class="mt-3 grid max-w-lg grid-cols-1 gap-3">
            <Input v-model="wifiSsid" placeholder="SSID" />
            <div class="flex gap-2">
              <Input v-model="wifiPsk" type="password" placeholder="Passphrase (leave blank to keep)" />
              <Button size="sm" variant="secondary" @click="saveWifiPsk">Set</Button>
            </div>
            <div class="flex gap-2 text-xs">
              <button
                v-for="b in ['2.4g', '5g']"
                :key="b"
                type="button"
                class="rounded-full border px-3 py-1 font-medium uppercase"
                :class="wifiBand === b ? 'border-accent bg-accent-muted text-accent' : 'border-border text-muted-foreground'"
                @click="wifiBand = b"
              >
                {{ b }}
              </button>
            </div>
          </div>
        </Card>
      </TabsContent>

      <TabsContent value="wireguard">
        <Card class="p-4">
          <div class="flex items-center justify-between">
            <h3 class="text-sm font-semibold">WireGuard tunnels</h3>
            <Button size="sm" variant="secondary" @click="addTunnel"><Plus class="h-3.5 w-3.5" /> Add</Button>
          </div>
          <p v-if="tunnels.length === 0" class="mt-3 text-sm text-muted-foreground">
            No tunnels configured.
          </p>
          <div v-for="(t, i) in tunnels" :key="i" class="mt-3 rounded-md border border-border p-3">
            <div class="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <Input
                :model-value="t.name"
                placeholder="Tunnel name"
                @update:model-value="(v: string | undefined) => updateTunnel(i, 'name', v)"
              />
              <Input
                :model-value="t.endpoint"
                placeholder="Endpoint (vpn.example.com:51820)"
                @update:model-value="(v: string | undefined) => updateTunnel(i, 'endpoint', v)"
              />
              <Input
                :model-value="t.public_key"
                placeholder="Peer public key"
                @update:model-value="(v: string | undefined) => updateTunnel(i, 'public_key', v)"
              />
              <Input
                :model-value="t.allowed_ips"
                placeholder="Allowed IPs (10.8.0.0/24)"
                @update:model-value="(v: string | undefined) => updateTunnel(i, 'allowed_ips', v)"
              />
            </div>
            <button
              type="button"
              class="mt-2 flex items-center gap-1 text-xs text-danger"
              @click="removeTunnel(i)"
            >
              <Trash2 class="h-3.5 w-3.5" /> Remove
            </button>
          </div>
        </Card>
      </TabsContent>
    </Tabs>

    <div class="mt-4 flex items-center gap-3">
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