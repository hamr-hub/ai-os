<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import { useTokenStats } from '@/composables/useTokenStats'
import { useSystemData } from '@/composables/useSystemData'
import { getGPUHistory } from '@/api/client'
import { useAppStore } from '@/stores/app'
import LineChart from '@/components/LineChart.vue'
import type { GPUHistoryEntry } from '@/types'
import {
  RefreshCw, Monitor, Cpu, Zap,
  Layers, Square, Play, ArrowRightLeft, Star,
  Coins, Activity, Box, MemoryStick,
  Server, HardDrive, AlertTriangle, ShieldCheck,
  ChevronDown, ChevronUp, RotateCw,
} from 'lucide-vue-next'

const store = useAppStore()
const { modelList, defaultModel, actionLoading, handleStartModel, handleStopModel, handleSwitchAndSetDefault, refresh: refreshModels, isRefreshing: isRefreshingModels } = useModels()
const { gpuSummary, refresh: refreshGPU, isRefreshing: isRefreshingGPU } = useGPU()
const { stats: tokenStats, totalTokens, promptTokens, completionTokens, modelStats, formatTokens, refresh: refreshTokens, isRefreshing: isRefreshingTokens } = useTokenStats()
const { systemStatus, queueStatus, healthAlert, loading: systemLoading, refresh: refreshSystem, isRefreshing: isRefreshingSystem } = useSystemData()

const gpuHistory = ref<GPUHistoryEntry[]>([])
const gpuHistoryError = ref<string | null>(null)
const alertExpanded = ref(false)

const isRefreshing = computed(() => isRefreshingModels.value || isRefreshingGPU.value || isRefreshingTokens.value || isRefreshingSystem.value)
const initialLoading = computed(() => isRefreshingModels.value && !modelList.value.length)

async function fetchGPUHistory() {
  try {
    const res = await getGPUHistory(60)
    gpuHistory.value = res?.history ?? []
    gpuHistoryError.value = null
  } catch (err) {
    gpuHistoryError.value = err instanceof Error ? err.message : 'GPU历史数据获取失败'
  }
}

const refreshAll = () => {
  refreshGPU()
  refreshModels()
  refreshTokens()
  refreshSystem()
  fetchGPUHistory()
}

let statsInterval: number | null = null
onMounted(() => {
  fetchGPUHistory()
  statsInterval = window.setInterval(fetchGPUHistory, 30000)
})
onUnmounted(() => {
  if (statsInterval) clearInterval(statsInterval)
})

const gpu = computed(() => gpuSummary.value?.current)
const gpuStatus = computed(() => gpuSummary.value?.status ?? 'unavailable')
const runningModels = computed(() => modelList.value.filter(m => m.running))

const formatBytes = (bytes: number) => {
  if (!bytes) return '0 GB'
  return `${(bytes / (1024 ** 3)).toFixed(1)} GB`
}

const progressColor = (pct: number) => {
  if (pct >= 90) return 'var(--color-danger)'
  if (pct >= 70) return 'var(--color-warning)'
  return 'var(--color-success)'
}

const statusColor = (value: number, warn = 70, danger = 90) => {
  if (value >= danger) return 'danger'
  if (value >= warn) return 'warning'
  return 'success'
}

