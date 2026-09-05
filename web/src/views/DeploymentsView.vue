<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { Plus, RefreshCw } from 'lucide-vue-next'
import { api, ApiError } from '@/lib/api'
import type { Device, DeviceGroup, UpdateArtifact, UpdateRollout } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import Badge from '@/components/ui/Badge.vue'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Dialog from '@/components/ui/Dialog.vue'
import Table from '@/components/ui/Table.vue'
import Input from '@/components/ui/Input.vue'

const auth = useAuthStore()

const artifacts = ref<UpdateArtifact[]>([])
const rollouts = ref<UpdateRollout[]>([])
const groups = ref<DeviceGroup[]>([])
const devices = ref<Device[]>([])
const loading = ref(true)
const error = ref('')
const message = ref('')
const busyId = ref<string | null>(null)

// fleet-level rollout creation
const createOpen = ref(false)
const createArtifactId = ref('')
const createGroupId = ref('')
const creating = ref(false)

// artifact creation
const artifactOpen = ref(false)
const form = ref({ version: '', target_board_rev: '', storage_url: '', checksum_sha256: '' })

// Version compliance: devices whose agent-reported software version does
// not match the newest artifact (naive semver-less compare).
const latestArtifact = computed(() => {
  const sorted = [...artifacts.value].sort((a, b) => b.version.localeCompare(a.version))
  return sorted[0] ?? null
})

const compliance = computed(() => {
  const latest = latestArtifact.value
  if (!latest) return null
  const onLatest = devices.value.filter((d) => d.sw_version?.endsWith(latest.version)).length
  return { total: devices.value.length, onLatest, behind: devices.value.length - onLatest, version: latest.version }
})

// Success rate across every per-device rollout outcome recorded so far.
const successStats = computed(() => {
  let succeeded = 0
  let failed = 0
  let inFlight = 0
  for (const r of rollouts.value)
    for (const d of r.devices) {
      if (d.status === 'succeeded') succeeded += 1
      else if (d.status === 'failed') failed += 1
      else inFlight += 1
    }
  const done = succeeded + failed
  return { succeeded, failed, inFlight, rate: done ? Math.round((succeeded / done) * 100) : null }
})

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const [a, r, g, d] = await Promise.all([
      api.updates.listArtifacts(),
      api.updates.listRollouts(),
      api.deviceGroups.list(),
      api.devices.list({ limit: 200 }),
    ])
    artifacts.value = a.items
    rollouts.value = r.items
    groups.value = g.items
    devices.value = d.items
  } catch {
    error.value = 'Could not load deployments.'
  } finally {
    loading.value = false
  }
}

async function abort(id: string) {
  if (
    !confirm('Abort this rollout? Undelivered commands are revoked; remaining devices are marked failed.')
  )
    return
  busyId.value = id
  error.value = ''
  try {
    const res = await api.updates.abortRollout(id)
    message.value = `Aborted — ${res.aborted_devices} device(s) revoked.`
    await load(true)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Abort failed.'
  } finally {
    busyId.value = null
  }
}

