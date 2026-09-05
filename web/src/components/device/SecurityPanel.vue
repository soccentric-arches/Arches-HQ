<script setup lang="ts">
import { computed } from 'vue'
import { Plus, ShieldCheck, Trash2 } from 'lucide-vue-next'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'
import { useDeviceConfig } from '@/lib/useDeviceConfig'

const props = defineProps<{ deviceId: string }>()

const cfg = useDeviceConfig(props.deviceId, 'security')

const sshEnabled = computed({
  get: () => ((cfg.config.value.ssh_enabled as boolean) ?? false),
  set: (v: boolean) => cfg.set('ssh_enabled', v),
})
const sshKeys = computed({
  get: () => ((cfg.config.value.ssh_keys as string) ?? ''),
  set: (v: string) => cfg.set('ssh_keys', v),
})

interface FirewallRule {
  direction: 'in' | 'out'
  action: 'allow' | 'deny'
  port: string
  source: string
}
const rules = computed<FirewallRule[]>(() => (cfg.config.value.firewall as FirewallRule[]) ?? [])

function addRule() {
  cfg.set('firewall', [...rules.value, { direction: 'in', action: 'deny', port: '', source: '' }])
}
function removeRule(i: number) {
  cfg.set('firewall', rules.value.filter((_, idx) => idx !== i))
}
function updateRule(i: number, key: keyof FirewallRule, value: string | undefined) {
  cfg.set(
    'firewall',
    rules.value.map((r, idx) => (idx === i ? { ...r, [key]: value ?? '' } : r)),
  )
}
</script>

<template>
  <div class="space-y-4">
    <Card class="p-4">
      <h3 class="flex items-center gap-2 text-sm font-semibold">
        <ShieldCheck class="h-4 w-4 text-muted-foreground" /> SSH console
      </h3>
      <label class="mt-3 flex items-center gap-2 text-sm">
        <input v-model="sshEnabled" type="checkbox" class="accent-[var(--color-accent)]" />
        Enable SSH server on the device
      </label>
      <label class="mt-3 block text-xs font-medium uppercase tracking-wide text-muted-foreground">
        Authorized public keys (one per line)
      </label>
      <textarea
        v-model="sshKeys"
        rows="4"
        placeholder="ssh-ed25519 AAAA…"
        class="mt-1 w-full max-w-2xl rounded-md border border-border bg-surface p-3 font-mono text-xs"
      />
    </Card>

    <Card class="p-4">
      <div class="flex items-center justify-between">
        <h3 class="text-sm font-semibold">Firewall rules</h3>
        <Button size="sm" variant="secondary" @click="addRule"><Plus class="h-3.5 w-3.5" /> Add rule</Button>
      </div>
      <p v-if="rules.length === 0" class="mt-3 text-sm text-muted-foreground">
        No rules configured (default deny incoming).
      </p>
      <div v-for="(r, i) in rules" :key="i" class="mt-3 flex flex-wrap items-center gap-2">
        <select
          :value="r.direction"
          class="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
          @change="updateRule(i, 'direction', ($event.target as HTMLSelectElement).value)"
        >
          <option value="in">in</option>
          <option value="out">out</option>
        </select>
        <select
          :value="r.action"
          class="rounded-md border border-border bg-surface px-2 py-1.5 text-sm"
          @change="updateRule(i, 'action', ($event.target as HTMLSelectElement).value)"
        >
          <option value="allow">allow</option>
          <option value="deny">deny</option>
        </select>
        <Input
          :model-value="r.port"
          placeholder="Port (443)"
          class="max-w-28"
          @update:model-value="(v: string | undefined) => updateRule(i, 'port', v)"
        />
        <Input
          :model-value="r.source"
          placeholder="Source (10.0.0.0/8)"
          class="max-w-44"
          @update:model-value="(v: string | undefined) => updateRule(i, 'source', v)"
        />
        <button type="button" class="text-danger" @click="removeRule(i)">
          <Trash2 class="h-4 w-4" />
        </button>
      </div>
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