import { onMounted, ref } from 'vue'
import { api } from '@/lib/api'
import type { ConfigSection } from '@/lib/types'

/**
 * Shared load/save state for device config sections: the desired
 * configuration HQ holds and delivers to the device via ApplyConfig
 * commands. `dirty` tracks unsaved edits; `savedAt` the last apply.
 */
export function useDeviceConfig(deviceId: string, section: ConfigSection) {
  const config = ref<Record<string, unknown>>({})
  const loading = ref(true)
  const saving = ref(false)
  const error = ref('')
  const savedAt = ref<string | null>(null)
  const dirty = ref(false)

  function set<K extends string>(key: K, value: unknown) {
    config.value = { ...config.value, [key]: value }
    dirty.value = true
  }

  async function load() {
    loading.value = true
    error.value = ''
    try {
      const res = await api.devices.getConfig(deviceId, section)
      config.value = res.config
      savedAt.value = res.updated_at
      dirty.value = false
    } catch {
      error.value = 'Could not load configuration.'
    } finally {
      loading.value = false
    }
  }

  async function save() {
    saving.value = true
    error.value = ''
    try {
      const res = await api.devices.putConfig(deviceId, section, config.value)
      config.value = res.config
      savedAt.value = res.updated_at
      dirty.value = false
      return true
    } catch {
      error.value = 'Could not save configuration.'
      return false
    } finally {
      saving.value = false
    }
  }

  onMounted(load)

  return { config, loading, saving, error, savedAt, dirty, set, load, save }
}