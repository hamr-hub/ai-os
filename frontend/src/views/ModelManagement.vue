<script setup lang="ts">
import { ref, computed, onMounted, watch, type Component } from 'vue'
import { useModels } from '@/composables/useModels'
import {
  runModelTest,
  getTestResults,
  getTestHistory,
  getGPUSummary,
} from '@/api/client'
import type {
  TestResponse,
  TestHistoryEntry,
  TestReport,
  GPUSummary,
  ModelVariant,
  VLLMConfig,
} from '@/types'
import {
  RefreshCw,
  Activity,
  Play,
  Square,
  ArrowRightLeft,
  Star,
  Loader2,
  Zap,
  MessageSquare,
  Eye,
  Wrench,
  Image,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Clock,
  ChevronDown,
  ChevronRight,
  Thermometer,
  MemoryStick,
  Cpu,
  Server,
  HardDrive,
  Settings,
  X,
  Save,
} from 'lucide-vue-next'

const {
  aggregatedModels,
  modelList,
  defaultModel,
  loading,
  actionLoading,
  switchingModel,
  isRefreshing,
  fetchAggregatedModels,
  saveVLLMParams,
  refresh,
  handleStartModel,
  handleStopModel,
  handleSwitchAndSetDefault,
  handleSetDefaultModel,
  handleTogglePreload,
} = useModels()

const runningModels = computed(() => modelList.value.filter((m) => m.running))
const stoppedModels = computed(() => modelList.value.filter((m) => !m.running))

const selectedTestModel = ref('')
const testing = ref(false)
const testResult = ref<TestResponse | null>(null)
const testError = ref<string | null>(null)

const historyList = ref<TestHistoryEntry[]>([])
const historyLoading = ref(false)
const expandedReport = ref<string | null>(null)

const cachedResults = ref<Record<string, TestResponse>>({})
const modelCapabilities = ref<Record<string, TestReport['feature_support']>>({})

const gpuInfo = ref<GPUSummary | null>(null)

const expandedGroups = ref<Set<string>>(new Set())
const selectedModelForConfig = ref<ModelVariant | null>(null)
const vllmConfigModal = ref(false)
const vllmConfig = ref<VLLMConfig | null>(null)
const configSaving = ref(false)
const viewMode = ref<'list' | 'grouped'>('grouped')

const recommendedConfig = computed(() => {
  if (!selectedModelForConfig.value) return null
  return getModelRecommendations(
    selectedModelForConfig.value.name,
    selectedModelForConfig.value.required_memory_gb
  )
})

function formatSizeMB(sizeMB: number): string {
  if (sizeMB >= 1024) {
    return `${(sizeMB / 1024).toFixed(1)} GB`
  }
  return `${sizeMB.toFixed(0)} MB`
}

function toggleGroup(baseName: string) {
  if (expandedGroups.value.has(baseName)) {
    expandedGroups.value.delete(baseName)
  } else {
    expandedGroups.value.add(baseName)
  }
}

function openVLLMConfig(model: ModelVariant) {
  selectedModelForConfig.value = model
  const recommended = getModelRecommendations(model.name, model.required_memory_gb)
  if (model.vllm_config && model.vllm_config.has_custom_config) {
    vllmConfig.value = { ...model.vllm_config }
  } else {
    vllmConfig.value = {
      gpu_memory_utilization: recommended.gpu_memory_utilization,
      max_model_len: recommended.max_model_len,
      max_num_seqs: recommended.max_num_seqs,
      max_num_batched_tokens: 16384,
      tensor_parallel_size: 1,
      has_custom_config: false,
    }
  }
  vllmConfigModal.value = true
}

function closeVLLMConfig() {
  vllmConfigModal.value = false
  selectedModelForConfig.value = null
  vllmConfig.value = null
}

async function saveVLLMConfig() {
  if (!selectedModelForConfig.value || !vllmConfig.value) return

  configSaving.value = true
  try {
    const params = {
      max_num_seqs: vllmConfig.value.max_num_seqs ?? 256,
      gpu_memory_utilization: vllmConfig.value.gpu_memory_utilization ?? 0.90,
      max_model_len: vllmConfig.value.max_model_len ?? 32768,
      max_num_batched_tokens: vllmConfig.value.max_num_batched_tokens ?? 16384,
      tensor_parallel_size: vllmConfig.value.tensor_parallel_size ?? 1,
    }

    await saveVLLMParams(selectedModelForConfig.value.name, params)
    closeVLLMConfig()
  } catch (e) {
    console.error('Failed to save vLLM config:', e)
  } finally {
    configSaving.value = false
  }
}

function getModelRecommendations(modelName: string, vramGB: number) {
  const upperName = modelName.toUpperCase()

  if (upperName.includes('GEMMA-4-31B')) {
    return {
      max_num_seqs: 256,
      gpu_memory_utilization: 0.90,
      max_model_len: 40960,
      max_num_batched_tokens: 16384,
      desc: '30-40GB模型: 可大并发,支持长上下文'
    }
  }
  if (upperName.includes('QWEN3.6-35B')) {
    return {
      max_num_seqs: 256,
      gpu_memory_utilization: 0.90,
      max_model_len: 40960,
      max_num_batched_tokens: 16384,
      desc: '30-40GB模型: 可大并发,支持长上下文'
    }
  }
  if (upperName.includes('QWEN3-235B')) {
    return {
      max_num_seqs: 32,
      gpu_memory_utilization: 0.75,
      max_model_len: 8192,
      max_num_batched_tokens: 4096,
      desc: 'MoE架构: 显存波动大,需保守配置'
    }
  }
  if (upperName.includes('LLAMA-3.3-70B') || upperName.includes('LLAMA-3.3-70B')) {
    return {
      max_num_seqs: 64,
      gpu_memory_utilization: 0.85,
      max_model_len: 16384,
      max_num_batched_tokens: 8192,
      desc: '70-80GB模型: 保守配置,中等并发'
    }
  }
  if (upperName.includes('QWEN2.5-72B')) {
    return {
      max_num_seqs: 64,
      gpu_memory_utilization: 0.85,
      max_model_len: 16384,
      max_num_batched_tokens: 8192,
      desc: '70-80GB模型: 保守配置,中等并发'
    }
  }
  if (upperName.includes('MIDNIGHT-MIQU') || upperName.includes('MIQU-103B')) {
    return {
      max_num_seqs: 32,
      gpu_memory_utilization: 0.80,
      max_model_len: 8192,
      max_num_batched_tokens: 4096,
      desc: '>90GB模型: 严格限制,最低并发'
    }
  }
  if (upperName.includes('DEEPSEEK-R1-70B')) {
    return {
      max_num_seqs: 64,
      gpu_memory_utilization: 0.85,
      max_model_len: 16384,
      max_num_batched_tokens: 8192,
      desc: '70-80GB模型: 保守配置,中等并发'
    }
  }
  if (upperName.includes('LLAMA-3.1-70B') || upperName.includes('LLAMA-3-8B')) {
    return {
      max_num_seqs: 64,
      gpu_memory_utilization: 0.85,
      max_model_len: 16384,
      max_num_batched_tokens: 8192,
      desc: '70-80GB模型: 保守配置,中等并发'
    }
  }

  if (vramGB >= 90) {
    return {
      max_num_seqs: 32,
      gpu_memory_utilization: 0.80,
      max_model_len: 8192,
      max_num_batched_tokens: 4096,
      desc: '>90GB模型: 严格限制,最低并发'
    }
  }
  if (vramGB >= 70) {
    return {
      max_num_seqs: 64,
      gpu_memory_utilization: 0.85,
      max_model_len: 16384,
      max_num_batched_tokens: 8192,
      desc: '70-80GB模型: 保守配置,中等并发'
    }
  }
  if (vramGB >= 45) {
    return {
      max_num_seqs: 32,
      gpu_memory_utilization: 0.75,
      max_model_len: 8192,
      max_num_batched_tokens: 4096,
      desc: '45-70GB模型: MoE架构需保守配置'
    }
  }
  if (vramGB >= 30) {
    return {
      max_num_seqs: 256,
      gpu_memory_utilization: 0.90,
      max_model_len: 40960,
      max_num_batched_tokens: 16384,
      desc: '30-40GB模型: 可大并发,支持长上下文'
    }
  }
  return {
    max_num_seqs: 256,
    gpu_memory_utilization: 0.90,
    max_model_len: 40960,
    max_num_batched_tokens: 16384,
    desc: '<30GB模型: 可大并发,支持超长上下文'
  }
}

