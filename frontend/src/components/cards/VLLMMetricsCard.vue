<script setup lang="ts">
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { getVLLMMetrics } from '@/api/client'
import { getProgressColor } from '@/utils/theme'
import type { VLLMMetricsData } from '@/types'
import { Activity, Layers, Clock, Gauge, ArrowRight, Server } from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    initialMetrics?: VLLMMetricsData | null
    refreshInterval?: number
  }>(),
  {
    initialMetrics: null,
    refreshInterval: 5000,
  }
)

const metrics = ref<VLLMMetricsData | null>(props.initialMetrics)
const loading = ref(false)
let intervalId: number | null = null

const fetchMetrics = async () => {
  loading.value = true
  try {
    metrics.value = await getVLLMMetrics()
  } catch {
    if (!metrics.value) {
      metrics.value = {
        vllm_available: false,
        running_requests: 0,
        waiting_requests: 0,
        gpu_cache_usage: 0,
        cpu_cache_usage: 0,
        generation_throughput: 0,
        prompt_throughput: 0,
        time_to_first_token: 0,
        time_per_output_token: 0,
        prefix_cache_hit_rate: 0,
        scraped_at: '',
      }
    }
  } finally {
    loading.value = false
  }
}

const isAvailable = computed(() => metrics.value?.vllm_available ?? false)
const cacheUsagePercent = computed(() => metrics.value?.gpu_cache_usage ?? 0)
const queueStatus = computed(() => {
  const w = metrics.value?.waiting_requests ?? 0
  if (w > 50) return 'critical'
  if (w > 10) return 'warning'
  return 'ok'
})
const cacheStatus = computed(() => {
  const u = cacheUsagePercent.value
  if (u > 90) return 'warning'
  return 'ok'
})

onMounted(() => {
  if (!props.initialMetrics) fetchMetrics()
  intervalId = window.setInterval(fetchMetrics, props.refreshInterval)
})

onUnmounted(() => {
  if (intervalId) clearInterval(intervalId)
})
</script>

<template>
  <div class="card-header">
    <div class="icon-wrap purple"><Server class="card-icon-inner" /></div>
    <span class="card-title">vLLM 服务指标</span>
    <span v-if="isAvailable" class="badge online"><span class="dot online"></span>运行中</span>
    <span v-else class="badge offline"><span class="dot offline"></span>未运行</span>
  </div>

  <template v-if="isAvailable && metrics">
    <div class="metrics-grid">
      <div class="metric-item">
        <Activity class="metric-icon blue" />
        <div class="metric-content">
          <div class="metric-label">运行请求</div>
          <div class="metric-val">{{ metrics.running_requests }}</div>
        </div>
      </div>

      <div class="metric-item">
        <ArrowRight
          class="metric-icon"
          :class="
            queueStatus === 'critical'
              ? 'red'
              : queueStatus === 'warning'
                ? 'yellow'
                : 'green'
          "
        />
        <div class="metric-content">
          <div class="metric-label">等待请求</div>
          <div
            class="metric-val"
            :class="
              queueStatus === 'critical'
                ? 'red'
                : queueStatus === 'warning'
                  ? 'yellow'
                  : ''
            "
          >
            {{ metrics.waiting_requests }}
          </div>
        </div>
      </div>

      <div class="metric-item">
        <Layers
          class="metric-icon"
          :class="cacheStatus === 'warning' ? 'yellow' : 'purple'"
        />
        <div class="metric-content">
          <div class="metric-label">KV 缓存使用</div>
          <div
            class="metric-val"
            :class="cacheStatus === 'warning' ? 'yellow' : ''"
          >
            {{ cacheUsagePercent.toFixed(1) }}%
          </div>
        </div>
      </div>

      <div class="metric-item">
        <Gauge class="metric-icon green" />
        <div class="metric-content">
          <div class="metric-label">生成吞吐</div>
          <div class="metric-val">{{ metrics.generation_throughput.toFixed(1) }} tok/s</div>
        </div>
      </div>

      <div class="metric-item">
        <Clock class="metric-icon orange" />
        <div class="metric-content">
          <div class="metric-label">首 Token 延迟</div>
          <div class="metric-val">{{ metrics.time_to_first_token.toFixed(3) }}s</div>
        </div>
      </div>

      <div class="metric-item">
        <Gauge class="metric-icon indigo" />
        <div class="metric-content">
          <div class="metric-label">缓存命中率</div>
          <div class="metric-val">{{ metrics.prefix_cache_hit_rate.toFixed(1) }}%</div>
        </div>
      </div>
    </div>

    <div class="cache-bar-section">
      <div class="cache-bar-track">
        <div
          class="cache-bar-fill"
          :style="{
            width: `${Math.min(cacheUsagePercent, 100)}%`,
            background: getProgressColor(cacheUsagePercent),
          }"
        />
      </div>
      <div class="cache-bar-label">
        GPU KV Cache: {{ cacheUsagePercent.toFixed(1) }}%
      </div>
    </div>
  </template>

  <div v-else class="empty-state">
    <Server class="empty-icon" />
    <p>vLLM 服务未运行或不可访问</p>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
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

.icon-wrap.purple {
  background: rgba(139, 92, 246, 0.15);
  color: #8b5cf6;
}

.card-icon-inner {
  width: 16px;
  height: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
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

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}

@media (max-width: 640px) {
  .metrics-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.metric-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.metric-icon {
  width: 16px;
  height: 16px;
}

.metric-icon.blue {
  color: #60a5fa;
}

.metric-icon.green {
  color: #22c55e;
}

.metric-icon.red {
  color: #ef4444;
}

.metric-icon.yellow {
  color: #f59e0b;
}

.metric-icon.purple {
  color: #8b5cf6;
}

.metric-icon.orange {
  color: #f97316;
}

.metric-icon.indigo {
  color: #6366f1;
}

.metric-content {
  display: flex;
  flex-direction: column;
}

.metric-label {
  font-size: 11px;
  color: var(--text-muted);
}

.metric-val {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.metric-val.red {
  color: #ef4444;
}

.metric-val.yellow {
  color: #f59e0b;
}

.cache-bar-section {
  margin-top: 12px;
}

.cache-bar-track {
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  overflow: hidden;
}

.cache-bar-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.3s ease;
}

.cache-bar-label {
  font-size: 11px;
  color: var(--text-muted);
  margin-top: 4px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 24px;
  color: var(--text-muted);
  text-align: center;
}

.empty-icon {
  width: 32px;
  height: 32px;
  opacity: 0.5;
}

.empty-state p {
  font-size: 13px;
  margin: 0;
}
</style>
