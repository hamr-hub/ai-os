<script setup lang="ts">
import { computed } from 'vue'
import GPUMonitor from '@/components/GPUMonitor.vue'
import ModelManager from '@/components/ModelManager.vue'
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
    gradient: 'gradient-blue',
    iconColor: 'text-blue-400',
  },
  {
    label: '可用模型',
    value: totalModels.value,
    icon: Package,
    gradient: 'gradient-purple',
    iconColor: 'text-purple-400',
  },
  {
    label: 'GPU 状态',
    value: gpuAvailable.value ? '在线' : '离线',
    icon: Cpu,
    gradient: gpuAvailable.value ? 'gradient-green' : 'bg-red-500',
    iconColor: gpuAvailable.value ? 'text-green-400' : 'text-red-400',
    pulse: gpuAvailable.value,
  },
  {
    label: 'GPU 型号',
    value: gpuName.value,
    icon: Monitor,
    gradient: 'gradient-orange',
    iconColor: 'text-orange-400',
  },
])
</script>

<template>
  <div class="space-y-8 p-6 fade-in">
    <div class="mb-8">
      <h1 class="text-3xl font-bold text-primary mb-2">欢迎回来</h1>
      <p class="text-secondary">这是您的 AI 模型管理控制台概览</p>
    </div>

    <div class="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-5 stagger-fade-in">
      <div
        v-for="(stat, index) in stats"
        :key="stat.label"
        class="relative overflow-hidden rounded-2xl p-5 transition-all duration-300 card-hover border-glow noise-overlay"
        :class="stat.gradient"
        :style="{ animationDelay: `${index * 100}ms` }"
      >
        <div class="absolute inset-0 bg-black/10"></div>
        <div class="absolute -top-8 -right-8 w-40 h-40 bg-white/10 rounded-full blur-2xl"></div>
        <div class="absolute bottom-0 left-0 w-24 h-24 bg-black/10 rounded-full blur-xl"></div>
        <div class="relative flex items-center justify-between">
          <div>
            <p class="text-white/70 text-sm mb-1">{{ stat.label }}</p>
            <p class="text-3xl font-bold text-white">{{ stat.value }}</p>
          </div>
          <div
            class="w-14 h-14 rounded-2xl bg-white/15 backdrop-blur-sm flex items-center justify-center flex-shrink-0 animate-float"
            :class="{ 'pulse-glow': stat.pulse }"
          >
            <component :is="stat.icon" class="w-7 h-7 text-white" />
          </div>
        </div>
      </div>
    </div>

    <div class="grid grid-cols-1 xl:grid-cols-2 gap-6">
      <GPUMonitor />
      <ModelManager />
    </div>
  </div>
</template>
