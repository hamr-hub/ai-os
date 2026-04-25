import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import './style.css'
import App from './App.vue'

const app = createApp(App)
const pinia = createPinia()

app.config.errorHandler = (err, instance, info) => {
  console.error('[Vue Error]', info, err)
}

app.config.warnHandler = (msg, instance, trace) => {
  console.warn('[Vue Warn]', msg, trace)
}

window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Promise]', event.reason)
  event.preventDefault()
})

app.use(pinia)
app.use(router)
app.mount('#app')
