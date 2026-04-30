<script setup lang="ts">
import { computed, ref } from 'vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import { useGPUHistory } from '@/composables/useGPUHistory'
import { useGPUChartDatasets } from '@/composables/useGPUChartDatasets'
import { useTokenStats } from '@/composables/useTokenStats'
import { useSystemData } from '@/composables/useSystemData'
import { useGPUMemory } from '@/composables/useGPUMemory'
import LineChart from '@/components/LineChart.vue'
import GpuMetricsCard from '@/components/cards/GpuMetricsCard.vue'
import VLLMMetricsCard from '@/components/cards/VLLMMetricsCard.vue'
import SystemStatusCard from '@/components/cards/SystemStatusCard.vue'
import TokenUsageCard from '@/components/cards/TokenUsageCard.vue'
import HealthAlertCard from '@/components/cards/HealthAlertCard.vue'
import { useRouter } from 'vue-router'
import { RefreshCw, Cpu, Thermometer, Zap, Activity, MemoryStick, TrendingUp, Server, Gpu, CircleDot, AlertTriangle, CheckCircle, ArrowRight, Layers, Star } from 'lucide-vue-next'
import { formatBytes } from '@/utils/format'
import type { EngineType } from '@/types'

const router = useRouter()

const {
  modelList,
  defaultModel,
  refresh: refreshModels,
  isRefreshing: isRefreshingModels,
} = useModels()
const { gpuSummary, refresh: refreshGPU, isRefreshing: isRefreshingGPU } = useGPU()
const { engineStatus: gpuEngineStatus, getEngines: gpuGetEngines } = useGPUMemory()
const {
  gpuHistory,
  error: gpuHistoryError,
  refresh: refreshGPUHistory,
  isRefreshing: isRefreshingGPUHistory,
} = useGPUHistory(60)
const {
  gpuTimeLabels,
  gpuUtilDataset,
  gpuTempDataset,
  gpuMemDataset,
  gpuPowerDataset,
  vllmRunningDataset,
  vllmWaitingDataset,
  vllmGpuCacheDataset,
} = useGPUChartDatasets(gpuHistory)
const {
  stats: tokenStats,
  totalTokens,
  promptTokens,
  completionTokens,
  modelStats,
  formatTokens,
  refresh: refreshTokens,
  isRefreshing: isRefreshingTokens,
} = useTokenStats()
const {
  systemStatus,
  healthAlert,
  systemHistory,
  refresh: refreshSystem,
  isRefreshing: isRefreshingSystem,
} = useSystemData()


const isRefreshing = computed(
  () =>
    isRefreshingModels.value ||
    isRefreshingGPU.value ||
    isRefreshingGPUHistory.value ||
    isRefreshingTokens.value ||
    isRefreshingSystem.value
)
const initialLoading = computed(() => isRefreshingModels.value && !modelList.value.length)

const refreshAll = () => {
  refreshGPU()
  refreshModels()
  refreshTokens()
  refreshSystem()
  refreshGPUHistory()
  gpuGetEngines()
}

const engineLabels: Record<string, string> = {
  vllm: 'vLLM',
  sglang: 'SGLang',
  llama_cpp: 'llama.cpp',
}

const gpu = computed(() => gpuSummary.value?.current ?? null)
const gpuStatus = computed(() => gpuSummary.value?.status ?? 'unavailable')

const cardScale = ref<Record<string, number>>({
  system: 1,
  vllm: 1,
  token: 1,
  gpu: 1,
  queue: 1,
  health: 1,
  models: 1,
})

const handleScale = (cardId: string, delta: number) => {
  const current = cardScale.value[cardId]
  const next = Math.max(0.8, Math.min(1.4, current + delta))
  cardScale.value[cardId] = next
}
</script>

<template>
  <div class="dashboard">
    <header class="header">
      <h1 class="header-title">仪表盘</h1>
      <button class="header-btn" @click="refreshAll">
        <RefreshCw class="refresh-icon" :class="{ 'animate-spin': isRefreshing }" />
        <span>刷新</span>
      </button>
    </header>

    <div class="content">
      <div v-if="initialLoading" class="grid">
        <div v-for="i in 6" :key="i" class="card skeleton-card">
          <div class="skeleton-line w-1/3"></div>
          <div class="skeleton-line w-2/3"></div>
          <div class="skeleton-line w-1/2"></div>
          <div class="skeleton-line w-3/4"></div>
        </div>
      </div>

