<script setup lang="ts">
import type { Component } from 'vue'
import { cn } from '@/lib/utils'

withDefaults(
  defineProps<{
    icon?: Component
    destructive?: boolean
    class?: string
  }>(),
  { destructive: false },
)

const emit = defineEmits<{ select: [] }>()
</script>

<template>
  <button
    type="button"
    :class="
      cn(
        'flex w-full items-center gap-2 rounded-sm px-2 py-1.5 text-left text-sm transition-colors hover:bg-surface-muted',
        destructive ? 'text-danger' : 'text-foreground',
        $props.class,
      )
    "
    @click="emit('select')"
  >
    <component :is="icon" v-if="icon" class="h-4 w-4 shrink-0" />
    <slot />
  </button>
</template>