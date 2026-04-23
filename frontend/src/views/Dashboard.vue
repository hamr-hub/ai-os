<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import { getTokenStats, getGPUHistory } from '@/api/client'
import LineChart from '@/components/LineChart.vue'
import type { TokenStats, GPUHistoryEntry } from '@/types'
import {
  RefreshCw,
  Monitor,
  Cpu,
  Thermometer,
  Zap,
  Layers,
  Square,
  Play,
  ArrowRightLeft,
  Star,
  Coins,
  TrendingUp,
  Activity,
  Box,
  MemoryStick,
} from 'lucide-vue-next'

const { modelList, defaultModel, actionLoading, handleStartModel, handleStopModel, handleSwitchAndSetDefault, refresh: refreshModels, isRefreshing: isRefreshingModels } = useModels()
const { gpuSummary, refresh: refreshGPU, isRefreshing: isRefreshingGPU } = useGPU()

const isRefreshing = computed(() => isRefreshingModels.value || isRefreshingGPU.value)

const tokenStats = ref<TokenStats | null>(null)
const gpuHistory = ref<GPUHistoryEntry[]>([])

const refreshAll = () => {
  refreshGPU()
  refreshModels()
  fetchTokenStats()
  fetchGPUHistory()
}

async function fetchTokenStats() {
  try {
    tokenStats.value = await getTokenStats()
  } catch {}
}

async function fetchGPUHistory() {
  try {
    const res = await getGPUHistory(60)
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
  }, 10000)
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

const formatTokens = (n: number) => {
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
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

const totalTokens = computed(() => tokenStats.value?.total_tokens ?? 0)
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

    <div class="grid">
      <div class="card gpu-card">
        <div class="card-header">
          <Monitor class="card-icon" />
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
              <LineChart
                :labels="gpuTimeLabels"
                :datasets="sparklineDatasets('utilization', '#6366f1', 'rgba(99, 102, 241, 0.1)')"
                :height="60"
                :show-legend="false"
                :animate="false"
                y-unit="%"
              />
              <span class="spark-val" :class="statusColor(gpu.utilization ?? 0)">{{ (gpu.utilization ?? 0).toFixed(0) }}%</span>
            </div>
            <div class="sparkline-item">
              <span class="spark-label">温度</span>
              <LineChart
                :labels="gpuTimeLabels"
                :datasets="sparklineDatasets('temperature', '#f59e0b', 'rgba(245, 158, 11, 0.1)')"
                :height="60"
                :show-legend="false"
                :animate="false"
                y-unit="°C"
              />
              <span class="spark-val" :class="statusColor(gpu.temperature ?? 0, 65, 85)">{{ gpu.temperature ?? '--' }}°C</span>
            </div>
            <div class="sparkline-item">
              <span class="spark-label">显存</span>
              <LineChart
                :labels="gpuTimeLabels"
                :datasets="sparklineDatasets('memory_utilization', '#06b6d4', 'rgba(6, 182, 212, 0.1)')"
                :height="60"
                :show-legend="false"
                :animate="false"
                y-unit="%"
              />
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
        <div v-else class="empty-state"><Cpu class="w-10 h-10 text-muted" /><p>GPU 不可用</p></div>
      </div>

      <div class="card token-card">
        <div class="card-header">
          <Coins class="card-icon" />
          <span class="card-title">Token 用量</span>
          <span v-if="tokenStats" class="count-badge">{{ formatTokens(totalTokens) }}</span>
        </div>
        <div v-if="tokenStats" class="token-grid">
          <div class="token-item">
            <TrendingUp class="w-4 h-4 text-blue-400" />
            <div class="token-info">
              <span class="token-value">{{ formatTokens(tokenStats.total_prompt_tokens) }}</span>
              <span class="token-label">Prompt</span>
            </div>
          </div>
          <div class="token-item">
            <Activity class="w-4 h-4 text-green-400" />
            <div class="token-info">
              <span class="token-value">{{ formatTokens(tokenStats.total_completion_tokens) }}</span>
              <span class="token-label">Completion</span>
            </div>
          </div>
          <div class="token-item">
            <Coins class="w-4 h-4 text-purple-400" />
            <div class="token-info">
              <span class="token-value">{{ formatTokens(tokenStats.total_tokens) }}</span>
              <span class="token-label">Total</span>
            </div>
          </div>
        </div>
        <div v-if="tokenStats && Object.keys(tokenStats.models).length" class="model-token-list">
          <div v-for="(stats, name) in tokenStats.models" :key="name" class="model-token-row">
            <span class="mt-name">{{ name }}</span>
            <div class="mt-bar-track"><div class="mt-bar-fill" :style="{ width: `${Math.min(100, (stats.total_tokens / Math.max(tokenStats.total_tokens, 1)) * 100)}%` }"></div></div>
            <span class="mt-count">{{ formatTokens(stats.total_tokens) }}</span>
          </div>
        </div>
        <div v-if="!tokenStats" class="empty-state">暂无统计</div>
      </div>

      <div class="card running-card">
        <div class="card-header">
          <Layers class="card-icon" />
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
              <button class="action-btn stop" @click="handleStopModel(model.name)" :disabled="!!actionLoading"><Square class="w-3 h-3" /> 停止</button>
            </div>
          </div>
        </div>
        <div v-else class="empty-state">暂无运行模型</div>
      </div>

      <div class="card model-list-card">
        <div class="card-header">
          <Box class="card-icon" />
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
                <button class="action-btn small" @click="handleStopModel(model.name)" :disabled="!!actionLoading"><Square class="w-3 h-3" /></button>
              </template>
              <template v-else>
                <button class="action-btn small primary" @click="handleSwitchAndSetDefault(model.name)" :disabled="!!actionLoading"><ArrowRightLeft class="w-3 h-3" /> 切换</button>
                <button class="action-btn small" @click="handleStartModel(model.name)" :disabled="!!actionLoading"><Play class="w-3 h-3" /></button>
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

.header-title { font-size: 18px; font-weight: 600; color: var(--text-primary); }

.header-btn {
  display: flex; align-items: center; gap: 6px;
  padding: 6px 12px; border-radius: 6px; font-size: 13px;
  color: var(--text-muted); background: transparent;
  border: 1px solid var(--border-primary); cursor: pointer; transition: all 0.2s;
}
.header-btn:hover { background: var(--bg-secondary); color: var(--text-primary); }

.grid {
  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 16px;
  padding: 16px 24px;
  align-content: start;
}

.card {
  background: var(--bg-card); border-radius: 12px;
  border: 1px solid var(--border-card); padding: 20px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.3), 0 0 1px rgba(99, 102, 241, 0.1);
  transition: box-shadow 0.3s ease, transform 0.2s ease, border-color 0.3s ease;
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
.card:hover::before { opacity: 0.6; }
.card:hover {
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4), 0 0 12px rgba(99, 102, 241, 0.1);
  transform: translateY(-2px);
  border-color: rgba(99, 102, 241, 0.25);
}

