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
import VLLMMetricsCard from '@/components/cards/VLLMMetricsCard.vue'
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
  return Object.values(queueStatus.value as Record<string, QueueModelEntry>).reduce(
    (sum, q) => sum + q.active_requests,
    0
  )
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

    <div class="content">
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
              <button class="retry-btn" @click="refreshAll">
                <RotateCw class="w-3 h-3" /> 重试
              </button>
            </template>
          </GpuMetricsCard>
        </div>

        <div class="card vllm-card card-glow-purple scale-in stagger-2">
          <VLLMMetricsCard />
        </div>

        <div class="card token-card card-glow-purple scale-in stagger-3">
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
                <Cpu
                  class="w-4 h-4"
                  :style="{ color: getProgressColor(systemStatus.cpu.percent) }"
                />
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
                <div
                  v-for="(reason, idx) in healthAlert.alert_reasons"
                  :key="idx"
                  class="alert-item"
                >
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

.grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: minmax(0, auto);
  gap: 20px;
  padding: 20px 24px;
}

@media (max-width: 1024px) {
  .grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .grid {
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

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
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
.icon-wrap.purple {
  background: rgba(139, 92, 246, 0.15);
  color: #8b5cf6;
}
.icon-wrap.primary {
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
}
.icon-wrap.green {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.card-icon-inner {
  width: 16px;
  height: 16px;
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

.count-badge {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: auto;
}

.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 24px 0;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.token-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.token-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.token-info {
  display: flex;
  flex-direction: column;
}

.token-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.token-label {
  font-size: 11px;
  color: var(--text-muted);
}

.model-token-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.model-token-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mt-name {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 80px;
}

.mt-bar-track {
  flex: 1;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.mt-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #8b5cf6, #7c3aed);
  border-radius: 2px;
  transition: width 0.5s ease;
  min-width: 2px;
}

.mt-count {
  font-size: 11px;
  color: var(--text-muted);
  min-width: 40px;
  text-align: right;
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.queue-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border-left: 3px solid;
}

.queue-row.warning {
  border-left-color: #f59e0b;
}

.q-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.q-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

.q-count.warning {
  color: #f59e0b;
  font-weight: 600;
}
.q-limit {
  font-size: 11px;
  color: var(--text-muted);
}

.q-status {
  margin-left: auto;
  font-size: 12px;
  font-weight: 500;
}

.q-status.success {
  color: #22c55e;
}
.q-status.danger {
  color: #ef4444;
}

.health-score-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.health-score {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
}

.health-score.good {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}
.health-score.degraded {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}
.health-score.bad {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.health-score-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  overflow: hidden;
}

.hs-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.alert-reasons {
  margin-top: 12px;
}

.alert-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  cursor: pointer;
  width: 100%;
  transition: all 0.2s;
}

.alert-toggle:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.alert-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
  font-size: 13px;
}

.alert-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.alert-dot.warning {
  background: #f59e0b;
}
.alert-dot.info {
  background: #22c55e;
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
  transition: all 0.2s;
}

.model-row:hover {
  transform: translateX(4px);
}

.model-row.stopped {
  border-left-color: var(--border-primary);
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

.model-actions {
  display: flex;
  gap: 4px;
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

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--border-primary);
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--border-secondary);
}

.action-btn:disabled {
  opacity: 0.5;
}

.action-btn.start {
  color: #22c55e;
  border-color: rgba(34, 197, 94, 0.3);
}
.action-btn.stop {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}
.action-btn.switch {
  color: var(--color-primary-light);
  border-color: rgba(99, 102, 241, 0.3);
}

.sub-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  padding: 12px 0 8px;
  border-top: 1px solid var(--border-primary);
  margin-top: 12px;
}

.stopped-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.switch-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  margin-top: 12px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-primary-light);
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
</style>
