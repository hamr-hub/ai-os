<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useEngineManagement } from '@/composables/useEngineManagement'
import { useModelSwitch } from '@/composables/useModelSwitch'
import {
  Zap,
  RefreshCw,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Play,
  Square,
  Server,
  Settings,
  ArrowRight,
} from 'lucide-vue-next'
import type { EngineType } from '@/types'

const { engineStatus, engineConfig, switchSession, loading, switching, error, fetchStatus, fetchConfig, doSwitchEngine, doUpdateConfig } = useEngineManagement()
const { isSwitching, currentSession, triggerSwitch, triggerCancel, initSwitchMonitor } = useModelSwitch()

const targetModel = ref('')
const targetEngine: Ref<EngineType> = ref('vllm')
const targetPort = ref(8000)
const showSwitchConfirm = ref(false)
const activeTab = ref<'status' | 'switch' | 'config'>('status')

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchStatus()
  fetchConfig()
  pollTimer = setInterval(() => {
    fetchStatus()
  }, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
  triggerCancel()
})

const handleRefresh = () => {
  fetchStatus()
  fetchConfig()
}

const handleSwitch = async () => {
  if (!targetModel.value) return
  showSwitchConfirm.value = false
  const result = await doSwitchEngine(targetModel.value, targetEngine.value, targetPort.value)
  if (result?.session_id) {
    triggerSwitch(targetModel.value)
    activeTab.value = 'switch'
  }
}

const engineList = computed(() => {
  if (!engineStatus.value) return []
  return ['vllm', 'sglang', 'llama_cpp'] as EngineType[]
})

const formatUptime = (seconds: number | null) => {
  if (!seconds) return '--'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}

const engineDisplayName = (type: EngineType) => {
  const names: Record<EngineType, string> = {
    vllm: 'vLLM',
    sglang: 'SGLang',
    llama_cpp: 'llama.cpp',
  }
  return names[type] || type
}

const phaseLabel = (phase: number) => {
  const labels: Record<number, string> = {
    1: '停止旧引擎',
    2: '启动新引擎',
    3: '模型加载',
    4: '验证就绪',
  }
  return labels[phase] || `阶段 ${phase}`
}

const configJsonStr = computed(() => {
  if (!engineConfig.value) return ''
  return JSON.stringify(engineConfig.value, null, 2)
})

const editingConfig = ref(false)
const editedConfig = ref('')

const startEditConfig = () => {
  editedConfig.value = configJsonStr.value
  editingConfig.value = true
}

const saveConfig = async () => {
  try {
    const parsed = JSON.parse(editedConfig.value)
    await doUpdateConfig(parsed)
    editingConfig.value = false
  } catch {
    error.value = 'JSON格式错误'
  }
}
</script>

