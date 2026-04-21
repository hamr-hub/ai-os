<script setup lang="ts">
import { ref } from 'vue'
import { TestTube, CheckCircle, XCircle, Loader2, AlertCircle, Sparkles, MessageCircle, Eye, Cpu, AlertTriangle, Clock, Gauge } from 'lucide-vue-next'
import { testModel, type ModelTestResult } from '@/api/client'
import { useModels } from '@/composables/useModels'

const { modelStatus } = useModels()

const testResult = ref<ModelTestResult | null>(null)
const isTesting = ref(false)
const selectedModel = ref<string>('')
const currentTest = ref<string>('')
const testProgress = ref(0)

const progressSteps = ['初始化', '聊天测试', '工具调用测试', '多模态测试', '性能评估', '生成报告']

const handleTest = async () => {
  if (!selectedModel.value || isTesting.value) return
  
  isTesting.value = true
  testResult.value = null
  testProgress.value = 0
  
  try {
    for (let i = 0; i < progressSteps.length; i++) {
      currentTest.value = progressSteps[i]
      testProgress.value = ((i + 1) / progressSteps.length) * 100
      await new Promise(resolve => setTimeout(resolve, 200))
    }
    
    testResult.value = await testModel(selectedModel.value)
    currentTest.value = '完成'
  } catch (error) {
    testResult.value = {
      status: 'error',
      message: error instanceof Error ? error.message : 'Test failed'
    }
  } finally {
    isTesting.value = false
    currentTest.value = ''
  }
}

const getStatusIcon = (status: string) => {
  switch (status.toLowerCase()) {
    case 'success':
    case 'passed':
      return CheckCircle
    case 'failed':
    case 'error':
      return XCircle
    default:
      return AlertCircle
  }
}

const getStatusColor = (status: string) => {
  switch (status.toLowerCase()) {
    case 'success':
    case 'passed':
      return 'text-green-500'
    case 'failed':
    case 'error':
      return 'text-red-500'
    default:
      return 'text-yellow-500'
  }
}

const getStatusBgColor = (status: string) => {
  switch (status.toLowerCase()) {
    case 'success':
    case 'passed':
      return 'bg-green-500'
    case 'failed':
    case 'error':
      return 'bg-red-500'
    default:
      return 'bg-yellow-500'
  }
}

const getFeatureStatus = (supported: boolean) => {
  return supported ? { icon: CheckCircle, color: 'text-green-500', bgColor: 'bg-green-500/10', text: '支持' } : { icon: XCircle, color: 'text-red-500', bgColor: 'bg-red-500/10', text: '不支持' }
}

const formatDuration = (ms?: number) => {
  if (!ms) return '-'
  if (ms < 1000) return `${ms}ms`
  return `${(ms / 1000).toFixed(2)}s`
}
</script>

