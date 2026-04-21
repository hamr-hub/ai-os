<script setup lang="ts">
import { computed } from 'vue'
import GPUMonitor from '@/components/GPUMonitor.vue'
import ModelManager from '@/components/ModelManager.vue'
import ChatWindow from '@/components/ChatWindow.vue'
import ModelTester from '@/components/ModelTester.vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'

const { modelStatus, runningModelsCount } = useModels()
const { gpuSummary } = useGPU()

const totalModels = computed(() => modelStatus.value ? Object.keys(modelStatus.value).length : 0)
const gpuAvailable = computed(() => gpuSummary.value?.status === 'available')
const gpuName = computed(() => gpuSummary.value?.current?.name || '未检测')
</script>

<template>
  <div class="space-y-6">
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-gradient-to-br from-blue-600 to-blue-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-blue-200 text-sm">运行中的模型</p>
            <p class="text-3xl font-bold text-white mt-1">{{ runningModelsCount }}</p>
          </div>
          <div class="w-12 h-12 bg-white/20 rounded-lg flex items-center justify-center">
            <span class="text-2xl">🚀</span>
          </div>
        </div>
      </div>

      <div class="bg-gradient-to-br from-purple-600 to-purple-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-purple-200 text-sm">可用模型</p>
            <p class="text-3xl font-bold text-white mt-1">{{ totalModels }}</p>
          </div>
          <div class="w-12 h-12 bg-white/20 rounded-lg flex items-center justify-center">
            <span class="text-2xl">📦</span>
          </div>
        </div>
      </div>

      <div class="bg-gradient-to-br from-green-600 to-green-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-green-200 text-sm">GPU 状态</p>
            <p class="text-3xl font-bold text-white mt-1">{{ gpuAvailable ? '在线' : '离线' }}</p>
          </div>
          <div class="w-12 h-12 bg-white/20 rounded-lg flex items-center justify-center">
            <span class="text-2xl">🎮</span>
          </div>
        </div>
      </div>

      <div class="bg-gradient-to-br from-orange-600 to-orange-800 rounded-xl p-5">
        <div class="flex items-center justify-between">
          <div>
            <p class="text-orange-200 text-sm">GPU 型号</p>
            <p class="text-lg font-bold text-white mt-1 truncate">{{ gpuName }}</p>
          </div>
          <div class="w-12 h-12 bg-white/20 rounded-lg flex items-center justify-center">
            <span class="text-2xl">💻</span>
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
