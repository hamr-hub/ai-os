<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useRateLimit } from '@/composables/useRateLimit'
import {
  Gauge,
  RefreshCw,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Settings,
  Activity,
  Shield,
} from 'lucide-vue-next'
import type { RateLimitConfig } from '@/types'

const { queueStatus, rateLimitConfig, rateLimitStats, loading, error, fetchQueueStatus, fetchConfig, fetchStats, doUpdateConfig } = useRateLimit()

const activeTab = ref<'status' | 'config' | 'stats'>('status')
const editing = ref(false)
const editConfig = ref<Partial<RateLimitConfig>>({})

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchQueueStatus()
  fetchConfig()
  fetchStats()
  pollTimer = setInterval(() => {
    fetchQueueStatus()
    fetchStats()
  }, 5000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})

const handleRefresh = () => {
  fetchQueueStatus()
  fetchConfig()
  fetchStats()
}

const startEdit = () => {
  if (rateLimitConfig.value) {
    editConfig.value = { ...rateLimitConfig.value }
  }
  editing.value = true
}

const saveEdit = async () => {
  const success = await doUpdateConfig(editConfig.value)
  if (success) editing.value = false
}

const queueEntries = computed(() => {
  if (!queueStatus.value) return []
  return Object.entries(queueStatus.value).map(([name, entry]) => ({ name, ...entry }))
})

const totalActiveRequests = computed(() => {
  return queueEntries.value.reduce((sum, e) => sum + e.active_requests, 0)
})

const totalConcurrency = computed(() => {
  return queueEntries.value.reduce((sum, e) => sum + e.concurrency_limit, 0)
})

const totalCanAccept = computed(() => {
  return queueEntries.value.filter(e => e.can_accept).length
})

const formatPct = (active: number, limit: number) => {
  if (!limit) return '--'
  return `${Math.round((active / limit) * 100)}%`
}
</script>

