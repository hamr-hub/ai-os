<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useModelPool } from '@/composables/useModelPool'
import { useLLMService } from '@/composables/useLLMService'
import {
  Database,
  Play,
  Square,
  Trash2,
  RefreshCw,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Server,
  Cpu,
} from 'lucide-vue-next'

const { poolList, total, loading: poolLoading, error: poolError, list: listPool, load: loadPoolModel, remove: removePoolModel } = useModelPool()
const { services, error: serviceError, getStatus: getServiceStatus, stop: stopService } = useLLMService()

const poolFilter = ref('all')
const showDeleteConfirm = ref<string | null>(null)
const engineSelect = ref('vllm')
const loadError = ref<string | null>(null)
let poolWsTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  listPool(poolFilter.value)
  getServiceStatus()
  poolWsTimer = setInterval(() => {
    listPool(poolFilter.value)
  }, 3000)
})

const handleRefresh = () => {
  listPool(poolFilter.value)
  getServiceStatus()
}

const handleLoad = async (modelKey: string) => {
  loadError.value = null
  const result = await loadPoolModel(modelKey, engineSelect.value)
  if (!result || (result as any).success === false) {
    const errMsg = (result as any)?.message || (result as any)?.error || '加载失败'
    if (errMsg.includes('memory') || errMsg.includes('显存') || errMsg.includes('OOM') || errMsg.includes('GPU')) {
      loadError.value = `显存不足: ${errMsg}`
    } else {
      loadError.value = errMsg
    }
  } else {
    getServiceStatus()
  }
}

const handleStopService = async (modelName: string) => {
  await stopService(modelName)
  getServiceStatus()
}

const handleDelete = (modelKey: string, removeFiles: boolean) => {
  removePoolModel(modelKey, removeFiles)
  showDeleteConfirm.value = null
}

const handleFilterChange = () => {
  listPool(poolFilter.value)
}

const formatSize = (bytes: number | null) => {
  if (!bytes) return '--'
  if (bytes > 1024 * 1024 * 1024) return (bytes / (1024 * 1024 * 1024)).toFixed(1) + ' GB'
  if (bytes > 1024 * 1024) return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  return bytes.toFixed(0) + ' B'
}

const sourceIcon = (source: string) => {
  if (source === 'hf') return '🤗'
  if (source === 'modelscope') return '🏠'
  if (source === 'openxlab') return '🔬'
  if (source === 'local') return '📁'
  if (source === 'oxl') return '🔬'
  return '📦'
}

onUnmounted(() => {
  if (poolWsTimer) {
    clearInterval(poolWsTimer)
    poolWsTimer = null
  }
})

const downloadStatusColor = (status: string) => {
  if (status === 'completed') return '#4ade80'
  if (status === 'downloading') return 'var(--color-primary-light)'
  if (status === 'failed') return '#f87171'
  return 'var(--text-muted)'
}

const runningStatusColor = (status: string) => {
  if (status === 'running') return '#4ade80'
  if (status === 'loading') return 'var(--color-primary-light)'
  return 'var(--text-muted)'
}

const poolStats = computed(() => {
  const models = poolList.value ?? []
  const totalSize = models.reduce((acc, m) => acc + (m.size_b ?? 0), 0)
  const runningCount = models.filter(m => m.running_status === 'running').length
  const downloadCompleted = models.filter(m => m.download_status === 'completed').length
  const downloadFailed = models.filter(m => m.download_status === 'failed').length
  const feasibleCount = models.filter(m => m.feasible === true).length
  const notFeasibleCount = models.filter(m => m.feasible === false).length
  const sourceMap: Record<string, number> = {}
  models.forEach(m => { sourceMap[m.source] = (sourceMap[m.source] || 0) + 1 })
  return {
    total: models.length,
    totalSize,
    runningCount,
    downloadCompleted,
    downloadFailed,
    feasibleCount,
    notFeasibleCount,
    sourceMap,
  }
})
</script>

