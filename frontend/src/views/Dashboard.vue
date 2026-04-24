<script setup lang="ts">
import { computed, ref } from 'vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import { useGPUHistory } from '@/composables/useGPUHistory'
import { useTokenStats } from '@/composables/useTokenStats'
import { useSystemData } from '@/composables/useSystemData'
import type { QueueModelEntry } from '@/types'
import { getProgressColor, getStatusLevel, getHealthStatusConfig } from '@/utils/theme'
import { formatTimeLabel } from '@/utils/format'
import { useAppStore } from '@/stores/app'
import GpuMetricsCard from '@/components/cards/GpuMetricsCard.vue'
import {
  RefreshCw,
  Monitor,
  Cpu,
  Zap,
  Layers,
  Square,
  Play,
  ArrowRightLeft,
  Star,
  Coins,
  Activity,
  Box,
  MemoryStick,
  Server,
  HardDrive,
  AlertTriangle,
  ShieldCheck,
  ChevronDown,
  ChevronUp,
  RotateCw,
} from 'lucide-vue-next'

const store = useAppStore()
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
  queueStatus,
  healthAlert,
  systemHistory,
  refresh: refreshSystem,
  isRefreshing: isRefreshingSystem,
} = useSystemData()

const alertExpanded = ref(false)

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
const runningModels = computed(() => modelList.value.filter((m) => m.running))
const healthStatusColor = computed(() =>
  getHealthStatusConfig(healthAlert.value?.status ?? 'critical')
)

const totalQueueRequests = computed(() => {
  if (!queueStatus.value) return 0
  return Object.values(queueStatus.value as Record<string, QueueModelEntry>).reduce((sum, q) => sum + q.active_requests, 0)
})

const activeQueueEntries = computed(() => {
  if (!queueStatus.value) return []
  const entries = Object.entries(queueStatus.value as Record<string, QueueModelEntry>)
    .filter(([, entry]) => entry.active_requests > 0)
    .sort(([, a], [, b]) => b.active_requests - a.active_requests)
  if (!entries.length) return []
  const target = defaultModel.value || entries[0][0]
  return entries
    .filter(([name]) => name === target)
    .slice(0, 1)
    .map(([name, entry]) => ({ name, ...entry }))
})

const sysTimeLabels = computed(() => systemHistory.value.map((e) => formatTimeLabel(e.timestamp)))

const sysSparklineDatasets = (
  key: 'cpu_percent' | 'memory_percent',
  color: string,
  bgColor: string
) => [
  {
    label: '',
    data: systemHistory.value.map((e) => Number(e[key]) || 0),
    borderColor: color,
    backgroundColor: bgColor,
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 2,
  },
]

const switchingProgress = computed(() => {
  if (!switchingModel.value) return null
  const model = modelList.value.find((m) => m.name === switchingModel.value)
  if (model?.running) return null
  return { model: switchingModel.value, phase: model ? '加载中' : '卸载旧模型' }
})

const handleStartWithToast = async (name: string) => {
  try {
    await handleStartModel(name)
    store.success(`模型 ${name} 已开始启动`)
  } catch {
    store.error(`模型 ${name} 启动失败`)
  }
}

const handleStopWithToast = async (name: string) => {
  try {
    await handleStopModel(name)
    store.success(`模型 ${name} 已停止`)
  } catch {
    store.error(`模型 ${name} 停止失败`)
  }
}

const handleSwitchWithToast = async (name: string) => {
  try {
    await handleSwitchAndSetDefault(name)
    store.success(`正在切换到模型 ${name}，请等待加载完成`)
  } catch {
    store.error(`切换模型 ${name} 失败`)
  }
}
</script>