<template>
  <div class="bg-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50 card-hover h-full flex flex-col">
    <div class="flex items-center justify-between mb-4">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center gradient-orange">
          <TestTube class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-white">模型检测</h2>
          <p class="text-slate-400 text-sm">检测模型支持的功能特性</p>
        </div>
      </div>
    </div>

    <div class="flex gap-3 mb-4">
      <select
        v-model="selectedModel"
        :disabled="isTesting"
        class="flex-1 bg-slate-700/50 text-white border border-slate-600/50 rounded-xl px-4 py-3 focus:outline-none focus:border-orange-500 focus:ring-1 focus:ring-orange-500/50 transition-all"
      >
        <option value="" disabled>选择模型</option>
        <option v-for="(status, modelName) in modelStatus" :key="modelName" :value="modelName">
          {{ modelName }} ({{ status.running ? '运行中' : '已停止' }})
        </option>
      </select>
      <button
        @click="handleTest"
        :disabled="isTesting || !selectedModel"
        class="px-6 py-3 gradient-orange hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-all flex items-center gap-2 btn-glow"
      >
        <Loader2 v-if="isTesting" class="w-4 h-4 animate-spin" />
        <TestTube v-else class="w-4 h-4" />
        <span>{{ isTesting ? '检测中...' : '一键检测' }}</span>
      </button>
    </div>

    <div v-if="isTesting" class="mb-4">
      <div class="bg-slate-700/30 rounded-xl p-4">
        <div class="flex items-center justify-between mb-2">
          <span class="text-slate-400 text-sm">检测进度</span>
          <span class="text-white text-sm font-medium">{{ currentTest }}</span>
        </div>
        <div class="h-3 bg-slate-600 rounded-full overflow-hidden">
          <div
            class="h-full gradient-orange rounded-full transition-all duration-300 ease-out"
            :style="{ width: `${testProgress}%` }"
          ></div>
        </div>
        <div class="flex justify-between mt-2">
          <span class="text-xs text-slate-500">{{ Math.round(testProgress) }}%</span>
          <div class="flex gap-1">
            <span
              v-for="(_, index) in progressSteps"
              :key="index"
              class="w-2 h-2 rounded-full transition-all duration-200"
              :class="index < testProgress / (100 / progressSteps.length) ? 'bg-orange-500' : 'bg-slate-600'"
            ></span>
          </div>
        </div>
      </div>
    </div>

    <div v-if="testResult" class="flex-1 overflow-y-auto space-y-4">
      <div class="flex items-center gap-3 p-4 bg-slate-700/30 rounded-xl">
        <div class="w-12 h-12 rounded-full flex items-center justify-center" :class="getStatusBgColor(testResult.status) + '/20'">
          <component
            :is="getStatusIcon(testResult.status)"
            class="w-6 h-6"
            :class="getStatusColor(testResult.status)"
          />
        </div>
        <div class="flex-1">
          <p class="font-medium text-white">{{ testResult.message }}</p>
          <p v-if="testResult.report?.model_name" class="text-sm text-slate-400">
            模型: {{ testResult.report.model_name }} | 时间: {{ new Date(testResult.report.test_timestamp).toLocaleString('zh-CN') }}
          </p>
        </div>
        <div v-if="testResult.report" class="px-3 py-1.5 rounded-full text-sm font-medium" :class="getStatusBgColor(testResult.report.overall_status) + '/20 ' + getStatusColor(testResult.report.overall_status)">
          {{ testResult.report.overall_status }}
        </div>
      </div>

      <div v-if="testResult.report?.warnings && testResult.report.warnings.length > 0" class="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-xl">
        <div class="flex items-center gap-2 mb-2">
          <AlertTriangle class="w-5 h-5 text-yellow-500" />
          <span class="text-yellow-400 font-medium">警告</span>
        </div>
        <ul class="text-sm text-yellow-300 space-y-1">
          <li v-for="(warning, index) in testResult.report?.warnings" :key="index" class="flex items-start gap-2">
            <span class="text-yellow-500">-</span>
            {{ warning }}
          </li>
        </ul>
      </div>

      <div v-if="testResult.report?.errors && testResult.report.errors.length > 0" class="p-4 bg-red-500/10 border border-red-500/30 rounded-xl">
        <div class="flex items-center gap-2 mb-2">
          <XCircle class="w-5 h-5 text-red-500" />
          <span class="text-red-400 font-medium">错误</span>
        </div>
        <ul class="text-sm text-red-300 space-y-1">
          <li v-for="(error, index) in testResult.report?.errors" :key="index" class="flex items-start gap-2">
            <span class="text-red-500">-</span>
            {{ error }}
          </li>
        </ul>
      </div>

      <div v-if="testResult.report" class="space-y-4">
        <div class="grid grid-cols-3 gap-3">
          <div class="bg-slate-700/30 rounded-xl p-4 text-center hover:bg-slate-700/50 transition-all duration-200">
            <div class="w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center" :class="getFeatureStatus(testResult.report.feature_support.chat).bgColor">
              <MessageCircle class="w-6 h-6" :class="getFeatureStatus(testResult.report.feature_support.chat).color" />
            </div>
            <p class="text-white font-medium text-sm mb-1">聊天功能</p>
            <span class="px-2 py-1 rounded-full text-xs font-medium" :class="getFeatureStatus(testResult.report.feature_support.chat).bgColor + ' ' + getFeatureStatus(testResult.report.feature_support.chat).color">
              {{ getFeatureStatus(testResult.report.feature_support.chat).text }}
            </span>
          </div>

          <div class="bg-slate-700/30 rounded-xl p-4 text-center hover:bg-slate-700/50 transition-all duration-200">
            <div class="w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center" :class="getFeatureStatus(testResult.report.feature_support.tool_calling).bgColor">
              <Sparkles class="w-6 h-6" :class="getFeatureStatus(testResult.report.feature_support.tool_calling).color" />
            </div>
            <p class="text-white font-medium text-sm mb-1">工具调用</p>
            <span class="px-2 py-1 rounded-full text-xs font-medium" :class="getFeatureStatus(testResult.report.feature_support.tool_calling).bgColor + ' ' + getFeatureStatus(testResult.report.feature_support.tool_calling).color">
              {{ getFeatureStatus(testResult.report.feature_support.tool_calling).text }}
            </span>
          </div>

          <div class="bg-slate-700/30 rounded-xl p-4 text-center hover:bg-slate-700/50 transition-all duration-200">
            <div class="w-12 h-12 mx-auto mb-2 rounded-full flex items-center justify-center" :class="getFeatureStatus(testResult.report.feature_support.multimodal).bgColor">
              <Eye class="w-6 h-6" :class="getFeatureStatus(testResult.report.feature_support.multimodal).color" />
            </div>
            <p class="text-white font-medium text-sm mb-1">多模态</p>
            <span class="px-2 py-1 rounded-full text-xs font-medium" :class="getFeatureStatus(testResult.report.feature_support.multimodal).bgColor + ' ' + getFeatureStatus(testResult.report.feature_support.multimodal).color">
              {{ getFeatureStatus(testResult.report.feature_support.multimodal).text }}
            </span>
          </div>
        </div>

        <div v-if="testResult.report.performance_metrics" class="bg-slate-700/30 rounded-xl p-4">
          <h3 class="text-white font-medium mb-3 flex items-center gap-2">
            <Gauge class="w-4 h-4 text-blue-400" />
            性能指标
          </h3>
          <div class="grid grid-cols-3 gap-3">
            <div class="text-center p-3 bg-slate-600/30 rounded-lg">
              <p class="text-slate-400 text-xs mb-1">延迟</p>
              <p class="text-white text-xl font-bold">{{ testResult.report.performance_metrics.latency_ms }}ms</p>
            </div>
            <div class="text-center p-3 bg-slate-600/30 rounded-lg">
              <p class="text-slate-400 text-xs mb-1">吞吐量</p>
              <p class="text-white text-xl font-bold">{{ testResult.report.performance_metrics.throughput }} req/s</p>
            </div>
            <div class="text-center p-3 bg-slate-600/30 rounded-lg">
              <p class="text-slate-400 text-xs mb-1">Token/s</p>
              <p class="text-white text-xl font-bold">{{ testResult.report.performance_metrics.tokens_per_second || '-' }}</p>
            </div>
          </div>
        </div>

        <div v-if="testResult.report.resource_utilization" class="bg-slate-700/30 rounded-xl p-4">
          <h3 class="text-white font-medium mb-3 flex items-center gap-2">
            <Cpu class="w-4 h-4 text-green-400" />
            资源使用
          </h3>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <div class="flex justify-between mb-2">
                <span class="text-slate-400 text-sm">GPU 利用率</span>
                <span class="text-slate-300 text-sm font-medium">{{ testResult.report.resource_utilization.gpu_utilization || 0 }}%</span>
              </div>
              <div class="h-3 bg-slate-600 rounded-full overflow-hidden">
                <div
                  class="h-full bg-gradient-to-r from-blue-500 to-blue-600 rounded-full transition-all duration-500"
                  :style="{ width: `${testResult.report.resource_utilization.gpu_utilization || 0}%` }"
                ></div>
              </div>
            </div>
            <div>
              <div class="flex justify-between mb-2">
                <span class="text-slate-400 text-sm">显存使用</span>
                <span class="text-slate-300 text-sm font-medium">{{ testResult.report.resource_utilization.memory_usage || 0 }}%</span>
              </div>
              <div class="h-3 bg-slate-600 rounded-full overflow-hidden">
                <div
                  class="h-full bg-gradient-to-r from-green-500 to-green-600 rounded-full transition-all duration-500"
                  :style="{ width: `${testResult.report.resource_utilization.memory_usage || 0}%` }"
                ></div>
              </div>
            </div>
          </div>
        </div>

        <div v-if="testResult.report.test_results" class="bg-slate-700/30 rounded-xl p-4">
          <h3 class="text-white font-medium mb-3 flex items-center gap-2">
            <Clock class="w-4 h-4 text-purple-400" />
            测试详情
          </h3>
          <div class="space-y-2">
            <div
              v-for="(test, index) in testResult.report.test_results"
              :key="index"
              class="p-3 bg-slate-600/30 rounded-lg hover:bg-slate-600/50 transition-all duration-200"
            >
              <div class="flex items-center justify-between mb-1">
                <div class="flex items-center gap-2">
                  <div class="w-6 h-6 rounded-full flex items-center justify-center" :class="getStatusBgColor(test.status) + '/20'">
                    <component
                      :is="getStatusIcon(test.status)"
                      class="w-4 h-4"
                      :class="getStatusColor(test.status)"
                    />
                  </div>
                  <span class="text-white text-sm font-medium">{{ test.test_name }}</span>
                  <span class="text-xs px-2 py-0.5 bg-slate-500 rounded">{{ test.feature_type }}</span>
                </div>
                <div class="flex items-center gap-2">
                  <span class="text-slate-400 text-xs">{{ formatDuration(test.duration) }}</span>
                  <span class="text-xs px-2 py-0.5 rounded-full" :class="getStatusBgColor(test.status) + '/20 ' + getStatusColor(test.status)">
                    {{ test.status }}
                  </span>
                </div>
              </div>
              <p v-if="test.details" class="text-slate-400 text-xs">{{ test.details }}</p>
              <p v-if="test.error" class="text-red-400 text-xs">{{ test.error }}</p>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else-if="!isTesting" class="flex-1 flex items-center justify-center">
      <div class="text-center py-8">
        <div class="w-16 h-16 bg-slate-700/50 rounded-full flex items-center justify-center mx-auto mb-4">
          <TestTube class="w-8 h-8 text-slate-500" />
        </div>
        <p class="text-slate-400">选择模型并点击检测按钮</p>
        <p class="text-slate-500 text-sm mt-1">将检测聊天、工具调用和多模态功能</p>
      </div>
    </div>
  </div>
</template>