<template>
  <div class="model-pool-page">
    <div class="page-header">
      <div class="header-title">
        <Database class="w-6 h-6 text-primary" />
        <h1 class="digital-font">Model Pool</h1>
      </div>
      <p class="header-subtitle">本地模型池 · 引擎管理 · 服务调度</p>
      <button class="btn btn-ghost" @click="handleRefresh">
        <RefreshCw v-if="poolLoading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" /> 刷新
      </button>
    </div>

    <div v-if="poolError || serviceError" class="error-banner">
      <AlertTriangle class="w-4 h-4" />
      {{ poolError || serviceError }}
      <button class="btn btn-sm btn-ghost" @click="handleRefresh" style="margin-left:auto">
        <RefreshCw class="w-3.5 h-3.5" /> 重试
      </button>
    </div>

    <div v-if="loadError" class="error-banner memory-warn">
      <Cpu class="w-4 h-4" />
      {{ loadError }}
      <button class="btn btn-sm btn-ghost" @click="loadError = null">关闭</button>
    </div>

    <div class="pool-controls">
      <select v-model="poolFilter" class="source-select" @change="handleFilterChange">
        <option value="all">全部</option>
        <option value="local">本地</option>
        <option value="downloading">下载中</option>
        <option value="running">运行中</option>
      </select>
      <select v-model="engineSelect" class="source-select">
        <option value="vllm">vLLM</option>
        <option value="sglang">SGLang</option>
      </select>
      <span class="total-count">共 {{ total }} 个模型</span>
      <span class="ws-poll-badge">
        <span class="ws-poll-dot"></span> 3s 自动刷新
      </span>
    </div>

    <div v-if="poolList.length" class="stats-overview">
      <div class="stat-card">
        <Database class="w-4 h-4 stat-icon" />
        <div class="stat-info">
          <span class="stat-num">{{ poolStats.total }}</span>
          <span class="stat-desc">总模型数</span>
        </div>
      </div>
      <div class="stat-card">
        <Cpu class="w-4 h-4 stat-icon" />
        <div class="stat-info">
          <span class="stat-num">{{ formatSize(poolStats.totalSize) }}</span>
          <span class="stat-desc">总大小</span>
        </div>
      </div>
      <div class="stat-card stat-green">
        <CheckCircle class="w-4 h-4 stat-icon" />
        <div class="stat-info">
          <span class="stat-num">{{ poolStats.runningCount }}</span>
          <span class="stat-desc">运行中</span>
        </div>
      </div>
      <div class="stat-card stat-blue">
        <Server class="w-4 h-4 stat-icon" />
        <div class="stat-info">
          <span class="stat-num">{{ poolStats.feasibleCount }}</span>
          <span class="stat-desc">可运行</span>
        </div>
      </div>
      <div class="stat-card stat-red">
        <XCircle class="w-4 h-4 stat-icon" />
        <div class="stat-info">
          <span class="stat-num">{{ poolStats.notFeasibleCount }}</span>
          <span class="stat-desc">显存不足</span>
        </div>
      </div>
      <div class="stat-card source-distribution">
        <span class="stat-label">来源分布</span>
        <div class="source-bar">
          <span v-for="(count, src) in poolStats.sourceMap" :key="src" class="source-seg" :style="{ width: (count / poolStats.total * 100) + '%' }">
            {{ sourceIcon(src) }} {{ count }}
          </span>
        </div>
      </div>
    </div>

    <div v-if="poolLoading" class="loading-state">
      <Loader2 class="w-8 h-8 animate-spin text-primary" />
      <p>加载中...</p>
    </div>

    <div v-else-if="!poolList.length" class="empty-state">
      <Database class="w-12 h-12 text-muted" />
      <p>模型池为空，请先在 Model Hub 中搜索下载模型</p>
    </div>

    <div v-else class="pool-table">
      <div class="table-header">
        <span>模型</span>
        <span>来源</span>
        <span>大小</span>
        <span>显存</span>
        <span>下载状态</span>
        <span>运行状态</span>
        <span>端口</span>
        <span>操作</span>
      </div>
      <div v-for="model in poolList" :key="model.config_key || model.name" class="table-row">
        <span class="model-name">{{ model.name }}</span>
        <span class="source-tag">{{ sourceIcon(model.source) }} {{ model.source }}</span>
        <span>{{ formatSize(model.size_b) }}</span>
        <span>
          <span v-if="model.feasible" style="color: #4ade80">
            <CheckCircle class="w-3.5 h-3.5 inline" /> {{ model.required_gb }} GB
          </span>
          <span v-else-if="model.feasible === false" style="color: #f87171">
            <XCircle class="w-3.5 h-3.5 inline" /> {{ model.required_gb }} GB
          </span>
          <span v-else>{{ model.required_gb ? model.required_gb + ' GB' : '--' }}</span>
        </span>
        <span :style="{ color: downloadStatusColor(model.download_status) }">{{ model.download_status }}</span>
        <span :style="{ color: runningStatusColor(model.running_status) }">{{ model.running_status }}</span>
        <span>{{ model.port || '--' }}</span>
        <span class="actions-cell">
          <button
            v-if="model.download_status === 'completed' && model.running_status !== 'running'"
            class="btn btn-sm btn-primary"
            @click="handleLoad(model.config_key || model.name)"
          >
            <Play class="w-3.5 h-3.5" /> 加载
          </button>
          <button
            v-if="model.running_status === 'running'"
            class="btn btn-sm btn-danger"
            @click="handleStopService(model.name)"
          >
            <Square class="w-3.5 h-3.5" /> 停止
          </button>
          <button
            v-if="model.download_status === 'completed'"
            class="btn btn-sm btn-ghost"
            @click="showDeleteConfirm = model.config_key || model.name"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </span>
      </div>
    </div>

    <div v-if="showDeleteConfirm" class="confirm-modal">
      <div class="confirm-content tech-border">
        <h3>确认删除</h3>
        <p>是否同时删除本地文件？</p>
        <div class="confirm-actions">
          <button class="btn btn-danger" @click="handleDelete(showDeleteConfirm!, true)">
            删除模型+文件
          </button>
          <button class="btn btn-ghost" @click="handleDelete(showDeleteConfirm!, false)">
            仅从池移除
          </button>
          <button class="btn btn-ghost" @click="showDeleteConfirm = null">取消</button>
        </div>
      </div>
    </div>

    <div v-if="Object.keys(services).length" class="service-section">
      <h3 class="section-title">
        <Server class="w-5 h-5" /> 运行中的服务
      </h3>
      <div class="service-list">
        <div v-for="(svc, name) in services" :key="name" class="service-card tech-border">
          <div class="svc-header">
            <span class="svc-name">{{ name }}</span>
            <span :class="['svc-status', svc.running ? 'running' : 'stopped']">
              {{ svc.running ? '运行中' : '已停止' }}
            </span>
          </div>
          <div class="svc-meta">
            <span>引擎: {{ svc.engine }}</span>
            <span v-if="svc.port">端口: {{ svc.port }}</span>
            <span v-if="svc.started_at">启动: {{ svc.started_at }}</span>
          </div>
          <div class="svc-actions">
            <button v-if="svc.running" class="btn btn-sm btn-danger" @click="handleStopService(name)">
              <Square class="w-3.5 h-3.5" /> 停止
            </button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-pool-page {
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

.memory-warn {
  background: rgba(245, 158, 11, 0.1);
  color: #f59e0b;
  border: 1px solid rgba(245, 158, 11, 0.2);
}

.pool-controls {
  display: flex;
  gap: 12px;
  align-items: center;
  margin-bottom: 16px;
}

.source-select {
  background: var(--bg-input);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
}

.total-count {
  color: var(--text-muted);
  font-size: 14px;
}

.ws-poll-badge {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: var(--text-muted);
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--bg-secondary);
}