function getRecommendedGPUUtil(vramGB: number): string {
  if (vramGB < 45) return '0.90'
  if (vramGB < 70) return '0.75-0.80'
  if (vramGB < 90) return '0.85'
  return '0.80'
}

function getRecommendedMaxSeqs(vramGB: number): string {
  if (vramGB < 45) return '256'
  if (vramGB < 70) return '32'
  if (vramGB < 90) return '64'
  return '32'
}

async function fetchGPUInfo() {
  try {
    gpuInfo.value = await getGPUSummary()
  } catch {
    gpuInfo.value = null
  }
}

function formatMemory(bytes: number): string {
  if (bytes >= 1024 ** 3) {
    return `${(bytes / (1024 ** 3)).toFixed(1)}GB`
  }
  return `${(bytes / (1024 ** 2)).toFixed(0)}MB`
}

function getModelMemoryWarning(modelName: string): string | null {
  if (!gpuInfo.value?.current) return null
  const model = modelList.value.find((m) => m.name === modelName)
  if (!model?.required_memory) return null

  const requiredGB = parseFloat(model.required_memory)
  const availableGB = gpuInfo.value.current.available_memory / (1024 ** 3)

  if (requiredGB > availableGB) {
    return `所需 ${model.required_memory} > 可用 ${formatMemory(gpuInfo.value.current.available_memory)}`
  }
  return null
}

onMounted(() => {
  fetchHistory()
  fetchGPUInfo()
  fetchAggregatedModels()
})

async function fetchCapabilities(modelNames: string[] = runningModels.value.map((model) => model.name)) {
  if (!modelNames.length) return

  const results = await Promise.allSettled(
    modelNames.map(async (modelName) => {
      const data = await getTestResults(modelName)
      return { modelName, featureSupport: data.report?.feature_support }
    })
  )

  results.forEach((result) => {
    if (result.status !== 'fulfilled') {
      console.warn('Failed to fetch model capability:', result.reason)
      return
    }

    const { modelName, featureSupport } = result.value
    if (featureSupport) {
      modelCapabilities.value[modelName] = featureSupport
    }
  })
}

const getCapabilityBadges = (
  modelName: string
): Array<{ label: string; icon: Component; color: string }> => {
  const caps = modelCapabilities.value[modelName]
  const model = modelList.value.find((m) => m.name === modelName)
  const badges: Array<{ label: string; icon: Component; color: string }> = []
  badges.push({ label: '对话', icon: MessageSquare, color: '#6366f1' })
  if (caps?.tool_calling || model?.supports_tool_calling) {
    badges.push({ label: '工具调用', icon: Wrench, color: '#3b82f6' })
  }
  if (caps?.image_generation || model?.supports_image_generation) {
    badges.push({ label: '图片生成', icon: Image, color: '#8b5cf6' })
  }
  if (caps?.multimodal || model?.supports_images) {
    badges.push({ label: '多模态', icon: Eye, color: '#f59e0b' })
  }
  return badges
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    historyList.value = await getTestHistory()
  } catch (e) {
    console.warn('Failed to fetch test history:', e)
  } finally {
    historyLoading.value = false
  }
}

async function runTest() {
  if (!selectedTestModel.value || testing.value) return
  testing.value = true
  testResult.value = null
  testError.value = null
  try {
    testResult.value = await runModelTest(selectedTestModel.value)
    cachedResults.value[selectedTestModel.value] = testResult.value
    if (testResult.value.report?.feature_support) {
      modelCapabilities.value[selectedTestModel.value] = testResult.value.report.feature_support
    }
    await fetchHistory()
  } catch (e: unknown) {
    testError.value = (e as Error)?.message ?? '检测失败'
  } finally {
    testing.value = false
  }
}

async function loadTestResults(modelName: string) {
  if (cachedResults.value[modelName]) {
    testResult.value = cachedResults.value[modelName]
    return
  }
  try {
    const result = await getTestResults(modelName)
    testResult.value = result
    cachedResults.value[modelName] = result
    if (result.report?.feature_support) {
      modelCapabilities.value[modelName] = result.report.feature_support
    }
  } catch (e) {
    console.warn(`Failed to load test results for ${modelName}:`, e)
  }
}

function toggleExpand(name: string) {
  if (expandedReport.value === name) {
    expandedReport.value = null
  } else {
    expandedReport.value = name
    loadTestResults(name)
  }
}

