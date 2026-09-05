<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { ChevronsUpDown, LogOut, Satellite } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { cn } from '@/lib/utils'
import Dropdown from '@/components/ui/Dropdown.vue'
import DropdownMenuItem from '@/components/ui/DropdownMenuItem.vue'

const auth = useAuthStore()
const route = useRoute()
const router = useRouter()

const navLinks = computed(() => {
  const links = [
    {
      to: { name: 'devices' },
      label: 'Devices',
      active: route.name === 'devices' || route.name === 'device-detail',
    },
    {
      to: { name: 'alarm-rules' },
      label: 'Alarm Rules',
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
</script>

<template>
  <div class="flex min-h-screen flex-col">
    <header class="sticky top-0 z-40 h-14 border-b border-border bg-surface">
      <div class="mx-auto flex h-full max-w-6xl items-center gap-4 px-4 sm:px-6">
        <RouterLink to="/" class="flex shrink-0 items-center gap-2 text-sm font-semibold tracking-tight">
          <span
            class="flex h-6 w-6 items-center justify-center rounded-md bg-accent text-accent-foreground"
          >
            <Satellite class="h-3.5 w-3.5" />
          </span>
          <span class="hidden sm:block">Arches-HQ</span>
        </RouterLink>

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
          <DropdownMenuItem :icon="LogOut" @select="handleLogout">Log out</DropdownMenuItem>
        </Dropdown>
      </div>
    </header>

    <main class="mx-auto w-full max-w-6xl flex-1 px-4 py-6 sm:px-6">
      <slot />
    </main>
  </div>
</template>