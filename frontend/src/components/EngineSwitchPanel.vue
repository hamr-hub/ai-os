<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getEngineStatus, switchEngine } from '@/api/client'
import type { EngineType, EngineStatus } from '@/types'
import {
  Zap,
  Loader2,
  CheckCircle,
  XCircle,
  Server,
  AlertTriangle,
} from 'lucide-vue-next'

const engineStatus = ref<EngineStatus | null>(null)
const switching = ref(false)
const error = ref<string | null>(null)
const switchError = ref<string | null>(null)

const engineOptions: { key: EngineType; label: string; icon: string }[] = [
  { key: 'vllm', label: 'vLLM', icon: '⚡' },
  { key: 'sglang', label: 'SGLang', icon: '🔥' },
  { key: 'llamacpp', label: 'llama.cpp', icon: '🦙' },
]

const currentEngine = computed(() => engineStatus.value?.current_engine ?? 'vllm')

const engineRunningInfo = computed(() => {
  if (!engineStatus.value) return null
  const info = engineStatus.value[currentEngine.value as EngineType]
  if (!info) return null
  return {
    running: info.running,
    pid: info.pid,
    port: info.port,
    model: info.model,
    uptime: info.uptime,
  }
})

async function fetchStatus() {
  try {
    engineStatus.value = await getEngineStatus()
    error.value = null
  } catch (e: any) {
    error.value = e.message || '获取引擎状态失败'
  }
}

async function handleSwitch(target: EngineType) {
  if (switching.value || target === currentEngine.value) return
  switching.value = true
  switchError.value = null
  try {
    const result = await switchEngine(target)
    if (result.status === 'success' || result.status === 'switching') {
      await fetchStatus()
    } else {
      switchError.value = result.message || '引擎切换失败'
    }
  } catch (e: any) {
    switchError.value = e.message || '引擎切换请求失败'
  } finally {
    switching.value = false
  }
}

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchStatus()
  pollTimer = setInterval(fetchStatus, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="engine-switch-panel">
    <div class="panel-header">
      <Zap class="w-4 h-4 panel-icon" />
      <span class="panel-title">推理引擎</span>
      <span v-if="switching" class="switching-badge">
        <Loader2 class="w-3 h-3 animate-spin" /> 切换中
      </span>
    </div>

    <div v-if="error && !engineStatus" class="panel-error">
      <AlertTriangle class="w-4 h-4" />
      <span>{{ error }}</span>
      <button class="retry-btn" @click="fetchStatus">重试</button>
    </div>

    <div v-if="engineStatus" class="engine-list">
      <div
        v-for="opt in engineOptions"
        :key="opt.key"
        class="engine-item"
        :class="{
          active: opt.key === currentEngine,
          running: engineStatus[opt.key]?.running,
        }"
        @click="handleSwitch(opt.key)"
      >
        <div class="engine-indicator">
          <span class="engine-emoji">{{ opt.icon }}</span>
          <span
            v-if="engineStatus[opt.key]?.running"
            class="running-dot"
            :class="{ pulse: opt.key === currentEngine }"
          ></span>
        </div>
        <div class="engine-info">
          <span class="engine-label">{{ opt.label }}</span>
          <span v-if="opt.key === currentEngine" class="current-tag">当前</span>
          <div v-if="engineStatus[opt.key]?.running" class="engine-detail">
            PID {{ engineStatus[opt.key]?.pid ?? '--' }} · 端口 {{ engineStatus[opt.key]?.port ?? '--' }}
            <span v-if="engineStatus[opt.key]?.model" class="engine-model">
              {{ engineStatus[opt.key]?.model }}
            </span>
          </div>
          <div v-if="!engineStatus[opt.key]?.running && opt.key !== currentEngine" class="engine-detail offline">
            未运行
          </div>
        </div>
        <div class="engine-action">
          <CheckCircle v-if="opt.key === currentEngine" class="w-4 h-4 check-icon" />
          <Loader2 v-else-if="switching" class="w-3.5 h-3.5 animate-spin" />
          <span v-else class="switch-arrow">→</span>
        </div>
      </div>
    </div>

    <div v-if="switchError" class="switch-error">
      <XCircle class="w-4 h-4" />
      <span>{{ switchError }}</span>
    </div>

    <div v-if="engineRunningInfo" class="current-info-bar">
      <Server class="w-3.5 h-3.5" />
      <span>
        {{ currentEngine.toUpperCase() }} 运行中
        <template v-if="engineRunningInfo.model">· {{ engineRunningInfo.model }}</template>
        <template v-if="engineRunningInfo.port">· {{ engineRunningInfo.port }} 端口</template>
      </span>
      <span v-if="engineRunningInfo.uptime" class="uptime">
        {{ Math.floor(engineRunningInfo.uptime / 60) }}分钟
      </span>
    </div>
  </div>
</template>

<style scoped>
.engine-switch-panel {
  background: var(--bg-card);
  border: 1px solid var(--border-primary);
  border-radius: 12px;
  padding: 16px;
}

.panel-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.panel-icon {
  color: var(--accent-primary);
}

.panel-title {
  font-weight: 700;
  font-size: 14px;
  font-family: var(--font-digital, monospace);
}

.switching-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
  font-size: 12px;
}

.panel-error {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  font-size: 13px;
}

.retry-btn {
  padding: 2px 8px;
  border-radius: 4px;
  border: 1px solid #ef4444;
  color: #ef4444;
  font-size: 12px;
  cursor: pointer;
}

.engine-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.engine-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: var(--bg-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.engine-item:hover:not(.active) {
  border-color: var(--accent-primary);
  background: rgba(99, 102, 241, 0.05);
}

.engine-item.active {
  border-color: var(--accent-primary);
  background: rgba(99, 102, 241, 0.08);
}

.engine-item.running {
  border-left: 3px solid #22c55e;
}

.engine-indicator {
  position: relative;
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.engine-emoji {
  font-size: 16px;
}

.running-dot {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #22c55e;
}

.running-dot.pulse {
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(0.8); }
  100% { opacity: 1; transform: scale(1); }
}

.engine-info {
  flex: 1;
  min-width: 0;
}

.engine-label {
  font-weight: 600;
  font-size: 13px;
}

.current-tag {
  margin-left: 6px;
  padding: 1px 6px;
  border-radius: 3px;
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
  font-size: 11px;
  font-weight: 500;
}

.engine-detail {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 2px;
}

.engine-detail.offline {
  color: var(--text-secondary);
  opacity: 0.6;
}

.engine-model {
  color: var(--accent-primary);
}

.engine-action {
  width: 20px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.check-icon {
  color: #22c55e;
}

.switch-arrow {
  color: var(--text-secondary);
  opacity: 0.5;
}

.switch-error {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 8px;
  padding: 6px 10px;
  border-radius: 6px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  font-size: 12px;
}

.current-info-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-top: 10px;
  padding: 8px 12px;
  border-radius: 8px;
  background: rgba(34, 197, 94, 0.08);
  border: 1px solid rgba(34, 197, 94, 0.2);
  font-size: 13px;
  color: #22c55e;
}

.uptime {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