const formatTime = (ts: string | null) => {
  if (!ts) return '--'
  return new Date(ts).toLocaleString('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

const featureItems = computed(() => {
  const fs = testResult.value?.report?.feature_support
  return [
    { key: 'chat', label: '对话', icon: MessageSquare, supported: fs?.chat ?? false },
    { key: 'multimodal', label: '多模态', icon: Eye, supported: fs?.multimodal ?? false },
    { key: 'tools', label: '工具调用', icon: Wrench, supported: fs?.tool_calling ?? false },
    { key: 'image_gen', label: '图片生成', icon: Image, supported: fs?.image_generation ?? false },
  ]
})

const overallStatus = computed(() => testResult.value?.report?.overall_status ?? '')
const statusColor = computed(() => {
  switch (overallStatus.value) {
    case 'passed':
      return '#22c55e'
    case 'degraded':
      return '#f59e0b'
    case 'partial':
      return '#3b82f6'
    case 'failed':
      return '#ef4444'
    default:
      return '#6b7280'
  }
})
const statusLabel = computed(() => {
  switch (overallStatus.value) {
    case 'passed':
      return '全部通过'
    case 'degraded':
      return '部分降级'
    case 'partial':
      return '部分通过'
    case 'failed':
      return '检测失败'
    default:
      return '--'
  }
})

const perfMetrics = computed(() => testResult.value?.report?.performance_metrics)
const resUtil = computed(() => testResult.value?.report?.resource_utilization)
const selectedTestModelInfo = computed(
  () => modelList.value.find((model) => model.name === selectedTestModel.value) ?? null
)
const selectedRuntimeStatus = computed(() => {
  const model = selectedTestModelInfo.value
  if (!model) return null

  const activeVllmModel =
    model.backend_type === 'vllm'
      ? modelList.value.find((item) => item.backend_type === 'vllm' && item.running) ?? null
      : null

  return {
    model,
    isRunning: model.running,
    activeModelName:
      model.backend_type === 'vllm' ? activeVllmModel?.name ?? null : model.running ? model.name : null,
    activeMatches: model.backend_type === 'vllm' ? activeVllmModel?.name === model.name : model.running,
  }
})
const reportRuntimeStatus = computed(() => testResult.value?.report?.runtime_status ?? null)

watch(
  modelList,
  (models) => {
    if (!models.length) return
    if (selectedTestModel.value && models.some((model) => model.name === selectedTestModel.value)) {
      return
    }
    selectedTestModel.value =
      defaultModel.value ?? models.find((model) => model.running)?.name ?? models[0]?.name ?? ''
  },
  { immediate: true }
)

watch(
  () => runningModels.value.map((model) => model.name).sort().join('|'),
  async () => {
    const missingModels = runningModels.value
      .map((model) => model.name)
      .filter((modelName) => !modelCapabilities.value[modelName])

    if (missingModels.length > 0) {
      await fetchCapabilities(missingModels)
    }
  },
  { immediate: true }
)
</script>

<template>
  <div class="model-mgmt">
    <header class="page-header">
      <div class="header-left">
        <Server class="header-icon" />
        <h1 class="header-title">模型管理</h1>
        <span class="count-badge">{{ runningModels.length }} / {{ modelList.length }} 运行中</span>
      </div>
      <div class="header-actions">
        <div class="view-toggle">
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'grouped' }"
            @click="viewMode = 'grouped'"
          >
            分组
          </button>
          <button
            class="toggle-btn"
            :class="{ active: viewMode === 'list' }"
            @click="viewMode = 'list'"
          >
            列表
          </button>
        </div>
        <button class="icon-btn" :disabled="isRefreshing" @click="refresh">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
        </button>
      </div>
    </header>

    <div v-if="switchingModel" class="switch-banner">
      <Loader2 class="w-5 h-5 animate-spin" />
      <span class="switch-text">正在切换到 {{ switchingModel }}，请耐心等待...</span>
      <span class="switch-hint">vLLM 加载模型通常需要 30-120 秒</span>
    </div>

    <div class="content">
      <div class="left-col">
        <section v-if="viewMode === 'grouped' && aggregatedModels?.groups?.length" class="card">
          <div class="card-header">
            <HardDrive class="card-icon" />
            <span class="card-title">模型列表</span>
            <span class="section-count">
              {{ aggregatedModels.total_variants }} 个模型 / {{ aggregatedModels.groups.length }} 组
            </span>
          </div>
          <div v-if="loading" class="loading-state">
            <Loader2 class="w-5 h-5 animate-spin" />
            <span>加载中...</span>
          </div>
          <div v-else class="model-groups">
            <div
              v-for="group in aggregatedModels.groups"
              :key="group.base_name"
              class="model-group"
            >
              <div class="group-header" @click="toggleGroup(group.base_name)">
                <component
                  :is="expandedGroups.has(group.base_name) ? ChevronDown : ChevronRight"
                  class="w-4 h-4"
                />
                <span class="group-name">{{ group.base_name }}</span>
                <span class="group-count">{{ group.variant_count }} 个变体</span>
                <span class="group-size">{{ formatSizeMB(group.total_size_mb) }}</span>
              </div>
              <div v-if="expandedGroups.has(group.base_name)" class="group-variants">
                <div
                  v-for="variant in group.variants"
                  :key="variant.name"
                  class="variant-item"
                  :class="{ running: variant.running, current: variant.is_current }"
                >
                  <div class="variant-info">
                    <div class="variant-header">
                      <span class="variant-name">{{ variant.name }}</span>
                      <div class="variant-badges">
                        <span v-if="variant.running" class="status-badge running">运行中</span>
                        <span v-if="variant.is_current" class="status-badge current">当前</span>
                        <span class="backend-badge">{{ variant.backend_type }}</span>
                      </div>
                    </div>
                    <div class="variant-meta">
                      <span class="meta-item">
                        <HardDrive class="w-3 h-3" />
                        {{ formatSizeMB(variant.size_mb) }}
                      </span>
                      <span v-if="variant.required_memory" class="meta-item">
                        <MemoryStick class="w-3 h-3" />
                        {{ variant.required_memory }}
                      </span>
                      <span v-if="variant.vllm_config?.has_custom_config" class="meta-item config">
                        <Settings class="w-3 h-3" />
                        已配置
                      </span>
                    </div>
                    <p v-if="variant.description" class="variant-desc">{{ variant.description }}</p>
                  </div>
                  <div class="variant-actions">
                    <button
                      class="action-btn small"
                      title="vLLM 配置"
                      @click.stop="openVLLMConfig(variant)"
                    >
                      <Settings class="w-3.5 h-3.5" />
                    </button>
                    <button
                      v-if="!variant.running"
                      class="action-btn primary small"
                      :disabled="!!actionLoading || !!switchingModel"
                      @click.stop="handleSwitchAndSetDefault(variant.name)"
                    >
                      <ArrowRightLeft class="w-3.5 h-3.5" /> 切换
                    </button>
                    <button
                      v-if="variant.running"
                      class="action-btn danger small"
                      :disabled="!!actionLoading || !!switchingModel"
                      @click.stop="handleStopModel(variant.name)"
                    >
                      <Square class="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        <section v-if="viewMode === 'list' && runningModels.length" class="card">
          <div class="card-header">
            <span class="card-title">运行中的模型</span>
            <span class="section-count">{{ runningModels.length }}</span>
          </div>
          <div class="model-cards">
            <div v-for="model in runningModels" :key="model.name" class="model-card running">
              <div class="card-top">
                <div class="model-info">
                  <span class="model-name">{{ model.name }}</span>
                  <p v-if="model.description" class="model-desc">{{ model.description }}</p>
                  <span class="model-meta">
                    <span class="status-dot online"></span>
                    <span class="backend-tag">{{ model.backend_type }}</span>
                    端口 {{ model.port ?? '--' }} · {{ model.active_requests }} 请求
                    <span v-if="model.required_memory" class="mem-req"
                      >显存 {{ model.required_memory }}</span
                    >
                  </span>
                </div>
                <span v-if="defaultModel === model.name" class="default-badge">
                  <Star class="w-3 h-3" /> 默认
                </span>
              </div>
              <div class="card-bottom">
                <div class="cap-badges">
                  <span
                    v-for="b in getCapabilityBadges(model.name)"
                    :key="b.label"
                    class="cap-badge"
                    :style="{
                      color: b.color,
                      borderColor: b.color + '40',
                      background: b.color + '10',
                    }"
                  >
                    <component :is="b.icon" class="w-3 h-3" />
                    {{ b.label }}
                  </span>
                </div>
                <div class="card-actions">
                  <label class="preload-toggle" :title="model.preloaded ? '关闭预加载' : '开启预加载'">
                    <input
                      type="checkbox"
                      :checked="model.preloaded"
                      :disabled="!!actionLoading || !!switchingModel"
                      @change="handleTogglePreload(model.name, ($event.target as HTMLInputElement).checked)"
                    />
                    <span class="toggle-slider"></span>
                  </label>
                  <button
                    class="action-btn"
                    :disabled="!!actionLoading || !!switchingModel"
                    title="设为默认"
                    @click="handleSetDefaultModel(model.name)"
                  >
                    <Star class="w-3.5 h-3.5" />
                  </button>
                  <button
                    class="action-btn danger"
                    :disabled="!!actionLoading || !!switchingModel"
                    title="停止"
                    @click="handleStopModel(model.name)"
                  >
                    <Square class="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
              <div v-if="actionLoading === model.name" class="loading-overlay">
                <Loader2 class="w-5 h-5 animate-spin" />
              </div>
            </div>
          </div>
        </section>

        <section v-if="viewMode === 'list' && stoppedModels.length" class="card">
          <div class="card-header">
            <span class="card-title">已停止</span>
            <span class="section-count">{{ stoppedModels.length }}</span>
          </div>
          <div class="model-list">
            <div v-for="model in stoppedModels" :key="model.name" class="model-item">
              <div class="item-info">
                <span class="item-name">{{ model.name }}</span>
                <p v-if="model.description" class="item-desc">{{ model.description }}</p>
                <span class="item-meta">
                  <span class="status-dot offline"></span>
                  <span class="backend-tag">{{ model.backend_type }}</span>
                  端口 {{ model.port ?? '--' }}
                  <span v-if="model.preloaded" class="preload-tag">预加载</span>
                  <span v-if="model.required_memory" class="mem-req"
                    >显存 {{ model.required_memory }}</span
                  >
                </span>
                <span v-if="getModelMemoryWarning(model.name)" class="mem-warning">
                  <AlertTriangle class="w-3 h-3" />
                  {{ getModelMemoryWarning(model.name) }}
                </span>
              </div>
              <div class="item-actions">
                <label class="preload-toggle" :title="model.preloaded ? '关闭预加载' : '开启预加载'">
                  <input
                    type="checkbox"
                    :checked="model.preloaded"
                    :disabled="!!actionLoading || !!switchingModel"
                    @change="handleTogglePreload(model.name, ($event.target as HTMLInputElement).checked)"
                  />
                  <span class="toggle-slider"></span>
                </label>
                <button
                  class="action-btn primary"
                  :disabled="!!actionLoading || !!switchingModel"
                  @click="handleSwitchAndSetDefault(model.name)"
                >
                  <ArrowRightLeft class="w-3.5 h-3.5" /> 切换
                </button>
                <button
                  class="action-btn"
                  :disabled="!!actionLoading || !!switchingModel"
                  @click="handleStartModel(model.name)"
                >
                  <Play class="w-3.5 h-3.5" /> 启动
                </button>
              </div>
            </div>
          </div>
        </section>

        <div v-if="viewMode === 'list' && !modelList.length" class="card empty-card">暂无可用模型</div>
      </div>

      <div class="right-col">
        <section class="card">
          <div class="card-header">
            <Zap class="card-icon" />
            <span class="card-title">模型能力检测</span>
          </div>
          <p class="section-desc">检测模型是否支持对话、多模态、工具调用和图片生成能力</p>
          <div class="test-controls">
            <select v-model="selectedTestModel" class="model-select" :disabled="testing">
              <option value="" disabled>选择模型</option>
              <option v-for="m in modelList" :key="m.name" :value="m.name">
                {{ m.name }} {{ m.running ? '(运行中)' : '' }}
              </option>
            </select>
            <button class="test-btn" :disabled="!selectedTestModel || testing" @click="runTest">
              <Loader2 v-if="testing" class="w-4 h-4 animate-spin" />
              <Activity v-else class="w-4 h-4" />
              {{ testing ? '检测中...' : '开始检测' }}
            </button>
          </div>

          <div v-if="selectedRuntimeStatus" class="runtime-panel">
            <div class="runtime-header">
              <Activity class="w-4 h-4" />
              <span>实际运行情况</span>
            </div>
            <div class="runtime-grid">
              <div class="runtime-item">
                <span class="runtime-label">当前模型</span>
                <span class="runtime-value">{{ selectedRuntimeStatus.model.name }}</span>
              </div>
              <div class="runtime-item">
                <span class="runtime-label">运行状态</span>
                <span class="runtime-value" :class="selectedRuntimeStatus.isRunning ? 'ok' : 'muted'">
                  {{ selectedRuntimeStatus.isRunning ? '运行中' : '未运行' }}
                </span>
              </div>
              <div class="runtime-item">
                <span class="runtime-label">实际活动模型</span>
                <span class="runtime-value">{{ selectedRuntimeStatus.activeModelName || '无' }}</span>
              </div>
              <div class="runtime-item">
                <span class="runtime-label">是否当前实例</span>
                <span class="runtime-value" :class="selectedRuntimeStatus.activeMatches ? 'ok' : 'warn'">
                  {{ selectedRuntimeStatus.activeMatches ? '是' : '否' }}
                </span>
              </div>
              <div class="runtime-item">
                <span class="runtime-label">后端</span>
                <span class="runtime-value">{{ selectedRuntimeStatus.model.backend_type || '--' }}</span>
              </div>
              <div class="runtime-item">
                <span class="runtime-label">端口 / 请求</span>
                <span class="runtime-value"
                  >{{ selectedRuntimeStatus.model.port ?? '--' }} / {{
                    selectedRuntimeStatus.model.active_requests
                  }}</span
                >
              </div>
            </div>
          </div>

          <div v-if="testError" class="error-banner">
            <AlertTriangle class="w-4 h-4" />
            <span>{{ testError }}</span>
          </div>

          <div v-if="testResult" class="results">
            <div class="overall-status" :style="{ borderColor: statusColor }">
              <span class="status-dot-lg" :style="{ background: statusColor }"></span>
              <span class="status-text" :style="{ color: statusColor }">{{ statusLabel }}</span>
              <span class="status-model">{{ testResult.report?.model_name }}</span>
              <span class="status-time">{{
                formatTime(testResult.report?.test_timestamp ?? null)
              }}</span>
            </div>

            <div v-if="reportRuntimeStatus" class="runtime-panel subtle">
              <div class="runtime-header">
                <Server class="w-4 h-4" />
                <span>检测时运行快照</span>
              </div>
              <div class="runtime-grid">
                <div class="runtime-item">
                  <span class="runtime-label">请求模型</span>
                  <span class="runtime-value">{{ reportRuntimeStatus.requested_model }}</span>
                </div>
                <div class="runtime-item">
                  <span class="runtime-label">实际活动模型</span>
                  <span class="runtime-value">{{ reportRuntimeStatus.active_model || '无' }}</span>
                </div>
                <div class="runtime-item">
                  <span class="runtime-label">服务状态</span>
                  <span class="runtime-value" :class="reportRuntimeStatus.service_running ? 'ok' : 'warn'">
                    {{ reportRuntimeStatus.service_running ? '运行中' : '未运行' }}
                  </span>
                </div>
                <div class="runtime-item">
                  <span class="runtime-label">模型匹配</span>
                  <span class="runtime-value" :class="reportRuntimeStatus.active_model_matches ? 'ok' : 'warn'">
                    {{ reportRuntimeStatus.active_model_matches ? '匹配' : '不匹配' }}
                  </span>
                </div>
              </div>
            </div>

            <div class="features-grid">
              <div
                v-for="feat in featureItems"
                :key="feat.key"
                class="feature-card"
                :class="{ supported: feat.supported }"
              >
                <component :is="feat.icon" class="feature-icon" />
                <span class="feature-label">{{ feat.label }}</span>
                <CheckCircle v-if="feat.supported" class="w-4 h-4 text-green-500" />
                <XCircle v-else class="w-4 h-4 text-gray-500" />
              </div>
            </div>

            <div v-if="perfMetrics?.overall" class="metrics-section">
              <h4 class="sub-title">性能指标</h4>
              <div class="perf-grid">
                <div class="perf-card">
                  <Zap class="perf-icon" />
                  <span class="perf-value">{{
                    perfMetrics.overall.avg_tps?.toFixed(1) ?? '--'
                  }}</span>
                  <span class="perf-label">Token/s</span>
                </div>
                <div class="perf-card">
                  <Clock class="perf-icon" />
                  <span class="perf-value">{{
                    perfMetrics.overall.avg_latency?.toFixed(2) ?? '--'
                  }}</span>
                  <span class="perf-label">延迟(秒)</span>
                </div>
                <div class="perf-card">
                  <Activity class="perf-icon" />
                  <span class="perf-value"
                    >{{ perfMetrics.overall.pass_rate?.toFixed(0) ?? '--' }}%</span
                  >
                  <span class="perf-label">通过率</span>
                </div>
                <div class="perf-card">
                  <CheckCircle class="perf-icon" />
                  <span class="perf-value"
                    >{{ perfMetrics.overall.tests_passed ?? 0 }}/{{
                      perfMetrics.overall.tests_total ?? 0
                    }}</span
                  >
                  <span class="perf-label">测试通过</span>
                </div>
              </div>
            </div>

            <div v-if="resUtil" class="metrics-section">
              <h4 class="sub-title">资源使用</h4>
              <div class="res-grid">
                <div v-if="resUtil.gpu?.available" class="res-item">
                  <Thermometer class="w-3.5 h-3.5" />
                  <span>GPU 温度</span>
                  <span class="res-val">{{ resUtil.gpu.end_temperature ?? '--' }}°C</span>
                </div>
                <div v-if="resUtil.gpu?.available" class="res-item">
                  <Cpu class="w-3.5 h-3.5" />
                  <span>GPU 利用率</span>
                  <span class="res-val">{{ resUtil.gpu.end_utilization ?? '--' }}%</span>
                </div>
                <div v-if="resUtil.gpu?.available" class="res-item">
                  <MemoryStick class="w-3.5 h-3.5" />
                  <span>显存</span>
                  <span class="res-val"
                    >{{ resUtil.gpu.end_memory_used_mb?.toFixed(0) ?? '--' }} MB</span
                  >
                </div>
                <div v-if="resUtil.test_duration_seconds" class="res-item">
                  <Clock class="w-3.5 h-3.5" />
                  <span>检测耗时</span>
                  <span class="res-val"
                    >{{ resUtil.test_duration_seconds?.toFixed(1) ?? '--' }}s</span
                  >
                </div>
              </div>
            </div>

            <div v-if="testResult.report?.test_results?.length" class="metrics-section">
              <h4 class="sub-title">检测详情</h4>
              <div class="detail-list">
                <div
                  v-for="tr in testResult.report.test_results"
                  :key="tr.test_name"
                  class="detail-item"
                >
                  <span class="detail-name">{{ tr.test_name }}</span>
                  <span class="detail-status" :class="tr.status">
                    <CheckCircle v-if="tr.status === 'passed'" class="w-3.5 h-3.5" />
                    <XCircle v-else-if="tr.status === 'failed'" class="w-3.5 h-3.5" />
                    <AlertTriangle v-else class="w-3.5 h-3.5" />
                    {{ tr.status }}
                  </span>
                  <span v-if="tr.duration" class="detail-duration"
                    >{{ tr.duration.toFixed(2) }}s</span
                  >
                </div>
              </div>
            </div>
          </div>
        </section>

        <section class="card">
          <div class="card-header">
            <Clock class="card-icon" />
            <span class="card-title">检测历史</span>
            <button class="icon-btn small" :disabled="historyLoading" @click="fetchHistory">
              <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': historyLoading }" />
            </button>
          </div>
          <div v-if="historyList.length" class="history-list">
            <div
              v-for="entry in historyList"
              :key="`${entry.model_name}-${entry.timestamp}`"
              class="history-item"
            >
              <div class="history-header" @click="toggleExpand(entry.model_name)">
                <component
                  :is="expandedReport === entry.model_name ? ChevronDown : ChevronRight"
                  class="w-3.5 h-3.5 text-muted"
                />
                <span class="history-name">{{ entry.model_name }}</span>
                <span
                  class="history-status"
                  :style="{
                    color:
                      entry.status === 'passed'
                        ? '#22c55e'
                        : entry.status === 'failed'
                          ? '#ef4444'
                          : '#f59e0b',
                  }"
                >
                  {{ entry.overall_status || entry.status }}
                </span>
                <span class="history-time">{{ formatTime(entry.timestamp) }}</span>
              </div>
              <div
                v-if="
                  expandedReport === entry.model_name && cachedResults[entry.model_name]?.report
                "
                class="history-detail"
              >
                <div class="feature-mini">
                  <span
                    :class="{
                      supported: cachedResults[entry.model_name]?.report?.feature_support?.chat,
                    }"
                  >
                    <MessageSquare class="w-3 h-3" /> 对话
                  </span>
                  <span
                    :class="{
                      supported:
                        cachedResults[entry.model_name]?.report?.feature_support?.tool_calling,
                    }"
                  >
                    <Wrench class="w-3 h-3" /> 工具
                  </span>
                  <span
                    :class="{
                      supported: (cachedResults[entry.model_name]?.report?.feature_support as any)
                        ?.image_generation,
                    }"
                  >
                    <Image class="w-3 h-3" /> 图片
                  </span>
                </div>
              </div>
            </div>
          </div>
          <div v-else class="empty-state">暂无检测记录</div>
        </section>
      </div>
    </div>

    <div v-if="vllmConfigModal" class="modal-overlay" @click.self="closeVLLMConfig">
      <div class="modal-content vllm-config-modal">
        <div class="modal-header">
          <div class="modal-title">
            <Settings class="w-5 h-5" />
            <span>vLLM 启动参数配置</span>
          </div>
          <button class="modal-close" @click="closeVLLMConfig">
            <X class="w-5 h-5" />
          </button>
        </div>
        <div v-if="selectedModelForConfig && vllmConfig" class="modal-body">
          <div class="config-model-info">
            <span class="config-model-name">{{ selectedModelForConfig.name }}</span>
            <span v-if="selectedModelForConfig.required_memory" class="config-model-mem">
              {{ selectedModelForConfig.required_memory }}
            </span>
          </div>

          <div v-if="gpuInfo?.current" class="gpu-recommend">
            <AlertTriangle class="w-4 h-4" />
            <span>当前可用显存: {{ formatMemory(gpuInfo.current.available_memory) }}</span>
            <span class="recommend-text">
              推荐配置: gpu_memory_utilization={{ getRecommendedGPUUtil(selectedModelForConfig.required_memory_gb) }},
              max_num_seqs={{ getRecommendedMaxSeqs(selectedModelForConfig.required_memory_gb) }}
            </span>
          </div>

          <div class="config-form">
            <div class="config-row">
              <label class="config-label">
                <span class="label-text">gpu_memory_utilization</span>
                <span class="label-desc">GPU 显存利用率 (0.1-0.99)</span>
              </label>
              <div class="config-input-wrap">
                <input
                  v-model.number="vllmConfig.gpu_memory_utilization"
                  type="number"
                  step="0.01"
                  min="0.1"
                  max="0.99"
                  class="config-input"
                  :placeholder="recommendedConfig?.gpu_memory_utilization?.toString() || '0.90'"
                />
                <span class="input-suffix">推荐: {{ recommendedConfig?.gpu_memory_utilization || 0.90 }}</span>
              </div>
            </div>

            <div class="config-row">
              <label class="config-label">
                <span class="label-text">max_model_len</span>
                <span class="label-desc">最大模型上下文长度</span>
              </label>
              <div class="config-input-wrap">
                <input
                  v-model.number="vllmConfig.max_model_len"
                  type="number"
                  step="1024"
                  min="512"
                  class="config-input"
                  :placeholder="recommendedConfig?.max_model_len?.toString() || '32768'"
                />
                <span class="input-suffix">推荐: {{ recommendedConfig?.max_model_len || 32768 }}</span>
              </div>
            </div>

            <div class="config-row">
              <label class="config-label">
                <span class="label-text">max_num_seqs</span>
                <span class="label-desc">最大并发序列数</span>
              </label>
              <div class="config-input-wrap">
                <input
                  v-model.number="vllmConfig.max_num_seqs"
                  type="number"
                  step="1"
                  min="1"
                  class="config-input"
                  :placeholder="recommendedConfig?.max_num_seqs?.toString() || '64'"
                />
                <span class="input-suffix">推荐: {{ recommendedConfig?.max_num_seqs || 64 }}</span>
              </div>
            </div>

            <div class="config-row">
              <label class="config-label">
                <span class="label-text">max_num_batched_tokens</span>
                <span class="label-desc">最大批处理 token 数</span>
              </label>
              <div class="config-input-wrap">
                <input
                  v-model.number="vllmConfig.max_num_batched_tokens"
                  type="number"
                  step="1024"
                  min="1"
                  class="config-input"
                  placeholder="16384"
                />
                <span class="input-suffix">默认: 16384</span>
              </div>
            </div>

            <div class="config-row">
              <label class="config-label">
                <span class="label-text">tensor_parallel_size</span>
                <span class="label-desc">Tensor 并行大小 (多 GPU)</span>
              </label>
              <div class="config-input-wrap">
                <input
                  v-model.number="vllmConfig.tensor_parallel_size"
                  type="number"
                  step="1"
                  min="1"
                  class="config-input"
                  placeholder="1"
                />
                <span class="input-suffix">默认: 1</span>
              </div>
            </div>

            <div v-if="recommendedConfig" class="config-recommend-hint">
              <span class="hint-label">配置说明:</span>
              <span class="hint-text">{{ recommendedConfig.desc }}</span>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button class="btn secondary" @click="closeVLLMConfig">取消</button>
          <button class="btn primary" :disabled="configSaving" @click="saveVLLMConfig">
            <Loader2 v-if="configSaving" class="w-4 h-4 animate-spin" />
            <Save v-else class="w-4 h-4" />
            {{ configSaving ? '保存中...' : '保存配置' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-mgmt {
  height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.page-header {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-primary);
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}
.header-icon {
  width: 18px;
  height: 18px;
  color: var(--text-muted);
}
.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.count-badge {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 10px;
}

.icon-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 34px;
  height: 34px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: var(--bg-secondary);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.25s;
}
.icon-btn:hover:not(:disabled) {
  color: var(--color-primary);
  border-color: var(--color-primary);
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
}
.icon-btn:disabled {
  opacity: 0.5;
}
.icon-btn.small {
  width: 28px;
  height: 28px;
}

.content {
  flex: 1;
  overflow: hidden;
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
  padding: 16px 24px;
}

.left-col,
.right-col {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.card {
  background: var(--bg-card);
  border-radius: 16px;
  border: 1px solid var(--border-card);
  padding: 20px;
  box-shadow: var(--shadow);
  transition: all 0.3s ease;
  animation: fade-in 0.4s ease-out;
  position: relative;
  overflow: hidden;
}
.card:hover {
  border-color: rgba(99, 102, 241, 0.25);
  box-shadow:
    var(--shadow-md),
    0 0 12px rgba(99, 102, 241, 0.08);
  transform: translateY(-1px);
}

.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.card-icon {
  width: 18px;
  height: 18px;
  color: var(--color-primary);
  filter: drop-shadow(0 0 4px rgba(99, 102, 241, 0.3));
  transition: transform 0.2s;
}
.card:hover .card-icon {
  transform: scale(1.1);
}
.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.section-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 1px 6px;
  border-radius: 8px;
  margin-left: auto;
}
.section-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 14px;
  line-height: 1.5;
}

