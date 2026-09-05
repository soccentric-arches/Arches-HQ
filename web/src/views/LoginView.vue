<script setup lang="ts">
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import Button from '@/components/ui/Button.vue'
import Card from '@/components/ui/Card.vue'
import Input from '@/components/ui/Input.vue'

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()

const email = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function handleLogin() {
  if (!email.value || !password.value) {
    error.value = 'Enter your email and password.'
    return
  }
  loading.value = true
  error.value = ''
  try {
    await auth.login(email.value.trim(), password.value)
    router.replace((route.query.redirect as string) || '/')
  } catch {
    error.value = 'Invalid email or password.'
    loading.value = false
  }
}
</script>

<template>
  <div class="flex min-h-screen items-center justify-center bg-surface-muted px-4">
    <Card class="w-full max-w-sm p-8">
      <h1 class="text-lg font-semibold">Arches-HQ</h1>
      <p class="mt-1 text-sm text-muted-foreground">Sign in to manage your device fleet.</p>
      <form class="mt-6 space-y-4" @submit.prevent="handleLogin">
        <label class="block">
          <span class="text-sm text-muted-foreground">Email</span>
          <Input
            v-model="email"
            type="email"
            name="email"
            autocomplete="username"
            placeholder="you@example.com"
            class="mt-1 w-full"
          />
        </label>
        <label class="block">
          <span class="text-sm text-muted-foreground">Password</span>
          <Input
            v-model="password"
            type="password"
            name="password"
            autocomplete="current-password"
            placeholder="••••••••"
            class="mt-1 w-full"
          />
        </label>
        <Button type="submit" class="w-full" :disabled="loading">
          {{ loading ? 'Signing in…' : 'Sign in' }}
        </Button>
        <p v-if="error" class="text-sm text-danger">{{ error }}</p>
      </form>
    </Card>
  </div>
</template>