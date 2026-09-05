<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import {
  Bell,
  ChevronsUpDown,
  CircleHelp,
  LoaderCircle,
  LogOut,
  Radar,
  Satellite,
  Search,
} from 'lucide-vue-next'
import { api } from '@/lib/api'
import type { ActiveAlarm, Device } from '@/lib/types'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/lib/utils'
import Dropdown from '@/components/ui/Dropdown.vue'
import DropdownMenuItem from '@/components/ui/DropdownMenuItem.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

// ── global nav ────────────────────────────────────────────────────────────
// Max 10 top-level items (Phase 1: Overview, Devices, Deployments, Alerts,
// Users, Audit Log); everything else lives on device pages or in
// future_feature.md.
const navLinks = computed(() => {
  const links = [
    { to: { name: 'overview' }, label: 'Overview', active: route.name === 'overview' },
    {
      to: { name: 'devices' },
      label: 'Devices',
      active: route.name === 'devices' || route.name === 'device-detail',
    },
    {
      to: { name: 'deployments' },
      label: 'Deployments',
      active: route.name === 'deployments',
    },
    {
      to: { name: 'alarm-rules' },
      label: 'Alerts',
      active: route.name === 'alarm-rules',
    },
  ]
  if (auth.hasRole('admin')) {
    links.push(
      { to: { name: 'users' }, label: 'Users', active: route.name === 'users' },
      { to: { name: 'audit-log' }, label: 'Audit Log', active: route.name === 'audit-log' },
    )
  }
  return links
})

const initials = computed(() => (auth.user?.email?.[0] ?? '?').toUpperCase())

async function handleLogout() {
  await auth.logout()
  router.push({ name: 'login' })
}

// ── global search (serial, IP, hostname, name) — `/` focuses ─────────────
const searchInput = ref<HTMLInputElement | null>(null)
const q = ref('')
const searchOpen = ref(false)
const searchResults = ref<Device[]>([])
const searching = ref(false)
let searchTimer: ReturnType<typeof setTimeout> | null = null

watch(q, (value) => {
  if (searchTimer) clearTimeout(searchTimer)
  const query = value.trim()
  if (query.length < 2) {
    searchResults.value = []
    searchOpen.value = false
    return
  }
  searchTimer = setTimeout(async () => {
    searching.value = true
    try {
      const res = await api.devices.list({ q: query, limit: 8 })
      searchResults.value = res.items
      searchOpen.value = true
    } catch {
      searchOpen.value = false
    } finally {
      searching.value = false
    }
  }, 250)
})

function goToDevice(id: string) {
  searchOpen.value = false
  q.value = ''
  router.push({ name: 'device-detail', params: { id } })
}

// ── alert bell (fleet-wide active alarms) ────────────────────────────────
const alarmCount = ref(0)
const activeAlarms = ref<ActiveAlarm[]>([])
let bellTimer: ReturnType<typeof setInterval> | null = null

async function loadAlarms() {
  try {
    const res = await api.alarms.active()
    alarmCount.value = res.count
    activeAlarms.value = res.items
  } catch {
    /* bell is best-effort; never block the UI */
  }
}

function alarmHex(code: number) {
  return `0x${code.toString(16).padStart(8, '0')}`
}

function goToDeviceAlarms(deviceId: string) {
  router.push({ name: 'device-detail', params: { id: deviceId }, query: { section: 'alarms' } })
}

// ── active deployments indicator ─────────────────────────────────────────
const activeRollouts = ref(0)
let rolloutTimer: ReturnType<typeof setInterval> | null = null

async function loadRollouts() {
  try {
    const res = await api.updates.listRollouts()
    activeRollouts.value = res.items.filter((r) => r.status === 'in_progress').length
  } catch {
    /* best-effort */
  }
}

// ── backend connection status + environment badge ────────────────────────
const backendUp = ref(true)
let healthTimer: ReturnType<typeof setInterval> | null = null

async function pingBackend() {
  try {
    const res = await fetch('/api/healthz', { credentials: 'include' })
    backendUp.value = res.ok
  } catch {
    backendUp.value = false
  }
}

const envBadge = computed(() => (import.meta.env.DEV ? 'DEV' : 'PROD'))