.model-cards {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-card {
  position: relative;
  padding: 14px;
  background: var(--bg-secondary);
  border-radius: 10px;
  border-left: 3px solid #22c55e;
  transition: all 0.2s;
}
.model-card:hover {
  transform: translateX(4px);
  border-left-color: var(--color-primary);
  box-shadow: 0 2px 12px rgba(99, 102, 241, 0.1);
}

.card-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 10px;
}
.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.model-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}
.model-desc {
  font-size: 12px;
  color: var(--text-muted);
  margin: 4px 0;
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}
.model-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
  flex-wrap: wrap;
}
.backend-tag {
  font-size: 10px;
  text-transform: uppercase;
  background: var(--bg-tertiary);
  padding: 1px 4px;
  border-radius: 4px;
  color: var(--text-secondary);
}
.mem-req {
  color: var(--color-primary-light);
  font-weight: 500;
}
.mem-warning {
  display: flex;
  align-items: center;
  gap: 4px;
  margin-top: 6px;
  padding: 6px 10px;
  background: rgba(239, 68, 68, 0.1);
  border: 1px solid rgba(239, 68, 68, 0.3);
  border-radius: 6px;
  font-size: 11px;
  color: #ef4444;
}
.status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  display: inline-block;
}
.status-dot.online {
  background: #22c55e;
  box-shadow: 0 0 6px rgba(34, 197, 94, 0.4);
}
.status-dot.offline {
  background: #6b7280;
}