<div v-else class="dashboard-grid">
          <div class="card system-card card-glow-primary scale-in stagger-1">
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('system', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('system', -0.1)">−</button>
            </div>
            <SystemStatusCard :system-status="systemStatus" :system-history="systemHistory" />
          </div>

          <div class="card vllm-card card-glow-purple scale-in stagger-2">
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('vllm', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('vllm', -0.1)">−</button>
            </div>
            <VLLMMetricsCard />
          </div>

          <div class="card token-card card-glow-purple scale-in stagger-3">
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('token', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('token', -0.1)">−</button>
            </div>
            <TokenUsageCard
              :stats="tokenStats"
              :total-tokens="totalTokens"
              :prompt-tokens="promptTokens"
              :completion-tokens="completionTokens"
              :model-stats="modelStats"
              :format-tokens="formatTokens"
            />
          </div>

          <div class="card health-card card-glow-green scale-in stagger-4">
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('health', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('health', -0.1)">−</button>
            </div>
            <HealthAlertCard :health-alert="healthAlert" />
          </div>

          <div class="card queue-card card-glow-blue scale-in stagger-4-5">
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('queue', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('queue', -0.1)">−</button>
            </div>
            <RequestQueueCard :queue-status="queueStatus" />
          </div>

          <div class="card gpu-card card-glow-cyan scale-in stagger-5 span-2">
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('gpu', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('gpu', -0.1)">−</button>
            </div>
            <div class="gpu-card-header">
              <div class="icon-wrap cyan"><Cpu class="card-icon-inner" /></div>
              <span class="card-title">GPU 监控</span>
              <span v-if="gpuStatus === 'available'" class="badge online"
                ><span class="dot online"></span>在线</span
              >
              <span v-else class="badge offline"><span class="dot offline"></span>离线</span>
            </div>
            <GpuMetricsCard
              :gpu="gpu"
              :gpu-history="gpuHistory"
              :gpu-status="gpuStatus"
              :error="gpuHistoryError"
            />
            <div v-if="gpu" class="memory-availability-bar">
              <span class="mem-avail-label">可用显存</span>
              <span class="mem-avail-value" :class="gpu.memory_utilization > 85 ? 'warn' : 'ok'">
                {{ formatBytes(gpu.available_memory) }}
              </span>
              <span v-if="gpu.memory_utilization > 85" class="mem-warn-badge">
                <AlertTriangle class="w-3 h-3" /> 显存紧张
              </span>
              <span v-else class="mem-ok-badge">
                <CheckCircle class="w-3 h-3" />
              </span>
            </div>
            <template v-if="gpuHistory.length > 0">
              <div class="gpu-charts-grid">
              <div class="chart-card">
                <div class="chart-header">
                  <TrendingUp class="chart-icon purple" />
                  <span class="chart-title">GPU 利用率</span>
                </div>
                <LineChart
                  :labels="gpuTimeLabels"
                  :datasets="gpuUtilDataset"
                  :height="120"
                  y-unit="%"
                  :y-min="0"
                  :y-max="100"
                />
              </div>
              <div class="chart-card">
                <div class="chart-header">
                  <Thermometer class="chart-icon orange" />
                  <span class="chart-title">GPU 温度</span>
                </div>
                <LineChart
                  :labels="gpuTimeLabels"
                  :datasets="gpuTempDataset"
                  :height="120"
                  y-unit="°C"
                  :y-min="0"
                />
              </div>
              <div class="chart-card">
                <div class="chart-header">
                  <MemoryStick class="chart-icon cyan" />
                  <span class="chart-title">显存利用率</span>
                </div>
                <LineChart
                  :labels="gpuTimeLabels"
                  :datasets="gpuMemDataset"
                  :height="120"
                  y-unit="%"
                  :y-min="0"
                  :y-max="100"
                />
              </div>
              <div class="chart-card">
                <div class="chart-header">
                  <Zap class="chart-icon red" />
                  <span class="chart-title">功耗</span>
                </div>
                <LineChart
                  :labels="gpuTimeLabels"
                  :datasets="gpuPowerDataset"
                  :height="120"
                  y-unit="W"
                  :y-min="0"
                />
              </div>
              <div class="chart-card">
                <div class="chart-header">
                  <Activity class="chart-icon green" />
                  <span class="chart-title">vLLM 运行请求</span>
                </div>
                <LineChart
                  :labels="gpuTimeLabels"
                  :datasets="vllmRunningDataset"
                  :height="120"
                  y-unit=""
                  :y-min="0"
                />
              </div>
              <div class="chart-card">
                <div class="chart-header">
                  <Activity class="chart-icon yellow" />
                  <span class="chart-title">vLLM 等待请求</span>
                </div>
                <LineChart
                  :labels="gpuTimeLabels"
                  :datasets="vllmWaitingDataset"
                  :height="120"
                  y-unit=""
                  :y-min="0"
                />
              </div>
              <div class="chart-card">
                <div class="chart-header">
                  <Server class="chart-icon purple" />
                  <span class="chart-title">vLLM KV 缓存</span>
                </div>
                <LineChart
                  :labels="gpuTimeLabels"
                  :datasets="vllmGpuCacheDataset"
                  :height="120"
                  y-unit="%"
                  :y-min="0"
                  :y-max="100"
                />
              </div>
              </div>
            </template>
            <div v-else class="gpu-chart-empty-state">
              <TrendingUp class="chart-empty-icon" />
              <p>暂无 GPU 历史数据</p>
              <span class="chart-empty-hint">历史数据将在后端运行后自动采集</span>
            </div>
          </div>

          <div class="card running-card card-glow-green scale-in stagger-6 span-2">
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('models', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('models', -0.1)">−</button>
            </div>
            <div class="card-header">
              <div class="icon-wrap green"><Layers class="card-icon-inner" /></div>
              <span class="card-title">运行模型</span>
              <span class="count-badge">{{ modelList.filter(m => m.running).length }} / {{ modelList.length }}</span>
              <button class="goto-btn" @click="router.push('/modelcenter')">
                <ArrowRight class="w-4 h-4" /> 前往模型中心
              </button>
            </div>
            <div v-if="modelList.filter(m => m.running).length" class="running-list">
              <div v-for="model in modelList.filter(m => m.running)" :key="model.name" class="model-row">
                <div class="model-info">
                  <span class="model-name">{{ model.name }}</span>
                  <span class="model-meta">端口 {{ model.port }} · {{ model.active_requests }} 请求</span>
                </div>
                <span v-if="defaultModel === model.name" class="default-tag">
                  <Star class="default-icon" /> 默认
                </span>
              </div>
            </div>
            <div v-else class="empty-state">暂无运行模型</div>
          </div>

          <div class="card engine-card card-glow-primary scale-in stagger-7">
            <div class="engine-card-header">
              <Gpu class="card-icon-inner" style="color:var(--accent-primary)" />
              <span class="card-title">推理引擎</span>
            </div>
            <div v-if="gpuEngineStatus" class="engine-card-content">
              <div class="engine-current-badge">
                当前: {{ engineLabels[gpuEngineStatus.current_engine] || gpuEngineStatus.current_engine }}
                <CircleDot v-if="gpuEngineStatus[gpuEngineStatus.current_engine]?.running" class="w-4 h-4" style="color:#4ade80" />
              </div>
              <div class="engine-list">
                <div v-for="eng in (['vllm', 'sglang', 'llama_cpp'] as EngineType[])" :key="eng" class="engine-row">
                  <span :class="gpuEngineStatus[eng]?.running ? 'engine-dot running' : 'engine-dot stopped'"></span>
                  <span class="engine-name">{{ engineLabels[eng] }}</span>
                  <span :class="gpuEngineStatus[eng]?.running ? 'engine-status running' : 'engine-status stopped'">
                    {{ gpuEngineStatus[eng]?.running ? '运行中' : '未运行' }}
                  </span>
                  <span v-if="gpuEngineStatus[eng]?.model" class="engine-model">{{ gpuEngineStatus[eng]?.model }}</span>
                  <span v-if="gpuEngineStatus[eng]?.pid" class="engine-detail">PID {{ gpuEngineStatus[eng]?.pid }}</span>
                  <span v-if="gpuEngineStatus[eng]?.port" class="engine-detail">:{{ gpuEngineStatus[eng]?.port }}</span>
                </div>
              </div>
            </div>
            <div v-else class="engine-card-empty">暂无引擎状态数据</div>
          </div>
        </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-primary);
  flex-shrink: 0;
  position: sticky;
  top: 0;
  z-index: 10;
}

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  cursor: pointer;
  transition: all 0.25s;
}

.header-btn:hover {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.3);
}

.refresh-icon {
  width: 16px;
  height: 16px;
}

.content {
  flex: 1;
  padding: 16px;
}

.dashboard-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  max-width: 1600px;
  margin: 0 auto;
}

.span-2 {
  grid-column: 1 / -1;
}

@media (max-width: 768px) {
  .dashboard-grid {
    grid-template-columns: 1fr;
    gap: 12px;
  }

  .span-2 {
    grid-column: 1;
  }

  .content {
    padding: 8px;
  }
}

.card {
  background: var(--bg-card);
  border-radius: 16px;
  border: 1px solid var(--border-card);
  padding: 16px;
  box-shadow: var(--shadow);
  transition: all 0.3s ease;
  animation: fade-in 0.4s ease-out;
  position: relative;
  overflow: hidden;
}

.card:hover {
  border-color: rgba(99, 102, 241, 0.25);
  box-shadow:
    var(--shadow-md),
    0 0 12px rgba(99, 102, 241, 0.08);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.icon-wrap {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-wrap.cyan {
  background: rgba(6, 182, 212, 0.15);
  color: #06b6d4;
}

.icon-wrap.green {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.card-icon-inner {
  width: 16px;
  height: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.badge.online {
  background: rgba(34, 197, 94, 0.1);
  color: #059669;
}

.badge.offline {
  background: rgba(239, 68, 68, 0.1);
  color: #dc2626;
}

.dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}

.dot.online {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.5);
}

.dot.offline {
  background: #6b7280;
}

.scale-controls {
  display: flex;
  gap: 2px;
  position: absolute;
  top: 8px;
  right: 8px;
  opacity: 0;
  transition: opacity 0.2s;
}

.card:hover .scale-controls {
  opacity: 1;
}

.scale-btn {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  cursor: pointer;
  transition: all 0.2s;
}

.scale-btn:hover {
  color: var(--text-primary);
  background: var(--color-primary);
  border-color: var(--color-primary);
}

.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-line {
  height: 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  animation: pulse-soft 2s ease-in-out infinite;
}

@keyframes fade-in {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.gpu-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.memory-availability-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  background: var(--bg-secondary);
  margin-top: 8px;
  font-size: 13px;
}

.mem-avail-label {
  color: var(--text-secondary);
}

.mem-avail-value.ok {
  color: #22c55e;
  font-weight: 600;
}

.mem-avail-value.warn {
  color: #f59e0b;
  font-weight: 600;
}

.mem-warn-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
  font-size: 12px;
}

.mem-ok-badge {
  color: #22c55e;
}

.gpu-charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-top: 12px;
}

@media (max-width: 768px) {
  .gpu-charts-grid {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.chart-icon {
  width: 16px;
  height: 16px;
}

.chart-icon.purple { color: #8b5cf6; }
.chart-icon.orange { color: #f59e0b; }
.chart-icon.cyan { color: #06b6d4; }
.chart-icon.red { color: #ef4444; }
.chart-icon.green { color: #22c55e; }
.chart-icon.yellow { color: #f59e0b; }

.chart-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
}

.gpu-chart-empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px 20px;
  background: var(--bg-secondary);
  border-radius: 12px;
  text-align: center;
}

.chart-empty-icon {
  width: 32px;
  height: 32px;
  color: var(--text-muted);
  opacity: 0.5;
}

.gpu-chart-empty-state p {
  font-size: 14px;
  color: var(--text-muted);
  margin: 0;
}

.chart-empty-hint {
  font-size: 12px;
  color: var(--text-muted);
  opacity: 0.7;
}

.engine-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.engine-card-content {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.engine-current-badge {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.engine-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.engine-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
}

.engine-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.engine-dot.running {
  background: #4ade80;
}

.engine-dot.stopped {
  background: var(--border-primary);
}

.engine-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.engine-status {
  font-size: 12px;
}

.engine-status.running {
  color: #4ade80;
}

.engine-status.stopped {
  color: var(--text-secondary);
}

.engine-model {
  font-size: 11px;
  color: var(--text-secondary);
}

.engine-detail {
  font-size: 10px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  padding: 1px 4px;
  border-radius: 3px;
}

.engine-card-empty {
  color: var(--text-secondary);
  font-size: 13px;
  text-align: center;
  padding: 20px;
}

.goto-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  color: var(--color-primary-light);
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.2);
  cursor: pointer;
  transition: all 0.2s;
  margin-left: auto;
}

.goto-btn:hover {
  background: rgba(99, 102, 241, 0.2);
  border-color: rgba(99, 102, 241, 0.4);
}

.running-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border-left: 3px solid #22c55e;
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.model-meta {
  font-size: 11px;
  color: var(--text-muted);
}

.default-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.default-icon {
  width: 12px;
  height: 12px;
}

.count-badge {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 10px;
}
</style>
