<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useGPU } from '@/composables/useGPU'
import { useModels } from '@/composables/useModels'
import { getGPUEnhancedInfo, getGPUProcesses, getVLLMMetrics, switchModel as apiSwitchModel, startModel as apiStartModel, stopModel as apiStopModel } from '@/api/client'
import { RefreshCw, Cpu, Thermometer, Zap, Activity, MemoryStick, Server, Play, Square, ArrowRightLeft, Fan, Gauge, HardDrive, AlertTriangle } from 'lucide-vue-next'

const { gpuSummary, loading: gpuLoading, refresh: refreshGPU } = useGPU()
const { modelList, actionLoading, refresh: refreshModels } = useModels()

const enhancedInfo = ref<any>(null)
const gpuProcesses = ref<any[]>([])
const vllmMetrics = ref<any>(null)
const polling = ref(false)
let pollTimer: number | null = null

const gpu = computed(() => gpuSummary.value?.current ?? null)
const gpuStatus = computed(() => gpuSummary.value?.status ?? 'unavailable')
const healthScore = computed(() => {
  if (gpu.value?.utilization !== undefined && gpu.value?.utilization !== null) {
    return Math.max(0, 100 - gpu.value.utilization)
  }
  return 0
})

const runningModels = computed(() =>
  modelList.value.filter((m: any) => m.running)
)

const stoppedModels = computed(() =>
  modelList.value.filter((m: any) => !m.running)
)

const getHealthColor = (score: number) => {
  if (score >= 80) return 'text-green-400'
  if (score >= 60) return 'text-yellow-400'
  return 'text-red-400'
}

const getHealthBg = (score: number) => {
  if (score >= 80) return 'bg-green-500'
  if (score >= 60) return 'bg-yellow-500'
  return 'bg-red-500'
}

