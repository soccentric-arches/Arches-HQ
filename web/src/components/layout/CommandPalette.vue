<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { Search } from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { Device } from '@/lib/types'

const open = ref(false)
const input = ref<HTMLInputElement | null>(null)
const q = ref('')
const results = ref<Device[]>([])
const searching = ref(false)
const highlighted = ref(0)
let timer: ReturnType<typeof setTimeout> | null = null

const emit = defineEmits<{ close: [] }>()
const router = useRouter()

watch(open, async (v) => {
  if (v) {
    q.value = ''
    results.value = []
    highlighted.value = 0
    await nextTick()
    input.value?.focus()
  }
})

watch(q, (value) => {
  if (timer) clearTimeout(timer)
  const query = value.trim()
  if (query.length < 2) {
    results.value = []
    return
  }
  timer = setTimeout(async () => {
    searching.value = true
    try {
      const res = await api.devices.list({ q: query, limit: 8 })
      results.value = res.items
      highlighted.value = 0
    } finally {
      searching.value = false
    }
  }, 200)
})

function go(id: string) {
  open.value = false
  emit('close')
  router.push({ name: 'device-detail', params: { id } })
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    open.value = false
    emit('close')
  } else if (e.key === 'ArrowDown') {
    e.preventDefault()
    highlighted.value = Math.min(highlighted.value + 1, results.value.length - 1)
  } else if (e.key === 'ArrowUp') {
    e.preventDefault()
    highlighted.value = Math.max(highlighted.value - 1, 0)
  } else if (e.key === 'Enter') {
    const d = results.value[highlighted.value]
    if (d) go(d.id)
  }
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="open"
      class="fixed inset-0 z-50 flex items-start justify-center bg-black/40 px-4 pt-[15vh]"
      @click.self="open = false; emit('close')"
      @keydown="onKeydown"
    >
      <div class="w-full max-w-lg overflow-hidden rounded-lg border border-border bg-surface shadow-lg">
        <div class="flex items-center gap-2 border-b border-border px-3">
          <Search class="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref="input"
            v-model="q"
            type="search"
            placeholder="Search devices by name, serial, IP, hostname…"
            class="h-11 w-full bg-transparent text-sm outline-none placeholder:text-muted"
          />
          <kbd class="shrink-0 rounded border border-border px-1 text-[10px] text-muted-foreground">esc</kbd>
        </div>
        <div class="max-h-80 overflow-y-auto py-1">
          <p v-if="q.trim().length < 2" class="px-3 py-3 text-sm text-muted-foreground">
            Type at least two characters — matches name, serial, IP address and hostname.
          </p>
          <p v-else-if="results.length === 0 && !searching" class="px-3 py-3 text-sm text-muted-foreground">
            No devices match “{{ q }}”.
          </p>
          <button
            v-for="(d, i) in results"
            :key="d.id"
            type="button"
            class="flex w-full items-center justify-between gap-3 px-3 py-2 text-left text-sm"
            :class="i === highlighted ? 'bg-surface-muted' : ''"
            @click="go(d.id)"
            @mouseenter="highlighted = i"
          >
            <span class="truncate font-medium">{{ d.name }}</span>
            <span class="shrink-0 font-mono text-xs text-muted-foreground">
              {{ d.serial ?? d.ip_address ?? '—' }}
            </span>
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>