.default-badge {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.card-bottom {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
}

.cap-badges {
  display: flex;
  gap: 4px;
  flex-wrap: wrap;
}
.cap-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  font-size: 10px;
  font-weight: 500;
  padding: 2px 7px;
  border-radius: 4px;
  border: 1px solid;
}

.card-actions {
  display: flex;
  gap: 4px;
}

.action-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 10px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid var(--border-primary);
  background: var(--bg-card);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}
.action-btn:hover:not(:disabled) {
  color: var(--text-primary);
  border-color: var(--border-secondary);
}
.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.action-btn.primary {
  color: #22c55e;
  border-color: rgba(34, 197, 94, 0.3);
}
.action-btn.primary:hover:not(:disabled) {
  background: rgba(34, 197, 94, 0.06);
}
.action-btn.danger {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}
.action-btn.danger:hover:not(:disabled) {
  background: rgba(239, 68, 68, 0.06);
}

.model-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  transition: background 0.2s;
}
.model-item:hover {
  background: var(--bg-tertiary);
  transform: translateX(2px);
}

.item-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.item-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}
.item-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin: 2px 0;
  line-height: 1.3;
}
.item-meta {
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.preload-tag {
  font-size: 10px;
  color: #3b82f6;
  background: rgba(59, 130, 246, 0.1);
  padding: 1px 5px;
  border-radius: 3px;
}
.preload-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  cursor: pointer;
  width: 28px;
  height: 16px;
  flex-shrink: 0;
}
.preload-toggle input {
  opacity: 0;
  width: 0;
  height: 0;
  position: absolute;
}
.preload-toggle .toggle-slider {
  position: absolute;
  inset: 0;
  background: #374151;
  border-radius: 8px;
  transition: background 0.2s;
}
.preload-toggle .toggle-slider::before {
  content: '';
  position: absolute;
  width: 12px;
  height: 12px;
  left: 2px;
  top: 2px;
  background: #fff;
  border-radius: 50%;
  transition: transform 0.2s;
}
.preload-toggle input:checked + .toggle-slider {
  background: #3b82f6;
}
.preload-toggle input:checked + .toggle-slider::before {
  transform: translateX(12px);
}
.preload-toggle input:disabled + .toggle-slider {
  opacity: 0.5;
  cursor: not-allowed;
}
.item-actions {
  display: flex;
  gap: 4px;
  align-items: center;
}