<template>
  <div class="engine-page">
    <div class="page-header">
      <div class="header-title">
        <Zap class="w-6 h-6 text-primary" />
        <h1 class="digital-font">Engine Management</h1>
      </div>
      <p class="header-subtitle">推理引擎管理 · 热切换 · 配置编辑</p>
      <button class="btn btn-ghost" @click="handleRefresh">
        <RefreshCw v-if="loading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" /> 刷新
      </button>
    </div>

    <div v-if="error" class="error-banner">
      <AlertTriangle class="w-4 h-4" />
      {{ error }}
    </div>

    <div class="tab-controls">
      <button :class="['tab-btn', activeTab === 'status' ? 'active' : '']" @click="activeTab = 'status'">
        <Server class="w-4 h-4" /> 状态概览
      </button>
      <button :class="['tab-btn', activeTab === 'switch' ? 'active' : '']" @click="activeTab = 'switch'">
        <ArrowRight class="w-4 h-4" /> 热切换
      </button>
      <button :class="['tab-btn', activeTab === 'config' ? 'active' : '']" @click="activeTab = 'config'">
        <Settings class="w-4 h-4" /> 配置编辑
      </button>
    </div>

    <div v-if="activeTab === 'status'" class="status-section">
      <div v-if="loading && !engineStatus" class="loading-state">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
        <p>加载中...</p>
      </div>
      <div v-else-if="!engineStatus" class="empty-state">
        <Server class="w-12 h-12 text-muted" />
        <p>无法获取引擎状态</p>
      </div>
      <div v-else class="engine-cards">
        <div v-for="eng in engineList" :key="eng" :class="['engine-card', engineStatus?.current_engine === eng ? 'current' : '']">
          <div class="engine-header">
            <span class="engine-name">{{ engineDisplayName(eng) }}</span>
            <span v-if="engineStatus?.current_engine === eng" class="current-badge">当前引擎</span>
          </div>
          <div class="engine-body">
            <div class="engine-field">
              <span class="field-label">状态</span>
              <span :class="['field-value', engineStatus?.[eng]?.running ? 'running' : 'stopped']">
                <CheckCircle v-if="engineStatus?.[eng]?.running" class="w-3.5 h-3.5" />
                <XCircle v-else class="w-3.5 h-3.5" />
                {{ engineStatus?.[eng]?.running ? '运行中' : '已停止' }}
              </span>
            </div>
            <div class="engine-field">
              <span class="field-label">PID</span>
              <span class="field-value">{{ engineStatus?.[eng]?.pid ?? '--' }}</span>
            </div>
            <div class="engine-field">
              <span class="field-label">端口</span>
              <span class="field-value">{{ engineStatus?.[eng]?.port ?? '--' }}</span>
            </div>
            <div class="engine-field">
              <span class="field-label">模型</span>
              <span class="field-value">{{ engineStatus?.[eng]?.model ?? '--' }}</span>
            </div>
            <div class="engine-field">
              <span class="field-label">运行时间</span>
              <span class="field-value">{{ formatUptime(engineStatus?.[eng]?.uptime) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'switch'" class="switch-section">
      <div class="switch-form card-base">
        <h3 class="section-title"><ArrowRight class="w-5 h-5" /> 引擎热切换</h3>
        <div class="form-row">
          <label class="form-label">目标模型</label>
          <input v-model="targetModel" class="form-input" placeholder="输入模型名称" />
        </div>
        <div class="form-row">
          <label class="form-label">目标引擎</label>
          <select v-model="targetEngine" class="form-input">
            <option value="vllm">vLLM</option>
            <option value="sglang">SGLang</option>
            <option value="llama_cpp">llama.cpp</option>
          </select>
        </div>
        <div class="form-row">
          <label class="form-label">端口</label>
          <input v-model.number="targetPort" type="number" class="form-input" />
        </div>
        <button class="btn btn-primary" :disabled="switching || !targetModel" @click="showSwitchConfirm = true">
          <Play v-if="!switching" class="w-4 h-4" />
          <Loader2 v-else class="w-4 h-4 animate-spin" />
          {{ switching ? '切换中...' : '执行切换' }}
        </button>
      </div>

      <div v-if="isSwitching || currentSession" class="switch-progress card-base">
        <h3 class="section-title"><RefreshCw class="w-5 h-5 animate-spin" /> 切换进度</h3>
        <div class="progress-phases">
          <div v-for="phase in [1, 2, 3, 4]" :key="phase" :class="['phase-item', currentSession?.overall_phase === `phase${phase}` ? 'active' : '', currentSession?.phases?.[phase - 1]?.status === 'success' ? 'done' : '', currentSession?.phases?.[phase - 1]?.status === 'failed' ? 'failed' : '']">
            <div class="phase-num">{{ phase }}</div>
            <div class="phase-info">
              <span class="phase-name">{{ phaseLabel(phase) }}</span>
              <span class="phase-status">{{ currentSession?.phases?.[phase - 1]?.status || 'pending' }}</span>
            </div>
            <div v-if="currentSession?.phases?.[phase - 1]?.status === 'running'" class="phase-progress-bar">
              <div class="progress-track"><div class="progress-fill" :style="{ width: (currentSession?.phases?.[phase - 1]?.progress || 0) + '%' }"></div></div>
            </div>
          </div>
        </div>
        <div class="overall-progress">
          <span>总进度: {{ currentSession?.overall_progress || 0 }}%</span>
          <span :class="['overall-phase', currentSession?.overall_phase]">{{ currentSession?.overall_phase }}</span>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'config'" class="config-section">
      <div v-if="!engineConfig" class="empty-state">
        <Settings class="w-12 h-12 text-muted" />
        <p>无法获取引擎配置</p>
      </div>
      <div v-else class="config-panel card-base">
        <h3 class="section-title"><Settings class="w-5 h-5" /> 引擎配置</h3>
        <div v-if="!editingConfig" class="config-display">
          <div v-for="(engConfig, engName) in engineConfig" :key="engName" class="config-block">
            <h4>{{ engineDisplayName(engName as EngineType) }}</h4>
            <div class="config-field">
              <span class="config-key">command</span>
              <span class="config-val">{{ engConfig.command }}</span>
            </div>
            <div class="config-params">
              <span class="config-key">default_params</span>
              <pre class="config-pre">{{ JSON.stringify(engConfig.default_params, null, 2) }}</pre>
            </div>
          </div>
          <button class="btn btn-primary" @click="startEditConfig">
            <Settings class="w-4 h-4" /> 编辑配置
          </button>
        </div>
        <div v-else class="config-editor">
          <textarea v-model="editedConfig" class="config-textarea" rows="20"></textarea>
          <div class="editor-actions">
            <button class="btn btn-primary" @click="saveConfig">保存</button>
            <button class="btn btn-ghost" @click="editingConfig = false">取消</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="showSwitchConfirm" class="confirm-modal">
      <div class="confirm-content tech-border">
        <h3>确认引擎切换</h3>
        <p>目标模型: {{ targetModel }}，引擎: {{ engineDisplayName(targetEngine) }}，端口: {{ targetPort }}</p>
        <p class="warn-text">切换过程中将停止当前服务，请确保无活跃请求</p>
        <div class="confirm-actions">
          <button class="btn btn-primary" @click="handleSwitch">确认切换</button>
          <button class="btn btn-ghost" @click="showSwitchConfirm = false">取消</button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.engine-page {
  padding: 24px;
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title h1 {
  font-size: 24px;
  color: var(--text-primary);
}

.header-subtitle {
  color: var(--text-muted);
  font-size: 14px;
  margin-left: auto;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.tab-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-muted);
}

.engine-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.engine-card {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 16px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  transition: all 0.2s;
}

.engine-card.current {
  border-color: var(--color-primary);
  box-shadow: 0 0 20px rgba(99, 102, 241, 0.15);
}

.engine-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.engine-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.current-badge {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--color-primary);
  color: white;
}

.engine-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.engine-field {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
}

.field-label {
  color: var(--text-muted);
}

.field-value {
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.field-value.running {
  color: #4ade80;
}

.field-value.stopped {
  color: var(--text-muted);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-size: 16px;
}

.card-base {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.switch-form .form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.form-label {
  font-size: 14px;
  color: var(--text-muted);
  min-width: 80px;
}

.form-input {
  background: var(--bg-input);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  flex: 1;
}

.progress-phases {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.phase-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--bg-secondary);
  transition: all 0.2s;
}

.phase-item.active {
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
}

.phase-item.done {
  background: rgba(74, 222, 128, 0.1);
}

.phase-item.failed {
  background: rgba(248, 113, 113, 0.1);
}

.phase-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
}

.phase-info {
  display: flex;
  flex-direction: column;
}

.phase-name {
  font-size: 14px;
  color: var(--text-primary);
}

.phase-status {
  font-size: 12px;
  color: var(--text-muted);
}

.phase-progress-bar {
  flex: 1;
  margin-left: auto;
}

.progress-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.1);
  border-radius: 2px;
}

