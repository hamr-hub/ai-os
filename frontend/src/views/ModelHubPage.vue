<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useModelSearch } from '@/composables/useModelSearch'
import { useModelDownload } from '@/composables/useModelDownload'
import { useGPUMemory } from '@/composables/useGPUMemory'
import {
  Search,
  Download,
  Cpu,
  Star,
  RefreshCw,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Zap,
  ArrowUpDown,
} from 'lucide-vue-next'

const { results, loading: searchLoading, error: searchError, search } = useModelSearch()
const { tasks, error: downloadError, wsConnected, start: startDownload, getStatus, cancel, list: listDownloads, connectDownloadWS, disconnectWS } = useModelDownload()
const { recommendResult, memoryCheckResult, loading: gpuLoading, error: gpuError, recommend: gpuRecommend, checkMemory: gpuCheckMemory } = useGPUMemory()

const searchKeyword = ref('')
const searchSource = ref('all')
const activeTab = ref<'search' | 'download' | 'recommend'>('search')
const activeTab = ref<'search' | 'download' | 'recommend'>('search')
const pollTimer = ref<ReturnType<typeof setInterval> | null>(null)
const sortBy = ref<'default' | 'size' | 'quant' | 'memory' | 'feasible'>('default')

const sortedResults = computed(() => {
  const r = [...results.value]
  switch (sortBy.value) {
    case 'size':
      return r.sort((a, b) => (b.required_gb ?? 0) - (a.required_gb ?? 0))
    case 'quant':
      return r.sort((a, b) => (a.quant ?? '').localeCompare(b.quant ?? ''))
    case 'memory':
      return r.sort((a, b) => (b.required_gb ?? 0) - (a.required_gb ?? 0))
    case 'feasible':
      return r.sort((a, b) => {
        if (a.feasible === true && b.feasible !== true) return -1
        if (a.feasible === false && b.feasible !== false) return 1
        return 0
      })
    default:
      return r
  }
})

const feasibleBadgeLabel = (feasible: boolean | null, requiredGb: number | null) => {
  if (feasible === true) return '可运行'
  if (feasible === false) return '显存不足'
  if (requiredGb && requiredGb > 0) return '接近上限'
  return '未知'
}

const feasibleBadgeClass = (feasible: boolean | null, _requiredGb: number | null) => {
  if (feasible === true) return 'badge-ok'
  if (feasible === false) return 'badge-fail'
  return 'badge-warn'
}

onMounted(() => {
  listDownloads()
  connectDownloadWS()
})

onUnmounted(() => {
  disconnectWS()
  if (pollTimer.value) {
    clearInterval(pollTimer.value)
    pollTimer.value = null
  }
})

const handleSearch = () => {
  if (!searchKeyword.value.trim()) return
  search(searchKeyword.value, searchSource.value)
}

const handleRecommend = () => {
  if (!searchKeyword.value.trim()) return
  gpuRecommend(searchKeyword.value, searchSource.value)
  activeTab.value = 'recommend'
}

const handleCheckMemory = (modelName: string) => {
  gpuCheckMemory(modelName)
}

const handleDownload = (modelName: string, source: string) => {
  startDownload(modelName, source)
  startPolling()
}

const startPolling = () => {
  if (pollTimer.value) clearInterval(pollTimer.value)
  pollTimer.value = setInterval(() => {
    listDownloads()
    const downloading = tasks.value.find(t => t.status === 'downloading' || t.status === 'pending')
    if (downloading) {
      getStatus(downloading.task_id)
    }
    if (!downloading) {
      clearInterval(pollTimer.value!)
      pollTimer.value = null
    }
  }, 3000)
}

const handleCancelDownload = (taskId: string) => {
  cancel(taskId)
  listDownloads()
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
  return '📦'
}
</script>

