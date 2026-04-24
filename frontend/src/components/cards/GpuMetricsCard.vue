<script setup lang="ts">
import { computed } from 'vue'
import LineChart from '@/components/LineChart.vue'
import { formatBytes } from '@/utils/format'
import { getProgressColor, getStatusLevel } from '@/utils/theme'
import type { GPUHistoryEntry, GPUSummaryCurrent } from '@/types'
import {
  Cpu,
  Thermometer,
  MemoryStick,
  Zap,
  TrendingUp,
  Activity,
  AlertTriangle,
} from 'lucide-vue-next'

const props = withDefaults(
  defineProps<{
    gpu: GPUSummaryCurrent | null
    gpuHistory: GPUHistoryEntry[]
    gpuStatus: 'available' | 'unavailable'
    error?: string | null
    mode?: 'compact' | 'full'
    runningModelsCount?: number
    totalModelsCount?: number
  }>(),
  {
    error: null,
    mode: 'compact',
    runningModelsCount: 0,
    totalModelsCount: 0,
  }
)

const gpuTimeLabels = computed(() =>
  props.gpuHistory.map((entry) => {
    const date = new Date(entry.timestamp)
    return date.toLocaleTimeString('zh-CN', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  })
)

const sparklineDatasets = (key: keyof GPUHistoryEntry, color: string, bgColor: string) => [
  {
    label: '',
    data: props.gpuHistory.map((entry) => Number(entry[key]) || 0),
    borderColor: color,
    backgroundColor: bgColor,
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 2,
  },
]
</script>

<template>
  <div v-if="mode === 'compact'" class="gpu-card-content">
    <template v-if="gpu">
      <div class="gpu-name-row">
        <span class="gpu-label">{{ gpu.name }}</span>
        <span class="gpu-vram"
          >{{ formatBytes(gpu.used_memory) }} / {{ formatBytes(gpu.total_memory) }}</span
        >
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
          <span class="spark-val" :class="getStatusLevel(gpu.utilization ?? 0)"
            >{{ (gpu.utilization ?? 0).toFixed(0) }}%</span
          >
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
          <span class="spark-val" :class="getStatusLevel(gpu.temperature ?? 0, 65, 85)"
            >{{ gpu.temperature ?? '--' }}°C</span
          >
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
          <span class="spark-val" :class="getStatusLevel(gpu.memory_utilization ?? 0)"
            >{{ (gpu.memory_utilization ?? 0).toFixed(0) }}%</span
          >
        </div>
      </div>
      <div class="metrics-row">
        <div class="mini-metric">
          <span class="mini-label">功耗</span>
          <span class="mini-val" :class="getStatusLevel(gpu.power_percent ?? 0)"
            >{{ gpu.power_draw ?? 0 }}W</span
          >
        </div>
        <div class="mini-metric">
          <span class="mini-label">VRAM</span>
          <div class="mini-bar">
            <div
              class="mini-fill"
              :style="{
                width: `${gpu.memory_utilization ?? 0}%`,
                background: getProgressColor(gpu.memory_utilization ?? 0),
              }"
            ></div>
          </div>
        </div>
      </div>
    </template>
    <div v-else-if="error" class="error-state">
      <AlertTriangle class="w-8 h-8" />
      <p>{{ error }}</p>
      <slot name="error-action" />
    </div>
    <div v-else class="empty-state">
      <Cpu class="w-10 h-10 text-muted" />
      <p>GPU 不可用</p>
    </div>
  </div>

  <div v-else class="gpu-stats-content">
    <div v-if="gpu" class="stats-grid">
      <div class="stat-item">
        <Cpu class="stat-icon" />
        <span class="stat-label">利用率</span>
        <span class="stat-val" :class="getStatusLevel(gpu.utilization ?? 0)"
          >{{ (gpu.utilization ?? 0).toFixed(1) }}%</span
        >
      </div>
      <div class="stat-item">
        <Thermometer class="stat-icon" />
        <span class="stat-label">温度</span>
        <span class="stat-val" :class="getStatusLevel(gpu.temperature ?? 0, 65, 85)"
          >{{ gpu.temperature ?? '--' }}°C</span
        >
      </div>
      <div class="stat-item">
        <MemoryStick class="stat-icon" />
        <span class="stat-label">显存</span>
        <span class="stat-val" :class="getStatusLevel(gpu.memory_utilization ?? 0)"
          >{{ (gpu.memory_utilization ?? 0).toFixed(1) }}%</span
        >
      </div>
      <div class="stat-item">
        <Zap class="stat-icon" />
        <span class="stat-label">功耗</span>
        <span class="stat-val">{{ gpu.power_draw ?? 0 }}W / {{ gpu.power_limit ?? 0 }}W</span>
      </div>
      <div class="stat-item">
        <TrendingUp class="stat-icon" />
        <span class="stat-label">VRAM</span>
        <span class="stat-val"
          >{{ formatBytes(gpu.used_memory) }} / {{ formatBytes(gpu.total_memory) }}</span
        >
      </div>
      <div class="stat-item">
        <Activity class="stat-icon" />
        <span class="stat-label">运行模型</span>
        <span class="stat-val">{{ runningModelsCount }} / {{ totalModelsCount }}</span>
      </div>
      <div v-if="gpu.fan_speed !== undefined" class="stat-item">
        <Activity class="stat-icon" />
        <span class="stat-label">风扇</span>
        <span class="stat-val">{{ gpu.fan_speed }}%</span>
      </div>
      <div v-if="gpu.clock_sm !== undefined" class="stat-item">
        <Cpu class="stat-icon" />
        <span class="stat-label">核心频率</span>
        <span class="stat-val">{{ gpu.clock_sm }} MHz</span>
      </div>
    </div>
    <div v-else class="empty-state">GPU 不可用</div>
  </div>
</template>
