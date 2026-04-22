<script setup lang="ts">
import { computed, ref, onMounted, onUnmounted } from 'vue'
import { useModels } from '@/composables/useModels'
import { useGPU } from '@/composables/useGPU'
import {
  RefreshCw,
  Settings,
  Box,
  Cpu,
  Activity,
  Thermometer,
  Zap,
  MemoryStick,
  ChevronDown,
  Plus,
  Gauge,
  Wind,
  Battery,
  Layers,
  Image,
  Monitor,
} from 'lucide-vue-next'

const { modelStatus, runningModelsCount } = useModels()
const { gpuSummary, refresh, isRefreshing } = useGPU()

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

const currentModel = computed(() => ({
  name: 'Stable Diffusion XL',
  file: 'sd_xl_base_1.0.safetensors',
  type: '文生图',
  resolution: '1024 × 1024',
  precision: 'FP16',
  vram: '12.6 GB',
  status: '运行中'
}))

const models = computed(() => [
  { name: 'Stable Diffusion XL', file: 'sd_xl_base_1.0.safetensors', type: '文生图', size: '6.46 GB', updated: '2024-05-20 14:30', status: '运行中' },
  { name: 'Real-ESRGAN', file: 'realesrgan-x4plus.pth', type: '超分辨率', size: '67.8 MB', updated: '2024-05-18 10:21', status: '运行' },
  { name: 'ControlNet v1.1', file: 'control_v11p_sd15.safetensors', type: '控制模型', size: '1.42 GB', updated: '2024-05-15 09:12', status: '运行' },
  { name: 'Llama 3 8B Instruct', file: 'llama3-8b-instruct.Q4_K_M.gguf', type: '大语言模型', size: '4.92 GB', updated: '2024-05-10 16:45', status: '运行' },
  { name: 'Anything V5', file: 'anything-v5-PrtRE.safetensors', type: '文生图', size: '4.07 GB', updated: '2024-05-08 11:33', status: '运行' },
])

const performanceModes = [
  { name: '静音', icon: Wind, active: false },
  { name: '节能', icon: Battery, active: false },
  { name: '平衡', icon: Gauge, active: true },
  { name: '性能', icon: Zap, active: false },
  { name: '极致', icon: Cpu, active: false },
]

const gpuMetrics = computed(() => [
  { label: '核心温度', value: '62', unit: '°C', icon: Thermometer, color: 'success' as const },
  { label: '显存温度', value: '68', unit: '°C', icon: Thermometer, color: 'success' as const },
  { label: '核心频率', value: '2520', unit: 'MHz', icon: Zap, color: 'info' as const },
  { label: '显存频率', value: '10502', unit: 'MHz', icon: MemoryStick, color: 'info' as const },
  { label: '核心电压', value: '1.050', unit: 'v', icon: Zap, color: 'purple' as const },
  { label: '功耗', value: '320', unit: 'W', icon: Zap, color: 'warning' as const },
])

const performanceSliders = [
  { label: '核心频率 (MHz)', min: 210, max: 3000, value: 2520, current: 2520 },
  { label: '显存频率 (MHz)', min: 405, max: 12000, value: 10502, current: 10502 },
  { label: '功耗限制 (%)', min: 70, max: 120, value: 100, current: 100 },
  { label: '温度限制 (°C)', min: 65, max: 95, value: 83, current: 83 },
]
</script>