<template>
  <div class="model-hub-page">
    <div class="page-header">
      <div class="header-title">
        <Zap class="w-6 h-6 text-primary" />
        <h1 class="digital-font">Model Hub</h1>
      </div>
      <p class="header-subtitle">多源模型搜索 · 显存优选 · 一键下载</p>
    </div>

    <div class="search-section tech-border">
      <div class="search-bar">
        <div class="search-input-wrapper">
          <Search class="w-5 h-5 text-muted" />
          <input
            v-model="searchKeyword"
            type="text"
            placeholder="搜索模型 (如 Qwen2.5-7B-Instruct)"
            class="search-input"
            @keyup.enter="handleSearch"
          />
        </div>
        <select v-model="searchSource" class="source-select">
          <option value="all">全部源</option>
          <option value="hf">HuggingFace</option>
          <option value="modelscope">ModelScope</option>
          <option value="openxlab">OpenXLab</option>
        </select>
        <button class="btn btn-primary" :disabled="!searchKeyword.trim()" @click="handleSearch">
          <RefreshCw v-if="searchLoading" class="w-4 h-4 animate-spin" />
          <Search v-else class="w-4 h-4" />
          搜索
        </button>
        <button class="btn btn-accent" :disabled="!searchKeyword.trim()" @click="handleRecommend">
          <Star class="w-4 h-4" />
          显存优选
        </button>
      </div>
    </div>

    <div class="tab-bar">
      <button :class="['tab-btn', { active: activeTab === 'search' }]" @click="activeTab = 'search'">
        <Search class="w-4 h-4" /> 搜索结果
      </button>
      <button :class="['tab-btn', { active: activeTab === 'download' }]" @click="activeTab = 'download'">
        <Download class="w-4 h-4" /> 下载任务
        <span v-if="tasks.length" class="badge">{{ tasks.length }}</span>
      </button>
      <button :class="['tab-btn', { active: activeTab === 'recommend' }]" @click="activeTab = 'recommend'">
        <Cpu class="w-4 h-4" /> 显存推荐
      </button>
    </div>

    <div v-if="searchError || downloadError || gpuError" class="error-banner">
      <AlertTriangle class="w-4 h-4" />
      {{ searchError || downloadError || gpuError }}
    </div>

    <div class="tab-content">
      <div v-if="activeTab === 'search'" class="search-results">
        <div v-if="searchLoading" class="loading-state">
          <Loader2 class="w-8 h-8 animate-spin text-primary" />
          <p>搜索中...</p>
        </div>
        <div v-else-if="!results.length" class="empty-state">
          <Search class="w-12 h-12 text-muted" />
          <p>输入关键词搜索模型</p>
        </div>
        <div v-else class="result-area">
          <div class="sort-bar">
            <ArrowUpDown class="w-4 h-4" />
            <select v-model="sortBy" class="sort-select">
              <option value="default">默认排序</option>
              <option value="size">按模型大小</option>
              <option value="quant">按量化类型</option>
              <option value="memory">按显存需求</option>
              <option value="feasible">按显存可行性</option>
            </select>
          </div>
          <div class="result-grid">
          <div v-for="item in sortedResults" :key="item.name + item.source" class="result-card tech-border">
            <div class="card-header">
              <span class="source-tag">{{ sourceIcon(item.source) }} {{ item.source }}</span>
              <span :class="['feasible-badge', feasibleBadgeClass(item.feasible, item.required_gb)]">
                <CheckCircle v-if="item.feasible === true" class="w-3.5 h-3.5" />
                <XCircle v-else-if="item.feasible === false" class="w-3.5 h-3.5" />
                <AlertTriangle v-else class="w-3.5 h-3.5" />
                {{ feasibleBadgeLabel(item.feasible, item.required_gb) }}
              </span>
            </div>
            <h3 class="model-name">{{ item.name }}</h3>
            <div class="card-meta">
              <span v-if="item.required_gb">{{ item.required_gb }} GB</span>
              <span v-if="item.quant">{{ item.quant }}</span>
              <span v-if="item.size_b">{{ formatSize(item.size_b) }}</span>
            </div>
            <p v-if="item.description" class="card-desc">{{ item.description }}</p>
            <div class="card-actions">
              <button class="btn btn-sm btn-primary" @click="handleDownload(item.name, item.source)">
                <Download class="w-3.5 h-3.5" /> 下载
              </button>
              <button class="btn btn-sm btn-ghost" @click="handleCheckMemory(item.name)">
                <Cpu class="w-3.5 h-3.5" /> 显存校验
              </button>
            </div>
          </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'download'" class="download-section">
        <div class="ws-status-bar">
          <span :class="['ws-indicator', wsConnected ? 'ws-live' : 'ws-poll']"></span>
          <span class="ws-label">{{ wsConnected ? '实时推送' : '3s 刷新' }}</span>
        </div>
        <div v-if="!tasks.length" class="empty-state">
          <Download class="w-12 h-12 text-muted" />
          <p>暂无下载任务</p>
        </div>
        <div v-else class="download-list">
          <div v-for="task in tasks" :key="task.task_id" class="download-item tech-border">
            <div class="download-header">
              <span class="model-name">{{ task.model_name }}</span>
              <span :class="['status-tag', task.status]">{{ task.status }}</span>
            </div>
            <div v-if="task.status === 'downloading'" class="progress-bar-wrapper">
              <div class="progress-bar-bg">
                <div class="progress-bar-fill" :style="{ width: task.progress_pct + '%' }"></div>
              </div>
              <span class="progress-text">{{ task.progress_pct.toFixed(1) }}%</span>
            </div>
            <div class="download-meta">
              <span v-if="task.speed_mbps">{{ task.speed_mbps.toFixed(1) }} MB/s</span>
              <span v-if="task.eta_seconds">ETA {{ Math.ceil(task.eta_seconds / 60) }}m</span>
              <span>{{ formatSize(task.downloaded_bytes) }} / {{ formatSize(task.total_bytes) }}</span>
            </div>
            <div v-if="task.error_message" class="error-text">{{ task.error_message }}</div>
            <div class="download-actions">
              <button
                v-if="task.status === 'downloading' || task.status === 'pending'"
                class="btn btn-sm btn-danger"
                @click="handleCancelDownload(task.task_id)"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      </div>

      <div v-if="activeTab === 'recommend'" class="recommend-section">
        <div v-if="gpuLoading" class="loading-state">
          <Loader2 class="w-8 h-8 animate-spin text-primary" />
          <p>分析中...</p>
        </div>
        <div v-else-if="!recommendResult" class="empty-state">
          <Cpu class="w-12 h-12 text-muted" />
          <p>点击"显存优选"按钮获取推荐</p>
        </div>
        <div v-else>
          <div v-if="recommendResult.recommended" class="recommend-card tech-border recommended">
            <div class="recommend-badge">
              <Star class="w-5 h-5" /> 最佳推荐
            </div>
            <h3>{{ recommendResult.recommended.name }}</h3>
            <div class="card-meta">
              <span v-if="recommendResult.recommended.required_gb">{{ recommendResult.recommended.required_gb }} GB</span>
              <span v-if="recommendResult.recommended.quant">{{ recommendResult.recommended.quant }}</span>
              <span>{{ sourceIcon(recommendResult.recommended.source) }} {{ recommendResult.recommended.source }}</span>
            </div>
            <button class="btn btn-primary" @click="handleDownload(recommendResult.recommended!.name, recommendResult.recommended!.source)">
              <Download class="w-4 h-4" /> 下载推荐模型
            </button>
          </div>
          <div v-if="recommendResult.gpu_info" class="gpu-info-card tech-border">
            <h4>GPU 信息</h4>
            <div class="gpu-stats">
              <div class="stat-item">
                <span class="stat-label">名称</span>
                <span class="stat-value">{{ recommendResult.gpu_info.name || '--' }}</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">总显存</span>
                <span class="stat-value">{{ recommendResult.gpu_info.total_gb?.toFixed(1) || '--' }} GB</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">可用显存</span>
                <span class="stat-value">{{ recommendResult.gpu_info.free_gb?.toFixed(1) || '--' }} GB</span>
              </div>
              <div class="stat-item">
                <span class="stat-label">安全可用</span>
                <span class="stat-value">{{ recommendResult.gpu_info.safety_available_gb?.toFixed(1) || '--' }} GB</span>
              </div>
            </div>
          </div>
          <div v-if="memoryCheckResult" class="memory-check-card tech-border">
            <h4>显存校验结果</h4>
            <div v-if="memoryCheckResult.feasible" class="check-pass">
              <CheckCircle class="w-6 h-6 text-green-400" /> 可运行 (需要 {{ memoryCheckResult.required_gb }} GB, 可用 {{ memoryCheckResult.available_gb }} GB)
            </div>
            <div v-else class="check-fail">
              <XCircle class="w-6 h-6 text-red-400" /> 显存不足 (需要 {{ memoryCheckResult.required_gb }} GB, 可用 {{ memoryCheckResult.available_gb }} GB)
            </div>
          </div>
          <div v-if="recommendResult.candidates?.length" class="candidates-section">
            <h4>其他候选</h4>
            <div class="result-grid">
              <div v-for="c in recommendResult.candidates" :key="c.name + c.source" class="result-card tech-border">
                <div class="card-header">
                  <span class="source-tag">{{ sourceIcon(c.source) }} {{ c.source }}</span>
                  <span v-if="c.feasible === true" class="feasible-tag feasible">
                    <CheckCircle class="w-3.5 h-3.5" /> 可运行
                  </span>
                </div>
                <h3 class="model-name">{{ c.name }}</h3>
                <div class="card-meta">
                  <span v-if="c.required_gb">{{ c.required_gb }} GB</span>
                  <span v-if="c.quant">{{ c.quant }}</span>
                </div>
                <button class="btn btn-sm btn-ghost" @click="handleDownload(c.name, c.source)">
                  <Download class="w-3.5 h-3.5" /> 下载
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ws-status-bar {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 12px;
  padding: 4px 10px;
  border-radius: 4px;
  background: var(--bg-secondary);
  font-size: 12px;
}