const formatTimeLabel = (ts: string) => {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const gpuTimeLabels = computed(() => gpuHistory.value.map(e => formatTimeLabel(e.timestamp)))

const sparklineDatasets = (key: keyof GPUHistoryEntry, color: string, bgColor: string) => [{
  label: '',
  data: gpuHistory.value.map(e => Number(e[key]) || 0),
  borderColor: color,
  backgroundColor: bgColor,
  fill: true,
  tension: 0.4,
  pointRadius: 0,
  borderWidth: 2,
}]

const healthStatusColor = (status: string) => {
  if (status === 'healthy') return { bg: 'rgba(34, 197, 94, 0.1)', color: '#22c55e', label: '健康' }
  if (status === 'degraded' || status === 'warning') return { bg: 'rgba(245, 158, 11, 0.1)', color: '#f59e0b', label: '降级' }
  return { bg: 'rgba(239, 68, 68, 0.1)', color: '#ef4444', label: '异常' }
}

const totalQueueRequests = computed(() => {
  if (!queueStatus.value) return 0
  return Object.values(queueStatus.value).reduce((sum, q) => sum + q.active_requests, 0)
})

const handleStartWithToast = async (name: string) => {
  try { await handleStartModel(name); store.success(`模型 ${name} 启动成功`) }
  catch { store.error(`模型 ${name} 启动失败`) }
}
const handleStopWithToast = async (name: string) => {
  try { await handleStopModel(name); store.success(`模型 ${name} 已停止`) }
  catch { store.error(`模型 ${name} 停止失败`) }
}
const handleSwitchWithToast = async (name: string) => {
  try { await handleSwitchAndSetDefault(name); store.success(`已切换到模型 ${name}`) }
  catch { store.error(`切换模型 ${name} 失败`) }
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
          <span v-if="gpuStatus === 'available'" class="badge online"><span class="dot online"></span>在线</span>
          <span v-else class="badge offline"><span class="dot offline"></span>离线</span>
        </div>
        <template v-if="gpu">
          <div class="gpu-name-row">
            <span class="gpu-label">{{ gpu.name }}</span>
            <span class="gpu-vram">{{ formatBytes(gpu.used_memory) }} / {{ formatBytes(gpu.total_memory) }}</span>
          </div>
          <div class="sparkline-row">
            <div class="sparkline-item">
              <span class="spark-label">利用率</span>
              <LineChart :labels="gpuTimeLabels" :datasets="sparklineDatasets('utilization', '#6366f1', 'rgba(99, 102, 241, 0.1)')" :height="60" :show-legend="false" :animate="false" y-unit="%" />
              <span class="spark-val" :class="statusColor(gpu.utilization ?? 0)">{{ (gpu.utilization ?? 0).toFixed(0) }}%</span>
            </div>
            <div class="sparkline-item">
              <span class="spark-label">温度</span>
              <LineChart :labels="gpuTimeLabels" :datasets="sparklineDatasets('temperature', '#f59e0b', 'rgba(245, 158, 11, 0.1)')" :height="60" :show-legend="false" :animate="false" y-unit="°C" />
              <span class="spark-val" :class="statusColor(gpu.temperature ?? 0, 65, 85)">{{ gpu.temperature ?? '--' }}°C</span>
            </div>
            <div class="sparkline-item">
              <span class="spark-label">显存</span>
              <LineChart :labels="gpuTimeLabels" :datasets="sparklineDatasets('memory_utilization', '#06b6d4', 'rgba(6, 182, 212, 0.1)')" :height="60" :show-legend="false" :animate="false" y-unit="%" />
              <span class="spark-val" :class="statusColor(gpu.memory_utilization ?? 0)">{{ (gpu.memory_utilization ?? 0).toFixed(0) }}%</span>
            </div>
          </div>
          <div class="metrics-row">
            <div class="mini-metric">
              <span class="mini-label">功耗</span>
              <span class="mini-val" :class="statusColor(gpu.power_percent ?? 0)">{{ gpu.power_draw ?? 0 }}W</span>
            </div>
            <div class="mini-metric">
              <span class="mini-label">VRAM</span>
              <div class="mini-bar"><div class="mini-fill" :style="{ width: `${gpu.memory_utilization ?? 0}%`, background: progressColor(gpu.memory_utilization ?? 0) }"></div></div>
            </div>
          </div>
        </template>
        <div v-else-if="gpuHistoryError" class="error-state">
          <AlertTriangle class="w-8 h-8" />
          <p>{{ gpuHistoryError }}</p>
          <button class="retry-btn" @click="refreshAll"><RotateCw class="w-3 h-3" /> 重试</button>
        </div>
        <div v-else class="empty-state"><Cpu class="w-10 h-10 text-muted" /><p>GPU 不可用</p></div>
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
            <div class="mt-bar-track"><div class="mt-bar-fill" :style="{ width: `${Math.min(100, (stats.total_tokens / Math.max(totalTokens, 1)) * 100)}%` }"></div></div>
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
              <Cpu class="w-4 h-4" :style="{ color: progressColor(systemStatus.cpu.percent) }" />
              <div class="sys-info">
                <span class="sys-label">CPU</span>
                <div class="sys-bar-track"><div class="sys-bar-fill" :style="{ width: `${systemStatus.cpu.percent}%`, background: progressColor(systemStatus.cpu.percent) }"></div></div>
                <span class="sys-val" :class="statusColor(systemStatus.cpu.percent)">{{ systemStatus.cpu.percent.toFixed(1) }}%</span>
              </div>
              <span class="sys-meta">{{ systemStatus.cpu.cores_physical }}核 / {{ systemStatus.cpu.cores }}线程</span>
            </div>
            <div class="sys-item">
              <MemoryStick class="w-4 h-4" :style="{ color: progressColor(systemStatus.memory.percent) }" />
              <div class="sys-info">
                <span class="sys-label">内存</span>
                <div class="sys-bar-track"><div class="sys-bar-fill" :style="{ width: `${systemStatus.memory.percent}%`, background: progressColor(systemStatus.memory.percent) }"></div></div>
                <span class="sys-val" :class="statusColor(systemStatus.memory.percent)">{{ systemStatus.memory.percent.toFixed(1) }}%</span>
              </div>
              <span class="sys-meta">{{ (systemStatus.memory.used_mb / 1024).toFixed(1) }} / {{ (systemStatus.memory.total_mb / 1024).toFixed(1) }} GB</span>
            </div>
            <div class="sys-item">
              <HardDrive class="w-4 h-4" :style="{ color: progressColor(systemStatus.disk.percent) }" />
              <div class="sys-info">
                <span class="sys-label">磁盘</span>
                <div class="sys-bar-track"><div class="sys-bar-fill" :style="{ width: `${systemStatus.disk.percent}%`, background: progressColor(systemStatus.disk.percent) }"></div></div>
                <span class="sys-val" :class="statusColor(systemStatus.disk.percent)">{{ systemStatus.disk.percent.toFixed(1) }}%</span>
              </div>
              <span class="sys-meta">{{ systemStatus.disk.used_gb }} / {{ systemStatus.disk.total_gb }} GB</span>
            </div>
          </div>
        </template>
        <div v-else class="empty-state"><Server class="w-10 h-10 text-muted" /><p>系统数据不可用</p></div>
      </div>

      <div class="card queue-card card-glow-primary scale-in stagger-4">
        <div class="card-header">
          <div class="icon-wrap primary"><Layers class="card-icon-inner" /></div>
          <span class="card-title">请求队列</span>
          <span v-if="queueStatus" class="count-badge">{{ totalQueueRequests }} 请求</span>
        </div>
        <template v-if="queueStatus">
          <div class="queue-list">
            <div v-for="(entry, name) in queueStatus" :key="name" class="queue-row" :class="{ warning: entry.active_requests > 0 }">
              <span class="q-name">{{ name }}</span>
              <div class="q-info">
                <span class="q-count" :class="entry.active_requests > 0 ? 'warning' : 'success'">{{ entry.active_requests }}</span>
                <span class="q-limit">/ {{ entry.concurrency_limit }}</span>
              </div>
              <span class="q-status" :class="entry.can_accept ? 'success' : 'danger'">{{ entry.can_accept ? '可接受' : '已满' }}</span>
            </div>
          </div>
        </template>
        <div v-else class="empty-state"><Layers class="w-10 h-10 text-muted" /><p>队列数据不可用</p></div>
      </div>

      <div class="card health-card card-glow-green scale-in stagger-5">
        <div class="card-header">
          <div class="icon-wrap green"><ShieldCheck class="card-icon-inner" /></div>
          <span class="card-title">健康告警</span>
          <span v-if="healthAlert" class="badge" :style="{ background: healthStatusColor(healthAlert.status).bg, color: healthStatusColor(healthAlert.status).color }">
            {{ healthStatusColor(healthAlert.status).label }}
          </span>
        </div>
        <template v-if="healthAlert">
          <div class="health-score-row">
            <div class="health-score" :class="healthAlert.health_score >= 70 ? 'good' : healthAlert.health_score >= 50 ? 'degraded' : 'bad'">
              {{ healthAlert.health_score.toFixed(0) }}
            </div>
            <div class="health-score-bar">
              <div class="hs-fill" :style="{ width: `${healthAlert.health_score}%`, background: healthAlert.health_score >= 70 ? '#22c55e' : healthAlert.health_score >= 50 ? '#f59e0b' : '#ef4444' }"></div>
            </div>
          </div>
          <div v-if="healthAlert.alert_reasons?.length" class="alert-reasons">
            <button class="alert-toggle" @click="alertExpanded = !alertExpanded">
              <AlertTriangle class="w-4 h-4" :style="{ color: healthAlert.should_alert ? '#f59e0b' : '#22c55e' }" />
              <span>{{ healthAlert.alert_reasons.length }} 条告警</span>
              <ChevronDown v-if="!alertExpanded" class="w-3 h-3" />
              <ChevronUp v-else class="w-3 h-3" />
            </button>
            <div v-if="alertExpanded" class="alert-list">
              <div v-for="(reason, idx) in healthAlert.alert_reasons" :key="idx" class="alert-item">
                <span class="alert-dot" :class="healthAlert.should_alert ? 'warning' : 'info'"></span>
                <span>{{ reason }}</span>
              </div>
            </div>
          </div>
        </template>
        <div v-else class="empty-state"><ShieldCheck class="w-10 h-10 text-muted" /><p>健康数据不可用</p></div>
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
              <span class="model-meta">端口 {{ model.port }} · {{ model.active_requests }} 请求</span>
            </div>
            <div class="model-actions">
              <span v-if="defaultModel === model.name" class="default-tag"><Star class="w-3 h-3" /> 默认</span>
              <button class="action-btn stop" @click="handleStopWithToast(model.name)" :disabled="!!actionLoading"><Square class="w-3 h-3" /> 停止</button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">暂无运行模型</div>
      </div>

      <div class="card model-list-card card-glow-primary scale-in stagger-7">
        <div class="card-header">
          <div class="icon-wrap primary"><Box class="card-icon-inner" /></div>
          <span class="card-title">模型列表</span>
        </div>
        <div v-if="modelList.length" class="model-table">
          <div class="table-row" v-for="model in modelList" :key="model.name" :class="{ running: model.running }">
            <div class="col-name">
              <span class="dot" :class="model.running ? 'online' : 'offline'"></span>
              <span>{{ model.name }}</span>
              <Star v-if="defaultModel === model.name" class="w-3 h-3 star-icon" />
            </div>
            <div class="col-action">
              <template v-if="model.running">
                <button class="action-btn small" @click="handleStopWithToast(model.name)" :disabled="!!actionLoading"><Square class="w-3 h-3" /></button>
              </template>
              <template v-else>
                <button class="action-btn small primary" @click="handleSwitchWithToast(model.name)" :disabled="!!actionLoading"><ArrowRightLeft class="w-3 h-3" /> 切换</button>
                <button class="action-btn small" @click="handleStartWithToast(model.name)" :disabled="!!actionLoading"><Play class="w-3 h-3" /></button>
              </template>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">暂无可用模型</div>
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

.header-title { font-size: 18px; font-weight: 600; color: var(--text-primary); letter-spacing: -0.3px; }

.header-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500;
  color: var(--text-muted); background: var(--bg-secondary);
  border: 1px solid var(--border-primary); cursor: pointer; transition: all 0.25s;
}
.header-btn:hover { background: var(--color-primary); color: #fff; border-color: var(--color-primary); box-shadow: 0 2px 12px rgba(99, 102, 241, 0.3); }

.grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  padding: 16px 24px;
  align-content: start;
}
@media (max-width: 1200px) { .grid { grid-template-columns: repeat(2, 1fr); } }
@media (max-width: 768px) { .grid { grid-template-columns: 1fr; } }

.skeleton-card { display: flex; flex-direction: column; gap: 14px; padding: 24px; }
.skeleton-line {
  height: 14px; background: var(--bg-tertiary); border-radius: 4px;
  animation: skeleton-pulse 1.5s ease-in-out infinite;
}
@keyframes skeleton-pulse { 0%, 100% { opacity: 0.4; } 50% { opacity: 1; } }

.card {
  background: var(--bg-card); border-radius: 14px;
  border: 1px solid var(--border-card); padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3), 0 0 1px rgba(99, 102, 241, 0.1);
  transition: box-shadow 0.3s ease, transform 0.2s ease, border-color 0.3s ease;
  position: relative; overflow: hidden;
}
.card::before {
  content: ''; position: absolute; top: 0; left: 0; right: 0;
  height: 2px; background: linear-gradient(90deg, transparent, var(--color-primary), transparent);
  opacity: 0; transition: opacity 0.3s;
}
.card:hover::before { opacity: 0.5; }
.card:hover {
  box-shadow: 0 6px 24px rgba(0, 0, 0, 0.4), 0 0 12px rgba(99, 102, 241, 0.08);
  transform: translateY(-2px); border-color: rgba(99, 102, 241, 0.2);
}