<template>
  <div class="dashboard">
    <!-- Header -->
    <header class="header">
      <div class="header-left">
        <h1 class="header-title">GPU Control</h1>
      </div>
      <div class="header-actions">
        <button class="header-btn" @click="refresh">
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
          <span>刷新</span>
        </button>
        <button class="header-btn">
          <Settings class="w-4 h-4" />
          <span>设置</span>
        </button>
      </div>
    </header>

    <!-- Main Content -->
    <div class="main-content">
      <!-- Left Column -->
      <div class="left-column">
        <!-- Current Running Model -->
        <div class="card">
          <div class="card-header">
            <Box class="card-icon" />
            <span class="card-title">当前运行模型</span>
          </div>
          <div class="model-info">
            <div class="model-details">
              <div class="model-header">
                <h2 class="model-name">{{ currentModel.name }}</h2>
                <span class="status-badge running">
                  <span class="status-dot online"></span>
                  {{ currentModel.status }}
                </span>
              </div>
              <p class="model-file">{{ currentModel.file }}</p>
              <div class="model-specs">
                <div class="spec-item">
                  <span class="spec-label">类型</span>
                  <span class="spec-value tag-green">{{ currentModel.type }}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">分辨率</span>
                  <span class="spec-value">{{ currentModel.resolution }}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">精度</span>
                  <span class="spec-value">{{ currentModel.precision }}</span>
                </div>
                <div class="spec-item">
                  <span class="spec-label">显存占用</span>
                  <span class="spec-value">{{ currentModel.vram }}</span>
                </div>
              </div>
            </div>
            <div class="model-preview">
              <div class="preview-placeholder">
                <Image class="w-12 h-12" />
              </div>
            </div>
          </div>
        </div>

        <!-- GPU Overview -->
        <div class="card">
          <div class="card-header">
            <Monitor class="card-icon" />
            <span class="card-title">GPU 概览</span>
          </div>
          <div class="gpu-overview">
            <div class="gpu-info">
              <div class="gpu-header">
                <span class="gpu-brand">NVIDIA GeForce</span>
                <h2 class="gpu-model">RTX 4090</h2>
                <span class="status-badge online">
                  <span class="status-dot online"></span>
                  运行正常
                </span>
              </div>
              <div class="gpu-image">
                <div class="gpu-illustration">
                  <Cpu class="w-16 h-16" />
                </div>
              </div>
            </div>
            <div class="gpu-metrics">
              <div v-for="metric in gpuMetrics" :key="metric.label" class="metric-item">
                <div class="metric-header">
                  <span class="metric-label">{{ metric.label }}</span>
                </div>
                <div class="metric-value-row">
                  <component :is="metric.icon" class="metric-icon" :class="metric.color" />
                  <span class="metric-value" :class="metric.color">{{ metric.value }}</span>
                  <span class="metric-unit">{{ metric.unit }}</span>
                </div>
                <div class="progress-bar">
                  <div class="progress-fill" :style="{ width: '45%' }"></div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Performance Monitor Chart -->
        <div class="card">
          <div class="card-header">
            <Activity class="card-icon" />
            <span class="card-title">性能监控</span>
            <div class="time-range">
              <span>时间范围:</span>
              <button class="range-btn">
                1小时
                <ChevronDown class="w-3 h-3" />
              </button>
            </div>
          </div>
          <div class="chart-container">
            <div class="chart-legend">
              <span class="legend-item"><span class="dot green"></span>GPU 温度 (°C)</span>
              <span class="legend-item"><span class="dot blue"></span>GPU 使用率 (%)</span>
              <span class="legend-item"><span class="dot purple"></span>显存使用率 (%)</span>
              <span class="legend-item"><span class="dot orange"></span>功耗 (W)</span>
            </div>
            <div class="chart-area">
              <svg viewBox="0 0 600 150" class="chart-svg">
                <defs>
                  <linearGradient id="greenGradient" x1="0%" y1="0%" x2="0%" y2="100%">
                    <stop offset="0%" stop-color="rgba(34, 197, 94, 0.3)" />
                    <stop offset="100%" stop-color="rgba(34, 197, 94, 0)" />
                  </linearGradient>
                </defs>
                <line x1="0" y1="30" x2="600" y2="30" stroke="currentColor" stroke-width="1" class="grid-line" />
                <line x1="0" y1="60" x2="600" y2="60" stroke="currentColor" stroke-width="1" class="grid-line" />
                <line x1="0" y1="90" x2="600" y2="90" stroke="currentColor" stroke-width="1" class="grid-line" />
                <line x1="0" y1="120" x2="600" y2="120" stroke="currentColor" stroke-width="1" class="grid-line" />
                <path d="M0,90 Q50,85 100,80 T200,70 T300,65 T400,60 T500,55 T600,50" fill="none" stroke="#22c55e" stroke-width="2" />
                <path d="M0,90 Q50,85 100,80 T200,70 T300,65 T400,60 T500,55 T600,50 L600,150 L0,150 Z" fill="url(#greenGradient)" />
                <path d="M0,100 Q50,95 100,90 T200,85 T300,75 T400,70 T500,65 T600,60" fill="none" stroke="#3b82f6" stroke-width="2" />
                <path d="M0,120 Q50,115 100,110 T200,105 T300,100 T400,95 T500,90 T600,85" fill="none" stroke="#8b5cf6" stroke-width="2" />
              </svg>
              <div class="chart-labels">
                <span>12:20</span><span>12:25</span><span>12:30</span><span>12:35</span><span>12:40</span>
                <span>12:45</span><span>12:50</span><span>12:55</span><span>13:00</span><span>13:05</span>
                <span>13:10</span><span>13:15</span><span>13:20</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Right Column -->
      <div class="right-column">
        <!-- Model Management -->
        <div class="card">
          <div class="card-header justify-between">
            <div class="flex items-center gap-2">
              <Layers class="card-icon" />
              <span class="card-title">模型管理</span>
            </div>
            <div class="header-actions-group">
              <button class="filter-btn">
                全部类型
                <ChevronDown class="w-3 h-3" />
              </button>
              <button class="import-btn">
                <Plus class="w-4 h-4" />
                导入模型
              </button>
            </div>
          </div>
          <div class="model-table">
            <div class="table-header">
              <span class="col-name">模型名称</span>
              <span class="col-type">类型</span>
              <span class="col-size">大小</span>
              <span class="col-updated">更新时间</span>
              <span class="col-action">操作</span>
            </div>
            <div class="table-body">
              <div v-for="(model, index) in models" :key="model.name" class="table-row" :class="{ active: index === 0 }">
                <div class="col-name">
                  <div class="model-name-col">
                    <span class="name">{{ model.name }}</span>
                    <span class="file">{{ model.file }}</span>
                  </div>
                </div>
                <span class="col-type">
                  <span class="tag" :class="{
                    'tag-green': model.type === '文生图',
                    'tag-purple': model.type === '超分辨率' || model.type === '大语言模型',
                    'tag-blue': model.type === '控制模型'
                  }">{{ model.type }}</span>
                </span>
                <span class="col-size">{{ model.size }}</span>
                <span class="col-updated text-muted">{{ model.updated }}</span>
                <span class="col-action">
                  <span class="status-text" :class="{ running: model.status === '运行中' }">{{ model.status }}</span>
                </span>
              </div>
            </div>
            <div class="table-footer">
              <span class="total">共 {{ models.length }} 个模型</span>
              <div class="pagination">
                <button class="page-btn disabled">&lt;</button>
                <button class="page-btn active">1</button>
                <button class="page-btn">2</button>
                <button class="page-btn">3</button>
                <button class="page-btn">&gt;</button>
              </div>
            </div>
          </div>
        </div>

        <!-- Performance Tuning -->
        <div class="card">
          <div class="card-header justify-between">
            <div class="flex items-center gap-2">
              <Gauge class="card-icon" />
              <span class="card-title">性能调节</span>
            </div>
            <button class="custom-btn">自定义</button>
          </div>
          <div class="performance-section">
            <div class="preset-modes">
              <span class="section-label">预设模式</span>
              <div class="mode-buttons">
                <button v-for="mode in performanceModes" :key="mode.name" class="mode-btn" :class="{ active: mode.active }">
                  <component :is="mode.icon" class="mode-icon" />
                  <span>{{ mode.name }}</span>
                </button>
              </div>
            </div>
            <div class="sliders-section">
              <div v-for="slider in performanceSliders" :key="slider.label" class="slider-item">
                <div class="slider-header">
                  <span class="slider-label">{{ slider.label }}</span>
                  <div class="slider-values">
                    <span class="current-value">{{ slider.current }}</span>
                    <span class="target-value">{{ slider.value }}</span>
                  </div>
                </div>
                <div class="slider-track">
                  <div class="slider-progress" :style="{ width: `${((slider.value - slider.min) / (slider.max - slider.min)) * 100}%` }"></div>
                  <div class="slider-thumb" :style="{ left: `${((slider.value - slider.min) / (slider.max - slider.min)) * 100}%` }"></div>
                </div>
                <div class="slider-range">
                  <span>{{ slider.min }}</span>
                  <span>{{ slider.max }}</span>
                </div>
              </div>
            </div>
            <div class="action-buttons">
              <button class="apply-btn">应用设置</button>
              <button class="reset-btn">重置</button>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.dashboard {
  height: 100vh;
  overflow: hidden;
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

.header-left { display: flex; align-items: center; gap: 12px; }

.header-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.header-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: var(--text-muted);
  background: transparent;
  border: 1px solid var(--border-primary);
  cursor: pointer;
  transition: all 0.2s;
}