// ── keyboard shortcuts: `/` search, `g d` devices, `g p` deployments ─────
let chordPending = false
function onKeydown(e: KeyboardEvent) {
  const target = e.target as HTMLElement
  const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || target.isContentEditable
  if (e.key === '/' && !typing) {
    e.preventDefault()
    searchInput.value?.focus()
    return
  }
  if (typing) return
  if (e.key === 'g' && !chordPending) {
    chordPending = true
    setTimeout(() => (chordPending = false), 800)
    return
  }
  if (chordPending) {
    if (e.key === 'd') router.push({ name: 'devices' })
    else if (e.key === 'p') router.push({ name: 'deployments' })
    chordPending = false
  }
}

onMounted(() => {
  loadAlarms()
  loadRollouts()
  pingBackend()
  bellTimer = setInterval(loadAlarms, 30000)
  rolloutTimer = setInterval(loadRollouts, 30000)
  healthTimer = setInterval(pingBackend, 30000)
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  if (bellTimer) clearInterval(bellTimer)
  if (rolloutTimer) clearInterval(rolloutTimer)
  if (healthTimer) clearInterval(healthTimer)
  window.removeEventListener('keydown', onKeydown)
})
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="sticky top-0 z-40 h-14 border-b border-border bg-surface">
      <div class="mx-auto flex h-full max-w-6xl items-center gap-4 px-4 sm:px-6">
        <RouterLink
          to="/"
          class="flex shrink-0 items-center gap-2 text-sm font-semibold tracking-tight"
        >
          <span
            class="flex h-6 w-6 items-center justify-center rounded-md bg-accent text-accent-foreground"
          >
            <Satellite class="h-3.5 w-3.5" />
          </span>
          <span class="hidden sm:block">Arches-HQ</span>
        </RouterLink>

        <!-- global search: serial, IP, hostname, name — `/` focuses -->
        <div class="relative min-w-0 max-w-xs flex-1 sm:flex-none">
          <span
            class="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted-foreground"
          >
            <Search class="h-3.5 w-3.5" />
          </span>
          <input
            ref="searchInput"
            v-model="q"
            type="search"
            placeholder="Search devices…  ( / )"
            class="h-8 w-full rounded-md border border-border bg-surface-muted pl-8 pr-8 text-sm placeholder:text-muted focus:border-accent focus:bg-surface"
            @focus="q.trim().length >= 2 && (searchOpen = true)"
            @keydown.esc="searchOpen = false; ($event.target as HTMLInputElement).blur()"
          />
          <kbd
            v-if="!q"
            class="pointer-events-none absolute right-2 top-1/2 hidden -translate-y-1/2 rounded border border-border bg-surface px-1 text-[10px] text-muted-foreground sm:block"
          >
            /
          </kbd>

          <!-- search results dropdown -->
          <div
            v-if="searchOpen && q.trim().length >= 2"
            class="absolute left-0 right-0 top-10 z-50 overflow-hidden rounded-md border border-border bg-surface py-1 shadow-md"
          >
            <p v-if="searchResults.length === 0 && !searching" class="px-3 py-2 text-sm text-muted-foreground">
              No devices match “{{ q }}”.
            </p>
            <button
              v-for="d in searchResults"
              :key="d.id"
              type="button"
              class="flex w-full items-center justify-between gap-3 px-3 py-1.5 text-left text-sm hover:bg-surface-muted"
              @click="goToDevice(d.id)"
            >
              <span class="truncate font-medium">{{ d.name }}</span>
              <span class="shrink-0 font-mono text-xs text-muted-foreground">
                {{ d.serial ?? d.ip_address ?? '—' }}
              </span>
            </button>
          </div>
        </div>

        <nav class="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto" aria-label="Global">
          <RouterLink
            v-for="link in navLinks"
            :key="link.label"
            :to="link.to"
            :class="
              cn(
                'whitespace-nowrap rounded-md px-2.5 py-1.5 text-sm transition-colors',
                link.active
                  ? 'bg-surface-muted font-medium text-foreground'
                  : 'text-muted-foreground hover:text-foreground',
              )
            "
          >
            {{ link.label }}
          </RouterLink>
        </nav>

        <!-- active deployments indicator -->
        <RouterLink
          v-if="activeRollouts > 0"
          to="/deployments"
          class="flex shrink-0 items-center gap-1.5 rounded-md px-2 py-1 text-xs font-medium text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
          :title="`${activeRollouts} active deployment(s)`"
        >
          <LoaderCircle class="h-4 w-4 animate-spin text-accent" />
          {{ activeRollouts }}
        </RouterLink>

        <!-- alert bell with unread (active) count -->
        <Dropdown v-if="auth.user">
          <template #trigger>
            <button
              type="button"
              class="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
              aria-label="Active alarms"
            >
              <Bell class="h-4 w-4" />
              <span
                v-if="alarmCount > 0"
                class="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold text-white"
              >
                {{ alarmCount > 99 ? '99+' : alarmCount }}
              </span>
            </button>
          </template>
          <div class="w-72">
            <p class="px-2 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Active alarms ({{ alarmCount }})
            </p>
            <p v-if="activeAlarms.length === 0" class="px-2 py-2 text-sm text-muted-foreground">
              No active alarms across the fleet.
            </p>
            <button
              v-for="a in activeAlarms.slice(0, 8)"
              :key="a.id"
              type="button"
              class="flex w-full items-center justify-between gap-2 rounded-sm px-2 py-1.5 text-left text-sm hover:bg-surface-muted"
              @click="goToDeviceAlarms(a.device_id)"
            >
              <span class="min-w-0">
                <span class="block truncate font-medium">{{ a.device_name }}</span>
                <span class="block font-mono text-xs text-muted-foreground">{{ alarmHex(a.alarm_code) }}</span>
              </span>
              <span class="shrink-0 text-xs text-muted-foreground">
                {{ new Date(a.triggered_at).toLocaleTimeString() }}
              </span>
            </button>
            <div class="my-1 border-t border-border" />
            <DropdownMenuItem class="text-muted-foreground" @select="router.push({ name: 'alarm-rules' })">
              Manage alert rules
            </DropdownMenuItem>
          </div>
        </Dropdown>

        <!-- help / keyboard shortcuts -->
        <Dropdown v-if="auth.user">
          <template #trigger>
            <button
              type="button"
              class="flex h-8 w-8 shrink-0 items-center justify-center rounded-md text-muted-foreground transition-colors hover:bg-surface-muted hover:text-foreground"
              aria-label="Help"
            >
              <CircleHelp class="h-4 w-4" />
            </button>
          </template>
          <div class="w-64">
            <p class="px-2 py-1.5 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Keyboard shortcuts
            </p>
            <div class="space-y-1 px-2 py-1 text-sm">
              <p class="flex justify-between"><span>Search</span><kbd class="font-mono text-xs text-muted-foreground">/</kbd></p>
              <p class="flex justify-between"><span>Devices</span><kbd class="font-mono text-xs text-muted-foreground">g d</kbd></p>
              <p class="flex justify-between"><span>Deployments</span><kbd class="font-mono text-xs text-muted-foreground">g p</kbd></p>
            </div>
          </div>
        </Dropdown>

        <!-- fleet status cluster: env badge + backend connection -->
        <div class="hidden shrink-0 items-center gap-2 lg:flex" aria-hidden="true">
          <span
            class="rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide"
            :class="envBadge === 'DEV' ? 'bg-warning-muted text-warning' : 'bg-success-muted text-success'"
          >
            {{ envBadge }}
          </span>
          <span class="flex items-center gap-1 text-[10px] text-muted-foreground" :title="backendUp ? 'Backend connected' : 'Backend unreachable'">
            <span class="h-1.5 w-1.5 rounded-full" :class="backendUp ? 'bg-success' : 'bg-danger'" />
            {{ backendUp ? 'Connected' : 'Offline' }}
          </span>
        </div>

        <Dropdown v-if="auth.user">
          <template #trigger>
            <button
              type="button"
              class="flex items-center gap-2 rounded-md p-1 pr-2 text-sm transition-colors hover:bg-surface-muted"
              aria-haspopup="menu"
            >
              <span
                class="flex h-7 w-7 items-center justify-center rounded-full bg-accent-muted text-xs font-semibold uppercase text-accent"
              >
                {{ initials }}
              </span>
              <span class="hidden max-w-40 truncate text-muted-foreground md:block">
                {{ auth.user.email }}
              </span>
              <ChevronsUpDown class="h-3.5 w-3.5 text-muted-foreground" />
            </button>
          </template>

          <div class="px-2 py-1.5">
            <p class="max-w-48 truncate text-sm font-medium">{{ auth.user.email }}</p>
            <p class="text-xs capitalize text-muted-foreground">{{ auth.user.role }}</p>
          </div>
          <div class="my-1 border-t border-border" />
          <DropdownMenuItem :icon="Radar" class="text-muted-foreground" @select="router.push({ name: 'audit-log' })">
            Audit log
          </DropdownMenuItem>
          <DropdownMenuItem :icon="LogOut" @select="handleLogout">Log out</DropdownMenuItem>
        </Dropdown>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
      <slot />
    </main>
  </div>
</template>