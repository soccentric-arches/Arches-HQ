import './assets/main.css'

import { createApp } from 'vue'
import { createPinia } from 'pinia'

import App from './App.vue'
import router from './router'
import { applySavedSettings } from './lib/useSettings'

// Apply the saved theme/density before mounting to avoid a flash of the
// wrong appearance (index.html also sets it early for the initial paint).
applySavedSettings()

const app = createApp(App)

app.use(createPinia())
app.use(router)

app.mount('#app')