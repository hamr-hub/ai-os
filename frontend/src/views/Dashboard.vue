<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import GPUMonitor from '@/components/GPUMonitor.vue'
import ModelManager from '@/components/ModelManager.vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import { Rocket, Package, Cpu, Monitor, Activity, Clock } from 'lucide-vue-next'

const { modelStatus, runningModelsCount } = useModels()
const { gpuSummary } = useGPU()

const now = ref(new Date())
let timer: ReturnType<typeof setInterval>

onMounted(() => {
  timer = setInterval(() => {
    now.value = new Date()
  }, 1000)
})

onUnmounted(() => {
  clearInterval(timer)
})

const greeting = computed(() => {
  const hour = now.value.getHours()
  if (hour < 6) return '深夜好'
  if (hour < 12) return '早上好'
  if (hour < 14) return '中午好'
  if (hour < 18) return '下午好'
  return '晚上好'
})

const timeStr = computed(() =>
  now.value.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
)

const dateStr = computed(() =>
  now.value.toLocaleDateString('zh-CN', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'long' })
)

const totalModels = computed(() => (modelStatus.value ? Object.keys(modelStatus.value).length : 0))
const gpuAvailable = computed(() => gpuSummary.value?.status === 'available')
const gpuUtilization = computed(() => gpuSummary.value?.current?.utilization ?? 0)
const gpuName = computed(() => gpuSummary.value?.current?.name || '未检测')

const stats = computed(() => [
  {
    label: '运行中的模型',
    value: runningModelsCount.value,
    sub: `共 ${totalModels.value} 个可用`,
    icon: Rocket,
    gradient: 'gradient-blue',
  },
  {
    label: '可用模型',
    value: totalModels.value,
    sub: runningModelsCount.value > 0 ? `${runningModelsCount.value} 个运行中` : '全部已停止',
    icon: Package,
    gradient: 'gradient-purple',
  },
  {
    label: 'GPU 状态',
    value: gpuAvailable.value ? '在线' : '离线',
    sub: gpuAvailable.value ? `利用率 ${gpuUtilization.value}%` : '未检测到 GPU',
    icon: Cpu,
    gradient: gpuAvailable.value ? 'gradient-green' : 'bg-gradient-to-br from-red-500 to-red-700',
    pulse: gpuAvailable.value,
  },
  {
    label: 'GPU 型号',
    value: gpuName.value.length > 16 ? gpuName.value.slice(0, 16) + '…' : gpuName.value,
    sub: gpuName.value !== '未检测' ? `${gpuSummary.value?.current?.gpu_count ?? 0} 张` : '-',
    icon: Monitor,
    gradient: 'gradient-orange',
  },
])
</script>

<template>
  <div class="h-full overflow-y-auto scrollbar-thin">
    <div class="space-y-6 p-6 max-w-screen-2xl mx-auto">
    <!-- Header -->
    <div class="flex items-start justify-between">
      <div class="fade-in">
        <h1 class="text-2xl font-bold text-primary mb-1">{{ greeting }}</h1>
        <p class="text-secondary text-sm">AI 模型管理控制台 · 欢迎使用</p>
      </div>
      <div class="text-right hidden sm:block fade-in" style="animation-delay: 100ms">
        <p class="text-xl font-mono font-semibold text-primary tabular-nums">{{ timeStr }}</p>
        <p class="text-xs text-muted mt-0.5 flex items-center gap-1 justify-end">
          <Clock class="w-3 h-3" />
          {{ dateStr }}
        </p>
      </div>
    </div>

    <!-- Stats Cards -->
    <div class="grid grid-cols-2 xl:grid-cols-4 gap-4">
      <div
        v-for="(stat, index) in stats"
        :key="stat.label"
        class="relative overflow-hidden rounded-xl p-4 card-hover fade-in"
        :class="stat.gradient"
        :style="{ animationDelay: `${(index + 1) * 75}ms` }"
      >
        <div class="relative flex items-start justify-between">
          <div class="min-w-0 flex-1">
            <p class="text-white/70 text-xs mb-1 truncate">{{ stat.label }}</p>
            <p class="text-2xl font-bold text-white truncate">{{ stat.value }}</p>
            <p class="text-white/60 text-xs mt-1 truncate">{{ stat.sub }}</p>
          </div>
          <div
            class="w-10 h-10 rounded-xl bg-white/15 flex items-center justify-center flex-shrink-0 ml-3"
            :class="{ 'pulse-glow': stat.pulse }"
          >
            <component :is="stat.icon" class="w-5 h-5 text-white" />
          </div>
        </div>
      </div>
    </div>

    <!-- System Overview -->
    <div v-if="gpuAvailable" class="bg-card backdrop-blur-sm rounded-2xl p-5 border border-primary fade-in" style="animation-delay: 400ms">
      <div class="flex items-center gap-2 mb-4">
        <Activity class="w-5 h-5 text-green-400" />
        <h3 class="font-semibold text-primary">系统概览</h3>
        <span class="ml-auto text-xs text-green-400 flex items-center gap-1.5">
          <span class="w-1.5 h-1.5 rounded-full bg-green-400 animate-pulse-slow"></span>
          实时更新
        </span>
      </div>
      <div class="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
        <div class="space-y-1">
          <p class="text-muted text-xs">GPU 利用率</p>
          <div class="h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700"
              :class="gpuUtilization >= 90 ? 'bg-red-500' : gpuUtilization >= 70 ? 'bg-yellow-500' : 'bg-green-500'"
              :style="{ width: `${gpuUtilization}%` }"
            ></div>
          </div>
          <p class="font-semibold text-primary tabular-nums">{{ gpuUtilization }}%</p>
        </div>
        <div class="space-y-1">
          <p class="text-muted text-xs">显存利用率</p>
          <div class="h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 bg-blue-500"
              :style="{ width: `${gpuSummary?.current?.memory_utilization ?? 0}%` }"
            ></div>
          </div>
          <p class="font-semibold text-primary tabular-nums">{{ gpuSummary?.current?.memory_utilization ?? 0 }}%</p>
        </div>
        <div class="space-y-1">
          <p class="text-muted text-xs">温度</p>
          <div class="h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700"
              :class="(gpuSummary?.current?.temperature ?? 0) >= 90 ? 'bg-red-500' : (gpuSummary?.current?.temperature ?? 0) >= 75 ? 'bg-yellow-500' : 'bg-orange-400'"
              :style="{ width: `${Math.min((gpuSummary?.current?.temperature ?? 0), 100)}%` }"
            ></div>
          </div>
          <p class="font-semibold text-primary tabular-nums">{{ gpuSummary?.current?.temperature ?? 0 }}°C</p>
        </div>
        <div class="space-y-1">
          <p class="text-muted text-xs">功耗</p>
          <div class="h-1.5 bg-secondary rounded-full overflow-hidden">
            <div
              class="h-full rounded-full transition-all duration-700 bg-yellow-400"
              :style="{ width: `${gpuSummary?.current?.power_limit ? Math.round((gpuSummary.current.power_draw / gpuSummary.current.power_limit) * 100) : 0}%` }"
            ></div>
          </div>
          <p class="font-semibold text-primary tabular-nums">{{ gpuSummary?.current?.power_draw ?? 0 }}W</p>
        </div>
      </div>
    </div>

    <!-- Main Panels -->
    <div class="grid grid-cols-1 xl:grid-cols-2 gap-5">
      <GPUMonitor class="fade-in" style="animation-delay: 500ms" />
      <ModelManager class="fade-in" style="animation-delay: 575ms" />
    </div>
  </div>
  </div>
</template>
