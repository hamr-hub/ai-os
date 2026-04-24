<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useGPU } from '@/composables/useGPU'
import { useModels } from '@/composables/useModels'
import { getTokenStats, getGPUHistory } from '@/api/client'
import LineChart from '@/components/LineChart.vue'
import type { TokenStats, GPUHistoryEntry } from '@/types'
import {
  RefreshCw,
  Monitor,
  Cpu,
  Thermometer,
  Zap,
  Coins,
  TrendingUp,
  Activity,
  MemoryStick,
  Clock,
} from 'lucide-vue-next'

const { gpuSummary, refresh: refreshGPU, isRefreshing: isRefreshingGPU } = useGPU()
const { modelList, refresh: refreshModels, isRefreshing: isRefreshingModels } = useModels()

const isRefreshing = computed(() => isRefreshingModels.value || isRefreshingGPU.value)
const gpu = computed(() => gpuSummary.value?.current)
const gpuStatus = computed(() => gpuSummary.value?.status ?? 'unavailable')
const runningModels = computed(() => modelList.value.filter(m => m.running))

const tokenStats = ref<TokenStats | null>(null)
const gpuHistory = ref<GPUHistoryEntry[]>([])
const tokenHistory = ref<Array<{ timestamp: string; total: number; prompt: number; completion: number }>>([])

const timeRange = ref<'1m' | '5m' | '15m' | '1h' | '6h'>(1 > 0 ? '1m' : '1m')
const timeRangeOptions = [
  { value: '1m' as const, label: '1分钟', count: 20 },
  { value: '5m' as const, label: '5分钟', count: 100 },
  { value: '15m' as const, label: '15分钟', count: 300 },
  { value: '1h' as const, label: '1小时', count: 1200 },
  { value: '6h' as const, label: '6小时', count: 7200 },
]

const historyCount = computed(() => {
  const opt = timeRangeOptions.find(o => o.value === timeRange.value)
  return opt?.count ?? 60
})

const refreshAll = () => {
  refreshGPU()
  refreshModels()
  fetchTokenStats()
  fetchGPUHistory()
}

async function fetchTokenStats() {
  try {
    const stats = await getTokenStats()
    tokenStats.value = stats
    tokenHistory.value.push({
      timestamp: stats.timestamp ?? new Date().toISOString(),
      total: stats.total_tokens,
      prompt: stats.total_prompt_tokens,
      completion: stats.total_completion_tokens,
    })
    if (tokenHistory.value.length > 300) {
      tokenHistory.value = tokenHistory.value.slice(-300)
    }
  } catch {}
}

async function fetchGPUHistory() {
  try {
    const res = await getGPUHistory(historyCount.value)
    gpuHistory.value = res?.history ?? []
  } catch {}
}

let statsInterval: number | null = null
onMounted(() => {
  fetchTokenStats()
  fetchGPUHistory()
  statsInterval = window.setInterval(() => {
    fetchTokenStats()
    fetchGPUHistory()
  }, 30000)
})
onUnmounted(() => {
  if (statsInterval) clearInterval(statsInterval)
})