.card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 14px; }
.card-icon {
  width: 18px; height: 18px;
  color: var(--color-primary);
  filter: drop-shadow(0 0 4px rgba(99, 102, 241, 0.3));
  transition: filter 0.3s;
}
.card:hover .card-icon {
  filter: drop-shadow(0 0 8px rgba(99, 102, 241, 0.5));
}
.card-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }

.badge { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 500; margin-left: auto; }
.badge.online { background: rgba(34, 197, 94, 0.1); color: #059669; }
.badge.offline { background: rgba(239, 68, 68, 0.1); color: #dc2626; }

.dot { width: 6px; height: 6px; border-radius: 50%; display: inline-block; }
.dot.online { background: #22c55e; box-shadow: 0 0 6px rgba(34, 197, 94, 0.5); }
.dot.offline { background: #6b7280; }

.count-badge { margin-left: auto; font-size: 12px; color: var(--text-muted); background: var(--bg-secondary); padding: 2px 8px; border-radius: 10px; }

.gpu-name-row { display: flex; justify-content: space-between; align-items: baseline; }
.gpu-label { font-size: 15px; font-weight: 600; color: var(--text-primary); }
.gpu-vram { font-size: 12px; color: var(--text-muted); }

.sparkline-row { display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-top: 12px; }
.sparkline-item { display: flex; flex-direction: column; gap: 4px; }
.spark-label { font-size: 11px; color: var(--text-muted); }
.spark-val { font-size: 13px; font-weight: 600; color: var(--text-primary); }
.spark-val.success { color: #22c55e; }
.spark-val.warning { color: #f59e0b; }
.spark-val.danger { color: #ef4444; }

.metrics-row { display: flex; gap: 12px; margin-top: 12px; }
.mini-metric { flex: 1; display: flex; flex-direction: column; gap: 4px; padding: 10px; background: var(--bg-secondary); border-radius: 8px; border: 1px solid transparent; transition: all 0.2s; }
.mini-metric:hover { border-color: var(--border-primary); transform: translateY(-1px); }
.mini-label { font-size: 12px; color: var(--text-muted); }
.mini-val { font-size: 14px; font-weight: 700; color: var(--text-primary); }
.mini-val.success { color: #22c55e; }
.mini-val.warning { color: #f59e0b; }
.mini-val.danger { color: #ef4444; }
.mini-bar { height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; margin-top: 4px; }
.mini-fill { height: 100%; border-radius: 2px; transition: width 0.5s ease; }

.empty-state { text-align: center; color: var(--text-muted); padding: 24px 0; font-size: 13px; }

.token-grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
.token-item { display: flex; align-items: center; gap: 10px; padding: 12px; background: var(--bg-secondary); border-radius: 8px; transition: background 0.2s, transform 0.2s; border: 1px solid transparent; }
.token-item:hover { background: var(--bg-tertiary); transform: translateY(-1px); border-color: var(--border-primary); }
.token-info { display: flex; flex-direction: column; gap: 2px; }
.token-value { font-size: 16px; font-weight: 700; color: var(--text-primary); }
.token-label { font-size: 11px; color: var(--text-muted); }

.model-token-list { display: flex; flex-direction: column; gap: 6px; margin-top: 12px; }
.model-token-row { display: flex; align-items: center; gap: 8px; padding: 6px 0; }
.mt-name { font-size: 12px; color: var(--text-secondary); min-width: 100px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.mt-bar-track { flex: 1; height: 4px; background: var(--bg-tertiary); border-radius: 2px; overflow: hidden; }
.mt-bar-fill { height: 100%; background: linear-gradient(90deg, #6366f1, #4f46e5); border-radius: 2px; transition: width 0.5s ease; min-width: 2px; }
.mt-count { font-size: 11px; color: var(--text-muted); min-width: 40px; text-align: right; }

.running-list { display: flex; flex-direction: column; gap: 8px; }
.model-row { display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--bg-secondary); border-radius: 8px; border-left: 3px solid #22c55e; transition: all 0.2s; }
.model-row:hover { background: var(--bg-tertiary); transform: translateX(2px); }
.model-info { display: flex; flex-direction: column; gap: 2px; }
.model-name { font-size: 14px; font-weight: 500; color: var(--text-primary); }
.model-meta { font-size: 12px; color: var(--text-muted); }
.model-actions { display: flex; align-items: center; gap: 8px; }
.default-tag { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; color: #f59e0b; background: rgba(245, 158, 11, 0.1); padding: 2px 8px; border-radius: 4px; }

.action-btn { display: inline-flex; align-items: center; gap: 4px; padding: 4px 10px; border-radius: 6px; font-size: 12px; font-weight: 500; border: 1px solid var(--border-primary); background: var(--bg-card); color: var(--text-primary); cursor: pointer; transition: all 0.2s; }
.action-btn:hover:not(:disabled) { border-color: var(--border-secondary); transform: translateY(-1px); }
.action-btn:disabled { opacity: 0.5; cursor: not-allowed; }
.action-btn.stop { color: #ef4444; border-color: rgba(239, 68, 68, 0.3); }
.action-btn.stop:hover:not(:disabled) { background: rgba(239, 68, 68, 0.1); box-shadow: 0 0 8px rgba(239, 68, 68, 0.2); }
.action-btn.primary { color: #22c55e; border-color: rgba(34, 197, 94, 0.3); }
.action-btn.primary:hover:not(:disabled) { background: rgba(34, 197, 94, 0.1); box-shadow: 0 0 8px rgba(34, 197, 94, 0.2); }
.action-btn.small { padding: 3px 6px; border-radius: 4px; }

.model-table { display: flex; flex-direction: column; gap: 4px; }
.table-row { display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--bg-secondary); border-radius: 8px; font-size: 13px; transition: all 0.2s; }
.table-row:hover { background: var(--bg-tertiary); }
.table-row.running { background: rgba(34, 197, 94, 0.04); border-left: 3px solid #22c55e; }
.table-row.running:hover { background: rgba(34, 197, 94, 0.08); }
.col-name { display: flex; align-items: center; gap: 6px; font-weight: 500; color: var(--text-primary); }
.col-action { display: flex; align-items: center; gap: 4px; }
.star-icon { color: #f59e0b; }

.grid::-webkit-scrollbar { width: 4px; }
.grid::-webkit-scrollbar-track { background: transparent; }
.grid::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 2px; }
</style>
