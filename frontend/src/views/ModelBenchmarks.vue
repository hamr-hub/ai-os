<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import {
  ShieldCheck,
  Play,
  History,
  BarChart3,
  CheckCircle2,
  XCircle,
  AlertCircle,
  Clock,
  Zap,
  RefreshCw,
  Search,
} from 'lucide-vue-next'
import { runModelTest, getTestHistory, getModels, getTestResults } from '@/api/client'
import type { TestHistoryEntry, TestReport, ModelInfo } from '@/types'
import { useAppStore } from '@/stores/app'

const appStore = useAppStore()

const loading = ref(false)
const testingModel = ref<string | null>(null)
const testHistory = ref<TestHistoryEntry[]>([])
const models = ref<ModelInfo[]>([])
const selectedModel = ref<string | null>(null)
const currentReport = ref<TestReport | null>(null)
const searchQuery = ref('')

const filteredModels = computed(() => {
  if (!searchQuery.value) return models.value
  return models.value.filter((m) => m.id.toLowerCase().includes(searchQuery.value.toLowerCase()))
})

const fetchInitialData = async () => {
  loading.value = true
  try {
    const [modelsData, historyData] = await Promise.all([getModels(), getTestHistory()])
    models.value = modelsData.data
    testHistory.value = historyData

    if (models.value.length > 0) {
      selectedModel.value = models.value[0].id
      await fetchReport(selectedModel.value)
    }
  } catch (err) {
    console.error('Failed to fetch benchmark data:', err)
  } finally {
    loading.value = false
  }
}

const fetchReport = async (modelName: string) => {
  try {
    const res = await getTestResults(modelName)
    if (res.status === 'found' && res.report) {
      currentReport.value = res.report
    } else {
      currentReport.value = null
    }
  } catch (err) {
    console.warn('[Benchmarks] Failed to fetch report:', err)
    currentReport.value = null
  }
}

const runTest = async (modelName: string) => {
  testingModel.value = modelName
  try {
    const res = await runModelTest(modelName)
    appStore.success(`模型 ${modelName} 评测完成`)
    if (res.report) {
      currentReport.value = res.report
    }
    // Refresh history
    testHistory.value = await getTestHistory()
  } catch (err) {
    console.error('[Benchmarks] Test failed:', err)
    appStore.error(`模型 ${modelName} 评测失败`)
  } finally {
    testingModel.value = null
  }
}

const selectModel = async (modelName: string) => {
  selectedModel.value = modelName
  await fetchReport(modelName)
}

onMounted(fetchInitialData)

const getStatusIcon = (status: string) => {
  switch (status?.toLowerCase()) {
    case 'success':
    case 'completed':
    case 'passed':
      return CheckCircle2
    case 'failed':
      return XCircle
    default:
      return AlertCircle
  }
}

const getStatusClass = (status: string) => {
  switch (status?.toLowerCase()) {
    case 'success':
    case 'completed':
    case 'passed':
      return 'text-green-400'
    case 'failed':
      return 'text-red-400'
    default:
      return 'text-yellow-400'
  }
}
</script>