.loading-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.1);
  border-radius: inherit;
  z-index: 1;
}

.empty-card {
  text-align: center;
  color: var(--text-muted);
  padding: 32px 0;
  font-size: 13px;
}

.test-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
}

.model-select {
  flex: 1;
  padding: 8px 12px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 13px;
  cursor: pointer;
  outline: none;
}
.model-select:focus {
  border-color: var(--border-secondary);
}
.model-select:disabled {
  opacity: 0.5;
}

.test-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 10px;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  transition: all 0.25s;
  box-shadow: 0 2px 10px rgba(99, 102, 241, 0.3);
}
.test-btn:hover:not(:disabled) {
  opacity: 0.9;
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
}
.test-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.runtime-panel {
  margin-bottom: 16px;
  padding: 12px 14px;
  border-radius: 10px;
  background: rgba(59, 130, 246, 0.08);
  border: 1px solid rgba(59, 130, 246, 0.18);
}
.runtime-panel.subtle {
  margin-bottom: 0;
  background: var(--bg-secondary);
  border-color: var(--border-primary);
}
.runtime-header {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}
.runtime-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}
.runtime-item {
  display: flex;
  align-items: center;
  gap: 8px;
  min-height: 36px;
  padding: 8px 10px;
  border-radius: 8px;
  background: var(--bg-card);
}
.runtime-label {
  font-size: 12px;
  color: var(--text-muted);
}
.runtime-value {
  margin-left: auto;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-primary);
}
.runtime-value.ok {
  color: #22c55e;
}
.runtime-value.warn {
  color: #f59e0b;
}
.runtime-value.muted {
  color: #6b7280;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 14px;
  background: rgba(239, 68, 68, 0.1);
  color: #ef4444;
  border-radius: 8px;
  font-size: 13px;
  margin-bottom: 16px;
}

