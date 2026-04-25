<script setup lang="ts">
import { computed } from 'vue'
import type { ModelInfo } from '@/types'
import { useAppStore } from '@/stores/app'
import { Layers, Square, Play, ArrowRightLeft, Star, Box } from 'lucide-vue-next'

const store = useAppStore()

const props = defineProps<{
  modelList: ModelInfo[]
  defaultModel: string | null
  actionLoading: string | null
  switchingModel: string | null
  handleStartModel: (name: string) => Promise<void>
  handleStopModel: (name: string) => Promise<void>
  handleSwitchAndSetDefault: (name: string) => Promise<void>
}>()

const runningModels = computed(() => props.modelList.filter((m) => m.running))

const switchingProgress = computed(() => {
  if (!props.switchingModel) return null
  const model = props.modelList.find((m) => m.name === props.switchingModel)
  if (model?.running) return null
  return { model: props.switchingModel, phase: model ? '加载中' : '卸载旧模型' }
})

const handleStartWithToast = async (name: string) => {
  try {
    await props.handleStartModel(name)
    store.success(`模型 ${name} 已开始启动`)
  } catch {
    store.error(`模型 ${name} 启动失败`)
  }
}

const handleStopWithToast = async (name: string) => {
  try {
    await props.handleStopModel(name)
    store.success(`模型 ${name} 已停止`)
  } catch {
    store.error(`模型 ${name} 停止失败`)
  }
}

const handleSwitchWithToast = async (name: string) => {
  try {
    await props.handleSwitchAndSetDefault(name)
    store.success(`正在切换到模型 ${name}，请等待加载完成`)
  } catch {
    store.error(`切换模型 ${name} 失败`)
  }
}
</script>

<template>
  <div class="card-header">
    <div class="icon-wrap green"><Layers class="card-icon-inner" /></div>
    <span class="card-title">运行模型</span>
    <span class="count-badge">{{ runningModels.length }} / {{ modelList.length }}</span>
  </div>
  <div v-if="runningModels.length" class="running-list">
    <div v-for="model in runningModels" :key="model.name" class="model-row">
      <div class="model-info">
        <span class="model-name">{{ model.name }}</span>
        <span class="model-meta">端口 {{ model.port }} · {{ model.active_requests }} 请求</span>
      </div>
      <div class="model-actions">
        <span v-if="defaultModel === model.name" class="default-tag">
          <Star class="default-icon" /> 默认
        </span>
        <button
          class="action-btn stop"
          :disabled="!!actionLoading"
          @click="handleStopWithToast(model.name)"
        >
          <Square class="btn-icon" /> 停止
        </button>
      </div>
    </div>
  </div>
  <div v-else class="empty-state">暂无运行模型</div>
  <div class="stopped-section">
    <div class="sub-header">可启动模型</div>
    <div class="stopped-list">
      <div
        v-for="model in modelList.filter((m) => !m.running)"
        :key="model.name"
        class="model-row stopped"
      >
        <div class="model-info">
          <span class="model-name">{{ model.name }}</span>
          <span class="model-meta">
            <Box class="inline-icon" />
            {{ model.supports_images ? '支持图片' : '纯文本' }}
          </span>
        </div>
        <div class="model-actions">
          <button
            class="action-btn start"
            :disabled="!!actionLoading"
            @click="handleStartWithToast(model.name)"
          >
            <Play class="btn-icon" /> 启动
          </button>
          <button
            class="action-btn switch"
            :disabled="!!actionLoading"
            @click="handleSwitchWithToast(model.name)"
          >
            <ArrowRightLeft class="btn-icon" /> 切换
          </button>
        </div>
      </div>
    </div>
  </div>
  <div v-if="switchingProgress" class="switch-progress">
    <span class="switch-spinner">⟳</span>
    <span>正在切换 {{ switchingProgress.model }} · {{ switchingProgress.phase }}</span>
  </div>
</template>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 16px;
}

.icon-wrap {
  width: 32px;
  height: 32px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.icon-wrap.green {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.card-icon-inner {
  width: 16px;
  height: 16px;
}

.card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.count-badge {
  font-size: 12px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  padding: 2px 8px;
  border-radius: 10px;
  margin-left: auto;
}

.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 24px 0;
  font-size: 13px;
}

.running-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.model-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border-left: 3px solid #22c55e;
  transition: all 0.2s;
}

.model-row:hover {
  transform: translateX(4px);
}

.model-row.stopped {
  border-left-color: var(--border-primary);
}

.model-info {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.model-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.model-meta {
  font-size: 11px;
  color: var(--text-muted);
  display: flex;
  align-items: center;
  gap: 4px;
}

.inline-icon {
  width: 12px;
  height: 12px;
  display: inline-block;
}

.model-actions {
  display: flex;
  gap: 4px;
}

.default-tag {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  color: #f59e0b;
  background: rgba(245, 158, 11, 0.1);
  padding: 2px 8px;
  border-radius: 4px;
}

.default-icon {
  width: 12px;
  height: 12px;
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
}

.btn-icon {
  width: 12px;
  height: 12px;
}

.action-btn.start {
  color: #22c55e;
  border-color: rgba(34, 197, 94, 0.3);
}

.action-btn.stop {
  color: #ef4444;
  border-color: rgba(239, 68, 68, 0.3);
}

.action-btn.switch {
  color: var(--color-primary-light);
  border-color: rgba(99, 102, 241, 0.3);
}

.sub-header {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  padding: 12px 0 8px;
  border-top: 1px solid var(--border-primary);
  margin-top: 12px;
}

.stopped-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.switch-progress {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  margin-top: 12px;
  background: rgba(99, 102, 241, 0.08);
  border-radius: 8px;
  font-size: 13px;
  color: var(--color-primary-light);
}

.switch-spinner {
  animation: spin 1s linear infinite;
  font-size: 16px;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
