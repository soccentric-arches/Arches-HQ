<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RefreshCw } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { UpdateArtifact, UpdateRollout } from '@/lib/types'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'


const artifacts = ref<UpdateArtifact[]>([])
const rollouts = ref<UpdateRollout[]>([])
const loading = ref(true)
const error = ref('')

function statusTone(s: string) {
  return s === 'succeeded' || s === 'completed'
    ? 'success'
    : s === 'failed'
      ? 'danger'
      : s === 'applying' || s === 'in_progress'
        ? 'warning'
        : 'neutral'
}

async function load(silent = false) {
  if (!silent) loading.value = true
  error.value = ''
  try {
    const [a, r] = await Promise.all([api.updates.listArtifacts(), api.updates.listRollouts()])
    artifacts.value = a.items
    rollouts.value = r.items
  } catch {
    error.value = 'Could not load deployments.'
  } finally {
    loading.value = false
  }
}

onMounted(() => load())
</script>

<template>
  <div>
    <div class="mb-6 flex items-center justify-between">
      <div>
        <h1 class="text-xl font-semibold">Deployments</h1>
        <p class="text-sm text-muted-foreground">
          Releases, artifacts and rollouts across the fleet. Start a rollout from a device's OTA
          page.
        </p>
      </div>
      <button
        type="button"
        class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
        @click="load(true)"
      >
        <RefreshCw class="h-3.5 w-3.5" /> Refresh
      </button>
    </div>

    <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
    <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
    <template v-else>
      <Card class="p-4">
        <h3 class="text-sm font-semibold">Rollouts</h3>
        <p v-if="rollouts.length === 0" class="mt-2 text-sm text-muted-foreground">
          No rollouts yet.
        </p>
        <div v-for="r in rollouts" :key="r.id" class="mt-3 rounded-md border border-border p-3">
          <div class="flex flex-wrap items-center gap-2">
            <span class="text-sm font-medium">v{{ r.artifact_version }}</span>
            <Badge :tone="statusTone(r.status)" class="capitalize">{{ r.status.replace('_', ' ') }}</Badge>
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

      <Card class="mt-4 overflow-hidden p-0">
        <h3 class="border-b border-border px-4 py-3 text-sm font-semibold">Artifacts</h3>
        <p v-if="artifacts.length === 0" class="px-4 py-6 text-sm text-muted-foreground">
          No artifacts yet — create one from a device's OTA page.
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
  </div>
</template>