.header-btn:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.main-content {
  flex: 1;
  overflow: hidden;
  display: grid;
  grid-template-columns: 1fr 480px;
  gap: 16px;
  padding: 16px 24px;
}

.left-column,
.right-column {
  display: flex;
  flex-direction: column;
  gap: 16px;
  overflow-y: auto;
}

.card {
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-card);
  padding: 20px;
  box-shadow: var(--shadow);
  transition: all 0.2s ease;
}

.card:hover { box-shadow: var(--shadow-md); }

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
}

.card-header.justify-between { justify-content: space-between; }

.card-icon { width: 18px; height: 18px; color: var(--text-muted); }

.card-title { font-size: 14px; font-weight: 600; color: var(--text-primary); }

.model-info {
  display: flex;
  gap: 20px;
}

.model-details { flex: 1; }

.model-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 4px;
}

.model-name { font-size: 20px; font-weight: 600; color: var(--text-primary); }

.model-file { font-size: 13px; color: var(--text-muted); margin-bottom: 16px; }

.model-specs {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
}

.spec-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.spec-label { font-size: 12px; color: var(--text-muted); }

.spec-value { font-size: 14px; font-weight: 500; color: var(--text-primary); }

.model-preview {
  width: 160px;
  height: 100px;
  border-radius: 8px;
  background: var(--bg-secondary);
  display: flex;
  align-items: center;
  justify-content: center;
  overflow: hidden;
}

