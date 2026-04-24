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
  <div
    class="vllm-metrics-card rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-800 p-4"
  >
    <div class="flex items-center justify-between mb-3">
      <div class="flex items-center gap-2">
        <Server class="w-4 h-4 text-purple-500" />
        <h3 class="text-sm font-semibold text-gray-900 dark:text-gray-100">vLLM 服务指标</h3>
      </div>
      <span
        class="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium"
        :class="
          isAvailable
            ? 'bg-green-100 text-green-700 dark:bg-green-900 dark:text-green-300'
            : 'bg-red-100 text-red-700 dark:bg-red-900 dark:text-red-300'
        "
      >
        {{ isAvailable ? '运行中' : '未运行' }}
      </span>
    </div>

    <template v-if="isAvailable && metrics">
      <div class="grid grid-cols-2 gap-3">
        <div class="flex items-center gap-2 p-2 rounded bg-gray-50 dark:bg-gray-700/50">
          <Activity class="w-4 h-4 text-blue-500" />
          <div>
            <div class="text-xs text-gray-500 dark:text-gray-400">运行请求</div>
            <div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {{ metrics.running_requests }}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 p-2 rounded bg-gray-50 dark:bg-gray-700/50">
          <ArrowRight
            class="w-4 h-4"
            :class="
              queueStatus === 'critical'
                ? 'text-red-500'
                : queueStatus === 'warning'
                  ? 'text-yellow-500'
                  : 'text-green-500'
            "
          />
          <div>
            <div class="text-xs text-gray-500 dark:text-gray-400">等待请求</div>
            <div
              class="text-sm font-semibold"
              :class="
                queueStatus === 'critical'
                  ? 'text-red-500'
                  : queueStatus === 'warning'
                    ? 'text-yellow-500'
                    : 'text-gray-900 dark:text-gray-100'
              "
            >
              {{ metrics.waiting_requests }}
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 p-2 rounded bg-gray-50 dark:bg-gray-700/50">
          <Layers
            class="w-4 h-4"
            :class="cacheStatus === 'warning' ? 'text-yellow-500' : 'text-purple-500'"
          />
          <div>
            <div class="text-xs text-gray-500 dark:text-gray-400">KV 缓存使用</div>
            <div
              class="text-sm font-semibold"
              :class="
                cacheStatus === 'warning' ? 'text-yellow-500' : 'text-gray-900 dark:text-gray-100'
              "
            >
              {{ cacheUsagePercent.toFixed(1) }}%
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 p-2 rounded bg-gray-50 dark:bg-gray-700/50">
          <Gauge class="w-4 h-4 text-green-500" />
          <div>
            <div class="text-xs text-gray-500 dark:text-gray-400">生成吞吐</div>
            <div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {{ metrics.generation_throughput.toFixed(1) }} tok/s
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 p-2 rounded bg-gray-50 dark:bg-gray-700/50">
          <Clock class="w-4 h-4 text-orange-500" />
          <div>
            <div class="text-xs text-gray-500 dark:text-gray-400">首 Token 延迟</div>
            <div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {{ metrics.time_to_first_token.toFixed(3) }}s
            </div>
          </div>
        </div>

        <div class="flex items-center gap-2 p-2 rounded bg-gray-50 dark:bg-gray-700/50">
          <Gauge class="w-4 h-4 text-indigo-500" />
          <div>
            <div class="text-xs text-gray-500 dark:text-gray-400">缓存命中率</div>
            <div class="text-sm font-semibold text-gray-900 dark:text-gray-100">
              {{ metrics.prefix_cache_hit_rate.toFixed(1) }}%
            </div>
          </div>
        </div>
      </div>

      <div class="mt-3">
        <div class="h-2 rounded-full bg-gray-200 dark:bg-gray-600 overflow-hidden">
          <div
            class="h-full rounded-full transition-all duration-300"
            :class="getProgressColor(cacheUsagePercent)"
            :style="{ width: `${Math.min(cacheUsagePercent, 100)}%` }"
          />
        </div>
        <div class="text-xs text-gray-400 mt-1">
          GPU KV Cache: {{ cacheUsagePercent.toFixed(1) }}%
        </div>
      </div>
    </template>

    <template v-else>
      <div class="text-center py-4 text-gray-400 dark:text-gray-500">
        <Server class="w-8 h-8 mx-auto mb-2 opacity-50" />
        <p class="text-sm">vLLM 服务未运行或不可访问</p>
      </div>
    </template>
  </div>
</template>