.ws-indicator {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.ws-indicator.ws-live {
  background: #22c55e;
  animation: blink 1.5s infinite;
}

.ws-indicator.ws-poll {
  background: #f59e0b;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.4; }
}

.ws-label {
  color: var(--text-secondary);
}

.sort-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 6px 10px;
  border-radius: 6px;
  background: var(--bg-secondary);
}

.sort-select {
  background: var(--bg-input);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 6px;
  padding: 4px 8px;
  font-size: 13px;
}

.feasible-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
}

.feasible-badge.badge-ok {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.feasible-badge.badge-fail {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.feasible-badge.badge-warn {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.model-hub-page {
  padding: 24px;
  max-width: 1200px;
}

.page-header {
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
  margin-top: 4px;
}

.search-section {
  background: var(--bg-card);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.search-bar {
  display: flex;
  gap: 12px;
  align-items: center;
}

.search-input-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  flex: 1;
  background: var(--bg-input);
  border-radius: 8px;
  padding: 8px 12px;
}

.search-input {
  flex: 1;
  background: transparent;
  border: none;
  color: var(--text-primary);
  font-size: 14px;
  outline: none;
}

.source-select {
  background: var(--bg-input);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
}

.tab-bar {
  display: flex;
  gap: 4px;
  margin-bottom: 16px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  background: var(--bg-card);
  color: var(--text-muted);
  border: 1px solid transparent;
  cursor: pointer;
  font-size: 14px;
}

.tab-btn.active {
  background: rgba(99, 102, 241, 0.1);
  color: var(--color-primary-light);
  border-color: rgba(99, 102, 241, 0.2);
}

.badge {
  background: var(--color-primary);
  color: white;
  font-size: 10px;
  padding: 1px 6px;
  border-radius: 8px;
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

.tab-content {
  min-height: 300px;
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

.result-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
  gap: 12px;
}

.result-card {
  background: var(--bg-card);
  padding: 16px;
  border-radius: 12px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.source-tag {
  font-size: 12px;
  color: var(--text-muted);
}

.feasible-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.feasible-tag.feasible {
  color: #4ade80;
}

.feasible-tag.not-feasible {
  color: #f87171;
}

.model-name {
  font-size: 16px;
  color: var(--text-primary);
  margin-bottom: 8px;
  font-weight: 600;
}

.card-meta {
  display: flex;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 8px;
}

.card-desc {
  font-size: 13px;
  color: var(--text-muted);
  line-height: 1.4;
  margin-bottom: 12px;
  max-height: 60px;
  overflow: hidden;
}

.card-actions {
  display: flex;
  gap: 8px;
}

.download-item {
  background: var(--bg-card);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 8px;
}

.download-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.status-tag {
  font-size: 12px;
  padding: 2px 8px;
  border-radius: 6px;
}

.status-tag.downloading {
  background: rgba(99, 102, 241, 0.2);
  color: var(--color-primary-light);
}

.status-tag.completed {
  background: rgba(74, 222, 128, 0.2);
  color: #4ade80;
}

.status-tag.failed {
  background: rgba(248, 113, 113, 0.2);
  color: #f87171;
}

.status-tag.pending {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}

.status-tag.cancelled {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-muted);
}

.progress-bar-wrapper {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 8px;
}

.progress-bar-bg {
  flex: 1;
  height: 6px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 3px;
  overflow: hidden;
}

.progress-bar-fill {
  height: 100%;
  background: var(--color-primary);
  transition: width 0.3s;
}

.progress-text {
  font-size: 12px;
  color: var(--text-muted);
  min-width: 50px;
}

.download-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
}

.error-text {
  color: #f87171;
  font-size: 12px;
  margin-top: 4px;
}

.download-actions {
  margin-top: 8px;
}

.recommend-card.recommended {
  border: 2px solid var(--color-primary);
  background: rgba(99, 102, 241, 0.05);
  padding: 20px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.recommend-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--color-primary-light);
  font-size: 14px;
  margin-bottom: 8px;
}

.gpu-info-card {
  background: var(--bg-card);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.gpu-info-card h4 {
  color: var(--text-primary);
  margin-bottom: 12px;
}

.gpu-stats {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.stat-item {
  display: flex;
  justify-content: space-between;
  padding: 4px 0;
}

.stat-label {
  color: var(--text-muted);
  font-size: 13px;
}

.stat-value {
  color: var(--text-primary);
  font-size: 13px;
}

.memory-check-card {
  background: var(--bg-card);
  padding: 16px;
  border-radius: 12px;
  margin-bottom: 16px;
}

.memory-check-card h4 {
  color: var(--text-primary);
  margin-bottom: 12px;
}

.check-pass,
.check-fail {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
}

.candidates-section h4 {
  color: var(--text-primary);
  margin-bottom: 12px;
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

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-accent {
  background: rgba(99, 102, 241, 0.1);
  color: var(--color-primary-light);
  border-color: rgba(99, 102, 241, 0.2);
}

.btn-accent:hover {
  background: rgba(99, 102, 241, 0.2);
}

.btn-accent:disabled {
  opacity: 0.5;
  cursor: not-allowed;
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
</style>