<template>
  <div class="benchmarks-view">
    <header class="header">
      <div class="header-left">
        <ShieldCheck class="header-icon" />
        <h1 class="header-title">模型自动化评测</h1>
      </div>
      <div class="header-right">
        <button class="header-btn" :disabled="loading" @click="fetchInitialData">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': loading }" />
          <span>刷新数据</span>
        </button>
      </div>
    </header>

    <div class="content">
      <aside class="sidebar-panel">
        <div class="search-box">
          <Search class="search-icon" />
          <input v-model="searchQuery" type="text" placeholder="搜索模型..." />
        </div>

        <div class="model-list scrollbar-none">
          <div
            v-for="model in filteredModels"
            :key="model.id"
            class="model-item"
            :class="{ active: selectedModel === model.id }"
            @click="selectModel(model.id)"
          >
            <div class="model-info">
              <span class="model-name">{{ model.id }}</span>
              <span class="model-provider">{{ model.owned_by }}</span>
            </div>
            <button
              class="test-btn"
              :disabled="testingModel === model.id"
              @click.stop="runTest(model.id)"
            >
              <Play v-if="testingModel !== model.id" class="w-3.5 h-3.5" />
              <RefreshCw v-else class="w-3.5 h-3.5 animate-spin" />
            </button>
          </div>
        </div>
      </aside>

      <main class="main-panel scrollbar-none">
        <div v-if="selectedModel" class="report-container">
          <div class="report-header card">
            <div class="h-top">
              <div class="title-group">
                <h2 class="report-title">{{ selectedModel }}</h2>
                <div
                  v-if="currentReport"
                  class="status-badge"
                  :class="getStatusClass(currentReport.overall_status)"
                >
                  <component :is="getStatusIcon(currentReport.overall_status)" class="w-4 h-4" />
                  <span>{{ currentReport.overall_status }}</span>
                </div>
              </div>
              <div v-if="currentReport" class="report-meta">
                <div class="meta-item">
                  <Clock class="w-3.5 h-3.5" />
                  <span>{{ new Date(currentReport.test_timestamp).toLocaleString() }}</span>
                </div>
              </div>
            </div>

            <div v-if="currentReport" class="quick-stats">
              <div class="q-stat">
                <span class="q-label">Pass Rate</span>
                <span class="q-val text-green-400"
                  >{{ currentReport.performance_metrics?.overall?.pass_rate }}%</span
                >
              </div>
              <div class="q-stat">
                <span class="q-label">Avg TPS</span>
                <span class="q-val text-blue-400">{{
                  currentReport.performance_metrics?.overall?.avg_tps?.toFixed(2) ?? '--'
                }}</span>
              </div>
              <div class="q-stat">
                <span class="q-label">Latency</span>
                <span class="q-val text-yellow-400"
                  >{{
                    currentReport.performance_metrics?.overall?.avg_latency?.toFixed(2) ?? '--'
                  }}s</span
                >
              </div>
              <div class="q-stat">
                <span class="q-label">Tests</span>
                <span class="q-val"
                  >{{ currentReport.performance_metrics?.overall?.tests_passed }}/{{
                    currentReport.performance_metrics?.overall?.tests_total
                  }}</span
                >
              </div>
            </div>
          </div>

          <div v-if="currentReport" class="report-grid">
            <div class="card feature-card">
              <div class="card-header">
                <Zap class="card-icon text-yellow-400" />
                <span class="card-title">功能支持</span>
              </div>
              <div class="feature-list">
                <div
                  v-for="(supported, feature) in currentReport.feature_support"
                  :key="feature"
                  class="feature-item"
                >
                  <span class="f-name">{{ feature }}</span>
                  <CheckCircle2 v-if="supported" class="w-4 h-4 text-green-400" />
                  <XCircle v-else class="w-4 h-4 text-red-400 opacity-50" />
                </div>
              </div>
            </div>

            <div class="card history-card">
              <div class="card-header">
                <History class="card-icon text-blue-400" />
                <span class="card-title">评测历史</span>
              </div>
              <div class="history-list">
                <div
                  v-for="entry in testHistory.filter((h) => h.model_name === selectedModel)"
                  :key="entry.timestamp"
                  class="h-item"
                >
                  <span class="h-time">{{ new Date(entry.timestamp).toLocaleDateString() }}</span>
                  <span class="h-status" :class="getStatusClass(entry.status)">{{
                    entry.status
                  }}</span>
                  <span class="h-duration">{{ entry.duration?.toFixed(1) }}s</span>
                </div>
                <div
                  v-if="!testHistory.filter((h) => h.model_name === selectedModel).length"
                  class="empty-text"
                >
                  暂无历史记录
                </div>
              </div>
            </div>

            <div class="card results-card wide">
              <div class="card-header">
                <BarChart3 class="card-icon text-purple-400" />
                <span class="card-title">详细测试结果</span>
              </div>
              <div class="results-table">
                <div class="t-head">
                  <div class="t-cell">测试名称</div>
                  <div class="t-cell">类型</div>
                  <div class="t-cell">耗时</div>
                  <div class="t-cell">状态</div>
                </div>
                <div v-for="res in currentReport.test_results" :key="res.test_name" class="t-row">
                  <div class="t-cell">{{ res.test_name }}</div>
                  <div class="t-cell">
                    <span class="type-tag">{{ res.feature_type }}</span>
                  </div>
                  <div class="t-cell">{{ res.duration?.toFixed(2) }}s</div>
                  <div class="t-cell" :class="getStatusClass(res.status)">{{ res.status }}</div>
                </div>
              </div>
            </div>
          </div>

          <div v-else-if="!loading" class="no-report card">
            <AlertCircle class="w-12 h-12 text-muted mb-4" />
            <h3>暂无该模型的评测数据</h3>
            <p>点击右上角的播放按钮开始运行自动化评测</p>
            <button class="primary-btn mt-6" @click="selectedModel && runTest(selectedModel)">
              <Play class="w-4 h-4" />
              <span>立即开始评测</span>
            </button>
          </div>
        </div>
        <div v-else class="empty-state">
          <div class="empty-content">
            <ShieldCheck class="w-16 h-16 text-muted mb-6" />
            <h2>选择一个模型查看评测结果</h2>
            <p>我们提供全自动的功能性测试和性能基准测试</p>
          </div>
        </div>
      </main>
    </div>
  </div>