<template>
  <div class="ratelimit-page fade-in">
    <div class="page-header">
      <div class="header-title">
        <div class="icon-box gradient-cyan">
          <Gauge class="w-5 h-5" />
        </div>
        <h1 class="digital-font">Rate Limit</h1>
      </div>
      <p class="header-subtitle">限流控制 · 排队管理 · 流量统计</p>
      <button class="btn btn-secondary" @click="handleRefresh">
        <RefreshCw v-if="loading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" /> 刷新
      </button>
    </div>

    <div v-if="error" class="error-banner toast-error">
      <AlertTriangle class="w-4 h-4" />
      {{ error }}
    </div>

    <div class="tab-controls">
      <button :class="['tab-btn', activeTab === 'status' ? 'active' : '']" @click="activeTab = 'status'">
        <Activity class="w-4 h-4" /> 排队状态
      </button>
      <button :class="['tab-btn', activeTab === 'config' ? 'active' : '']" @click="activeTab = 'config'">
        <Settings class="w-4 h-4" /> 限流配置
      </button>
      <button :class="['tab-btn', activeTab === 'stats' ? 'active' : '']" @click="activeTab = 'stats'">
        <Shield class="w-4 h-4" /> 流量统计
      </button>
    </div>

    <div v-if="activeTab === 'status'">
      <div v-if="loading && !queueStatus" class="loading-state">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
        <p>加载中...</p>
      </div>
      <div v-else-if="!loading && !queueEntries.length" class="empty-state">
        <Gauge class="w-12 h-12 text-muted" />
        <p>暂无排队数据</p>
      </div>
      <div v-else>
        <div class="stats-overview">
          <div class="stat-card card-base card-hover scale-in stagger-1">
            <Activity class="w-5 h-5 stat-icon text-primary" />
            <div class="stat-info">
              <span class="stat-num digital-font">{{ totalActiveRequests }}</span>
              <span class="stat-desc">活跃请求</span>
            </div>
          </div>
          <div class="stat-card card-base card-hover scale-in stagger-2">
            <Gauge class="w-5 h-5 stat-icon text-secondary" />
            <div class="stat-info">
              <span class="stat-num digital-font">{{ totalConcurrency }}</span>
              <span class="stat-desc">并发上限</span>
            </div>
          </div>
          <div class="stat-card card-base card-hover card-glow-green scale-in stagger-3">
            <CheckCircle class="w-5 h-5 stat-icon" />
            <div class="stat-info">
              <span class="stat-num digital-font">{{ totalCanAccept }}</span>
              <span class="stat-desc">可接受</span>
            </div>
          </div>
          <div class="stat-card card-base card-hover card-glow-red scale-in stagger-4">
            <XCircle class="w-5 h-5 stat-icon" />
            <div class="stat-info">
              <span class="stat-num digital-font">{{ queueEntries.length - totalCanAccept }}</span>
              <span class="stat-desc">已满</span>
            </div>
          </div>
        </div>

        <div class="queue-table card-base">
          <div class="table-header">
            <span>模型</span>
            <span>活跃请求</span>
            <span>并发上限</span>
            <span>使用率</span>
            <span>状态</span>
          </div>
          <div v-for="entry in queueEntries" :key="entry.name" class="table-row">
            <span class="model-name">{{ entry.name }}</span>
            <span class="mono">{{ entry.active_requests }}</span>
            <span class="mono">{{ entry.concurrency_limit }}</span>
            <span>
              <div class="usage-bar">
                <div class="progress-track"><div :class="['progress-fill', entry.active_requests / entry.concurrency_limit > 0.9 ? 'red' : entry.active_requests / entry.concurrency_limit > 0.7 ? 'yellow' : 'green']" :style="{ width: formatPct(entry.active_requests, entry.concurrency_limit) }"></div></div>
                <span class="usage-text">{{ formatPct(entry.active_requests, entry.concurrency_limit) }}</span>
              </div>
            </span>
            <span :class="['status-tag', entry.can_accept ? 'tag-green' : 'tag-orange']">
              <CheckCircle v-if="entry.can_accept" class="w-3.5 h-3.5" />
              <XCircle v-else class="w-3.5 h-3.5" />
              {{ entry.can_accept ? '可接受' : '已满' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'config'">
      <div v-if="!rateLimitConfig" class="loading-state">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
      </div>
      <div v-else class="config-panel card-base tech-border fade-in">
        <h3 class="section-title"><Settings class="w-5 h-5 text-primary" /> 限流配置</h3>
        <div v-if="!editing" class="config-display">
          <div class="config-row">
            <span class="config-label">IP QPS 限制</span>
            <span class="config-value digital-font">{{ rateLimitConfig.ip_qps_limit }} 次/{{ rateLimitConfig.ip_qps_window_seconds }}秒</span>
          </div>
          <div class="config-row">
            <span class="config-label">并发上限</span>
            <span class="config-value digital-font">{{ rateLimitConfig.concurrency_limit }}</span>
          </div>
          <div class="config-row">
            <span class="config-label">排队超时</span>
            <span class="config-value digital-font">{{ rateLimitConfig.queue_timeout_seconds }} 秒</span>
          </div>
          <div class="config-row">
            <span class="config-label">白名单 IP</span>
            <span class="config-value">{{ rateLimitConfig.whitelist_ips.join(', ') || '无' }}</span>
          </div>
          <div class="config-row">
            <span class="config-label">限流路径</span>
            <span class="config-value">{{ rateLimitConfig.rate_limited_paths.join(', ') }}</span>
          </div>
          <button class="btn btn-primary" @click="startEdit">
            <Settings class="w-4 h-4" /> 编辑配置
          </button>
        </div>
        <div v-else class="config-editor">
          <div class="form-row">
            <label class="form-label">IP QPS 限制</label>
            <input v-model.number="editConfig.ip_qps_limit" type="number" class="form-input" />
          </div>
          <div class="form-row">
            <label class="form-label">QPS 窗口(秒)</label>
            <input v-model.number="editConfig.ip_qps_window_seconds" type="number" class="form-input" />
          </div>
          <div class="form-row">
            <label class="form-label">并发上限</label>
            <input v-model.number="editConfig.concurrency_limit" type="number" class="form-input" />
          </div>
          <div class="form-row">
            <label class="form-label">排队超时(秒)</label>
            <input v-model.number="editConfig.queue_timeout_seconds" type="number" class="form-input" />
          </div>
          <div class="form-row">
            <label class="form-label">白名单 IP</label>
            <textarea
              :value="(editConfig.whitelist_ips || []).join(', ')"
              class="form-input"
              rows="3"
              @input="editConfig.whitelist_ips = ($event.target as HTMLTextAreaElement).value.split(',').map(item => item.trim()).filter(Boolean)"
            />
          </div>
          <div class="form-row">
            <label class="form-label">限流路径</label>
            <textarea
              :value="(editConfig.rate_limited_paths || []).join(', ')"
              class="form-input"
              rows="3"
              @input="editConfig.rate_limited_paths = ($event.target as HTMLTextAreaElement).value.split(',').map(item => item.trim()).filter(Boolean)"
            />
          </div>
          <div class="editor-actions">
            <button class="btn btn-primary" @click="saveEdit">保存</button>
            <button class="btn btn-secondary" @click="editing = false">取消</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'stats'">
      <div v-if="!rateLimitStats" class="loading-state">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
      </div>
      <div v-else class="stats-panel card-base tech-border fade-in">
        <h3 class="section-title"><Shield class="w-5 h-5 text-primary" /> 流量统计</h3>
        <div class="stats-grid">
          <div class="stats-item card-base card-hover card-glow-red scale-in stagger-1">
            <span class="stats-label">总拒绝数</span>
            <span class="stats-num digital-font">{{ rateLimitStats.total_rejected }}</span>
          </div>
          <div class="stats-item card-base card-hover card-glow-orange scale-in stagger-2">
            <span class="stats-label">近期429</span>
            <span class="stats-num digital-font">{{ rateLimitStats.recent_429_count }}</span>
          </div>
          <div class="stats-item card-base card-hover card-glow-cyan scale-in stagger-3">
            <span class="stats-label">当前排队</span>
            <span class="stats-num digital-font">{{ rateLimitStats.current_queue_depth }}</span>
          </div>
        </div>
        <div v-if="Object.keys(rateLimitStats.rejection_by_ip).length" class="stats-detail card-base">
          <h4>按IP拒绝统计</h4>
          <div v-for="(count, ip) in rateLimitStats.rejection_by_ip" :key="ip" class="detail-row">
            <span class="mono">{{ ip }}</span>
            <span class="tag tag-orange">{{ count }} 次</span>
          </div>
        </div>
        <div v-if="Object.keys(rateLimitStats.rejection_by_path).length" class="stats-detail card-base">
          <h4>按路径拒绝统计</h4>
          <div v-for="(count, path) in rateLimitStats.rejection_by_path" :key="path" class="detail-row">
            <span class="mono">{{ path }}</span>
            <span class="tag tag-orange">{{ count }} 次</span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ratelimit-page {
  padding: 24px;
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 28px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.icon-box {
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 2px 8px rgba(6, 182, 212, 0.3);
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
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.tab-controls {
  display: flex;
  gap: 6px;
  margin-bottom: 24px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  font-size: 14px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid var(--border-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.tab-btn:hover {
  background: var(--bg-tertiary);
  color: var(--text-secondary);
}

.tab-btn.active {
  background: linear-gradient(135deg, rgba(6, 182, 212, 0.15) 0%, rgba(6, 182, 212, 0.08) 100%);
  color: #22d3ee;
  border-color: rgba(6, 182, 212, 0.3);
  box-shadow: 0 0 12px rgba(6, 182, 212, 0.1);
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

.stats-overview {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  padding: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
  flex: 1;
}

.stat-icon { color: var(--color-primary); }
.stat-card .stat-icon:nth-child(1) { color: #22d3ee; }
.stat-card:nth-child(3) .stat-icon { color: #4ade80; }
.stat-card:nth-child(4) .stat-icon { color: #f87171; }

.stat-info { display: flex; flex-direction: column; }
.stat-num { font-size: 22px; font-weight: 700; color: var(--text-primary); }
.stat-desc { font-size: 13px; color: var(--text-muted); }

.queue-table {
  overflow: hidden;
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1.5fr 1fr;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-card);
  background: var(--bg-secondary);
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1.5fr 1fr;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  align-items: center;
  transition: background 0.2s;
}

.table-row:hover {
  background: var(--bg-hover);
}

.model-name { font-weight: 600; }

.mono {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.usage-bar {
  display: flex;
  align-items: center;
  gap: 8px;
}

.usage-bar .progress-track {
  flex: 1;
  height: 6px;
}

.usage-text {
  font-size: 12px;
  color: var(--text-muted);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-size: 16px;
}

.config-row {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  font-size: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.config-label { color: var(--text-muted); }
.config-value { color: var(--text-primary); }

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.form-label {
  font-size: 14px;
  color: var(--text-muted);
  min-width: 120px;
}

.form-input {
  background: var(--bg-input);
  border: 1px solid var(--border-primary);
  color: var(--text-primary);
  border-radius: 10px;
  padding: 8px 12px;
  font-size: 14px;
  flex: 1;
  transition: border-color 0.2s;
}

.form-input:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.1);
}

.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stats-item {
  padding: 20px;
  text-align: center;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.stats-label { font-size: 13px; color: var(--text-muted); }
.stats-num { font-size: 28px; font-weight: 700; color: var(--text-primary); }

.stats-detail {
  margin-top: 16px;
  padding: 16px;
}

.stats-detail h4 {
  color: var(--text-primary);
  margin-bottom: 12px;
  font-size: 14px;
  font-weight: 600;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 8px 0;
  color: var(--text-secondary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