.ws-poll-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #f59e0b;
  animation: blink 1.5s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
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

.pool-table {
  background: var(--bg-card);
  border-radius: 12px;
  overflow: hidden;
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 0.5fr 1.5fr;
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr 1fr 0.5fr 1.5fr;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  align-items: center;
}

.model-name {
  font-weight: 600;
}

.source-tag {
  font-size: 12px;
  color: var(--text-muted);
}

.actions-cell {
  display: flex;
  gap: 4px;
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
}

.confirm-content h3 {
  color: var(--text-primary);
  margin-bottom: 12px;
}

.confirm-content p {
  color: var(--text-muted);
  margin-bottom: 16px;
}

.confirm-actions {
  display: flex;
  gap: 8px;
}

.service-section {
  margin-top: 32px;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  margin-bottom: 16px;
}

.service-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 12px;
}

.service-card {
  background: var(--bg-card);
  padding: 16px;
  border-radius: 12px;
}

.svc-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.svc-name {
  font-weight: 600;
  color: var(--text-primary);
}

.svc-status.running {
  color: #4ade80;
}

.svc-status.stopped {
  color: var(--text-muted);
}

.svc-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.svc-actions {
  display: flex;
  gap: 4px;
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

.stats-overview {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: 10px;
  margin-bottom: 16px;
}

.stat-card {
  background: var(--bg-card);
  border-radius: 10px;
  padding: 12px;
  display: flex;
  align-items: center;
  gap: 10px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.stat-icon {
  color: var(--text-muted);
  flex-shrink: 0;
}

.stat-card.stat-green .stat-icon { color: #4ade80; }
.stat-card.stat-blue .stat-icon { color: var(--color-primary-light); }
.stat-card.stat-red .stat-icon { color: #f87171; }

.stat-info {
  display: flex;
  flex-direction: column;
}

.stat-num {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}

.stat-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.source-distribution {
  grid-column: span 2;
  flex-direction: column;
  align-items: flex-start;
  gap: 6px;
}

.source-bar {
  display: flex;
  width: 100%;
  height: 24px;
  border-radius: 4px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.source-seg {
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--text-primary);
  background: rgba(99, 102, 241, 0.15);
  border-right: 1px solid rgba(255, 255, 255, 0.05);
  overflow: hidden;
  white-space: nowrap;
}

.stat-label {
  font-size: 12px;
  color: var(--text-muted);
}
</style>