.card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.icon-wrap {
  width: 32px; height: 32px; border-radius: 10px;
  display: flex; align-items: center; justify-content: center;
  transition: transform 0.2s;
}
.card:hover .icon-wrap { transform: scale(1.1); }
.icon-wrap.primary { background: rgba(99, 102, 241, 0.12); }
.icon-wrap.green { background: rgba(34, 197, 94, 0.12); }
.icon-wrap.purple { background: rgba(139, 92, 246, 0.12); }
.icon-wrap.cyan { background: rgba(6, 182, 212, 0.12); }
.icon-wrap.orange { background: rgba(245, 158, 11, 0.12); }
.icon-wrap.red { background: rgba(239, 68, 68, 0.12); }
.card-icon-inner { width: 16px; height: 16px; }
.icon-wrap.primary .card-icon-inner { color: #6366f1; }
.icon-wrap.green .card-icon-inner { color: #22c55e; }
.icon-wrap.purple .card-icon-inner { color: #8b5cf6; }
.icon-wrap.cyan .card-icon-inner { color: #06b6d4; }
.icon-wrap.orange .card-icon-inner { color: #f59e0b; }
.icon-wrap.red .card-icon-inner { color: #ef4444; }
.card-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }

.badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; margin-left: auto; }
.badge.online { background: rgba(34, 197, 94, 0.1); color: #059669; }
.badge.offline { background: rgba(239, 68, 68, 0.1); color: #dc2626; }

.dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.dot.online { background: #22c55e; box-shadow: 0 0 6px rgba(34, 197, 94, 0.5); }
.dot.offline { background: #6b7280; }

.count-badge { margin-left: auto; font-size: 12px; color: var(--text-muted); background: var(--bg-secondary); padding: 2px 8px; border-radius: 10px; }

.error-state { text-align: center; color: var(--text-muted); padding: 24px 0; font-size: 13px; display: flex; flex-direction: column; align-items: center; gap: 8px; }
.retry-btn { display: inline-flex; align-items: center; gap: 4px; padding: 4px 12px; border-radius: 6px; font-size: 12px; color: var(--text-primary); background: var(--bg-secondary); border: 1px solid var(--border-primary); cursor: pointer; }

.empty-state { text-align: center; color: var(--text-muted); padding: 32px 0; font-size: 13px; display: flex; flex-direction: column; align-items: center; gap: 10px; }

.gpu-name-row { display: flex; justify-content: space-between; align-items: baseline; }
.gpu-label { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.gpu-vram { font-size: 12px; color: var(--text-muted); }

.sparkline-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }
.sparkline-item { display: flex; flex-direction: column; gap: 4px; }
.spark-label { font-size: 11px; color: var(--text-muted); }
.spark-val { font-size: 13px; font-weight: 600; }
.spark-val.success { color: #22c55e; }
.spark-val.warning { color: #f59e0b; }
.spark-val.danger { color: #ef4444; }

.metrics-row { display: flex; gap: 12px; margin-top: 12px; }
.mini-metric { flex: 1; display: flex; flex-direction: column; gap: 4px; padding: 12px; background: var(--bg-secondary); border-radius: 10px; border: 1px solid transparent; transition: border-color 0.2s; }
.mini-metric:hover { border-color: var(--border-primary); }
.mini-label { font-size: 12px; color: var(--text-muted); }
.mini-val { font-size: 14px; font-weight: 700; }
.mini-val.success { color: #22c55e; }
.mini-val.warning { color: #f59e0b; }
.mini-val.danger { color: #ef4444; }
.mini-bar { height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; margin-top: 4px; }
.mini-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

.token-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.token-item { display: flex; align-items: center; gap: 10px; padding: 12px; background: var(--bg-secondary); border-radius: 10px; border: 1px solid transparent; transition: border-color 0.2s, transform 0.2s; }
.token-item:hover { border-color: var(--border-primary); transform: translateY(-1px); }
.token-info { display: flex; flex-direction: column; gap: 2px; }
.token-value { font-size: 18px; font-weight: 700; color: var(--text-primary); }
.token-label { font-size: 11px; color: var(--text-muted); }

.model-token-list { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.model-token-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.mt-name { font-size: 12px; color: var(--text-secondary); min-width: 100px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mt-bar-track { flex: 1; height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
.mt-bar-fill { height: 100%; background: linear-gradient(90deg, #6366f1, #4f46e5); border-radius: 2px; transition: width 0.5s ease; min-width: 2px; }
.mt-count { font-size: 11px; color: var(--text-muted); min-width: 40px; text-align: right; }

.system-grid { display: flex; flex-direction: column; gap: 12px; }
.sys-item { display: flex; align-items: center; gap: 10px; padding: 12px; background: var(--bg-secondary); border-radius: 10px; border: 1px solid transparent; transition: border-color 0.2s, transform 0.2s; }
.sys-item:hover { border-color: var(--border-primary); transform: translateX(2px); }
.sys-info { flex: 1; display: flex; flex-direction: column; gap: 2px; }
.sys-label { font-size: 12px; color: var(--text-muted); }
.sys-bar-track { height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
.sys-bar-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }
.sys-val { font-size: 14px; font-weight: 700; }
.sys-val.success { color: #22c55e; }
.sys-val.warning { color: #f59e0b; }
.sys-val.danger { color: #ef4444; }
.sys-meta { font-size: 11px; color: var(--text-muted); white-space: nowrap; }

.queue-list { display: flex; flex-direction: column; gap: 8px; }
.queue-row { display: flex; align-items: center; justify-content: space-between; padding: 10px 12px; background: var(--bg-secondary); border-radius: 10px; font-size: 13px; border: 1px solid transparent; transition: border-color 0.2s; }
.queue-row:hover { border-color: var(--border-primary); }
.queue-row.warning { border-left: 3px solid #f59e0b; background: rgba(245, 158, 11, 0.03); }
.q-name { font-weight: 500; color: var(--text-primary); min-width: 80px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.q-info { display: flex; align-items: baseline; gap: 2px; }
.q-count { font-weight: 700; }
.q-count.success { color: #22c55e; }
.q-count.warning { color: #f59e0b; }
.q-limit { font-size: 12px; color: var(--text-muted); }
.q-status { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.q-status.success { background: rgba(34, 197, 94, 0.1); color: #22c55e; }
.q-status.danger { background: rgba(239, 68, 68, 0.1); color: #ef4444; }

.health-score-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.health-score { font-size: 32px; font-weight: 800; min-width: 52px; }
.health-score.good { color: #22c55e; }
.health-score.degraded { color: #f59e0b; }
.health-score.bad { color: #ef4444; }
.health-score-bar { flex: 1; height: 8px; background: var(--bg-tertiary); border-radius: 4px; overflow: hidden; }
.hs-fill { height: 100%; border-radius: 3px; transition: width 0.5s ease; }

.alert-toggle { display: flex; align-items: center; gap: 6px; padding: 6px 10px; border-radius: 6px; font-size: 12px; color: var(--text-secondary); background: var(--bg-secondary); border: 1px solid var(--border-primary); cursor: pointer; width: 100%; }
.alert-list { display: flex; flex-direction: column; gap: 6px; margin-top: 8px; }
.alert-item { display: flex; align-items: center; gap: 8px; padding: 6px 12px; background: var(--bg-secondary); border-radius: 6px; font-size: 12px; color: var(--text-secondary); }
.alert-dot { width: 6px; height: 6px; border-radius: 50%; }
.alert-dot.warning { background: #f59e0b; }
.alert-dot.info { background: #3b82f6; }

.running-list { display: flex; flex-direction: column; gap: 8px; }
.model-row { display: flex; align-items: center; justify-content: space-between; padding: 12px 14px; background: var(--bg-secondary); border-radius: 10px; border-left: 3px solid #22c55e; transition: transform 0.2s, box-shadow 0.2s; }
.model-row:hover { transform: translateX(4px); box-shadow: 0 2px 8px rgba(99, 102, 241, 0.1); }
.model-info { display: flex; flex-direction: column; gap: 2px; }
.model-name { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.model-meta { font-size: 12px; color: var(--text-muted); }
.model-actions { display: flex; align-items: center; gap: 8px; }
.default-tag { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #f59e0b; background: rgba(245, 158, 11, 0.1); padding: 2px 8px; border-radius: 4px; }

.action-btn { display: inline-flex; align-items: center; gap: 4px; padding: 5px 12px; border-radius: 8px; font-size: 12px; font-weight: 500; border: 1px solid var(--border-primary); background: var(--bg-card); color: var(--text-primary); cursor: pointer; transition: all 0.25s; }
.action-btn:hover:not(:disabled) { border-color: var(--border-secondary); transform: translateY(-1px); }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.action-btn.stop { color: #ef4444; border-color: rgba(239, 68, 68, 0.3); }
.action-btn.stop:hover:not(:disabled) { background: rgba(239, 68, 68, 0.1); }
.action-btn.primary { color: #22c55e; border-color: rgba(34, 197, 94, 0.3); }
.action-btn.primary:hover:not(:disabled) { background: rgba(34, 197, 94, 0.1); }
.action-btn.small { padding: 3px 6px; border-radius: 4px; }

.model-table { display: flex; flex-direction: column; gap: 4px; }
.table-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--bg-secondary); border-radius: 8px; font-size: 13px; }
.table-row.running { background: rgba(34, 197, 94, 0.04); border-left: 3px solid #22c55e; }
.col-name { display: flex; align-items: center; gap: 6px; font-weight: 500; color: var(--text-primary); }
.col-action { display: flex; align-items: center; gap: 4px; }
.star-icon { color: #f59e0b; }

.grid::-webkit-scrollbar { width: 4px; }
.grid::-webkit-scrollbar-track { background: transparent; }
.grid::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 2px; }
</style>
