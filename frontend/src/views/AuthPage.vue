<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuth } from '@/composables/useAuth'
import { useAuthStore } from '@/stores/auth'
import {
  Shield,
  Loader2,
  AlertTriangle,
  LogOut,
  Key,
} from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()
const { isAuthenticated, loading, error, login, logout } = useAuth()

const apiKey = ref('')
const password = ref('')
const mode = ref<'apikey' | 'password'>('apikey')

const handleLogin = async () => {
  if (mode.value === 'apikey') {
    if (!apiKey.value) return
    const success = await login(apiKey.value)
    if (success) {
      authStore.setToken(apiKey.value)
      router.push({ name: 'dashboard' })
    }
  } else {
    if (!password.value) return
    const success = await login(password.value)
    if (success) {
      authStore.setToken(password.value)
      router.push({ name: 'dashboard' })
    }
  }
}

const handleLogout = () => {
  logout()
  authStore.clearToken()
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-container card-base">
      <div class="auth-header">
        <Shield class="w-8 h-8 text-primary" />
        <h1 class="digital-font">AI-OS Security</h1>
      </div>

      <div v-if="isAuthenticated" class="logged-in-section">
        <div class="user-info">
          <Key class="w-4 h-4" />
          <span>已登录: {{ authStore.user }}</span>
          <span class="token-hint">Token: {{ authStore.token.substring(0, 8) }}...</span>
        </div>
        <button class="btn btn-danger" @click="handleLogout">
          <LogOut class="w-4 h-4" /> 退出登录
        </button>
      </div>

      <div v-else class="login-section">
        <div v-if="error" class="error-banner">
          <AlertTriangle class="w-4 h-4" />
          {{ error }}
        </div>

        <div class="mode-switch">
          <button :class="['mode-btn', mode === 'apikey' ? 'active' : '']" @click="mode = 'apikey'">
            API Key 登录
          </button>
          <button :class="['mode-btn', mode === 'password' ? 'active' : '']" @click="mode = 'password'">
            密码登录
          </button>
        </div>

        <div v-if="mode === 'apikey'" class="form-group">
          <label class="form-label">API Key</label>
          <input v-model="apiKey" type="password" class="form-input" placeholder="输入 API Key" />
        </div>

        <div v-if="mode === 'password'" class="form-group">
          <label class="form-label">密码</label>
          <input v-model="password" type="password" class="form-input" placeholder="输入管理密码" />
        </div>

        <button class="btn btn-primary" :disabled="loading || (!apiKey && !password)" @click="handleLogin">
          <Loader2 v-if="loading" class="w-4 h-4 animate-spin" />
          <Shield v-else class="w-4 h-4" />
          {{ loading ? '验证中...' : '登录' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
}

.auth-container {
  width: 400px;
  max-width: 90vw;
}

.auth-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.auth-header h1 {
  font-size: 20px;
  color: var(--text-primary);
}

.logged-in-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-primary);
  padding: 12px;
  background: rgba(74, 222, 128, 0.1);
  border-radius: 8px;
}

.token-hint {
  font-size: 12px;
  color: var(--text-muted);
}

.login-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
}

.mode-switch {
  display: flex;
  gap: 8px;
}

.mode-btn {
  flex: 1;
  padding: 8px;
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn.active {
  background: var(--color-primary);
  color: white;
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.form-label {
  font-size: 14px;
  color: var(--text-muted);
}

.form-input {
  background: var(--bg-input);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 10px 12px;
  font-size: 14px;
}

.card-base {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 24px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  background: var(--color-primary-dark);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-danger {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.2);
}
</style>