.results {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.overall-status {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border-left: 3px solid;
}
.status-dot-lg {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}
.status-text {
  font-size: 14px;
  font-weight: 600;
}
.status-model {
  font-size: 13px;
  color: var(--text-primary);
  margin-left: 4px;
}
.status-time {
  font-size: 12px;
  color: var(--text-muted);
  margin-left: auto;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.feature-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 8px;
  background: var(--bg-secondary);
  border-radius: 10px;
  border: 1px solid var(--border-primary);
  transition:
    border-color 0.2s,
    transform 0.2s;
}
.feature-card.supported {
  border-color: rgba(34, 197, 94, 0.3);
}
.feature-card:hover {
  transform: translateY(-2px);
}
.feature-icon {
  width: 20px;
  height: 20px;
  color: var(--text-muted);
}
.feature-card.supported .feature-icon {
  color: #22c55e;
}
.feature-label {
  font-size: 12px;
  color: var(--text-muted);
  font-weight: 500;
}

.sub-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 10px;
}

.perf-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.perf-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
}
.perf-icon {
  width: 16px;
  height: 16px;
  color: var(--text-muted);
}
.perf-value {
  font-size: 16px;
  font-weight: 700;
  color: var(--text-primary);
}
.perf-label {
  font-size: 11px;
  color: var(--text-muted);
}

