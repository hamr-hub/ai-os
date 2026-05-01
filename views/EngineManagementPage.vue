<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, type Ref } from 'vue'
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
  Server,
  Settings,
  ArrowRight,
  SlidersHorizontal,
} from 'lucide-vue-next'
import type { EngineType } from '@/types'
import EngineParamEditor from '@/components/EngineParamEditor.vue'

const { engineStatus, engineConfig, loading, switching, error, fetchStatus, fetchConfig, doSwitchEngine, doUpdateConfig } = useEngineManagement()
const { isSwitching, currentSession, triggerSwitch, triggerCancel } = useModelSwitch()

const targetModel = ref('')
const targetEngine: Ref<EngineType> = ref('vllm')
const targetPort = ref(8000)
const showSwitchConfirm = ref(false)
const activeTab = ref<'status' | 'switch' | 'config' | 'params'>('status')

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
    triggerSwitch(targetModel.value, false, 'switch')
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
  <div class="engine-page fade-in">
    <div class="page-header">
      <div class="header-title">
        <div class="icon-box gradient-primary">
          <Zap class="w-5 h-5" />
        </div>
        <h1 class="digital-font">Engine Management</h1>
      </div>
      <p class="header-subtitle">推理引擎管理 · 热切换 · 配置编辑</p>
      <button class="btn btn-secondary" @click="handleRefresh">
        <RefreshCw v-if="loading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" /> 刷新
      </button>
    </div>

    <div v-if="error" class="error-banner toast-error">
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
      <button :class="['tab-btn', activeTab === 'params' ? 'active' : '']" @click="activeTab = 'params'">
        <SlidersHorizontal class="w-4 h-4" /> 参数定制
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
        <div v-for="eng in engineList" :key="eng" :class="['engine-card card-base card-hover', engineStatus?.current_engine === eng ? 'current card-glow-primary' : '']" >
          <div class="engine-header">
            <div class="engine-name-row">
              <span :class="['status-dot', engineStatus?.[eng]?.running ? 'online' : 'offline']"></span>
              <span class="engine-name">{{ engineDisplayName(eng) }}</span>
            </div>
            <span v-if="engineStatus?.current_engine === eng" class="current-badge tag tag-purple">当前引擎</span>
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
              <span class="field-value mono">{{ engineStatus?.[eng]?.pid ?? '--' }}</span>
            </div>
            <div class="engine-field">
              <span class="field-label">端口</span>
              <span class="field-value mono">{{ engineStatus?.[eng]?.port ?? '--' }}</span>
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

    <div v-if="activeTab === 'switch'" class="switch-section fade-in">
      <div class="switch-form card-base tech-border">
        <h3 class="section-title"><ArrowRight class="w-5 h-5 text-primary" /> 引擎热切换</h3>
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

      <div v-if="isSwitching || currentSession" class="switch-progress card-base tech-border">
        <h3 class="section-title"><RefreshCw class="w-5 h-5 animate-spin text-primary" /> 切换进度</h3>
        <div class="progress-phases">
          <div v-for="phase in [1, 2, 3, 4]" :key="phase" :class="['phase-item', currentSession?.overall_phase === `phase${phase}` ? 'active' : '', currentSession?.phases?.[phase - 1]?.status === 'success' ? 'done' : '', currentSession?.phases?.[phase - 1]?.status === 'failed' ? 'failed' : '']">
            <div :class="['phase-num', currentSession?.phases?.[phase - 1]?.status === 'success' ? 'gradient-green' : 'gradient-primary']">{{ phase }}</div>
            <div class="phase-info">
              <span class="phase-name">{{ phaseLabel(phase) }}</span>
              <span class="phase-status">{{ currentSession?.phases?.[phase - 1]?.status || 'pending' }}</span>
            </div>
            <div v-if="currentSession?.phases?.[phase - 1]?.status === 'running'" class="phase-progress-bar">
              <div class="progress-track"><div class="progress-fill indigo" :style="{ width: (currentSession?.phases?.[phase - 1]?.progress || 0) + '%' }"></div></div>
            </div>
          </div>
        </div>
        <div class="overall-progress">
          <span>总进度: {{ currentSession?.overall_progress || 0 }}%</span>
          <span :class="['overall-phase tag', currentSession?.overall_phase ? 'tag-blue' : 'tag-cyan']">{{ currentSession?.overall_phase }}</span>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'config'" class="config-section fade-in">
      <div v-if="!engineConfig" class="empty-state">
        <Settings class="w-12 h-12 text-muted" />
        <p>无法获取引擎配置</p>
      </div>
      <div v-else class="config-panel card-base tech-border">
        <h3 class="section-title"><Settings class="w-5 h-5 text-primary" /> 引擎配置</h3>
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
            <button class="btn btn-secondary" @click="editingConfig = false">取消</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'params'" class="params-section fade-in">
      <div v-if="!targetModel" class="empty-state">
        <SlidersHorizontal class="w-12 h-12 text-muted" />
        <p>请先在"热切换"面板选择目标模型，或输入模型名称</p>
        <div class="param-model-input">
          <label class="form-label">模型名称</label>
          <input v-model="targetModel" class="form-input" placeholder="输入模型名称" />
        </div>
      </div>
      <div v-else>
        <div class="param-engine-select">
          <label class="form-label">目标引擎</label>
          <select v-model="targetEngine" class="form-input">
            <option value="vllm">vLLM</option>
            <option value="sglang">SGLang</option>
            <option value="llama_cpp">llama.cpp</option>
          </select>
        </div>
        <EngineParamEditor
          :model-name="targetModel"
          :engine-type="targetEngine"
          @saved="() => { fetchStatus(); fetchConfig() }"
          @error="(msg) => { error = msg }"
        />
      </div>
    </div>

    <div v-if="showSwitchConfirm" class="confirm-modal">
      <div class="confirm-content glass-card tech-border">
        <h3 class="digital-font">确认引擎切换</h3>
        <p>目标模型: {{ targetModel }}，引擎: {{ engineDisplayName(targetEngine) }}，端口: {{ targetPort }}</p>
        <p class="warn-text">切换过程中将停止当前服务，请确保无活跃请求</p>
        <div class="confirm-actions">
          <button class="btn btn-primary" @click="handleSwitch">确认切换</button>
          <button class="btn btn-secondary" @click="showSwitchConfirm = false">取消</button>
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
  margin-bottom: 28px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.icon-box {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.3);
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
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.tab-controls {
  display: flex;
  gap: 6px;
  margin-bottom: 24px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 14px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.tab-btn.active {
  background: linear-gradient(135deg, rgba(var(--color-primary-rgb), 0.15) 0%, rgba(var(--color-primary-rgb), 0.08) 100%);
  color: var(--color-primary-light);
  border-color: rgba(var(--color-primary-rgb), 0.3);
  box-shadow: 0 0 12px rgba(var(--color-primary-rgb), 0.1);
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
  padding: 20px;
  animation: scale-in 0.3s ease-out both;
}

.engine-card.current {
  border-color: rgba(var(--color-primary-rgb), 0.3);
}

.engine-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 14px;
}