const formatTimeLabel = (ts: string) => {
  if (!ts) return ''
  const d = new Date(ts)
  return d.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

const formatBytes = (bytes: number) => {
  if (!bytes) return '0 GB'
  return `${(bytes / (1024 ** 3)).toFixed(1)} GB`
}

const formatTokens = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

const gpuTimeLabels = computed(() => gpuHistory.value.map(e => formatTimeLabel(e.timestamp)))
const tokenTimeLabels = computed(() => tokenHistory.value.map(e => formatTimeLabel(e.timestamp)))

const gpuUtilDataset = computed(() => [{
  label: 'GPU 利用率',
  data: gpuHistory.value.map(e => e.utilization),
  borderColor: '#6366f1',
  backgroundColor: 'rgba(99, 102, 241, 0.08)',
  fill: true,
  tension: 0.4,
  pointRadius: 0,
  borderWidth: 2,
}])

const gpuTempDataset = computed(() => [{
  label: 'GPU 温度',
  data: gpuHistory.value.map(e => e.temperature),
  borderColor: '#f59e0b',
  backgroundColor: 'rgba(245, 158, 11, 0.08)',
  fill: true,
  tension: 0.4,
  pointRadius: 0,
  borderWidth: 2,
}])

const gpuMemDataset = computed(() => [{
  label: '显存利用率',
  data: gpuHistory.value.map(e => e.memory_utilization),
  borderColor: '#06b6d4',
  backgroundColor: 'rgba(6, 182, 212, 0.08)',
  fill: true,
  tension: 0.4,
  pointRadius: 0,
  borderWidth: 2,
}])

const gpuPowerDataset = computed(() => [{
  label: '功耗',
  data: gpuHistory.value.map(e => e.power_percent ?? e.power_draw),
  borderColor: '#ef4444',
  backgroundColor: 'rgba(239, 68, 68, 0.08)',
  fill: true,
  tension: 0.4,
  pointRadius: 0,
  borderWidth: 2,
}])

const tokenTotalDataset = computed(() => [
  {
    label: 'Total Tokens',
    data: tokenHistory.value.map(e => e.total),
    borderColor: '#8b5cf6',
    backgroundColor: 'rgba(139, 92, 246, 0.08)',
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 2,
  },
  {
    label: 'Prompt Tokens',
    data: tokenHistory.value.map(e => e.prompt),
    borderColor: '#3b82f6',
    backgroundColor: 'rgba(59, 130, 246, 0.05)',
    fill: false,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 1.5,
  },
  {
    label: 'Completion Tokens',
    data: tokenHistory.value.map(e => e.completion),
    borderColor: '#22c55e',
    backgroundColor: 'rgba(34, 197, 94, 0.05)',
    fill: false,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 1.5,
  },
])

const gpuMultiDataset = computed(() => [
  {
    label: '利用率 (%)',
    data: gpuHistory.value.map(e => e.utilization),
    borderColor: '#6366f1',
    backgroundColor: 'rgba(99, 102, 241, 0.08)',
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 2,
  },
  {
    label: '温度 (°C)',
    data: gpuHistory.value.map(e => e.temperature),
    borderColor: '#f59e0b',
    backgroundColor: 'rgba(245, 158, 11, 0.05)',
    fill: false,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 1.5,
  },
  {
    label: '显存 (%)',
    data: gpuHistory.value.map(e => e.memory_utilization),
    borderColor: '#06b6d4',
    backgroundColor: 'rgba(6, 182, 212, 0.05)',
    fill: false,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 1.5,
  },
])

const statusColor = (value: number, warn = 70, danger = 90) => {
  if (value >= danger) return 'danger'
  if (value >= warn) return 'warning'
  return 'success'
}

const changeTimeRange = (range: '1m' | '5m' | '15m' | '1h' | '6h') => {
  timeRange.value = range
  fetchGPUHistory()
}
</script>

<template>
  <div class="monitor-view">
    <header class="header">
      <div class="header-left">
        <Monitor class="header-icon" />
        <h1 class="header-title">实时监控</h1>
        <span v-if="gpuStatus === 'available'" class="badge online"><span class="dot online"></span>在线</span>
        <span v-else class="badge offline"><span class="dot offline"></span>离线</span>
      </div>
      <div class="header-right">
        <div class="time-range-btns">
          <button
            v-for="opt in timeRangeOptions"
            :key="opt.value"
            class="range-btn"
            :class="{ active: timeRange === opt.value }"
            @click="changeTimeRange(opt.value)"
          >{{ opt.label }}</button>
        </div>
        <button class="header-btn" @click="refreshAll">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
          <span>刷新</span>
        </button>
      </div>
    </header>

    <div class="content">
      <div class="chart-section">
        <div class="card chart-card wide">
          <div class="card-header">
            <Cpu class="card-icon" />
            <span class="card-title">GPU 综合监控</span>
            <span class="live-tag">LIVE</span>
          </div>
          <LineChart
            :labels="gpuTimeLabels"
            :datasets="gpuMultiDataset"
            :height="280"
            y-unit=""
            :show-legend="true"
          />
        </div>

        <div class="card chart-card">
          <div class="card-header">
            <Thermometer class="card-icon warm" />
            <span class="card-title">GPU 温度趋势</span>
          </div>
          <LineChart
            :labels="gpuTimeLabels"
            :datasets="gpuTempDataset"
            :height="180"
            y-unit="°C"
            :y-min="0"
            :y-max="100"
          />
        </div>

        <div class="card chart-card">
          <div class="card-header">
            <Zap class="card-icon power" />
            <span class="card-title">功耗趋势</span>
          </div>
          <LineChart
            :labels="gpuTimeLabels"
            :datasets="gpuPowerDataset"
            :height="180"
            y-unit="W"
            :y-min="0"
          />
        </div>
      </div>

      <div class="chart-section">
        <div class="card chart-card">
          <div class="card-header">
            <Activity class="card-icon blue" />
            <span class="card-title">GPU 利用率</span>
          </div>
          <LineChart
            :labels="gpuTimeLabels"
            :datasets="gpuUtilDataset"
            :height="180"
            y-unit="%"
            :y-min="0"
            :y-max="100"
          />
        </div>

        <div class="card chart-card">
          <div class="card-header">
            <MemoryStick class="card-icon cyan" />
            <span class="card-title">显存利用率</span>
          </div>
          <LineChart
            :labels="gpuTimeLabels"
            :datasets="gpuMemDataset"
            :height="180"
            y-unit="%"
            :y-min="0"
            :y-max="100"
          />
        </div>

        <div class="card chart-card wide">
          <div class="card-header">
            <Coins class="card-icon purple" />
            <span class="card-title">Token 用量趋势</span>
            <span v-if="tokenStats" class="count-badge">{{ formatTokens(tokenStats.total_tokens) }}</span>
          </div>
          <LineChart
            :labels="tokenTimeLabels"
            :datasets="tokenTotalDataset"
            :height="220"
            y-unit=""
            :show-legend="true"
          />
        </div>
      </div>

      <div class="stats-section">
        <div class="card stats-card">
          <div class="card-header">
            <Monitor class="card-icon" />
            <span class="card-title">GPU 实时指标</span>
          </div>
          <div v-if="gpu" class="stats-grid">
            <div class="stat-item">
              <Cpu class="stat-icon" />
              <span class="stat-label">利用率</span>
              <span class="stat-val" :class="statusColor(gpu.utilization ?? 0)">{{ (gpu.utilization ?? 0).toFixed(1) }}%</span>
            </div>
            <div class="stat-item">
              <Thermometer class="stat-icon" />
              <span class="stat-label">温度</span>
              <span class="stat-val" :class="statusColor(gpu.temperature ?? 0, 65, 85)">{{ gpu.temperature ?? '--' }}°C</span>
            </div>
            <div class="stat-item">
              <MemoryStick class="stat-icon" />
              <span class="stat-label">显存</span>
              <span class="stat-val" :class="statusColor(gpu.memory_utilization ?? 0)">{{ (gpu.memory_utilization ?? 0).toFixed(1) }}%</span>
            </div>
            <div class="stat-item">
              <Zap class="stat-icon" />
              <span class="stat-label">功耗</span>
              <span class="stat-val">{{ gpu.power_draw ?? 0 }}W / {{ gpu.power_limit ?? 0 }}W</span>
            </div>
            <div class="stat-item">
              <TrendingUp class="stat-icon" />
              <span class="stat-label">VRAM</span>
              <span class="stat-val">{{ formatBytes(gpu.used_memory) }} / {{ formatBytes(gpu.total_memory) }}</span>
            </div>
            <div class="stat-item">
              <Activity class="stat-icon" />
              <span class="stat-label">运行模型</span>
              <span class="stat-val">{{ runningModels.length }} / {{ modelList.length }}</span>
            </div>
          </div>
          <div v-else class="empty-state">GPU 不可用</div>
        </div>

        <div class="card stats-card">
          <div class="card-header">
            <Coins class="card-icon purple" />
            <span class="card-title">Token 统计</span>
          </div>
          <div v-if="tokenStats" class="token-detail">
            <div class="token-row">
              <TrendingUp class="w-4 h-4 text-blue-400" />
              <span class="token-label">Prompt</span>
              <span class="token-val">{{ formatTokens(tokenStats.total_prompt_tokens) }}</span>
            </div>
            <div class="token-row">
              <Activity class="w-4 h-4 text-green-400" />
              <span class="token-label">Completion</span>
              <span class="token-val">{{ formatTokens(tokenStats.total_completion_tokens) }}</span>
            </div>
            <div class="token-row">
              <Coins class="w-4 h-4 text-purple-400" />
              <span class="token-label">Total</span>
              <span class="token-val primary">{{ formatTokens(tokenStats.total_tokens) }}</span>
            </div>
            <div v-if="Object.keys(tokenStats.models).length" class="model-breakdown">
              <h4 class="breakdown-title">各模型用量</h4>
              <div v-for="(stats, name) in tokenStats.models" :key="name" class="model-row">
                <span class="m-name">{{ name }}</span>
                <div class="m-bar"><div class="m-fill" :style="{ width: `${Math.min(100, (stats.total_tokens / Math.max(tokenStats.total_tokens, 1)) * 100)}%` }"></div></div>
                <span class="m-count">{{ formatTokens(stats.total_tokens) }}</span>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">暂无统计</div>
        </div>

        <div class="card stats-card">
          <div class="card-header">
            <Clock class="card-icon" />
            <span class="card-title">运行模型</span>
          </div>
          <div v-if="runningModels.length" class="running-list">
            <div v-for="model in runningModels" :key="model.name" class="run-item">
              <span class="dot online"></span>
              <span class="run-name">{{ model.name }}</span>
              <span class="run-meta">端口 {{ model.port }} · {{ model.active_requests }} 请求</span>
            </div>
          </div>
          <div v-else class="empty-state">暂无运行模型</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.monitor-view {
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

.header-left { display: flex; align-items: center; gap: 8px; }
.header-icon { width: 18px; height: 18px; color: var(--text-muted); }
.header-title { font-size: 18px; font-weight: 600; color: var(--text-primary); }

.header-right { display: flex; align-items: center; gap: 12px; }

.time-range-btns { display: flex; gap: 4px; }
.range-btn {
  padding: 4px 10px; border-radius: 6px; font-size: 12px;
  color: var(--text-muted); background: var(--bg-secondary);
  border: 1px solid var(--border-primary); cursor: pointer; transition: all 0.2s;
}
.range-btn.active {
  color: #fff; background: var(--color-primary);
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
}
.range-btn:hover:not(.active) { color: var(--text-primary); border-color: var(--border-secondary); }

.header-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 8px; font-size: 13px; font-weight: 500;
  color: var(--text-muted); background: var(--bg-secondary);
  border: 1px solid var(--border-primary); cursor: pointer; transition: all 0.25s;
}
.header-btn:hover { background: var(--color-primary); color: #fff; border-color: var(--color-primary); box-shadow: 0 2px 12px rgba(99, 102, 241, 0.3); }

.badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; }
.badge.online { background: rgba(34, 197, 94, 0.1); color: #059669; }
.badge.offline { background: rgba(239, 68, 68, 0.1); color: #dc2626; }
.dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.dot.online { background: #22c55e; box-shadow: 0 0 6px rgba(34, 197, 94, 0.5); }
.dot.offline { background: #6b7280; }

.content {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 16px;
  padding: 16px 24px;
}

.chart-section {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.card {
  background: var(--bg-card); border-radius: 14px;
  border: 1px solid var(--border-card); padding: 20px;
  box-shadow: var(--shadow);
  transition: all 0.3s ease;
  animation: fade-in 0.4s ease-out;
  position: relative;
  overflow: hidden;
}
.card::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--color-primary), transparent);
  opacity: 0;
  transition: opacity 0.3s;
}
.card:hover::before { opacity: 0.5; }
.card:hover {
  border-color: rgba(99, 102, 241, 0.25);
  box-shadow: var(--shadow-md), 0 0 12px rgba(99, 102, 241, 0.08);
  transform: translateY(-1px);
}

.card-header { display: flex; align-items: center; gap: 10px; margin-bottom: 16px; }
.card-icon { width: 18px; height: 18px; color: var(--color-primary); filter: drop-shadow(0 0 4px rgba(99, 102, 241, 0.3)); transition: transform 0.2s; }
.card:hover .card-icon { transform: scale(1.1); }
.card-icon.warm { color: #f59e0b; }
.card-icon.power { color: #ef4444; }
.card-icon.blue { color: #3b82f6; }
.card-icon.cyan { color: #06b6d4; }
.card-icon.purple { color: #8b5cf6; }
.card-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }

.live-tag {
  margin-left: auto;
  padding: 2px 8px; border-radius: 4px; font-size: 10px; font-weight: 700;
  color: #22c55e; background: rgba(34, 197, 94, 0.15);
  border: 1px solid rgba(34, 197, 94, 0.3);
  animation: pulse 2s ease-in-out infinite;
  box-shadow: 0 0 8px rgba(34, 197, 94, 0.2);
}

.count-badge { margin-left: auto; font-size: 12px; color: var(--text-muted); background: var(--bg-secondary); padding: 2px 8px; border-radius: 10px; }

.chart-card.wide { grid-column: span 2; }

.stats-section {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.stats-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.stat-item {
  display: flex; flex-direction: column; align-items: center; gap: 4px;
  padding: 12px; background: var(--bg-secondary); border-radius: 8px;
  border: 1px solid transparent; transition: all 0.2s;
}
.stat-item:hover { border-color: var(--border-primary); transform: translateY(-1px); }
.stat-icon { width: 16px; height: 16px; color: var(--text-muted); }
.stat-label { font-size: 12px; color: var(--text-muted); }
.stat-val { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.stat-val.success { color: #22c55e; }
.stat-val.warning { color: #f59e0b; }
.stat-val.danger { color: #ef4444; }

.token-detail { display: flex; flex-direction: column; gap: 10px; }
.token-row {
  display: flex; align-items: center; gap: 8px;
  padding: 10px; background: var(--bg-secondary); border-radius: 8px;
}
.token-label { font-size: 13px; color: var(--text-muted); }
.token-val { font-size: 14px; font-weight: 600; color: var(--text-primary); margin-left: auto; }
.token-val.primary { color: #8b5cf6; }

.model-breakdown { margin-top: 8px; }
.breakdown-title { font-size: 12px; font-weight: 600; color: var(--text-secondary); margin-bottom: 8px; }
.model-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.m-name { font-size: 12px; color: var(--text-secondary); min-width: 80px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.m-bar { flex: 1; height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
.m-fill { height: 100%; background: linear-gradient(90deg, #8b5cf6, #7c3aed); border-radius: 2px; transition: width 0.5s ease; min-width: 2px; }
.m-count { font-size: 11px; color: var(--text-muted); min-width: 40px; text-align: right; }

.running-list { display: flex; flex-direction: column; gap: 8px; }
.run-item {
  display: flex; align-items: center; gap: 8px;
  padding: 10px 12px; background: var(--bg-secondary); border-radius: 8px;
  border-left: 3px solid #22c55e;
}
.run-name { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.run-meta { font-size: 12px; color: var(--text-muted); margin-left: auto; }

.empty-state { text-align: center; color: var(--text-muted); padding: 24px 0; font-size: 13px; }

.content::-webkit-scrollbar { width: 4px; }
.content::-webkit-scrollbar-track { background: transparent; }
.content::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 2px; }

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.6; }
}
</style>
