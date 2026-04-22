<script setup lang="ts">
import { useGPU } from '@/composables/useGPU'
import { Activity, Thermometer, Zap, Cpu, MemoryStick, Fan, RefreshCw, Pause, Play } from 'lucide-vue-next'

const { gpuSummary, loading, error, isRefreshing, isAutoRefreshEnabled, refresh, toggleAutoRefresh, formatMemory } = useGPU()

const getStatusColor = (value: number, warning = 70, danger = 90): string => {
  if (value >= danger) return 'text-red-500'
  if (value >= warning) return 'text-yellow-500'
  return 'text-green-500'
}

const getProgressColor = (value: number, warning = 70, danger = 90): string => {
  if (value >= danger) return 'bg-gradient-to-r from-red-500 to-red-600'
  if (value >= warning) return 'bg-gradient-to-r from-yellow-500 to-orange-500'
  return 'bg-gradient-to-r from-green-500 to-green-600'
}
</script>

<template>
  <div class="bg-card backdrop-blur-sm rounded-2xl p-6 border border-primary card-hover noise-overlay">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center gradient-blue shadow-lg">
          <Cpu class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-primary">GPU 监控</h2>
          <p class="text-secondary text-sm">实时监控 GPU 状态和性能指标</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="refresh"
          :disabled="isRefreshing"
          class="flex items-center gap-1.5 px-3 py-1.5 bg-hover hover:opacity-80 disabled:opacity-50 text-secondary rounded-lg text-sm transition-all"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
          <span>{{ isRefreshing ? '刷新中' : '刷新' }}</span>
        </button>
        <button
          @click="toggleAutoRefresh"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all"
          :class="isAutoRefreshEnabled ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' : 'bg-hover text-muted'"
        >
          <Pause v-if="isAutoRefreshEnabled" class="w-4 h-4" />
          <Play v-else class="w-4 h-4" />
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex flex-col items-center justify-center py-12">
      <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
      <p class="text-secondary">正在检测 GPU...</p>
    </div>

    <div v-else-if="error" class="text-center py-8">
      <div class="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
        <Cpu class="w-8 h-8 text-red-400" />
      </div>
      <p class="text-red-400 font-medium">{{ error }}</p>
    </div>

    <div v-else-if="gpuSummary?.status === 'unavailable'" class="text-center py-8">
      <div class="w-16 h-16 bg-tertiary rounded-full flex items-center justify-center mx-auto mb-4">
        <Cpu class="w-8 h-8 text-muted" />
      </div>
      <p class="text-secondary">未检测到 GPU</p>
    </div>

    <div v-else>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6 stagger-fade-in">
        <div class="bg-tertiary rounded-xl p-4 hover:bg-hover transition-all duration-200 border border-primary/50">
          <div class="flex items-center gap-2 mb-2">
            <MemoryStick class="w-5 h-5 text-blue-400" />
            <span class="text-secondary text-sm">显存使用</span>
          </div>
          <p class="text-2xl font-bold text-primary">
            {{ formatMemory(gpuSummary?.current?.used_memory || 0) }}
          </p>
          <p class="text-muted text-xs mt-1">
            / {{ formatMemory(gpuSummary?.current?.total_memory || 0) }}
          </p>
        </div>

        <div class="bg-tertiary rounded-xl p-4 hover:bg-hover transition-all duration-200 border border-primary/50">
          <div class="flex items-center gap-2 mb-2">
            <Activity class="w-5 h-5 text-green-400" />
            <span class="text-secondary text-sm">GPU 利用率</span>
          </div>
          <p class="text-2xl font-bold" :class="getStatusColor(gpuSummary?.current?.utilization || 0)">
            {{ gpuSummary?.current?.utilization || 0 }}%
          </p>
        </div>

        <div class="bg-tertiary rounded-xl p-4 hover:bg-hover transition-all duration-200 border border-primary/50">
          <div class="flex items-center gap-2 mb-2">
            <Thermometer class="w-5 h-5 text-orange-400" />
            <span class="text-secondary text-sm">温度</span>
          </div>
          <p class="text-2xl font-bold" :class="getStatusColor(gpuSummary?.current?.temperature || 0, 75, 90)">
            {{ gpuSummary?.current?.temperature || 0 }}°C
          </p>
        </div>

        <div class="bg-tertiary rounded-xl p-4 hover:bg-hover transition-all duration-200 border border-primary/50">
          <div class="flex items-center gap-2 mb-2">
            <Zap class="w-5 h-5 text-yellow-400" />
            <span class="text-secondary text-sm">功耗</span>
          </div>
          <p class="text-2xl font-bold text-primary">
            {{ gpuSummary?.current?.power_draw || 0 }}W
          </p>
          <p class="text-muted text-xs mt-1">
            / {{ gpuSummary?.current?.power_limit || 0 }}W
          </p>
        </div>
      </div>

      <div class="space-y-4">
        <div class="bg-tertiary rounded-xl p-4 border border-primary/30">
          <div class="flex justify-between items-center mb-2">
            <div class="flex items-center gap-2">
              <MemoryStick class="w-4 h-4 text-blue-400" />
              <span class="text-secondary text-sm">显存占用</span>
            </div>
            <span class="text-secondary text-sm font-medium">
              {{ gpuSummary?.current?.memory_utilization || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-secondary rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 ease-out shadow-inner"
              :class="getProgressColor(gpuSummary?.current?.memory_utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.memory_utilization || 0}%` }"
            ></div>
          </div>
        </div>

        <div class="bg-tertiary rounded-xl p-4 border border-primary/30">
          <div class="flex justify-between items-center mb-2">
            <div class="flex items-center gap-2">
              <Activity class="w-4 h-4 text-green-400" />
              <span class="text-secondary text-sm">GPU 利用率</span>
            </div>
            <span class="text-secondary text-sm font-medium">
              {{ gpuSummary?.current?.utilization || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-secondary rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 ease-out shadow-inner"
              :class="getProgressColor(gpuSummary?.current?.utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.utilization || 0}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div class="mt-6 pt-6 border-t border-primary">
        <div class="flex items-center gap-2 mb-3">
          <Fan class="w-5 h-5 text-secondary" />
          <span class="text-secondary text-sm font-medium">详细信息</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          <div class="bg-tertiary rounded-lg p-3 border border-primary/30">
            <span class="text-muted text-xs">GPU 名称</span>
            <p class="text-primary font-medium truncate">{{ gpuSummary?.current?.name || '-' }}</p>
          </div>
          <div class="bg-tertiary rounded-lg p-3 border border-primary/30">
            <span class="text-muted text-xs">GPU 数量</span>
            <p class="text-primary font-medium">{{ gpuSummary?.current?.gpu_count || 0 }}</p>
          </div>
          <div class="bg-tertiary rounded-lg p-3 border border-primary/30">
            <span class="text-muted text-xs">风扇转速</span>
            <p class="text-primary font-medium">{{ gpuSummary?.current?.fan_speed || 0 }}%</p>
          </div>
          <div class="bg-tertiary rounded-lg p-3 border border-primary/30">
            <span class="text-muted text-xs">可用显存</span>
            <p class="text-primary font-medium">{{ formatMemory(gpuSummary?.current?.available_memory || 0) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
