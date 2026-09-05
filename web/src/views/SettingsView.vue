<script setup lang="ts">
import { Monitor, Moon, Sun, UserRound } from 'lucide-vue-next'
import { useAuthStore } from '@/stores/auth'
import { useSettings, type Density, type Theme } from '@/lib/useSettings'
import Badge from '@/components/ui/Badge.vue'
import Card from '@/components/ui/Card.vue'

const auth = useAuthStore()
const { theme, density, setTheme, setDensity } = useSettings()

const themes: { value: Theme; label: string; icon: typeof Sun; hint: string }[] = [
  { value: 'light', label: 'Light', icon: Sun, hint: 'Bright surfaces' },
  { value: 'dark', label: 'Dark', icon: Moon, hint: 'Low-glare surfaces' },
  { value: 'system', label: 'System', icon: Monitor, hint: 'Follow your OS' },
]

const densities: { value: Density; label: string; hint: string }[] = [
  { value: 'relaxed', label: 'Relaxed', hint: 'Airy spacing (16px base)' },
  { value: 'mid', label: 'Mid', hint: 'Balanced (15px base)' },
  { value: 'compact', label: 'Compact', hint: 'Densest (14px base)' },
]

const identity = [
  { label: 'Email', value: () => auth.user?.email ?? '—' },
  { label: 'Role', value: () => auth.user?.role ?? '—' },
  { label: 'User ID', value: () => auth.user?.id ?? '—' },
]

const adminLinks = [
  { to: { name: 'users' }, label: 'User management', hint: 'Invite teammates, manage roles' },
  { to: { name: 'audit-log' }, label: 'Audit log', hint: 'Every privileged action, who and when' },
]
</script>

<template>
  <div class="mx-auto max-w-3xl">
    <div class="mb-6">
      <h1 class="text-xl font-semibold">Settings</h1>
      <p class="text-sm text-muted-foreground">Console appearance, your profile and workspace links.</p>
    </div>

    <div class="space-y-4">
      <!-- profile -->
      <Card class="p-4">
        <h3 class="flex items-center gap-2 text-sm font-semibold">
          <UserRound class="h-4 w-4 text-muted-foreground" /> Profile
        </h3>
        <dl class="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div v-for="f in identity" :key="f.label">
            <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
              {{ f.label }}
            </dt>
            <dd class="mt-0.5 truncate font-mono text-xs">
              {{ f.value() }}
              <Badge v-if="f.label === 'Role'" tone="accent" class="ml-1 capitalize font-sans">
                {{ auth.user?.role }}
              </Badge>
            </dd>
          </div>
        </dl>
      </Card>

      <!-- appearance -->
      <Card class="p-4">
        <h3 class="text-sm font-semibold">Appearance</h3>

        <p class="mt-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">Theme</p>
        <div class="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <button
            v-for="t in themes"
            :key="t.value"
            type="button"
            class="flex items-start gap-3 rounded-md border p-3 text-left transition-colors"
            :class="
              theme === t.value ? 'border-accent bg-accent-muted' : 'border-border hover:bg-surface-muted'
            "
            @click="setTheme(t.value)"
          >
            <component
              :is="t.icon"
              class="mt-0.5 h-4 w-4 shrink-0"
              :class="theme === t.value ? 'text-accent' : 'text-muted-foreground'"
            />
            <span>
              <span class="block text-sm font-medium">{{ t.label }}</span>
              <span class="block text-xs text-muted-foreground">{{ t.hint }}</span>
            </span>
          </button>
        </div>

        <p class="mt-4 text-xs font-medium uppercase tracking-wide text-muted-foreground">Density</p>
        <div class="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-3">
          <button
            v-for="d in densities"
            :key="d.value"
            type="button"
            class="flex items-start gap-3 rounded-md border p-3 text-left transition-colors"
            :class="
              density === d.value ? 'border-accent bg-accent-muted' : 'border-border hover:bg-surface-muted'
            "
            @click="setDensity(d.value)"
          >
            <span>
              <span class="block text-sm font-medium">{{ d.label }}</span>
              <span class="block text-xs text-muted-foreground">{{ d.hint }}</span>
            </span>
          </button>
        </div>
      </Card>

      <!-- workspace (admin) -->
      <Card v-if="auth.hasRole('admin')" class="p-4">
        <h3 class="text-sm font-semibold">Workspace</h3>
        <p class="mt-1 text-sm text-muted-foreground">Tenant-wide administration.</p>
        <ul class="mt-3 divide-y divide-border">
          <li v-for="l in adminLinks" :key="l.label">
            <RouterLink :to="l.to" class="flex items-center justify-between gap-3 py-2 text-sm hover:text-accent">
              <span class="min-w-0">
                <span class="block font-medium">{{ l.label }}</span>
                <span class="block text-xs text-muted-foreground">{{ l.hint }}</span>
              </span>
              <span aria-hidden="true">→</span>
            </RouterLink>
          </li>
        </ul>
      </Card>

      <!-- about -->
      <Card class="p-4">
        <h3 class="text-sm font-semibold">About</h3>
        <dl class="mt-3 grid grid-cols-1 gap-x-6 gap-y-3 text-sm sm:grid-cols-3">
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Version</dt>
            <dd class="mt-0.5 font-mono text-xs">0.1.0-dev</dd>
          </div>
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Storage</dt>
            <dd class="mt-0.5 font-mono text-xs">SQLite · storage/</dd>
          </div>
          <div>
            <dt class="text-xs font-medium uppercase tracking-wide text-muted-foreground">Roadmap</dt>
            <dd class="mt-0.5 font-mono text-xs">future_feature.md</dd>
          </div>
        </dl>
      </Card>
    </div>
  </div>
</template>