async function retry(id: string) {
  busyId.value = id
  error.value = ''
  try {
    const res = await api.updates.retryRollout(id)
    message.value = `Retry queued for ${res.retried_devices} device(s).`
    await load(true)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Retry failed.'
  } finally {
    busyId.value = null
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
  if (!createArtifactId.value || !createGroupId.value) return
  creating.value = true
  error.value = ''
  try {
    const res = await api.updates.createRollout({
      artifact_id: createArtifactId.value,
      target: 'device_group',
      device_group_id: createGroupId.value,
    })
    message.value = `Rollout created — queued for ${res.device_count} device(s).`
    createOpen.value = false
    await load(true)
  } catch (e) {
    error.value = e instanceof ApiError ? e.message : 'Could not create rollout.'
  } finally {
    creating.value = false
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
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold">Deployments</h1>
        <p class="text-sm text-muted-foreground">
          Releases, artifacts and rollouts across the fleet.
        </p>
      </div>
      <div class="flex gap-2">
        <button
          type="button"
          class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
          @click="load(true)"
        >
          <RefreshCw class="h-3.5 w-3.5" /> Refresh
        </button>
        <Button v-if="auth.hasRole('admin')" size="sm" variant="secondary" @click="artifactOpen = true">
          <Plus class="h-3.5 w-3.5" /> Artifact
        </Button>
        <Button
          v-if="auth.hasRole('admin')"
          size="sm"
          :disabled="artifacts.length === 0 || groups.length === 0"
          :title="groups.length === 0 ? 'Create a device group first (device settings page)' : ''"
          @click="createOpen = true"
        >
          <Plus class="h-3.5 w-3.5" /> Rollout
        </Button>
      </div>
    </div>

    <p v-if="message" class="mb-4 text-sm text-muted-foreground">{{ message }}</p>
    <Card v-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <Card v-else-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>

    <template v-else>
      <div class="mb-4 grid grid-cols-2 gap-4 lg:grid-cols-5">
        <Card class="p-4">
          <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Version compliance
          </p>
          <p class="mt-1 text-2xl font-semibold">
            {{ compliance ? `${compliance.onLatest}/${compliance.total}` : '—' }}
          </p>
          <p class="mt-1 text-xs text-muted-foreground">
            {{ compliance ? `on v${compliance.version} · ${compliance.behind} behind` : 'no artifacts yet' }}
          </p>
        </Card>
        <Card class="p-4 text-center">
          <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Success rate</p>
          <p class="mt-1 text-2xl font-semibold">
            {{ successStats.rate === null ? '—' : `${successStats.rate}%` }}
          </p>
        </Card>
        <Card class="p-4 text-center">
          <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Succeeded</p>
          <p class="mt-1 text-2xl font-semibold text-success">{{ successStats.succeeded }}</p>
        </Card>
        <Card class="p-4 text-center">
          <p class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            Failed / in flight
          </p>
          <p class="mt-1 text-2xl font-semibold">
            <span class="text-danger">{{ successStats.failed }}</span>
            <span class="text-sm text-muted-foreground"> / {{ successStats.inFlight }} </span>
          </p>
        </Card>
      </div>

      <Card class="p-4">
        <h3 class="text-sm font-semibold">Rollouts</h3>
        <p v-if="rollouts.length === 0" class="mt-2 text-sm text-muted-foreground">
          No rollouts yet. Create a device group (on a device's Settings page), then start a rollout.
        </p>
        <div v-for="r in rollouts" :key="r.id" class="mt-3 rounded-md border border-border p-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium">v{{ r.artifact_version }}</span>
            <Badge :tone="statusTone(r.status)" class="capitalize">{{ r.status.replace('_', ' ') }}</Badge>
            <Badge tone="neutral" class="capitalize">{{ r.target.replace('_', ' ') }}</Badge>
            <span class="text-xs text-muted-foreground">
              {{ r.started_at ? new Date(r.started_at).toLocaleString() : '' }}
            </span>
            <span class="ml-auto flex gap-2">
              <Button
                v-if="r.status === 'in_progress' && auth.hasRole('admin')"
                size="sm"
                variant="secondary"
                :disabled="busyId === r.id"
                @click="abort(r.id)"
                >Abort</Button
              >
              <Button
                v-if="r.devices.some((d) => d.status === 'failed') && auth.hasRole('admin')"
                size="sm"
                variant="secondary"
                :disabled="busyId === r.id"
                @click="retry(r.id)"
                >Retry failed</Button
              >
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

      <Card class="mt-4 overflow-hidden p-0">
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
    <Dialog v-model:open="createOpen">
      <template #default="{ close }">
        <h2 class="text-base font-semibold">New rollout</h2>
        <p class="mt-1 text-sm text-muted-foreground">
          Queues an apply-update command for every authorized device in the target group.
        </p>
        <div class="mt-3 space-y-3">
          <select
            v-model="createArtifactId"
            class="w-full rounded-md border border-border bg-surface px-2 py-2 text-sm"
          >
            <option value="" disabled>Select artifact</option>
            <option v-for="a in artifacts" :key="a.id" :value="a.id">
              v{{ a.version }} ({{ a.target_board_rev }})
            </option>
          </select>
          <select
            v-model="createGroupId"
            class="w-full rounded-md border border-border bg-surface px-2 py-2 text-sm"
          >
            <option value="" disabled>Select device group</option>
            <option v-for="g in groups" :key="g.id" :value="g.id">
              {{ g.name }} ({{ g.device_ids.length }} devices)
            </option>
          </select>
        </div>
        <div class="mt-4 flex justify-end gap-2">
          <Button variant="secondary" @click="close">Cancel</Button>
          <Button :disabled="creating || !createArtifactId || !createGroupId" @click="createRollout">
            {{ creating ? 'Creating…' : 'Start rollout' }}
          </Button>
        </div>
      </template>
    </Dialog>
  </div>
</template>
