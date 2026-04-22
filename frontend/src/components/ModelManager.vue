<script setup lang="ts">
import { useModels } from '@/composables/useModels'
import { Server, RefreshCw, Pause, Play as PlayIcon, Star, StarOff, Loader2, Play, Square, Zap, CheckCircle, ChevronDown, Plus, Layers } from 'lucide-vue-next'

const { modelStatus, defaultModel, loading, error, actionLoading, isRefreshing, isAutoRefreshEnabled, refresh, toggleAutoRefresh, handleStartModel, handleStopModel, handleSwitchAndSetDefault, handleSetDefaultModel, handleClearDefaultModel } = useModels()

const modelList = [
  { name: 'Stable Diffusion XL', file: 'sd_xl_base_1.0.safetensors', type: '文生图', size: '6.46 GB', updated: '2024-05-20 14:30', status: '运行中' },
  { name: 'Real-ESRGAN', file: 'realesrgan-x4plus.pth', type: '超分辨率', size: '67.8 MB', updated: '2024-05-18 10:21', status: '运行' },
  { name: 'ControlNet v1.1', file: 'control_v11p_sd15.safetensors', type: '控制模型', size: '1.42 GB', updated: '2024-05-15 09:12', status: '运行' },
  { name: 'Llama 3 8B Instruct', file: 'llama3-8b-instruct.Q4_K_M.gguf', type: '大语言模型', size: '4.92 GB', updated: '2024-05-10 16:45', status: '运行' },
  { name: 'Anything V5', file: 'anything-v5-PrtRE.safetensors', type: '文生图', size: '4.07 GB', updated: '2024-05-08 11:33', status: '运行' },
]
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
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
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
  color: #64748b;
}

.header-title {
  font-size: 14px;
  font-weight: 600;
  color: #0f172a;
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
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  background: #ffffff;
  font-size: 13px;
  color: #0f172a;
  cursor: pointer;
  transition: all 0.2s;
}

.filter-btn:hover {
  border-color: #cbd5e1;
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
  color: #94a3b8;
  border-bottom: 1px solid #f1f5f9;
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
  border-bottom: 1px solid #f8fafc;
  font-size: 13px;
  align-items: center;
  transition: all 0.2s;
}

.table-row:hover {
  background: #f8fafc;
}

.table-row.active {
  background: linear-gradient(90deg, #ecfdf5 0%, transparent 100%);
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-title {
  font-weight: 500;
  color: #0f172a;
}

.model-file {
  font-size: 11px;
  color: #94a3b8;
}

.tag {
  display: inline-flex;
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 500;
}

.tag-green {
  background: #ecfdf5;
  color: #059669;
}

.tag-purple {
  background: #faf5ff;
  color: #7c3aed;
}

.tag-blue {
  background: #eff6ff;
  color: #2563eb;
}

.status-text {
  font-size: 12px;
  color: #64748b;
}

.status-text.running {
  color: #059669;
  font-weight: 500;
}

.text-muted {
  color: #94a3b8;
}

/* Footer */
.table-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 16px;
  padding-top: 16px;
  border-top: 1px solid #f1f5f9;
}

.total {
  font-size: 12px;
  color: #94a3b8;
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
  border: 1px solid #e2e8f0;
  background: #ffffff;
  font-size: 12px;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.page-btn:hover:not(.disabled):not(.active) {
  border-color: #cbd5e1;
  color: #0f172a;
}

.page-btn.active {
  background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
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
  background: #cbd5e1;
  border-radius: 2px;
}
</style>
