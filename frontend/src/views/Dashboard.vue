<script setup lang="ts">
import { computed } from 'vue'
import GPUMonitor from '@/components/GPUMonitor.vue'
import ModelManager from '@/components/ModelManager.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ModelTester from '@/components/ModelTester.vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import { Rocket, Package, Cpu, Monitor } from 'lucide-vue-next'

const { modelStatus, runningModelsCount } = useModels()
const { gpuSummary } = useGPU()

const totalModels = computed(() => modelStatus.value ? Object.keys(modelStatus.value).length : 0)
const gpuAvailable = computed(() => gpuSummary.value?.status === 'available')
const gpuName = computed(() => gpuSummary.value?.current?.name || '未检测')

const stats = computed(() => [
  {
    label: '运行中的模型',
    value: runningModelsCount.value,
    icon: Rocket,
    gradient: 'from-blue-500 to-blue-700',
    bgColor: 'bg-blue-500/10',
    iconColor: 'text-blue-400',
  },
  {
    label: '可用模型',
    value: totalModels.value,
    icon: Package,
    gradient: 'from-purple-500 to-purple-700',
    bgColor: 'bg-purple-500/10',
    iconColor: 'text-purple-400',
  },
  {
    label: 'GPU 状态',
    value: gpuAvailable.value ? '在线' : '离线',
    icon: Cpu,
    gradient: gpuAvailable.value ? 'from-green-500 to-green-700' : 'from-red-500 to-red-700',
    bgColor: gpuAvailable.value ? 'bg-green-500/10' : 'bg-red-500/10',
    iconColor: gpuAvailable.value ? 'text-green-400' : 'text-red-400',
    pulse: gpuAvailable.value,
  },
  {
    label: 'GPU 型号',
    value: gpuName.value,
    icon: Monitor,
    gradient: 'from-orange-500 to-orange-700',
    bgColor: 'bg-orange-500/10',
    iconColor: 'text-orange-400',
  },
])
</script>

<template>
  <div class="space-y-6 fade-in">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-white mb-2">欢迎回来</h1>
      <p class="text-slate-400">这是您的 AI 模型管理控制台概览</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div
        v-for="(stat, index) in stats"
        :key="stat.label"
        class="relative overflow-hidden rounded-2xl p-5 transition-all duration-300 card-hover"
        :class="`bg-gradient-to-br ${stat.gradient}`"
        :style="{ animationDelay: `${index * 100}ms` }"
      >
        <div class="absolute inset-0 bg-black/10"></div>
        <div class="absolute top-0 right-0 w-32 h-32 bg-white/10 rounded-full -translate-y-1/2 translate-x-1/2"></div>
        <div class="relative flex items-center justify-between">
          <div>
            <p class="text-white/80 text-sm mb-1">{{ stat.label }}</p>
            <p class="text-3xl font-bold text-white">{{ stat.value }}</p>
          </div>
          <div
            class="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
            :class="[stat.bgColor, stat.pulse ? 'pulse-glow' : '']"
          >
            <component :is="stat.icon" class="w-6 h-6" :class="stat.iconColor" />
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <GPUMonitor />
      <ModelManager />
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <ChatWindow />
      <ModelTester />
    </div>
  </div>
</template>
