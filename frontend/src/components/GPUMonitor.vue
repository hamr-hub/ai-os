<script setup lang="ts">
import { useGPU } from '@/composables/useGPU'
import { Activity, Thermometer, Zap, Cpu, MemoryStick, Fan, RefreshCw, Pause, Play, TrendingUp, TrendingDown, Minus } from 'lucide-vue-next'

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

const metrics = [
  { key: 'used_memory', label: '显存使用', icon: MemoryStick, color: 'text-blue-400', bgColor: 'bg-blue-500/10' },
  { key: 'utilization', label: 'GPU 利用率', icon: Activity, color: 'text-green-400', bgColor: 'bg-green-500/10' },
  { key: 'temperature', label: '温度', icon: Thermometer, color: 'text-orange-400', bgColor: 'bg-orange-500/10' },
  { key: 'power_draw', label: '功耗', icon: Zap, color: 'text-yellow-400', bgColor: 'bg-yellow-500/10' },
]
</script>

<template>
  <div class="bg-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50 card-hover">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center gradient-blue">
          <Cpu class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-white">GPU 监控</h2>
          <p class="text-slate-400 text-sm">实时监控 GPU 状态和性能指标</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="refresh"
          :disabled="isRefreshing"
          class="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700/50 hover:bg-slate-700 disabled:bg-slate-700/50 disabled:opacity-50 text-slate-300 rounded-lg text-sm transition-all"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
          <span>{{ isRefreshing ? '刷新中' : '刷新' }}</span>
        </button>
        <button
          @click="toggleAutoRefresh"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all"
          :class="isAutoRefreshEnabled ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'"
          :title="isAutoRefreshEnabled ? '暂停自动刷新' : '开启自动刷新'"
        >
          <Pause v-if="isAutoRefreshEnabled" class="w-4 h-4" />
          <Play v-else class="w-4 h-4" />
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex flex-col items-center justify-center py-12">
      <div class="w-12 h-12 border-4 border-blue-500 border-t-transparent rounded-full animate-spin mb-4"></div>
      <p class="text-slate-400">正在检测 GPU...</p>
    </div>

    <div v-else-if="error" class="text-center py-8">
      <div class="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
        <Cpu class="w-8 h-8 text-red-400" />
      </div>
      <p class="text-red-400 font-medium">{{ error }}</p>
    </div>

    <div v-else-if="gpuSummary?.status === 'unavailable'" class="text-center py-8">
      <div class="w-16 h-16 bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
        <Cpu class="w-8 h-8 text-slate-500" />
      </div>
      <p class="text-slate-400">未检测到 GPU</p>
    </div>

    <div v-else>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-6">
        <div class="bg-slate-700/30 rounded-xl p-4 hover:bg-slate-700/50 transition-all duration-200">
          <div class="flex items-center gap-2 mb-2">
            <MemoryStick class="w-5 h-5 text-blue-400" />
            <span class="text-slate-400 text-sm">显存使用</span>
          </div>
          <p class="text-2xl font-bold text-white">
            {{ formatMemory(gpuSummary?.current?.used_memory || 0) }}
          </p>
          <p class="text-slate-500 text-xs mt-1">
            / {{ formatMemory(gpuSummary?.current?.total_memory || 0) }}
          </p>
        </div>

        <div class="bg-slate-700/30 rounded-xl p-4 hover:bg-slate-700/50 transition-all duration-200">
          <div class="flex items-center gap-2 mb-2">
            <Activity class="w-5 h-5 text-green-400" />
            <span class="text-slate-400 text-sm">GPU 利用率</span>
          </div>
          <p class="text-2xl font-bold" :class="getStatusColor(gpuSummary?.current?.utilization || 0)">
            {{ gpuSummary?.current?.utilization || 0 }}%
          </p>
        </div>

        <div class="bg-slate-700/30 rounded-xl p-4 hover:bg-slate-700/50 transition-all duration-200">
          <div class="flex items-center gap-2 mb-2">
            <Thermometer class="w-5 h-5 text-orange-400" />
            <span class="text-slate-400 text-sm">温度</span>
          </div>
          <p class="text-2xl font-bold" :class="getStatusColor(gpuSummary?.current?.temperature || 0, 75, 90)">
            {{ gpuSummary?.current?.temperature || 0 }}°C
          </p>
        </div>

        <div class="bg-slate-700/30 rounded-xl p-4 hover:bg-slate-700/50 transition-all duration-200">
          <div class="flex items-center gap-2 mb-2">
            <Zap class="w-5 h-5 text-yellow-400" />
            <span class="text-slate-400 text-sm">功耗</span>
          </div>
          <p class="text-2xl font-bold text-white">
            {{ gpuSummary?.current?.power_draw || 0 }}W
          </p>
          <p class="text-slate-500 text-xs mt-1">
            / {{ gpuSummary?.current?.power_limit || 0 }}W
          </p>
        </div>
      </div>

      <div class="space-y-4">
        <div class="bg-slate-700/30 rounded-xl p-4">
          <div class="flex justify-between items-center mb-2">
            <div class="flex items-center gap-2">
              <MemoryStick class="w-4 h-4 text-blue-400" />
              <span class="text-slate-400 text-sm">显存占用</span>
            </div>
            <span class="text-slate-300 text-sm font-medium">
              {{ gpuSummary?.current?.memory_utilization || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-slate-600 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 ease-out"
              :class="getProgressColor(gpuSummary?.current?.memory_utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.memory_utilization || 0}%` }"
            ></div>
          </div>
        </div>

        <div class="bg-slate-700/30 rounded-xl p-4">
          <div class="flex justify-between items-center mb-2">
            <div class="flex items-center gap-2">
              <Activity class="w-4 h-4 text-green-400" />
              <span class="text-slate-400 text-sm">GPU 利用率</span>
            </div>
            <span class="text-slate-300 text-sm font-medium">
              {{ gpuSummary?.current?.utilization || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-slate-600 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 ease-out"
              :class="getProgressColor(gpuSummary?.current?.utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.utilization || 0}%` }"
            ></div>
          </div>
        </div>

        <div class="bg-slate-700/30 rounded-xl p-4">
          <div class="flex justify-between items-center mb-2">
            <div class="flex items-center gap-2">
              <Zap class="w-4 h-4 text-yellow-400" />
              <span class="text-slate-400 text-sm">功耗</span>
            </div>
            <span class="text-slate-300 text-sm font-medium">
              {{ gpuSummary?.current?.power_percent || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-slate-600 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 ease-out"
              :class="getProgressColor(gpuSummary?.current?.power_percent || 0)"
              :style="{ width: `${gpuSummary?.current?.power_percent || 0}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div class="mt-6 pt-6 border-t border-slate-700/50">
        <div class="flex items-center gap-2 mb-3">
          <Fan class="w-5 h-5 text-slate-400" />
          <span class="text-slate-400 text-sm font-medium">详细信息</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div class="bg-slate-700/30 rounded-lg p-3">
            <span class="text-slate-500 text-xs">GPU 名称</span>
            <p class="text-slate-300 font-medium">{{ gpuSummary?.current?.name || '-' }}</p>
          </div>
          <div class="bg-slate-700/30 rounded-lg p-3">
            <span class="text-slate-500 text-xs">GPU 数量</span>
            <p class="text-slate-300 font-medium">{{ gpuSummary?.current?.gpu_count || 0 }}</p>
          </div>
          <div class="bg-slate-700/30 rounded-lg p-3">
            <span class="text-slate-500 text-xs">风扇转速</span>
            <p class="text-slate-300 font-medium">{{ gpuSummary?.current?.fan_speed || 0 }}%</p>
          </div>
          <div class="bg-slate-700/30 rounded-lg p-3">
            <span class="text-slate-500 text-xs">可用显存</span>
            <p class="text-slate-300 font-medium">{{ formatMemory(gpuSummary?.current?.available_memory || 0) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
