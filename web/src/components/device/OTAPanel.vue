<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { Plus, RefreshCw } from 'lucide-vue-next'
import { api, ApiError } from '@/lib/api'
import type { Device, UpdateArtifact, UpdateRollout } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Dialog from '@/components/ui/Dialog.vue'
import Input from '@/components/ui/Input.vue'
import Table from '@/components/ui/Table.vue'

defineProps<{ device: Device }>()
const auth = useAuthStore()

const artifacts = ref<UpdateArtifact[]>([])
const rollouts = ref<UpdateRollout[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')

// create artifact
const artifactOpen = ref(false)
const form = ref({ version: '', target_board_rev: '', storage_url: '', checksum_sha256: '' })
const creating = ref(false)

// create rollout
const rolloutOpen = ref(false)
const rolloutArtifactId = ref('')
const rolloutTarget = ref<'all' | 'specific_devices'>('all')
const creatingRollout = ref(false)

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const [a, r] = await Promise.all([api.updates.listArtifacts(), api.updates.listRollouts()])
    artifacts.value = a.items
    rollouts.value = r.items
  } catch {
    error.value = 'Could not load update artifacts or rollouts.'
  } finally {
    loading.value = false
  }
}

async function createArtifact() {
  creating.value = true
  error.value = ''
  try {
    await api.updates.createArtifact({ ...form.value })
    artifactOpen.value = false
    form.value = { version: '', target_board_rev: '', storage_url: '', checksum_sha256: '' }
    message.value = 'Artifact created.'
    await load(true)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Could not create artifact.'
  } finally {
    creating.value = false
  }
}

async function createRollout() {
  if (!rolloutArtifactId.value) return
  creatingRollout.value = true
  error.value = ''
  try {
    const res = await api.updates.createRollout({
      artifact_id: rolloutArtifactId.value,
      target: rolloutTarget.value,
    })
    message.value = `Rollout created — queued for ${res.device_count} device(s).`
    rolloutOpen.value = false
    await load(true)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Could not create rollout.'
  } finally {
    creatingRollout.value = false
  }
}

function statusTone(s: string) {
  return s === 'succeeded' || s === 'completed'
    ? 'success'
    : s === 'failed'
      ? 'danger'
      : s === 'applying' || s === 'in_progress'
        ? 'warning'
        : 'neutral'
}

onMounted(() => load())
</script>

