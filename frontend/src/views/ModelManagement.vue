<script setup lang="ts">
import { ref, computed, onMounted, type Component } from 'vue'
import { useModels } from '@/composables/useModels'
import { runModelTest, getTestResults, getTestHistory } from '@/api/client'
import type { TestResponse, TestHistoryEntry, TestReport } from '@/types'
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
} from 'lucide-vue-next'

const {
  modelList,
  defaultModel,
  actionLoading,
  switchingModel,
  isRefreshing,
  refresh,
  handleStartModel,
  handleStopModel,
  handleSwitchAndSetDefault,
  handleSetDefaultModel,
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

onMounted(() => {
  fetchHistory()
  fetchCapabilities()
})

async function fetchCapabilities() {
  for (const m of runningModels.value) {
    try {
      const result = await getTestResults(m.name)
      if (result.report?.feature_support) {
        modelCapabilities.value[m.name] = result.report.feature_support
        cachedResults.value[m.name] = result
      }
    } catch {}
  }
}

const getCapabilityBadges = (
  modelName: string
): Array<{ label: string; icon: Component; color: string }> => {
  const caps = modelCapabilities.value[modelName]
  const badges: Array<{ label: string; icon: Component; color: string }> = []
  badges.push({ label: '对话', icon: MessageSquare, color: '#6366f1' })
  if (caps?.tool_calling) badges.push({ label: '工具调用', icon: Wrench, color: '#3b82f6' })
  if (caps?.image_generation) badges.push({ label: '图片生成', icon: Image, color: '#8b5cf6' })
  const model = modelList.value.find((m) => m.name === modelName)
  if (model?.supports_images) badges.push({ label: '多模态', icon: Eye, color: '#f59e0b' })
  return badges
}

async function fetchHistory() {
  historyLoading.value = true
  try {
    historyList.value = await getTestHistory()
  } catch {
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
  } catch {}
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
</script>

<template>
  <div class="model-mgmt">
    <header class="page-header">
      <div class="header-left">
        <Server class="header-icon" />
        <h1 class="header-title">模型管理</h1>
        <span class="count-badge">{{ runningModels.length }} / {{ modelList.length }} 运行中</span>
      </div>
      <button class="icon-btn" :disabled="isRefreshing" @click="refresh">
        <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
      </button>
    </header>

    <div v-if="switchingModel" class="switch-banner">
      <Loader2 class="w-5 h-5 animate-spin" />
      <span class="switch-text">正在切换到 {{ switchingModel }}，请耐心等待...</span>
      <span class="switch-hint">vLLM 加载模型通常需要 30-120 秒</span>
    </div>

    <div class="content">
      <div class="left-col">
        <section v-if="runningModels.length" class="card">
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
                    <span v-if="model.required_memory" class="mem-req">显存 {{ model.required_memory }}</span>
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

        <section v-if="stoppedModels.length" class="card">
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
                  <span v-if="model.required_memory" class="mem-req">显存 {{ model.required_memory }}</span>
                </span>
              </div>
              <div class="item-actions">
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

        <div v-if="!modelList.length" class="card empty-card">暂无可用模型</div>
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
                  <span class="res-val">{{ resUtil.test_duration_seconds.toFixed(1) }}s</span>
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
  border-radius: 14px;
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
.item-actions {
  display: flex;
  gap: 4px;
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
</style>
