import { ref } from 'vue'

export type Theme = 'light' | 'dark' | 'system'
export type Density = 'relaxed' | 'mid' | 'compact'

const THEME_KEY = 'hq.theme'
const DENSITY_KEY = 'hq.density'

const theme = ref<Theme>('system')
const density = ref<Density>('relaxed')

function resolveSystem(): boolean {
  return window.matchMedia('(prefers-color-scheme: dark)').matches
}

function applyTheme() {
  const dark = theme.value === 'dark' || (theme.value === 'system' && resolveSystem())
  document.documentElement.classList.toggle('dark', dark)
}

function applyDensity() {
  const root = document.documentElement
  root.classList.toggle('mid', density.value === 'mid')
  root.classList.toggle('compact', density.value === 'compact')
}

// Follow OS preference live when theme === system.
const media = window.matchMedia('(prefers-color-scheme: dark)')
media.addEventListener('change', () => {
  if (theme.value === 'system') applyTheme()
})

export function useSettings() {
  function setTheme(value: Theme) {
    theme.value = value
    localStorage.setItem(THEME_KEY, value)
    applyTheme()
  }

  function setDensity(value: Density) {
    density.value = value
    localStorage.setItem(DENSITY_KEY, value)
    applyDensity()
  }

  return { theme, density, setTheme, setDensity }
}

/** Called once from main.ts before mounting. */
export function applySavedSettings(): void {
  try {
    const t = localStorage.getItem(THEME_KEY) as Theme | null
    if (t === 'light' || t === 'dark' || t === 'system') theme.value = t
    const d = localStorage.getItem(DENSITY_KEY) as Density | null
    if (d === 'relaxed' || d === 'mid' || d === 'compact') density.value = d
  } catch {
    /* private mode etc. -- defaults are fine */
  }
  applyTheme()
  applyDensity()
}