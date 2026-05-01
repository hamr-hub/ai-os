<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useHealthOps } from '@/composables/useHealthOps'
import {
  Heart,
  RefreshCw,
  Loader2,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Activity,
  Server,
  Cpu,
  Zap,
} from 'lucide-vue-next'

const { healthAlert, healthDetail, healthHistory, loading, error, fetchAlert, fetchDetail, fetchHistory, runCheck } = useHealthOps()

const activeTab = ref<'overview' | 'detail' | 'history'>('overview')

let pollTimer: ReturnType<typeof setInterval> | null = null

onMounted(() => {
  fetchAlert()
  fetchDetail()
  fetchHistory()
  pollTimer = setInterval(() => {
    fetchAlert()
    fetchDetail()
  }, 10000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})

const handleRefresh = () => {
  fetchAlert()
  fetchDetail()
  fetchHistory()
}

const handleRunCheck = () => runCheck()

const statusColor = computed(() => {
  const status = healthAlert.value?.status
  if (status === 'healthy') return '#4ade80'
  if (status === 'degraded' || status === 'warning') return '#f59e0b'
  if (status === 'unhealthy') return '#f87171'
  return 'var(--text-muted)'
})

const statusLabel = computed(() => {
  const status = healthAlert.value?.status
  if (status === 'healthy') return '健康'
  if (status === 'degraded') return '降级'
  if (status === 'warning') return '警告'
  if (status === 'unhealthy') return '异常'
  return '--'
})

const statusTag = computed(() => {
  const status = healthAlert.value?.status
  if (status === 'healthy') return 'tag-green'
  if (status === 'degraded' || status === 'warning') return 'tag-orange'
  if (status === 'unhealthy') return 'tag-orange'
  return 'tag-cyan'
})

const checkIcon = (available: boolean) => available ? CheckCircle : XCircle
</script>

<template>
  <div class="health-page fade-in">
    <div class="page-header">
      <div class="header-title">
        <div class="icon-box gradient-green">
          <Heart class="w-5 h-5" />
        </div>
        <h1 class="digital-font">Health Ops</h1>
      </div>
      <p class="header-subtitle">健康运维 · 告警监控 · 服务状态</p>
      <button class="btn btn-secondary" @click="handleRefresh">
        <RefreshCw v-if="loading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" /> 刷新
      </button>
      <button class="btn btn-primary" @click="handleRunCheck">
        <Activity class="w-4 h-4" /> 执行检查
      </button>
    </div>

    <div v-if="error" class="error-banner toast-error">
      <AlertTriangle class="w-4 h-4" />
      {{ error }}
    </div>

    <div class="tab-controls">
      <button :class="['tab-btn', activeTab === 'overview' ? 'active' : '']" @click="activeTab = 'overview'">
        <Heart class="w-4 h-4" /> 健康总览
      </button>
      <button :class="['tab-btn', activeTab === 'detail' ? 'active' : '']" @click="activeTab = 'detail'">
        <Server class="w-4 h-4" /> 服务状态
      </button>
      <button :class="['tab-btn', activeTab === 'history' ? 'active' : '']" @click="activeTab = 'history'">
        <Activity class="w-4 h-4" /> 告警趋势
      </button>
    </div>

    <div v-if="activeTab === 'overview'">
      <div v-if="loading && !healthAlert" class="loading-state">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
      </div>
      <div v-else-if="healthAlert" class="overview-card card-base tech-border fade-in">
        <div class="health-score-row">
          <div class="health-score">
            <span class="score-num digital-font" :style="{ color: statusColor }">{{ healthAlert.health_score }}</span>
            <span class="score-label">健康评分</span>
          </div>
          <div :class="['status-badge tag', statusTag]">
            <component :is="healthAlert.health_score >= 80 ? CheckCircle : healthAlert.health_score >= 50 ? AlertTriangle : XCircle" class="w-4 h-4" />
            {{ statusLabel }}
          </div>
        </div>
        <div v-if="healthAlert.alert_reasons.length" class="alert-reasons">
          <h4>告警原因</h4>
          <div v-for="reason in healthAlert.alert_reasons" :key="reason" class="reason-item">
            <AlertTriangle class="w-3.5 h-3.5" />
            {{ reason }}
          </div>
        </div>
        <div class="timestamp">
          最后更新: {{ healthAlert.timestamp }}
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'detail'">
      <div v-if="loading && !healthDetail" class="loading-state">
        <Loader2 class="w-8 h-8 animate-spin text-primary" />
      </div>
      <div v-else-if="healthDetail" class="detail-grid fade-in">
        <div class="check-card card-base card-hover scale-in stagger-1">
          <h4 class="check-title"><Cpu class="w-4 h-4 text-primary" /> GPU</h4>
          <div class="check-rows">
            <div class="check-row">
              <span class="check-label">可用</span>
              <component :is="checkIcon(healthDetail.checks.gpu.available)" :class="['w-3.5 h-3.5', healthDetail.checks.gpu.available ? 'text-green' : 'text-red']" />
            </div>
            <div class="check-row">
              <span class="check-label">利用率</span>
              <span class="check-val mono">{{ healthDetail.checks.gpu.utilization }}%</span>
            </div>
            <div class="check-row">
              <span class="check-label">温度</span>
              <span class="check-val mono">{{ healthDetail.checks.gpu.temperature }}°C</span>
            </div>
            <div class="check-row">
              <span class="check-label">显存使用</span>
              <span class="check-val mono">{{ healthDetail.checks.gpu.memory_used_pct }}%</span>
            </div>
          </div>
        </div>
        <div class="check-card card-base card-hover scale-in stagger-2">
          <h4 class="check-title"><Server class="w-4 h-4 text-primary" /> Go 后端</h4>
          <div class="check-rows">
            <div class="check-row">
              <span class="check-label">可达</span>
              <component :is="checkIcon(healthDetail.checks.go_backend.reachable)" :class="['w-3.5 h-3.5', healthDetail.checks.go_backend.reachable ? 'text-green' : 'text-red']" />
            </div>
            <div class="check-row">
              <span class="check-label">响应时间</span>
              <span class="check-val mono">{{ healthDetail.checks.go_backend.response_time_ms }}ms</span>
            </div>
          </div>
        </div>
        <div class="check-card card-base card-hover scale-in stagger-3">
          <h4 class="check-title"><Server class="w-4 h-4 text-primary" /> Python 后端</h4>
          <div class="check-rows">
            <div class="check-row">
              <span class="check-label">可达</span>
              <component :is="checkIcon(healthDetail.checks.python_backend.reachable)" :class="['w-3.5 h-3.5', healthDetail.checks.python_backend.reachable ? 'text-green' : 'text-red']" />
            </div>
            <div class="check-row">
              <span class="check-label">响应时间</span>
              <span class="check-val mono">{{ healthDetail.checks.python_backend.response_time_ms }}ms</span>
            </div>
          </div>
        </div>
        <div class="check-card card-base card-hover scale-in stagger-4">
          <h4 class="check-title"><Zap class="w-4 h-4 text-primary" /> vLLM 服务</h4>
          <div class="check-rows">
            <div class="check-row">
              <span class="check-label">运行</span>
              <component :is="checkIcon(healthDetail.checks.vllm_service.running)" :class="['w-3.5 h-3.5', healthDetail.checks.vllm_service.running ? 'text-green' : 'text-red']" />
            </div>
            <div class="check-row">
              <span class="check-label">活跃请求</span>
              <span class="check-val mono">{{ healthDetail.checks.vllm_service.active_requests }}</span>
            </div>
          </div>
        </div>
        <div class="check-card card-base card-hover scale-in stagger-5">
          <h4 class="check-title"><Activity class="w-4 h-4 text-primary" /> Redis</h4>
          <div class="check-rows">
            <div class="check-row">
              <span class="check-label">可用</span>
              <component :is="checkIcon(healthDetail.checks.redis.available)" :class="['w-3.5 h-3.5', healthDetail.checks.redis.available ? 'text-green' : 'text-red']" />
            </div>
            <div class="check-row">
              <span class="check-label">连接</span>
              <component :is="checkIcon(healthDetail.checks.redis.connected)" :class="['w-3.5 h-3.5', healthDetail.checks.redis.connected ? 'text-green' : 'text-red']" />
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'history'">
      <div v-if="!healthHistory.length" class="loading-state">
        <Loader2 v-if="loading" class="w-8 h-8 animate-spin text-primary" />
        <Activity v-else class="w-12 h-12 text-muted" />
        <p v-if="!loading">暂无健康历史数据</p>
      </div>
      <div v-else class="history-table card-base fade-in">
        <div class="table-header">
          <span>时间</span>
          <span>评分</span>
          <span>状态</span>
          <span>告警数</span>
        </div>
        <div v-for="entry in healthHistory" :key="entry.timestamp" class="table-row">
          <span>{{ entry.timestamp }}</span>
          <span class="mono" :style="{ color: entry.health_score >= 80 ? '#4ade80' : entry.health_score >= 50 ? '#f59e0b' : '#f87171' }">{{ entry.health_score }}</span>
          <span :class="['tag', entry.status === 'healthy' ? 'tag-green' : entry.status === 'degraded' || entry.status === 'warning' ? 'tag-orange' : 'tag-orange']">{{ entry.status }}</span>
          <span class="mono">{{ entry.alert_count }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.health-page {
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
  box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
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
  background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(34, 197, 94, 0.08) 100%);
  color: #4ade80;
  border-color: rgba(34, 197, 94, 0.3);
  box-shadow: 0 0 12px rgba(34, 197, 94, 0.1);
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

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-size: 16px;
}

.health-score-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}

.health-score {
  display: flex;
  flex-direction: column;
}

.score-num {
  font-size: 48px;
  font-weight: 700;
}

.score-label {
  font-size: 14px;
  color: var(--text-muted);
}

.alert-reasons {
  margin-top: 16px;
}

.alert-reasons h4 {
  color: var(--text-primary);
  margin-bottom: 8px;
  font-size: 14px;
}

.reason-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 0;
  font-size: 13px;
  color: #fbbf24;
}

.timestamp {
  font-size: 12px;
  color: var(--text-muted);
  margin-top: 16px;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 12px;
}

.check-card {
  padding: 16px;
}

.check-title {
  display: flex;
  align-items: center;
  gap: 6px;
  color: var(--text-primary);
  margin-bottom: 12px;
  font-size: 14px;
}

.check-rows {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.check-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 13px;
  padding: 4px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.check-label { color: var(--text-muted); }
.check-val { color: var(--text-primary); }

.mono {
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.text-green { color: #4ade80; }
.text-red { color: #f87171; }

.history-table {
  overflow: hidden;
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
  padding: 12px 16px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  border-bottom: 1px solid var(--border-card);
  background: var(--bg-secondary);
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 1fr 1fr 1fr;
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
