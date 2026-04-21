<script setup lang="ts">
import { useGPU } from '@/composables/useGPU'
import { Activity, Thermometer, Zap, Cpu, MemoryStick, Fan } from 'lucide-vue-next'

const { gpuSummary, loading, error, formatMemory } = useGPU()

const getStatusColor = (value: number, warning = 70, danger = 90): string => {
  if (value >= danger) return 'text-red-500'
  if (value >= warning) return 'text-yellow-500'
  return 'text-green-500'
}

const getProgressColor = (value: number, warning = 70, danger = 90): string => {
  if (value >= danger) return 'bg-red-500'
  if (value >= warning) return 'bg-yellow-500'
  return 'bg-green-500'
}
</script>

<template>
  <div class="bg-slate-800 rounded-xl p-6">
    <div class="flex items-center gap-3 mb-6">
      <div class="w-10 h-10 bg-blue-600 rounded-lg flex items-center justify-center">
        <Cpu class="w-6 h-6 text-white" />
      </div>
      <div>
        <h2 class="text-xl font-semibold text-white">GPU 监控</h2>
        <p class="text-slate-400 text-sm">实时监控 GPU 状态和性能指标</p>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <div v-else-if="error" class="text-red-400 text-center py-8">
      <p class="font-medium">{{ error }}</p>
    </div>

    <div v-else-if="gpuSummary?.status === 'unavailable'" class="text-center py-8">
      <div class="w-16 h-16 bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
        <Cpu class="w-8 h-8 text-slate-500" />
      </div>
      <p class="text-slate-400">未检测到 GPU</p>
    </div>

    <div v-else>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <div class="bg-slate-700/50 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-2">
            <MemoryStick class="w-5 h-5 text-blue-400" />
            <span class="text-slate-400 text-sm">显存使用</span>
          </div>
          <p class="text-2xl font-bold text-white">
            {{ formatMemory(gpuSummary?.current?.used_memory || 0) }}
          </p>
          <p class="text-slate-500 text-xs">
            / {{ formatMemory(gpuSummary?.current?.total_memory || 0) }}
          </p>
        </div>

        <div class="bg-slate-700/50 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-2">
            <Activity class="w-5 h-5 text-green-400" />
            <span class="text-slate-400 text-sm">GPU 利用率</span>
          </div>
          <p class="text-2xl font-bold" :class="getStatusColor(gpuSummary?.current?.utilization || 0)">
            {{ gpuSummary?.current?.utilization || 0 }}%
          </p>
        </div>

        <div class="bg-slate-700/50 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-2">
            <Thermometer class="w-5 h-5 text-orange-400" />
            <span class="text-slate-400 text-sm">温度</span>
          </div>
          <p class="text-2xl font-bold" :class="getStatusColor(gpuSummary?.current?.temperature || 0, 75, 90)">
            {{ gpuSummary?.current?.temperature || 0 }}°C
          </p>
        </div>

        <div class="bg-slate-700/50 rounded-lg p-4">
          <div class="flex items-center gap-2 mb-2">
            <Zap class="w-5 h-5 text-yellow-400" />
            <span class="text-slate-400 text-sm">功耗</span>
          </div>
          <p class="text-2xl font-bold text-white">
            {{ gpuSummary?.current?.power_draw || 0 }}W
          </p>
          <p class="text-slate-500 text-xs">
            / {{ gpuSummary?.current?.power_limit || 0 }}W
          </p>
        </div>
      </div>

      <div class="space-y-4">
        <div>
          <div class="flex justify-between items-center mb-2">
            <span class="text-slate-400 text-sm">显存占用</span>
            <span class="text-slate-300 text-sm">
              {{ gpuSummary?.current?.memory_utilization || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-slate-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="getProgressColor(gpuSummary?.current?.memory_utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.memory_utilization || 0}%` }"
            ></div>
          </div>
        </div>

        <div>
          <div class="flex justify-between items-center mb-2">
            <span class="text-slate-400 text-sm">GPU 利用率</span>
            <span class="text-slate-300 text-sm">
              {{ gpuSummary?.current?.utilization || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-slate-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="getProgressColor(gpuSummary?.current?.utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.utilization || 0}%` }"
            ></div>
          </div>
        </div>

        <div>
          <div class="flex justify-between items-center mb-2">
            <span class="text-slate-400 text-sm">功耗</span>
            <span class="text-slate-300 text-sm">
              {{ gpuSummary?.current?.power_percent || 0 }}%
            </span>
          </div>
          <div class="h-3 bg-slate-700 rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-300"
              :class="getProgressColor(gpuSummary?.current?.power_percent || 0)"
              :style="{ width: `${gpuSummary?.current?.power_percent || 0}%` }"
            ></div>
          </div>
        </div>
      </div>

      <div class="mt-6 pt-6 border-t border-slate-700">
        <div class="flex items-center gap-2 mb-3">
          <Fan class="w-5 h-5 text-slate-400" />
          <span class="text-slate-400 text-sm">详细信息</span>
        </div>
        <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
          <div>
            <span class="text-slate-500">GPU 名称</span>
            <p class="text-slate-300">{{ gpuSummary?.current?.name || '-' }}</p>
          </div>
          <div>
            <span class="text-slate-500">GPU 数量</span>
            <p class="text-slate-300">{{ gpuSummary?.current?.gpu_count || 0 }}</p>
          </div>
          <div>
            <span class="text-slate-500">风扇转速</span>
            <p class="text-slate-300">{{ gpuSummary?.current?.fan_speed || 0 }}%</p>
          </div>
          <div>
            <span class="text-slate-500">可用显存</span>
            <p class="text-slate-300">{{ formatMemory(gpuSummary?.current?.available_memory || 0) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
