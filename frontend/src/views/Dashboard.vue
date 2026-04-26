<script setup lang="ts">
import { computed, ref } from 'vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import { useGPUHistory } from '@/composables/useGPUHistory'
import { useGPUChartDatasets } from '@/composables/useGPUChartDatasets'
import { useTokenStats } from '@/composables/useTokenStats'
import { useSystemData } from '@/composables/useSystemData'
import LineChart from '@/components/LineChart.vue'
import GpuMetricsCard from '@/components/cards/GpuMetricsCard.vue'
import VLLMMetricsCard from '@/components/cards/VLLMMetricsCard.vue'
import SystemStatusCard from '@/components/cards/SystemStatusCard.vue'
import TokenUsageCard from '@/components/cards/TokenUsageCard.vue'
import HealthAlertCard from '@/components/cards/HealthAlertCard.vue'
import RunningModelsCard from '@/components/cards/RunningModelsCard.vue'
import { RefreshCw, Cpu, Thermometer, Zap, Activity, MemoryStick, TrendingUp, Server } from 'lucide-vue-next'

const {
  modelList,
  defaultModel,
  actionLoading,
  switchingModel,
  handleStartModel,
  handleStopModel,
  handleSwitchAndSetDefault,
  refresh: refreshModels,
  isRefreshing: isRefreshingModels,
} = useModels()
const { gpuSummary, refresh: refreshGPU, isRefreshing: isRefreshingGPU } = useGPU()
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

<div v-else class="dashboard-layout">
        <div class="dashboard-row top-row">
          <div
            class="card system-card card-glow-primary scale-in stagger-1"
            :style="{ transform: `scale(${cardScale.system})`, transformOrigin: 'top left' }"
          >
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('system', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('system', -0.1)">−</button>
            </div>
            <SystemStatusCard :system-status="systemStatus" :system-history="systemHistory" />
          </div>

          <div
            class="card vllm-card card-glow-purple scale-in stagger-2"
            :style="{ transform: `scale(${cardScale.vllm})`, transformOrigin: 'top center' }"
          >
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('vllm', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('vllm', -0.1)">−</button>
            </div>
            <VLLMMetricsCard />
          </div>

          <div
            class="card token-card card-glow-purple scale-in stagger-3"
            :style="{ transform: `scale(${cardScale.token})`, transformOrigin: 'top right' }"
          >
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
        </div>

        <div
          class="dashboard-row gpu-row"
          :style="{ transform: `scale(${cardScale.gpu})`, transformOrigin: 'top center' }"
        >
          <div class="card gpu-card card-glow-cyan scale-in stagger-2 full-width">
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
                  :height="160"
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
                  :height="160"
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
                  :height="160"
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
                  :height="160"
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
                  :height="160"
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
                  :height="160"
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
                  :height="160"
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

          <div
            class="card health-card card-glow-green scale-in stagger-5"
            :style="{ transform: `scale(${cardScale.health})`, transformOrigin: 'top center' }"
          >
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('health', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('health', -0.1)">−</button>
            </div>
            <HealthAlertCard :health-alert="healthAlert" />
          </div>

          <div
            class="card running-card card-glow-green scale-in stagger-6"
            :style="{ transform: `scale(${cardScale.models})`, transformOrigin: 'top right' }"
          >
            <div class="scale-controls">
              <button class="scale-btn" @click="handleScale('models', 0.1)">+</button>
              <button class="scale-btn" @click="handleScale('models', -0.1)">−</button>
            </div>
            <RunningModelsCard
              :model-list="modelList"
              :default-model="defaultModel"
              :action-loading="actionLoading"
              :switching-model="switchingModel"
              :handle-start-model="handleStartModel"
              :handle-stop-model="handleStopModel"
              :handle-switch-and-set-default="handleSwitchAndSetDefault"
            />
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  height: 100vh;
  overflow: hidden;
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
  min-height: 0;
  overflow-y: auto;
}

.content::-webkit-scrollbar {
  width: 4px;
}

.content::-webkit-scrollbar-track {
  background: transparent;
}

.content::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 2px;
}

.dashboard-layout {
  display: flex;
  flex-direction: column;
  gap: 20px;
  padding: 20px 24px;
}

.dashboard-row {
  display: grid;
  gap: 20px;
}

.top-row {
  grid-template-columns: repeat(3, 1fr);
}

.gpu-row {
  grid-template-columns: 1fr;
}

.bottom-row {
  grid-template-columns: repeat(3, 1fr);
}

@media (max-width: 1200px) {
  .top-row {
    grid-template-columns: repeat(2, 1fr);
  }
  .bottom-row {
    grid-template-columns: repeat(2, 1fr);
  }

  .gpu-full-width {
    grid-column: 1 / -1;
  }

  .card-expanded {
    grid-column: 1 / -1 !important;
  }
}

@media (max-width: 640px) {
  .top-row {
    grid-template-columns: 1fr;
  }
  .bottom-row {
    grid-template-columns: 1fr;
    gap: 12px;
    padding: 12px 16px;
  }

  .gpu-full-width {
    grid-column: 1;
  }

  .card-expanded {
    grid-column: 1 !important;
  }

  .card-header {
    flex-wrap: wrap;
  }

  .card-title {
    font-size: 13px;
  }

  .token-grid {
    grid-template-columns: 1fr;
  }
}

.card {
  background: var(--bg-card);
  border-radius: 16px;
  border: 1px solid var(--border-card);
  padding: 20px;
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
  transform: translateY(-1px);
}

.full-width {
  width: 100%;
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

.retry-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border-radius: 6px;
  font-size: 12px;
  color: var(--color-primary-light);
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  cursor: pointer;
  transition: all 0.2s;
}

.retry-btn:hover {
  background: rgba(99, 102, 241, 0.15);
  color: var(--color-primary);
}

.retry-icon {
  width: 12px;
  height: 12px;
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

.gpu-charts-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  margin-top: 16px;
}

@media (max-width: 1200px) {
  .gpu-charts-grid {
    grid-template-columns: 1fr;
  }
}

.chart-card {
  background: var(--bg-secondary);
  border-radius: 12px;
  padding: 16px;
}

.chart-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.chart-icon {
  width: 16px;
  height: 16px;
}

.chart-icon.purple {
  color: #8b5cf6;
}

.chart-icon.orange {
  color: #f59e0b;
}

.chart-icon.cyan {
  color: #06b6d4;
}

.chart-icon.red {
  color: #ef4444;
}

.chart-icon.green {
  color: #22c55e;
}

.chart-icon.yellow {
  color: #f59e0b;
}

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
</style>