</template>

<style scoped>
.benchmarks-view {
  height: 100vh;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}

.header {
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
  gap: 10px;
}
.header-icon {
  width: 20px;
  height: 20px;
  color: var(--color-primary);
}
.header-title {
  font-size: 18px;
  font-weight: 600;
}

.header-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 13px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  color: var(--text-secondary);
  cursor: pointer;
  transition: all 0.2s;
}
.header-btn:hover:not(:disabled) {
  background: var(--color-primary);
  color: #fff;
}

.content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.sidebar-panel {
  width: 280px;
  border-right: 1px solid var(--border-primary);
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
}

.search-box {
  padding: 16px;
  position: relative;
}
.search-icon {
  position: absolute;
  left: 28px;
  top: 50%;
  transform: translateY(-50%);
  width: 14px;
  height: 14px;
  color: var(--text-muted);
}
.search-box input {
  width: 100%;
  padding: 8px 12px 8px 32px;
  background: var(--bg-primary);
  border: 1px solid var(--border-primary);
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-primary);
}

.model-list {
  flex: 1;
  overflow-y: auto;
  padding: 0 12px 12px;
}

.model-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px;
  border-radius: 10px;
  margin-bottom: 4px;
  cursor: pointer;
  transition: all 0.2s;
  border: 1px solid transparent;
}
.model-item:hover {
  background: var(--bg-secondary);
}
.model-item.active {
  background: rgba(99, 102, 241, 0.1);
  border-color: rgba(99, 102, 241, 0.2);
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow: hidden;
}
.model-name {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.model-provider {
  font-size: 11px;
  color: var(--text-muted);
}

.test-btn {
  width: 28px;
  height: 28px;
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border-primary);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}
.test-btn:hover:not(:disabled) {
  background: var(--color-primary);
  color: #fff;
  border-color: var(--color-primary);
}

.main-panel {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
}

.report-container {
  max-width: 1000px;
  margin: 0 auto;
}

.card {
  background: var(--bg-card);
  border: 1px solid var(--border-primary);
  border-radius: 16px;
  padding: 24px;
  margin-bottom: 20px;
}

.report-header .h-top {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 24px;
}
.title-group {
  display: flex;
  align-items: center;
  gap: 12px;
}
.report-title {
  font-size: 24px;
  font-weight: 700;
  margin: 0;
}
.status-badge {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  background: rgba(255, 255, 255, 0.05);
}

.report-meta {
  display: flex;
  gap: 16px;
}
.meta-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  color: var(--text-muted);
}

.quick-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}
.q-stat {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: 12px;
}
.q-label {
  font-size: 12px;
  color: var(--text-muted);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.q-val {
  font-size: 20px;
  font-weight: 700;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 20px;
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
}
.card-title {
  font-size: 15px;
  font-weight: 600;
}

.feature-list {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}
.feature-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 14px;
  background: var(--bg-secondary);
  border-radius: 10px;
}
.f-name {
  font-size: 13px;
  color: var(--text-secondary);
  text-transform: capitalize;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.h-item {
  display: flex;
  justify-content: space-between;
  padding: 10px 0;
  border-bottom: 1px solid var(--border-primary);
  font-size: 13px;
}
.h-item:last-child {
  border-bottom: none;
}
.h-time {
  color: var(--text-secondary);
}
.h-duration {
  color: var(--text-muted);
}

.results-card.wide {
  grid-column: span 2;
}

.results-table {
  display: flex;
  flex-direction: column;
}
.t-head {
  display: grid;
  grid-template-columns: 1fr 100px 100px 100px;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
}
.t-row {
  display: grid;
  grid-template-columns: 1fr 100px 100px 100px;
  padding: 14px 12px;
  border-bottom: 1px solid var(--border-primary);
  font-size: 13px;
}
.type-tag {
  padding: 2px 6px;
  background: rgba(99, 102, 241, 0.1);
  color: var(--color-primary-light);
  border-radius: 4px;
  font-size: 11px;
}

.no-report {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 60px;
  text-align: center;
}
.no-report h3 {
  font-size: 18px;
  margin-bottom: 8px;
}
.no-report p {
  color: var(--text-muted);
}

.primary-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 20px;
  background: var(--color-primary);
  color: #fff;
  border: none;
  border-radius: 10px;
  font-weight: 600;
  cursor: pointer;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
}
.empty-content {
  text-align: center;
  color: var(--text-muted);
}
.empty-content h2 {
  color: var(--text-secondary);
  margin-bottom: 8px;
}

@keyframes animate-spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
.animate-spin {
  animation: animate-spin 1s linear infinite;
}
</style>