.engine-name-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.engine-name {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
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
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
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

.field-value.mono {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-size: 16px;
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
  border: 1px solid var(--border-primary);
  color: var(--text-primary);
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 14px;
  flex: 1;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.1);
}

.progress-phases {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.phase-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 14px;
  border-radius: 10px;
  background: var(--bg-secondary);
  transition: all 0.3s ease;
  border: 1px solid transparent;
}

.phase-item.active {
  background: rgba(var(--color-primary-rgb), 0.08);
  border-color: rgba(var(--color-primary-rgb), 0.2);
}

.phase-item.done {
  background: rgba(34, 197, 94, 0.08);
  border-color: rgba(34, 197, 94, 0.15);
}

.phase-item.failed {
  background: rgba(239, 68, 68, 0.08);
  border-color: rgba(239, 68, 68, 0.15);
}

.phase-num {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
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

.overall-progress {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: 16px;
  font-size: 14px;
  color: var(--text-muted);
}

.config-block {
  margin-bottom: 24px;
}

.config-block h4 {
  color: var(--text-primary);
  margin-bottom: 10px;
  font-size: 15px;
}

.config-field {
  display: flex;
  gap: 8px;
  font-size: 13px;
  margin-bottom: 6px;
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
  padding: 10px;
  border-radius: 10px;
  color: var(--text-primary);
  overflow-x: auto;
  border: 1px solid var(--border-primary);
}

.config-textarea {
  width: 100%;
  background: var(--bg-input);
  border: 1px solid var(--border-primary);
  color: var(--text-primary);
  border-radius: 10px;
  padding: 14px;
  font-size: 13px;
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
  resize: vertical;
}

.config-textarea:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.1);
}

.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
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

.btn-danger:hover {
  background: rgba(239, 68, 68, 0.2);
}

.params-section {
  margin-top: 16px;
}

.param-model-input {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 16px;
}

.param-engine-select {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.confirm-modal {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 999;
  animation: fade-in 0.2s ease-out;
}

.confirm-content {
  padding: 28px;
  max-width: 420px;
  animation: scale-in 0.25s ease-out;
}

.confirm-content h3 {
  color: var(--text-primary);
  margin-bottom: 14px;
  font-size: 18px;
}

.confirm-content p {
  color: var(--text-secondary);
  margin-bottom: 8px;
  font-size: 14px;
}

.warn-text {
  color: #fbbf24;
}

.confirm-actions {
  display: flex;
  gap: 8px;
  margin-top: 18px;
}
</style>
