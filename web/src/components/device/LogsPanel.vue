<script setup lang="ts">
import { onMounted, ref, watch } from 'vue'
import { Download, RefreshCw, ScrollText } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { LogBundle } from '@/lib/types'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Table from '@/components/ui/Table.vue'
import Tabs from '@/components/ui/Tabs.vue'
import TabsList from '@/components/ui/TabsList.vue'
import TabsTrigger from '@/components/ui/TabsTrigger.vue'
import TabsContent from '@/components/ui/TabsContent.vue'

const props = defineProps<{ deviceId: string }>()

// Log sources the device agent will stream. Live tailing needs the agent
// protocol; the bundles below are the real, downloadable history today.
const sources = ['Syslog', 'Kernel', 'Application']

const bundles = ref<LogBundle[]>([])
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.logs.list(props.deviceId)
    bundles.value = res.items
  } catch {
    error.value = 'Could not load log bundles.'
  } finally {
    loading.value = false
  }
}

async function download(id: string) {
  const { download_url } = await api.logs.downloadUrl(props.deviceId, id)
  window.open(download_url, '_blank')
}

function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`
  return `${(n / 1024 / 1024).toFixed(1)} MB`
}

watch(() => props.deviceId, load)
onMounted(load)
</script>

<template>
  <div>
    <Tabs default-value="syslog">
      <TabsList>
        <TabsTrigger v-for="s in sources" :key="s" :value="s.toLowerCase()">{{ s }}</TabsTrigger>
        <TabsTrigger value="history">History</TabsTrigger>
      </TabsList>

      <TabsContent v-for="s in sources" :key="s" :value="s.toLowerCase()">
        <Card class="p-6">
          <div class="flex items-start gap-3">
            <ScrollText class="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" />
            <div>
              <h3 class="text-sm font-semibold">{{ s }} — live tail</h3>
              <p class="mt-1 text-sm text-muted-foreground">
                Live log streaming requires device-agent support (Arches-Configuration). Once the
                agent streams logs, they appear here in real time.
              </p>
              <div
                class="mt-3 rounded-md bg-surface-muted p-4 font-mono text-xs text-muted-foreground"
              >
                <p># waiting for {{ s.toLowerCase() }} stream…</p>
              </div>
            </div>
          </div>
        </Card>
      </TabsContent>

      <TabsContent value="history">
        <div class="mb-3 flex items-center justify-between">
          <p class="text-xs text-muted-foreground">
            Bundles the device uploaded on request — the downloadable log history.
          </p>
          <button
            type="button"
            class="flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
            @click="load()"
          >
            <RefreshCw class="h-3.5 w-3.5" /> Refresh
          </button>
        </div>

        <Card v-if="loading" class="p-6 text-sm text-muted-foreground">Loading…</Card>
        <Card v-else-if="error" class="p-6 text-sm text-danger">{{ error }}</Card>
        <Card v-else-if="bundles.length === 0" class="p-6 text-sm text-muted-foreground">
          No log bundles uploaded yet.
        </Card>
        <Table v-else>
          <thead class="border-b border-border bg-surface-muted text-xs uppercase text-muted-foreground">
            <tr>
              <th class="px-4 py-2 font-medium">Time range</th>
              <th class="px-4 py-2 font-medium">Uploaded</th>
              <th class="px-4 py-2 font-medium">Size</th>
              <th class="px-4 py-2 font-medium"></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="b in bundles" :key="b.id" class="border-b border-border last:border-0">
              <td class="px-4 py-2">
                {{ new Date(b.time_range_start).toLocaleString() }} &ndash;
                {{ new Date(b.time_range_end).toLocaleString() }}
              </td>
              <td class="px-4 py-2 text-muted-foreground">
                {{ new Date(b.uploaded_at).toLocaleString() }}
              </td>
              <td class="px-4 py-2 text-muted-foreground">{{ formatBytes(b.size_bytes) }}</td>
              <td class="px-4 py-2 text-right">
                <Button size="sm" variant="secondary" @click="download(b.id)">
                  <Download class="h-3.5 w-3.5" /> Download
                </Button>
              </td>
            </tr>
          </tbody>
        </Table>
      </TabsContent>
    </Tabs>
  </div>
</template>