.preview-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  color: var(--text-muted);
}

.status-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
}

.status-badge.running {
  background: rgba(34, 197, 94, 0.1);
  color: #059669;
}

[data-theme='dark'] .status-badge.running {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.status-badge.online {
  background: rgba(34, 197, 94, 0.1);
  color: #059669;
}

[data-theme='dark'] .status-badge.online {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.status-dot { width: 6px; height: 6px; border-radius: 50%; background: #22c55e; }

.status-dot.online { box-shadow: 0 0 6px rgba(34, 197, 94, 0.5); }

.gpu-overview {
  display: grid;
  grid-template-columns: 200px 1fr;
  gap: 24px;
}

.gpu-info {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.gpu-header { margin-bottom: 16px; }

.gpu-brand { font-size: 12px; color: var(--text-muted); display: block; margin-bottom: 4px; }

.gpu-model { font-size: 24px; font-weight: 700; color: var(--text-primary); margin-bottom: 8px; }

.gpu-image { display: flex; align-items: center; justify-content: center; }

.gpu-illustration {
  width: 120px;
  height: 80px;
  background: var(--bg-secondary);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
}

.gpu-metrics {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
}

.metric-item {
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.metric-header { margin-bottom: 8px; }

.metric-label { font-size: 12px; color: var(--text-muted); }

.metric-value-row {
  display: flex;
  align-items: center;
  gap: 6px;
  margin-bottom: 8px;
}

.metric-icon { width: 16px; height: 16px; }

.metric-icon.success { color: #22c55e; }
.metric-icon.info { color: #3b82f6; }
.metric-icon.warning { color: #f59e0b; }
.metric-icon.purple { color: #8b5cf6; }

.metric-value { font-size: 20px; font-weight: 700; }

.metric-value.success { color: #22c55e; }
.metric-value.info { color: #3b82f6; }
.metric-value.warning { color: #f59e0b; }
.metric-value.purple { color: #8b5cf6; }

.metric-unit { font-size: 12px; color: var(--text-muted); }

.progress-bar {
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
  border-radius: 2px;
}

.time-range {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: var(--text-muted);
}

.range-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  border: 1px solid var(--border-primary);
  border-radius: 6px;
  background: var(--bg-card);
  font-size: 12px;
  color: var(--text-primary);
  cursor: pointer;
}

.chart-container { margin-top: 12px; }

.chart-legend {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  flex-wrap: wrap;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: var(--text-muted);
}

.dot { width: 8px; height: 8px; border-radius: 50%; }

.dot.green { background: #22c55e; }
.dot.blue { background: #3b82f6; }
.dot.purple { background: #8b5cf6; }
.dot.orange { background: #f59e0b; }

.chart-area { position: relative; color: var(--border-primary); }

.chart-svg { width: 100%; height: 150px; }

.grid-line { opacity: 0.3; }

.chart-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
  font-size: 11px;
  color: var(--text-muted);
}

.header-actions-group { display: flex; gap: 8px; }

.filter-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border: 1px solid var(--border-primary);
  border-radius: 6px;
  background: var(--bg-card);
  font-size: 13px;
  color: var(--text-primary);
  cursor: pointer;
}

.import-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 6px;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: #ffffff;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
  transition: all 0.2s;
}

.import-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(34, 197, 94, 0.4);
}

.model-table { margin-top: 12px; }

.table-header {
  display: grid;
  grid-template-columns: 2fr 80px 70px 120px 60px;
  gap: 12px;
  padding: 10px 0;
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px solid var(--bg-secondary);
}

.table-body { max-height: 200px; overflow-y: auto; }

.table-row {
  display: grid;
  grid-template-columns: 2fr 80px 70px 120px 60px;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--bg-secondary);
  font-size: 13px;
  align-items: center;
  transition: background 0.2s;
}

.table-row:hover { background: var(--bg-secondary); }

.table-row.active { background: rgba(34, 197, 94, 0.05); }

[data-theme='dark'] .table-row.active { background: rgba(34, 197, 94, 0.1); }

.model-name-col {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-name-col .name { font-weight: 500; color: var(--text-primary); }

.model-name-col .file { font-size: 11px; color: var(--text-muted); }

.text-muted { color: var(--text-muted); }

.status-text { font-size: 12px; color: var(--text-muted); }

.status-text.running { color: #059669; font-weight: 500; }

[data-theme='dark'] .status-text.running { color: #4ade80; }

.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--bg-secondary);
}

.total { font-size: 12px; color: var(--text-muted); }

.pagination { display: flex; gap: 4px; }

.page-btn {
  width: 28px;
  height: 28px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid var(--border-primary);
  background: var(--bg-card);
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.page-btn:hover:not(.disabled):not(.active) {
  border-color: var(--border-secondary);
  color: var(--text-primary);
}

.page-btn.active {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: #ffffff;
  border-color: transparent;
}

.page-btn.disabled { opacity: 0.5; cursor: not-allowed; }

.custom-btn {
  font-size: 12px;
  color: #3b82f6;
  background: transparent;
  border: none;
  cursor: pointer;
}

.performance-section { margin-top: 12px; }

.preset-modes { margin-bottom: 20px; }

.section-label {
  display: block;
  font-size: 12px;
  color: var(--text-muted);
  margin-bottom: 10px;
}

.mode-buttons { display: flex; gap: 8px; }

.mode-btn {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 12px 8px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: var(--bg-card);
  font-size: 12px;
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
}

.mode-btn:hover { border-color: #22c55e; color: var(--text-primary); }

.mode-btn.active {
  border-color: #22c55e;
  background: rgba(34, 197, 94, 0.1);
  color: #059669;
}

[data-theme='dark'] .mode-btn.active {
  background: rgba(34, 197, 94, 0.2);
  color: #4ade80;
}

.mode-icon { width: 20px; height: 20px; }

.sliders-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.slider-item { padding: 12px; background: var(--bg-secondary); border-radius: 8px; }

.slider-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 10px;
}

.slider-label { font-size: 12px; color: var(--text-muted); }

.slider-values { display: flex; align-items: center; gap: 12px; }

.current-value { font-size: 11px; color: var(--text-muted); }

.target-value { font-size: 14px; font-weight: 600; color: var(--text-primary); min-width: 40px; text-align: right; }

.slider-track { position: relative; height: 6px; background: var(--bg-tertiary); border-radius: 3px; margin-bottom: 6px; }

.slider-progress {
  position: absolute;
  left: 0;
  top: 0;
  height: 100%;
  background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
  border-radius: 3px;
}

.slider-thumb {
  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  width: 16px;
  height: 16px;
  background: var(--bg-card);
  border: 2px solid #22c55e;
  border-radius: 50%;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
}

.slider-range {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-muted);
}

.action-buttons { display: flex; gap: 12px; }

.apply-btn {
  flex: 1;
  padding: 10px 16px;
  border-radius: 8px;
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
  color: #ffffff;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  box-shadow: 0 4px 12px rgba(34, 197, 94, 0.3);
  transition: all 0.2s;
}

.apply-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 6px 16px rgba(34, 197, 94, 0.4);
}

.reset-btn {
  padding: 10px 24px;
  border-radius: 8px;
  background: var(--bg-secondary);
  color: var(--text-muted);
  font-size: 13px;
  font-weight: 500;
  border: 1px solid var(--border-primary);
  cursor: pointer;
  transition: all 0.2s;
}

.reset-btn:hover { background: var(--bg-tertiary); color: var(--text-primary); }

.left-column::-webkit-scrollbar,
.right-column::-webkit-scrollbar { width: 4px; }

.left-column::-webkit-scrollbar-track,
.right-column::-webkit-scrollbar-track { background: transparent; }

.left-column::-webkit-scrollbar-thumb,
.right-column::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 2px;
}
</style>