<template>
  <div class="dashboard">
    <header class="header">
      <h1 class="header-title">仪表盘</h1>
      <button class="header-btn" @click="refreshAll">
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
        <span>刷新</span>
      </button>
    </header>

    <div v-if="initialLoading" class="grid">
      <div v-for="i in 6" :key="i" class="card skeleton-card">
        <div class="skeleton-line w-1/3"></div>
        <div class="skeleton-line w-2/3"></div>
        <div class="skeleton-line w-1/2"></div>
        <div class="skeleton-line w-3/4"></div>
      </div>
    </div>

    <div v-else class="grid">
      <div class="card gpu-card card-glow-cyan scale-in stagger-1">
        <div class="card-header">
          <div class="icon-wrap cyan"><Monitor class="card-icon-inner" /></div>
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
          mode="compact"
        >
          <template #error-action>
            <button class="retry-btn" @click="refreshAll"><RotateCw class="w-3 h-3" /> 重试</button>
          </template>
        </GpuMetricsCard>
      </div>

      <div class="card token-card card-glow-purple scale-in stagger-2">
        <div class="card-header">
          <div class="icon-wrap purple"><Coins class="card-icon-inner" /></div>
          <span class="card-title">Token 用量</span>
          <span v-if="tokenStats" class="count-badge">{{ formatTokens(totalTokens) }}</span>
        </div>
        <div v-if="tokenStats" class="token-grid">
          <div class="token-item">
            <Activity class="w-4 h-4 text-blue-400" />
            <div class="token-info">
              <span class="token-value">{{ formatTokens(promptTokens) }}</span>
              <span class="token-label">Prompt</span>
            </div>
          </div>
          <div class="token-item">
            <Coins class="w-4 h-4 text-green-400" />
            <div class="token-info">
              <span class="token-value">{{ formatTokens(completionTokens) }}</span>
              <span class="token-label">Completion</span>
            </div>
          </div>
          <div class="token-item">
            <Zap class="w-4 h-4 text-purple-400" />
            <div class="token-info">
              <span class="token-value">{{ formatTokens(totalTokens) }}</span>
              <span class="token-label">Total</span>
            </div>
          </div>
        </div>
        <div v-if="tokenStats && Object.keys(modelStats).length" class="model-token-list">
          <div v-for="(stats, name) in modelStats" :key="name" class="model-token-row">
            <span class="mt-name">{{ name }}</span>
            <div class="mt-bar-track">
              <div
                class="mt-bar-fill"
                :style="{
                  width: `${Math.min(100, (stats.total_tokens / Math.max(totalTokens, 1)) * 100)}%`,
                }"
              ></div>
            </div>
            <span class="mt-count">{{ formatTokens(stats.total_tokens) }}</span>
          </div>
        </div>
        <div v-if="!tokenStats" class="empty-state">暂无统计</div>
      </div>

      <div class="card system-card card-glow-primary scale-in stagger-3">
        <div class="card-header">
          <div class="icon-wrap primary"><Server class="card-icon-inner" /></div>
          <span class="card-title">系统状态</span>
        </div>
        <template v-if="systemStatus">
          <div class="system-grid">
            <div class="sys-item">
              <Cpu class="w-4 h-4" :style="{ color: getProgressColor(systemStatus.cpu.percent) }" />
              <div class="sys-info">
                <span class="sys-label">CPU</span>
                <span class="sys-val" :class="getStatusLevel(systemStatus.cpu.percent)"
                  >{{ systemStatus.cpu.percent.toFixed(1) }}%</span
                >
              </div>
              <span class="sys-meta"
                >{{ systemStatus.cpu.cores_physical }}核 / {{ systemStatus.cpu.cores }}线程</span
              >
              <div v-if="systemHistory.length >= 2" class="sys-chart">
                <LineChart
                  :labels="sysTimeLabels"
                  :datasets="
                    sysSparklineDatasets('cpu_percent', '#fbbf24', 'rgba(251,191,36,0.05)')
                  "
                  :height="60"
                  :show-legend="false"
                  :animate="false"
                  y-unit="%"
                  y-min="0"
                  y-max="100"
                />
              </div>
            </div>
            <div class="sys-item">
              <MemoryStick
                class="w-4 h-4"
                :style="{ color: getProgressColor(systemStatus.memory.percent) }"
              />
              <div class="sys-info">
                <span class="sys-label">内存</span>
                <span class="sys-val" :class="getStatusLevel(systemStatus.memory.percent)"
                  >{{ systemStatus.memory.percent.toFixed(1) }}%</span
                >
              </div>
              <span class="sys-meta"
                >{{ (systemStatus.memory.used_mb / 1024).toFixed(1) }} /
                {{ (systemStatus.memory.total_mb / 1024).toFixed(1) }} GB</span
              >
              <div v-if="systemHistory.length >= 2" class="sys-chart">
                <LineChart
                  :labels="sysTimeLabels"
                  :datasets="
                    sysSparklineDatasets('memory_percent', '#22d3ee', 'rgba(34,211,238,0.05)')
                  "
                  :height="60"
                  :show-legend="false"
                  :animate="false"
                  y-unit="%"
                  y-min="0"
                  y-max="100"
                />
              </div>
            </div>
            <div class="sys-item">
              <HardDrive
                class="w-4 h-4"
                :style="{ color: getProgressColor(systemStatus.disk.percent) }"
              />
              <div class="sys-info">
                <span class="sys-label">磁盘</span>
                <div class="sys-bar-track">
                  <div
                    class="sys-bar-fill"
                    :style="{
                      width: `${systemStatus.disk.percent}%`,
                      background: getProgressColor(systemStatus.disk.percent),
                    }"
                  ></div>
                </div>
                <span class="sys-val" :class="getStatusLevel(systemStatus.disk.percent)"
                  >{{ systemStatus.disk.percent.toFixed(1) }}%</span
                >
              </div>
              <span class="sys-meta"
                >{{ systemStatus.disk.used_gb }} / {{ systemStatus.disk.total_gb }} GB</span
              >
            </div>
          </div>
        </template>
        <div v-else class="empty-state">
          <Server class="w-10 h-10 text-muted" />
          <p>系统数据不可用</p>
        </div>
      </div>

      <div class="card queue-card card-glow-primary scale-in stagger-4">
        <div class="card-header">
          <div class="icon-wrap primary"><Layers class="card-icon-inner" /></div>
          <span class="card-title">请求队列</span>
          <span v-if="queueStatus" class="count-badge">{{ totalQueueRequests }} 请求</span>
        </div>
        <template v-if="queueStatus">
          <div v-if="activeQueueEntries.length" class="queue-list">
            <div v-for="entry in activeQueueEntries" :key="entry.name" class="queue-row warning">
              <span class="q-name">{{ entry.name }}</span>
              <div class="q-info">
                <span class="q-count warning">{{ entry.active_requests }}</span>
                <span class="q-limit">/ {{ entry.concurrency_limit }}</span>
              </div>
              <span class="q-status" :class="entry.can_accept ? 'success' : 'danger'">{{
                entry.can_accept ? '可接受' : '已满'
              }}</span>
            </div>
          </div>
          <div v-else class="empty-state">
            <Layers class="w-8 h-8 text-muted" />
            <p>当前无活跃请求</p>
          </div>
        </template>
        <div v-else class="empty-state">
          <Layers class="w-10 h-10 text-muted" />
          <p>队列数据不可用</p>
        </div>
      </div>

      <div class="card health-card card-glow-green scale-in stagger-5">
        <div class="card-header">
          <div class="icon-wrap green"><ShieldCheck class="card-icon-inner" /></div>
          <span class="card-title">健康告警</span>
          <span
            v-if="healthAlert"
            class="badge"
            :style="{ background: healthStatusColor.bg, color: healthStatusColor.color }"
          >
            {{ healthStatusColor.label }}
          </span>
        </div>
        <template v-if="healthAlert">
          <div class="health-score-row">
            <div
              class="health-score"
              :class="
                healthAlert.health_score >= 70
                  ? 'good'
                  : healthAlert.health_score >= 50
                    ? 'degraded'
                    : 'bad'
              "
            >
              {{ healthAlert.health_score.toFixed(0) }}
            </div>
            <div class="health-score-bar">
              <div
                class="hs-fill"
                :style="{
                  width: `${healthAlert.health_score}%`,
                  background:
                    healthAlert.health_score >= 70
                      ? '#22c55e'
                      : healthAlert.health_score >= 50
                        ? '#f59e0b'
                        : '#ef4444',
                }"
              ></div>
            </div>
          </div>
          <div v-if="healthAlert.alert_reasons?.length" class="alert-reasons">
            <button class="alert-toggle" @click="alertExpanded = !alertExpanded">
              <AlertTriangle
                class="w-4 h-4"
                :style="{ color: healthAlert.should_alert ? '#f59e0b' : '#22c55e' }"
              />
              <span>{{ healthAlert.alert_reasons.length }} 条告警</span>
              <ChevronDown v-if="!alertExpanded" class="w-3 h-3" />
              <ChevronUp v-else class="w-3 h-3" />
            </button>
            <div v-if="alertExpanded" class="alert-list">
              <div v-for="(reason, idx) in healthAlert.alert_reasons" :key="idx" class="alert-item">
                <span
                  class="alert-dot"
                  :class="healthAlert.should_alert ? 'warning' : 'info'"
                ></span>
                <span>{{ reason }}</span>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="empty-state">
          <ShieldCheck class="w-10 h-10 text-muted" />
          <p>健康数据不可用</p>
        </div>
      </div>

      <div class="card running-card card-glow-green scale-in stagger-6">
        <div class="card-header">
          <div class="icon-wrap green"><Layers class="card-icon-inner" /></div>
          <span class="card-title">运行模型</span>
          <span class="count-badge">{{ runningModels.length }} / {{ modelList.length }}</span>
        </div>
        <div v-if="runningModels.length" class="running-list">
          <div v-for="model in runningModels" :key="model.name" class="model-row">
            <div class="model-info">
              <span class="model-name">{{ model.name }}</span>
              <span class="model-meta"
                >端口 {{ model.port }} · {{ model.active_requests }} 请求</span
              >
            </div>
            <div class="model-actions">
              <span v-if="defaultModel === model.name" class="default-tag"
                ><Star class="w-3 h-3" /> 默认</span
              >
              <button
                class="action-btn stop"
                :disabled="!!actionLoading"
                @click="handleStopWithToast(model.name)"
              >
                <Square class="w-3 h-3" /> 停止
              </button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">暂无运行模型</div>
        <div class="stopped-section">
          <div class="sub-header">可启动模型</div>
          <div class="stopped-list">
            <div
              v-for="model in modelList.filter((m) => !m.running)"
              :key="model.name"
              class="model-row stopped"
            >
              <div class="model-info">
                <span class="model-name">{{ model.name }}</span>
                <span class="model-meta">
                  <Box class="w-3 h-3 inline-block" />
                  {{ model.supports_images ? '支持图片' : '纯文本' }}
                </span>
              </div>
              <div class="model-actions">
                <button
                  class="action-btn start"
                  :disabled="!!actionLoading"
                  @click="handleStartWithToast(model.name)"
                >
                  <Play class="w-3 h-3" /> 启动
                </button>
                <button
                  class="action-btn switch"
                  :disabled="!!actionLoading"
                  @click="handleSwitchWithToast(model.name)"
                >
                  <ArrowRightLeft class="w-3 h-3" /> 切换
                </button>
              </div>
            </div>
          </div>
        </div>
        <div v-if="switchingProgress" class="switch-progress">
          <RefreshCw class="w-4 h-4 animate-spin" />
          <span>正在切换 {{ switchingProgress.model }} · {{ switchingProgress.phase }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.system-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sys-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sys-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sys-label {
  font-size: 11px;
  color: var(--text-muted);
}

.sys-val {
  font-size: 13px;
  font-weight: 600;
}

.sys-meta {
  font-size: 10px;
  color: var(--text-muted);
}

.sys-chart {
  margin-top: 4px;
}

.sys-bar-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
  overflow: hidden;
}

.sys-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}
</style>