<template>
  <div class="space-y-4">
    <div class="flex items-center justify-between">
      <p class="text-xs text-muted-foreground">
        Artifacts are versioned images; a rollout queues an apply-update command for each targeted
        device, delivered on its next heartbeat.
      </p>
      <div class="flex gap-2">
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
          @click="load()"
        >
          <RefreshCw class="h-3.5 w-3.5" /> Refresh
        </button>
        <Button v-if="auth.hasRole('admin')" size="sm" variant="secondary" @click="artifactOpen = true">
          <Plus class="h-3.5 w-3.5" /> Artifact
        </Button>
        <Button
          v-if="auth.hasRole('admin')"
          size="sm"
          :disabled="artifacts.length === 0"
          @click="rolloutOpen = true"
        >
          <Plus class="h-3.5 w-3.5" /> Rollout
        </Button>
      </div>
    </div>

    <p v-if="message" class="text-sm text-muted-foreground">{{ message }}</p>
    <Card v-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <Card v-else-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>

    <template v-else>
      <Card class="p-4">
        <h3 class="text-sm font-semibold">Rollouts</h3>
        <p v-if="rollouts.length === 0" class="mt-2 text-sm text-muted-foreground">
          No rollouts yet.
        </p>
        <div v-for="r in rollouts" :key="r.id" class="mt-3 rounded-md border border-border p-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium">v{{ r.artifact_version }}</span>
            <Badge :tone="statusTone(r.status)" class="capitalize">{{ r.status }}</Badge>
            <Badge tone="neutral" class="capitalize">{{ r.target.replace('_', ' ') }}</Badge>
            <span class="text-xs text-muted-foreground">
              {{ r.started_at ? new Date(r.started_at).toLocaleString() : '' }}
            </span>
          </div>
          <div class="mt-2 flex flex-wrap gap-1.5">
            <Badge
              v-for="d in r.devices"
              :key="d.device_id"
              :tone="statusTone(d.status)"
              class="font-mono text-[10px]"
              :title="d.error ?? ''"
            >
              {{ d.device_id.slice(0, 8) }}… {{ d.status }}
            </Badge>
          </div>
        </div>
      </Card>

      <Card class="p-0 overflow-hidden">
        <h3 class="border-b border-border px-4 py-3 text-sm font-semibold">Artifacts</h3>
        <p v-if="artifacts.length === 0" class="px-4 py-6 text-sm text-muted-foreground">
          No artifacts yet — create one to start rolling out updates.
        </p>
        <Table v-else>
          <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
            <tr>
              <th class="px-4 py-2 font-medium">Version</th>
              <th class="px-4 py-2 font-medium">Board rev</th>
              <th class="px-4 py-2 font-medium">Checksum (sha256)</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="a in artifacts" :key="a.id" class="border-b border-border last:border-0">
              <td class="px-4 py-2 font-medium">v{{ a.version }}</td>
              <td class="px-4 py-2">{{ a.target_board_rev }}</td>
              <td class="px-4 py-2 font-mono text-xs text-muted-foreground">
                {{ a.checksum_sha256.slice(0, 16) }}…
              </td>
            </tr>
          </tbody>
        </Table>
      </Card>
    </template>

    <!-- create artifact -->
    <Dialog v-model:open="artifactOpen">
      <template #default="{ close }">
        <h2 class="text-base font-semibold">New update artifact</h2>
        <div class="mt-3 grid grid-cols-1 gap-3">
          <Input v-model="form.version" placeholder="Version (2.1.0)" />
          <Input v-model="form.target_board_rev" placeholder="Target board revision (rev-c)" />
          <Input v-model="form.storage_url" placeholder="Storage URL (s3://artifacts/2.1.0.img)" />
          <Input v-model="form.checksum_sha256" placeholder="SHA-256 checksum" />
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="secondary" @click="close">Cancel</Button>
          <Button :disabled="creating" @click="createArtifact">
            {{ creating ? 'Creating…' : 'Create' }}
          </Button>
        </div>
      </template>
    </Dialog>

    <!-- create rollout -->
    <Dialog v-model:open="rolloutOpen">
      <template #default="{ close }">
        <h2 class="text-base font-semibold">New rollout</h2>
        <p class="mt-1 text-sm text-muted-foreground">
          Queues an apply-update command for every authorized device in the target set.
        </p>
        <div class="mt-3 space-y-3">
          <select
            v-model="rolloutArtifactId"
            class="w-full rounded-md border border-border bg-surface px-2 py-2 text-sm"
          >
            <option value="" disabled>Select artifact</option>
            <option v-for="a in artifacts" :key="a.id" :value="a.id">v{{ a.version }} ({{ a.target_board_rev }})</option>
          </select>
          <div class="flex gap-2 text-xs">
            <button
              v-for="t in ['all', 'specific_devices']"
              :key="t"
              type="button"
              class="rounded-full border px-3 py-1 font-medium"
              :class="rolloutTarget === t ? 'border-accent bg-accent-muted text-accent' : 'border-border text-muted-foreground'"
              @click="rolloutTarget = t as 'all' | 'specific_devices'"
            >
              {{ t === 'all' ? 'All authorized devices' : 'Specific devices (via API)' }}
            </button>
          </div>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="secondary" @click="close">Cancel</Button>
          <Button :disabled="creatingRollout || !rolloutArtifactId" @click="createRollout">
            {{ creatingRollout ? 'Creating…' : 'Start rollout' }}
          </Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>