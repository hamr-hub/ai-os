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
  <div class="ratelimit-page">
    <div class="page-header">
      <div class="header-title">
        <Gauge class="w-6 h-6 text-primary" />
        <h1 class="digital-font">Rate Limit</h1>
      </div>
      <p class="header-subtitle">限流控制 · 排队管理 · 流量统计</p>
      <button class="btn btn-ghost" @click="handleRefresh">
        <RefreshCw v-if="loading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" /> 刷新
      </button>
    </div>

    <div v-if="error" class="error-banner">
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
          <div class="stat-card">
            <Activity class="w-4 h-4 stat-icon" />
            <div class="stat-info">
              <span class="stat-num">{{ totalActiveRequests }}</span>
              <span class="stat-desc">活跃请求</span>
            </div>
          </div>
          <div class="stat-card">
            <Gauge class="w-4 h-4 stat-icon" />
            <div class="stat-info">
              <span class="stat-num">{{ totalConcurrency }}</span>
              <span class="stat-desc">并发上限</span>
            </div>
          </div>
          <div class="stat-card stat-green">
            <CheckCircle class="w-4 h-4 stat-icon" />
            <div class="stat-info">
              <span class="stat-num">{{ totalCanAccept }}</span>
              <span class="stat-desc">可接受</span>
            </div>
          </div>
          <div class="stat-card stat-red">
            <XCircle class="w-4 h-4 stat-icon" />
            <div class="stat-info">
              <span class="stat-num">{{ queueEntries.length - totalCanAccept }}</span>
              <span class="stat-desc">已满</span>
            </div>
          </div>
        </div>

        <div class="queue-table">
          <div class="table-header">
            <span>模型</span>
            <span>活跃请求</span>
            <span>并发上限</span>
            <span>使用率</span>
            <span>状态</span>
          </div>
          <div v-for="entry in queueEntries" :key="entry.name" class="table-row">
            <span class="model-name">{{ entry.name }}</span>
            <span>{{ entry.active_requests }}</span>
            <span>{{ entry.concurrency_limit }}</span>
            <span>{{ formatPct(entry.active_requests, entry.concurrency_limit) }}</span>
            <span :class="['status-tag', entry.can_accept ? 'available' : 'full']">
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
      <div v-else class="config-panel card-base">
        <h3 class="section-title"><Settings class="w-5 h-5" /> 限流配置</h3>
        <div v-if="!editing" class="config-display">
          <div class="config-row">
            <span class="config-label">IP QPS 限制</span>
            <span class="config-value">{{ rateLimitConfig.ip_qps_limit }} 次/{{ rateLimitConfig.ip_qps_window_seconds }}秒</span>
          </div>
          <div class="config-row">
            <span class="config-label">并发上限</span>
            <span class="config-value">{{ rateLimitConfig.concurrency_limit }}</span>
          </div>
          <div class="config-row">
            <span class="config-label">排队超时</span>
            <span class="config-value">{{ rateLimitConfig.queue_timeout_seconds }} 秒</span>
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
            <button class="btn btn-ghost" @click="editing = false">取消</button>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'stats'">
      <div v-if="!rateLimitStats" class="loading-state">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
      </div>
      <div v-else class="stats-panel card-base">
        <h3 class="section-title"><Shield class="w-5 h-5" /> 流量统计</h3>
        <div class="stats-grid">
          <div class="stats-item">
            <span class="stats-label">总拒绝数</span>
            <span class="stats-num">{{ rateLimitStats.total_rejected }}</span>
          </div>
          <div class="stats-item">
            <span class="stats-label">近期429</span>
            <span class="stats-num">{{ rateLimitStats.recent_429_count }}</span>
          </div>
          <div class="stats-item">
            <span class="stats-label">当前排队</span>
            <span class="stats-num">{{ rateLimitStats.current_queue_depth }}</span>
          </div>
        </div>
        <div v-if="Object.keys(rateLimitStats.rejection_by_ip).length" class="stats-detail">
          <h4>按IP拒绝统计</h4>
          <div v-for="(count, ip) in rateLimitStats.rejection_by_ip" :key="ip" class="detail-row">
            <span>{{ ip }}</span>
            <span>{{ count }} 次</span>
          </div>
        </div>
        <div v-if="Object.keys(rateLimitStats.rejection_by_path).length" class="stats-detail">
          <h4>按路径拒绝统计</h4>
          <div v-for="(count, path) in rateLimitStats.rejection_by_path" :key="path" class="detail-row">
            <span>{{ path }}</span>
            <span>{{ count }} 次</span>
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

.tab-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
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
  margin-bottom: 16px;
}

.stat-card {
  background: var(--bg-card);
  padding: 12px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  gap: 8px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.stat-card.stat-green { border-color: rgba(74, 222, 128, 0.2); }
.stat-card.stat-red { border-color: rgba(248, 113, 113, 0.2); }

.stat-icon { color: var(--color-primary); }
.stat-card.stat-green .stat-icon { color: #4ade80; }
.stat-card.stat-red .stat-icon { color: #f87171; }

.stat-info { display: flex; flex-direction: column; }
.stat-num { font-size: 18px; font-weight: 600; color: var(--text-primary); }
.stat-desc { font-size: 12px; color: var(--text-muted); }

.queue-table {
  background: var(--bg-card);
  border-radius: 12px;
  overflow: hidden;
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
  padding: 12px 16px;
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.05);
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr 1fr;
  padding: 12px 16px;
  font-size: 13px;
  color: var(--text-primary);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
  align-items: center;
}

.model-name { font-weight: 600; }

.status-tag {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
}

.status-tag.available { color: #4ade80; }
.status-tag.full { color: #f87171; }

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-size: 16px;
}

.card-base {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.config-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
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
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  flex: 1;
}

.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 16px;
}

.stats-item {
  background: var(--bg-secondary);
  padding: 12px;
  border-radius: 8px;
  text-align: center;
}

.stats-label { font-size: 12px; color: var(--text-muted); }
.stats-num { font-size: 24px; font-weight: 600; color: var(--text-primary); }

.stats-detail {
  margin-top: 16px;
}

.stats-detail h4 {
  color: var(--text-primary);
  margin-bottom: 8px;
  font-size: 14px;
}

.detail-row {
  display: flex;
  justify-content: space-between;
  font-size: 13px;
  padding: 6px 0;
  color: var(--text-muted);
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
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
</style>
