<script setup lang="ts">
import { computed } from 'vue'
import { useModels } from '@/composables/useModels'
import { Server, RefreshCw, Pause, Play as PlayIcon, Star, StarOff, Loader2, Play, Square, Zap, CheckCircle, ChevronDown, Plus, Layers } from 'lucide-vue-next'

const { modelStatus, defaultModel, loading, error, actionLoading, isRefreshing, isAutoRefreshEnabled, refresh, toggleAutoRefresh, handleStartModel, handleStopModel, handleSwitchAndSetDefault, handleSetDefaultModel, handleClearDefaultModel } = useModels()

const modelList = computed(() => [
  { name: 'Stable Diffusion XL', file: 'sd_xl_base_1.0.safetensors', type: '文生图', size: '6.46 GB', updated: '2024-05-20 14:30', status: '运行中' },
  { name: 'Real-ESRGAN', file: 'realesrgan-x4plus.pth', type: '超分辨率', size: '67.8 MB', updated: '2024-05-18 10:21', status: '运行' },
  { name: 'ControlNet v1.1', file: 'control_v11p_sd15.safetensors', type: '控制模型', size: '1.42 GB', updated: '2024-05-15 09:12', status: '运行' },
  { name: 'Llama 3 8B Instruct', file: 'llama3-8b-instruct.Q4_K_M.gguf', type: '大语言模型', size: '4.92 GB', updated: '2024-05-10 16:45', status: '运行' },
  { name: 'Anything V5', file: 'anything-v5-PrtRE.safetensors', type: '文生图', size: '4.07 GB', updated: '2024-05-08 11:33', status: '运行' },
])
</script>

<template>
  <div class="model-manager">
    <div class="manager-header">
      <div class="header-left">
        <Layers class="header-icon" />
        <span class="header-title">模型管理</span>
      </div>
      <div class="header-actions">
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

    <div class="table-container">
      <div class="table-header">
        <span class="col-name">模型名称</span>
        <span class="col-type">类型</span>
        <span class="col-size">大小</span>
        <span class="col-updated">更新时间</span>
        <span class="col-action">操作</span>
      </div>
      <div class="table-body">
        <div v-for="(model, index) in modelList" :key="model.name" class="table-row" :class="{ active: index === 0 }">
          <div class="col-name">
            <div class="model-info">
              <span class="model-title">{{ model.name }}</span>
              <span class="model-file">{{ model.file }}</span>
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
    </div>

    <div class="table-footer">
      <span class="total">共 {{ modelList.length }} 个模型</span>
      <div class="pagination">
        <button class="page-btn disabled">&lt;</button>
        <button class="page-btn active">1</button>
        <button class="page-btn">2</button>
        <button class="page-btn">3</button>
        <button class="page-btn">&gt;</button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.model-manager {
  background: var(--bg-card);
  border-radius: 14px;
  border: 1px solid var(--border-card);
  padding: 20px;
  box-shadow: var(--shadow);
}

.manager-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
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
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.header-actions {
  display: flex;
  gap: 8px;
}

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
  transition: all 0.2s;
}

.filter-btn:hover {
  border-color: var(--border-secondary);
}

.import-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 14px;
  border-radius: 8px;
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #ffffff;
  font-size: 13px;
  font-weight: 500;
  border: none;
  cursor: pointer;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.3);
  transition: all 0.2s;
}

.import-btn:hover {
  opacity: 0.9;
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
}

/* Table */
.table-container {
  margin-top: 12px;
}

.table-header {
  display: grid;
  grid-template-columns: 2fr 80px 70px 120px 60px;
  gap: 12px;
  padding: 10px 0;
  font-size: 12px;
  color: var(--text-muted);
  border-bottom: 1px solid var(--bg-secondary);
}

.table-body {
  max-height: 240px;
  overflow-y: auto;
}

.table-row {
  display: grid;
  grid-template-columns: 2fr 80px 70px 120px 60px;
  gap: 12px;
  padding: 14px 0;
  border-bottom: 1px solid var(--bg-secondary);
  font-size: 13px;
  align-items: center;
  transition: background 0.2s;
}

.table-row:hover {
  background: var(--bg-secondary);
}

.table-row.active {
  background: rgba(99, 102, 241, 0.06);
}

[data-theme='light'] .table-row.active {
  background: rgba(34, 197, 94, 0.05);
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-title {
  font-weight: 500;
  color: var(--text-primary);
}

.model-file {
  font-size: 11px;
  color: var(--text-muted);
}

.tag {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.tag-green {
  background: rgba(34, 197, 94, 0.12);
  color: #4ade80;
}

[data-theme='light'] .tag-green {
  background: #ecfdf5;
  color: #047857;
}

.tag-purple {
  background: rgba(139, 92, 246, 0.12);
  color: #a78bfa;
}

[data-theme='light'] .tag-purple {
  background: #faf5ff;
  color: #7c3aed;
}

.tag-blue {
  background: rgba(59, 130, 246, 0.12);
  color: #60a5fa;
}

[data-theme='light'] .tag-blue {
  background: #eff6ff;
  color: #2563eb;
}

.status-text {
  font-size: 12px;
  color: var(--text-muted);
}

.status-text.running {
  color: #4ade80;
  font-weight: 500;
}

.text-muted {
  color: var(--text-muted);
}

/* Footer */
.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid var(--bg-secondary);
}

.total {
  font-size: 12px;
  color: var(--text-muted);
}

.pagination {
  display: flex;
  gap: 4px;
}

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
  background: linear-gradient(135deg, #6366f1 0%, #4f46e5 100%);
  color: #ffffff;
  border-color: transparent;
}

.page-btn.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Scrollbar */
.table-body::-webkit-scrollbar {
  width: 4px;
}

.table-body::-webkit-scrollbar-track {
  background: transparent;
}

.table-body::-webkit-scrollbar-thumb {
  background: var(--scrollbar-thumb);
  border-radius: 2px;
}
</style>