const formatMemory = (bytes: number) => {
  if (!bytes) return '--'
  if (bytes >= 1024 * 1024 * 1024) {
    return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`
  }
  if (bytes >= 1024 * 1024) {
    return `${(bytes / (1024 * 1024)).toFixed(0)} MB`
  }
  return `${(bytes / 1024).toFixed(0)} KB`
}

const fetchEnhancedInfo = async () => {
  try {
    enhancedInfo.value = await getGPUEnhancedInfo()
  } catch {
    // silent
  }
}

const fetchProcesses = async () => {
  try {
    const res = await getGPUProcesses()
    gpuProcesses.value = res.processes
  } catch {
    // silent
  }
}

const fetchVLLMMetrics = async () => {
  try {
    vllmMetrics.value = await getVLLMMetrics()
  } catch {
    // silent
  }
}

const refreshAll = async () => {
  await Promise.all([
    refreshGPU(),
    fetchEnhancedInfo(),
    fetchProcesses(),
    fetchVLLMMetrics(),
    refreshModels(),
  ])
}

const togglePolling = () => {
  polling.value = !polling.value
  if (polling.value) {
    refreshAll()
    pollTimer = window.setInterval(refreshAll, 3000)
  } else {
    if (pollTimer) {
      clearInterval(pollTimer)
      pollTimer = null
    }
  }
}

const handleSwitchModel = async (modelName: string) => {
  try {
    await apiSwitchModel(modelName)
    await refreshAll()
  } catch {
    // handled by global error
  }
}

const handleStartModel = async (modelName: string) => {
  try {
    await apiStartModel(modelName)
    await refreshAll()
  } catch {
    // handled by global error
  }
}

const handleStopModel = async (modelName: string) => {
  try {
    await apiStopModel(modelName)
    await refreshAll()
  } catch {
    // handled by global error
  }
}

onMounted(() => {
  refreshAll()
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<template>
  <div class="gpu-manage-page">
    <!-- Header -->
    <div class="page-header">
      <div class="header-left">
        <Cpu class="w-6 h-6 text-primary" />
        <h1 class="page-title">GPU 管理</h1>
      </div>
      <div class="header-right">
        <button
          class="btn btn-secondary"
          :class="{ 'animate-pulse': polling }"
          @click="togglePolling"
        >
          <Activity class="w-4 h-4" />
          {{ polling ? '轮询中' : '开启轮询' }}
        </button>
        <button class="btn btn-primary" :disabled="gpuLoading" @click="refreshAll">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': gpuLoading }" />
          刷新
        </button>
      </div>
    </div>

    <!-- GPU Status Overview -->
    <div v-if="gpuStatus === 'unavailable'" class="gpu-unavailable">
      <AlertTriangle class="w-12 h-12 text-yellow-400 mb-4" />
      <h2>GPU 不可用</h2>
      <p class="text-muted">未检测到 GPU 设备</p>
    </div>

    <template v-else>
      <!-- GPU Info Cards -->
      <div class="info-grid">
        <!-- Main GPU Card -->
        <div class="card gpu-main-card">
          <div class="card-header">
            <Cpu class="w-5 h-5 text-primary" />
            <span class="card-title">{{ gpu?.name ?? 'Unknown GPU' }}</span>
            <span class="badge">{{ gpu?.gpu_count }}x GPU</span>
          </div>
          <div class="metrics-grid">
            <div class="metric-item">
              <div class="metric-icon">
                <Gauge class="w-5 h-5 text-primary" />
              </div>
              <div class="metric-content">
                <div class="metric-label">GPU 使用率</div>
                <div class="metric-value" :class="getHealthColor(100 - (gpu?.utilization ?? 0))">
                  {{ gpu?.utilization ?? '--' }}%
                </div>
                <div class="progress-bar">
                  <div
                    class="progress-fill"
                    :class="getHealthBg(100 - (gpu?.utilization ?? 0))"
                    :style="{ width: (gpu?.utilization ?? 0) + '%' }"
                  ></div>
                </div>
              </div>
            </div>

            <div class="metric-item">
              <div class="metric-icon">
                <MemoryStick class="w-5 h-5 text-blue-400" />
              </div>
              <div class="metric-content">
                <div class="metric-label">显存使用</div>
                <div class="metric-value">{{ formatMemory(gpu?.used_memory ?? 0) }}</div>
                <div class="metric-subtext">
                  / {{ formatMemory(gpu?.total_memory ?? 0) }}
                  ({{ gpu?.memory_utilization ?? '--' }}%)
                </div>
                <div class="progress-bar">
                  <div
                    class="progress-fill bg-blue-500"
                    :style="{ width: (gpu?.memory_utilization ?? 0) + '%' }"
                  ></div>
                </div>
              </div>
            </div>

            <div class="metric-item">
              <div class="metric-icon">
                <Thermometer class="w-5 h-5 text-red-400" />
              </div>
              <div class="metric-content">
                <div class="metric-label">温度</div>
                <div class="metric-value" :class="gpu && gpu.temperature > 80 ? 'text-red-400' : 'text-green-400'">
                  {{ gpu?.temperature ?? '--' }}°C
                </div>
              </div>
            </div>

            <div class="metric-item">
              <div class="metric-icon">
                <Zap class="w-5 h-5 text-yellow-400" />
              </div>
              <div class="metric-content">
                <div class="metric-label">功耗</div>
                <div class="metric-value">{{ gpu?.power_draw ?? '--' }}W</div>
                <div class="metric-subtext">/ {{ gpu?.power_limit ?? '--' }}W ({{ gpu?.power_percent ?? '--' }}%)</div>
              </div>
            </div>

            <div class="metric-item">
              <div class="metric-icon">
                <Fan class="w-5 h-5 text-cyan-400" />
              </div>
              <div class="metric-content">
                <div class="metric-label">风扇速度</div>
                <div class="metric-value">{{ gpu?.fan_speed ?? '--' }}%</div>
              </div>
            </div>

            <div class="metric-item">
              <div class="metric-icon">
                <HardDrive class="w-5 h-5 text-purple-400" />
              </div>
              <div class="metric-content">
                <div class="metric-label">显存可用</div>
                <div class="metric-value">{{ formatMemory(gpu?.available_memory ?? 0) }}</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Health Score Card -->
        <div class="card health-card">
          <div class="card-header">
            <Activity class="w-5 h-5 text-primary" />
            <span class="card-title">GPU 健康评分</span>
          </div>
          <div class="health-score-display">
            <div class="score-circle" :class="getHealthColor(healthScore)">
              <span class="score-value">{{ healthScore.toFixed(0) }}</span>
              <span class="score-max">/ 100</span>
            </div>
          </div>
          <div class="health-bar-bg">
            <div
              class="health-bar-fill"
              :class="getHealthBg(healthScore)"
              :style="{ width: healthScore + '%' }"
            ></div>
          </div>
        </div>

        <!-- VLLM Metrics Card -->
        <div v-if="vllmMetrics && vllmMetrics.vllm_available" class="card vllm-card">
          <div class="card-header">
            <Server class="w-5 h-5 text-primary" />
            <span class="card-title">vLLM 运行时指标</span>
          </div>
          <div class="vllm-metrics">
            <div class="vllm-metric">
              <span class="vllm-label">运行中</span>
              <span class="vllm-value">{{ vllmMetrics.running_requests }}</span>
            </div>
            <div class="vllm-metric">
              <span class="vllm-label">等待中</span>
              <span class="vllm-value">{{ vllmMetrics.waiting_requests }}</span>
            </div>
            <div class="vllm-metric">
              <span class="vllm-label">GPU 缓存</span>
              <span class="vllm-value">{{ vllmMetrics.gpu_cache_usage.toFixed(1) }}%</span>
            </div>
            <div class="vllm-metric">
              <span class="vllm-label">吞吐量</span>
              <span class="vllm-value">{{ vllmMetrics.request_throughput.toFixed(1) }} req/s</span>
            </div>
            <div class="vllm-metric">
              <span class="vllm-label">TTFT P50</span>
              <span class="vllm-value">{{ (vllmMetrics.time_to_first_token_p50 * 1000).toFixed(0) }}ms</span>
            </div>
            <div class="vllm-metric">
              <span class="vllm-label">TPOT P50</span>
              <span class="vllm-value">{{ (vllmMetrics.time_per_output_token_p50 * 1000).toFixed(0) }}ms</span>
            </div>
          </div>
        </div>
      </div>

      <!-- GPU Processes -->
      <div v-if="gpuProcesses.length > 0" class="card processes-card">
        <div class="card-header">
          <Activity class="w-5 h-5 text-primary" />
          <span class="card-title">GPU 进程</span>
          <span class="badge">{{ gpuProcesses.length }}</span>
        </div>
        <div class="process-list">
          <div v-for="proc in gpuProcesses" :key="proc.pid" class="process-item">
            <span class="process-pid">PID: {{ proc.pid }}</span>
            <span class="process-name">{{ proc.name }}</span>
            <span class="process-memory">{{ formatMemory(proc.used_gpu_memory) }}</span>
          </div>
        </div>
      </div>

      <!-- Model Management -->
      <div class="card models-card">
        <div class="card-header">
          <Server class="w-5 h-5 text-primary" />
          <span class="card-title">模型管理</span>
        </div>

        <!-- Running Models -->
        <div v-if="runningModels.length > 0" class="model-section">
          <h3 class="section-title">运行中的模型</h3>
          <div class="model-list">
            <div v-for="model in runningModels" :key="model.name" class="model-item running">
              <div class="model-info">
                <span class="model-name">{{ model.name }}</span>
                <span class="model-status-badge running">运行中</span>
                <span v-if="model.backend_type" class="model-badge">{{ model.backend_type }}</span>
                <span v-if="model.port" class="model-port">:{{ model.port }}</span>
              </div>
              <div class="model-actions">
                <button
                  class="btn btn-sm btn-primary"
                  :disabled="!!actionLoading"
                  @click="handleSwitchModel(model.name)"
                >
                  <ArrowRightLeft class="w-3.5 h-3.5" />
                  切换
                </button>
                <button
                  class="btn btn-sm btn-danger"
                  :disabled="!!actionLoading"
                  @click="handleStopModel(model.name)"
                >
                  <Square class="w-3.5 h-3.5" />
                  停止
                </button>
              </div>
            </div>
          </div>
        </div>

        <!-- Stopped Models -->
        <div v-if="stoppedModels.length > 0" class="model-section">
          <h3 class="section-title">已停止的模型</h3>
          <div class="model-list">
            <div v-for="model in stoppedModels" :key="model.name" class="model-item stopped">
              <div class="model-info">
                <span class="model-name">{{ model.name }}</span>
                <span class="model-status-badge stopped">已停止</span>
                <span v-if="model.backend_type" class="model-badge">{{ model.backend_type }}</span>
              </div>
              <div class="model-actions">
                <button
                  class="btn btn-sm btn-success"
                  :disabled="!!actionLoading"
                  @click="handleStartModel(model.name)"
                >
                  <Play class="w-3.5 h-3.5" />
                  启动
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.gpu-manage-page {
  padding: 24px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.page-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0;
}

.header-right {
  display: flex;
  gap: 8px;
}

.btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 500;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s;
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
}

.btn-secondary {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.1);
}

.btn-sm {
  padding: 6px 12px;
  font-size: 13px;
}

.btn-success {
  background: #059669;
  color: white;
}

.btn-danger {
  background: #dc2626;
  color: white;
}

.gpu-unavailable {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 20px;
  text-align: center;
}

.gpu-unavailable h2 {
  font-size: 20px;
  color: var(--text-primary);
  margin-bottom: 8px;
}

.info-grid {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr;
  gap: 16px;
  margin-bottom: 16px;
}

@media (max-width: 1200px) {
  .info-grid {
    grid-template-columns: 1fr;
  }
}

.card {
  background: rgba(255, 255, 255, 0.03);
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 20px;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  flex: 1;
}

.badge {
  background: rgba(99, 102, 241, 0.2);
  color: var(--color-primary-light);
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 12px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
}

@media (max-width: 800px) {
  .metrics-grid {
    grid-template-columns: 1fr;
  }
}

.metric-item {
  display: flex;
  gap: 12px;
  padding: 12px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.metric-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 10px;
  flex-shrink: 0;
}

.metric-content {
  flex: 1;
}

.metric-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
}

.metric-subtext {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 2px;
}

.progress-bar {
  height: 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
  margin-top: 8px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}

.health-card {
  display: flex;
  flex-direction: column;
  align-items: center;
}

.health-score-display {
  display: flex;
  justify-content: center;
  padding: 20px 0;
}

.score-circle {
  width: 100px;
  height: 100px;
  border-radius: 50%;
  border: 4px solid currentColor;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
}

.score-value {
  font-size: 32px;
  font-weight: 800;
}

.score-max {
  font-size: 12px;
  opacity: 0.7;
}

.health-bar-bg {
  width: 100%;
  height: 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 3px;
  margin-top: 16px;
  overflow: hidden;
}

.health-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.vllm-metrics {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.vllm-metric {
  padding: 12px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 10px;
  display: flex;
  flex-direction: column;
}

.vllm-label {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 4px;
}

.vllm-value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.processes-card {
  margin-bottom: 16px;
}

.process-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 200px;
  overflow-y: auto;
}

.process-item {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 10px 14px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 8px;
  font-size: 14px;
}

.process-pid {
  font-family: monospace;
  color: var(--color-primary-light);
  min-width: 80px;
}

.process-name {
  flex: 1;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.process-memory {
  color: var(--text-muted);
  font-family: monospace;
}

.models-card .model-section {
  margin-bottom: 20px;
}

.models-card .model-section:last-child {
  margin-bottom: 0;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-muted);
  margin-bottom: 12px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.model-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  max-height: 400px;
  overflow-y: auto;
}

.model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: rgba(0, 0, 0, 0.15);
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.04);
}

.model-item.running {
  border-color: rgba(34, 197, 94, 0.2);
}

.model-item.stopped {
  opacity: 0.7;
}

.model-info {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
  min-width: 0;
}

.model-name {
  font-weight: 600;
  color: var(--text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.model-status-badge {
  padding: 2px 8px;
  border-radius: 8px;
  font-size: 11px;
  font-weight: 600;
}

.model-status-badge.running {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.model-status-badge.stopped {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}

.model-badge {
  background: rgba(99, 102, 241, 0.15);
  color: var(--color-primary-light);
  padding: 2px 6px;
  border-radius: 6px;
  font-size: 11px;
}

.model-port {
  font-family: monospace;
  color: var(--text-muted);
  font-size: 12px;
}

.model-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.text-muted {
  color: var(--text-muted);
}

.text-green-400 {
  color: #4ade80;
}

.text-yellow-400 {
  color: #facc15;
}

.text-red-400 {
  color: #f87171;
}

.text-blue-400 {
  color: #60a5fa;
}

.text-cyan-400 {
  color: #22d3ee;
}

.text-purple-400 {
  color: #c084fc;
}

.bg-green-500 {
  background: #22c55e;
}

.bg-yellow-500 {
  background: #eab308;
}

.bg-red-500 {
  background: #ef4444;
}

.bg-blue-500 {
  background: #3b82f6;
}
</style>