.res-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
}

.res-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
  font-size: 12px;
  color: var(--text-muted);
}
.res-val {
  margin-left: auto;
  font-weight: 600;
  color: var(--text-primary);
  font-size: 13px;
}

.detail-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.detail-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 10px;
  background: var(--bg-secondary);
  border-radius: 6px;
  font-size: 12px;
}
.detail-name {
  font-weight: 500;
  color: var(--text-primary);
}
.detail-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-weight: 500;
}
.detail-status.passed {
  color: #22c55e;
}
.detail-status.failed {
  color: #ef4444;
}
.detail-status.skipped {
  color: #6b7280;
}
.detail-duration {
  color: var(--text-muted);
  margin-left: auto;
}

.metrics-section {
  margin-top: 4px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.history-item {
  background: var(--bg-secondary);
  border-radius: 6px;
  overflow: hidden;
}

.history-header {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 10px 12px;
  cursor: pointer;
  font-size: 13px;
}
.history-header:hover {
  background: var(--bg-tertiary);
}
.history-name {
  font-weight: 500;
  color: var(--text-primary);
}
.history-status {
  font-size: 12px;
  font-weight: 500;
  margin-left: 4px;
}
.history-time {
  font-size: 11px;
  color: var(--text-muted);
  margin-left: auto;
}

.history-detail {
  padding: 10px 12px 10px 28px;
  border-top: 1px solid var(--bg-tertiary);
}

.feature-mini {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-muted);
}
.feature-mini span {
  display: flex;
  align-items: center;
  gap: 4px;
}
.feature-mini span.supported {
  color: #22c55e;
}

.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 24px 0;
  font-size: 13px;
}

.left-col::-webkit-scrollbar,
.right-col::-webkit-scrollbar {
  width: 4px;
}
.left-col::-webkit-scrollbar-track,
.right-col::-webkit-scrollbar-track {
  background: transparent;
}
.left-col::-webkit-scrollbar-thumb,
.right-col::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 2px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.view-toggle {
  display: flex;
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 2px;
  border: 1px solid var(--border-primary);
}

.toggle-btn {
  padding: 4px 12px;
  border-radius: 6px;
  font-size: 12px;
  font-weight: 500;
  color: var(--text-muted);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn:hover {
  color: var(--text-primary);
}

.toggle-btn.active {
  background: var(--color-primary);
  color: white;
}

.loading-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 32px;
  color: var(--text-muted);
  font-size: 13px;
}

.model-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-group {
  background: var(--bg-secondary);
  border-radius: 10px;
  overflow: hidden;
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  cursor: pointer;
  transition: background 0.2s;
}

.group-header:hover {
  background: var(--bg-tertiary);
}

.group-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.group-count {
  font-size: 11px;
  color: var(--text-muted);
  background: var(--bg-tertiary);
  padding: 1px 6px;
  border-radius: 8px;
}

.group-size {
  margin-left: auto;
  font-size: 12px;
  color: var(--text-muted);
}

.group-variants {
  border-top: 1px solid var(--border-primary);
}

.variant-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 12px 14px;
  border-bottom: 1px solid var(--border-primary);
  transition: background 0.2s;
}

.variant-item:last-child {
  border-bottom: none;
}

.variant-item:hover {
  background: var(--bg-tertiary);
}

.variant-item.running {
  border-left: 3px solid #22c55e;
}

.variant-item.current {
  background: rgba(99, 102, 241, 0.05);
}

.variant-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.variant-header {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.variant-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.variant-badges {
  display: flex;
  gap: 4px;
}

.status-badge {
  font-size: 10px;
  padding: 1px 5px;
  border-radius: 4px;
  font-weight: 500;
}

.status-badge.running {
  color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
}

.status-badge.current {
  color: var(--color-primary);
  background: rgba(99, 102, 241, 0.1);
}

.backend-badge {
  font-size: 10px;
  text-transform: uppercase;
  background: var(--bg-tertiary);
  padding: 1px 4px;
  border-radius: 4px;
  color: var(--text-secondary);
}

.variant-meta {
  display: flex;
  align-items: center;
  gap: 12px;
  font-size: 11px;
  color: var(--text-muted);
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
}

.meta-item.config {
  color: var(--color-primary);
}

.variant-desc {
  font-size: 11px;
  color: var(--text-muted);
  margin: 2px 0 0;
  line-height: 1.4;
}

.variant-actions {
  display: flex;
  gap: 4px;
  margin-left: 12px;
}

.action-btn.small {
  padding: 5px 8px;
  font-size: 11px;
}

.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  backdrop-filter: blur(4px);
}

.modal-content {
  background: var(--bg-card);
  border-radius: 16px;
  border: 1px solid var(--border-card);
  box-shadow: var(--shadow-lg);
  max-width: 520px;
  width: 90%;
  max-height: 90vh;
  overflow-y: auto;
}

.modal-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-primary);
}

.modal-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.modal-title .w-5 {
  width: 20px;
  height: 20px;
  color: var(--color-primary);
}

.modal-close {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: none;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.modal-close:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.modal-body {
  padding: 20px;
}

.config-model-info {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
}

.config-model-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.config-model-mem {
  font-size: 12px;
  color: var(--color-primary);
  background: rgba(99, 102, 241, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.gpu-recommend {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  padding: 12px;
  background: rgba(245, 158, 11, 0.1);
  border: 1px solid rgba(245, 158, 11, 0.3);
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 12px;
  color: #f59e0b;
}

.gpu-recommend .w-4 {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
  margin-top: 1px;
}

.recommend-text {
  color: var(--text-muted);
  margin-top: 4px;
}

.config-form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.config-row {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.config-label {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.label-text {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.label-desc {
  font-size: 11px;
  color: var(--text-muted);
}

.config-input-wrap {
  display: flex;
  align-items: center;
  gap: 8px;
}

.config-input {
  flex: 1;
  padding: 8px 12px;
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-primary);
  font-size: 13px;
  transition: all 0.2s;
}

.config-input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.1);
}

.input-suffix {
  font-size: 11px;
  color: var(--text-muted);
  white-space: nowrap;
}

.modal-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  padding: 16px 20px;
  border-top: 1px solid var(--border-primary);
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  border: none;
}

.btn.primary {
  background: var(--color-primary);
  color: white;
}

.btn.primary:hover:not(:disabled) {
  background: var(--color-primary-dark);
}

.btn.primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn.secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border-primary);
}

.btn.secondary:hover {
  background: var(--bg-tertiary);
}

.config-recommend-hint {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: rgba(99, 102, 241, 0.08);
  border: 1px solid rgba(99, 102, 241, 0.2);
  border-radius: 8px;
  margin-top: 8px;
}

.hint-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--color-primary);
}

.hint-text {
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