.progress-fill {
  height: 4px;
  background: var(--color-primary);
  border-radius: 2px;
  transition: width 0.3s;
}

.overall-progress {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  font-size: 14px;
  color: var(--text-muted);
}

.overall-phase {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
}

.config-block {
  margin-bottom: 24px;
}

.config-block h4 {
  color: var(--text-primary);
  margin-bottom: 8px;
}

.config-field {
  display: flex;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 4px;
}

.config-key {
  color: var(--text-muted);
  min-width: 120px;
}

.config-val {
  color: var(--text-primary);
}

.config-pre {
  font-size: 12px;
  background: var(--bg-secondary);
  padding: 8px;
  border-radius: 8px;
  color: var(--text-primary);
  overflow-x: auto;
}

.config-textarea {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 12px;
  font-size: 13px;
  font-family: monospace;
  resize: vertical;
}

.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.confirm-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
}

.confirm-content {
  background: var(--bg-card);
  padding: 24px;
  border-radius: 12px;
  max-width: 400px;
}

.confirm-content h3 {
  color: var(--text-primary);
  margin-bottom: 12px;
}

.confirm-content p {
  color: var(--text-muted);
  margin-bottom: 8px;
  font-size: 14px;
}

.warn-text {
  color: #f59e0b;
}

.confirm-actions {
  display: flex;
  gap: 8px;
  margin-top: 16px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
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

.btn-ghost {
  background: transparent;
  color: var(--text-muted);
  border-color: rgba(255, 255, 255, 0.1);
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.2);
}

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
}

.tech-border {
  border: 1px solid rgba(99, 102, 241, 0.1);
}
</style>
