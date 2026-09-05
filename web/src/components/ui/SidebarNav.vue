<script setup lang="ts">
import type { Component } from 'vue'
import { cn } from '@/lib/utils'

export interface SidebarNavItem {
  value: string
  label: string
  icon?: Component
}

withDefaults(
  defineProps<{
    items: SidebarNavItem[]
    modelValue?: string
    label?: string
    class?: string
  }>(),
  { modelValue: '', label: '' },
)

const emit = defineEmits<{ 'update:modelValue': [string] }>()
</script>

<template>
  <nav :class="cn('flex flex-col gap-0.5', $props.class)" aria-label="Sidebar">
    <p
      v-if="label"
      class="mb-1 px-2 text-xs font-medium uppercase tracking-wider text-muted-foreground"
    >
      {{ label }}
    </p>
    <button
      v-for="item in items"
      :key="item.value"
      type="button"
      :class="
        cn(
          'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors',
          modelValue === item.value
            ? 'bg-accent-muted font-medium text-accent'
            : 'text-muted-foreground hover:bg-surface-muted hover:text-foreground',
        )
      "
      :aria-current="modelValue === item.value ? 'page' : undefined"
      @click="emit('update:modelValue', item.value)"
    >
      <component :is="item.icon" v-if="item.icon" class="h-4 w-4 shrink-0" />
      <span class="truncate">{{ item.label }}</span>
    </button>
  </nav>
</template>