<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useConfigManagement } from '@/composables/useConfigManagement'
import {
  Settings,
  RefreshCw,
  Loader2,
  AlertTriangle,
  Save,
  Star,
  Trash2,
} from 'lucide-vue-next'
import type { SystemConfig } from '@/types'

const { vllmDefaultConfig, engineConfig, systemConfig, defaultModel, loading, error, fetchAll, updateSystemConf, setDefault, clearDefault } = useConfigManagement()

const activeTab = ref<'vllm' | 'engine' | 'system' | 'default'>('vllm')
const editingSystem = ref(false)
const editSystem = ref<Partial<SystemConfig>>({})
const setDefaultInput = ref('')

onMounted(() => {
  fetchAll()
})

const handleRefresh = () => fetchAll()

const startEditSystem = () => {
  if (systemConfig.value) editSystem.value = { ...systemConfig.value }
  editingSystem.value = true
}

const saveSystem = async () => {
  const success = await updateSystemConf(editSystem.value)
  if (success) editingSystem.value = false
}

const handleSetDefault = async () => {
  if (!setDefaultInput.value) return
  await setDefault(setDefaultInput.value)
  setDefaultInput.value = ''
}

const handleClearDefault = async () => {
  await clearDefault()
}
</script>

<template>
  <div class="config-page">
    <div class="page-header">
      <div class="header-title">
        <Settings class="w-6 h-6 text-primary" />
        <h1 class="digital-font">Config Center</h1>
      </div>
      <p class="header-subtitle">配置中心 · 全局参数 · 默认模型</p>
      <button class="btn btn-ghost" @click="handleRefresh">
        <RefreshCw v-if="loading" class="w-4 h-4 animate-spin" />
        <RefreshCw v-else class="w-4 h-4" /> 刷新
      </button>
    </div>

    <div v-if="error" class="error-banner">
      <AlertTriangle class="w-4 h-4" />
      {{ error }}
    </div>

    <div class="tab-controls">
      <button :class="['tab-btn', activeTab === 'vllm' ? 'active' : '']" @click="activeTab = 'vllm'">
        <Settings class="w-4 h-4" /> vLLM 默认配置
      </button>
      <button :class="['tab-btn', activeTab === 'engine' ? 'active' : '']" @click="activeTab = 'engine'">
        <Settings class="w-4 h-4" /> 引擎配置
      </button>
      <button :class="['tab-btn', activeTab === 'system' ? 'active' : '']" @click="activeTab = 'system'">
        <Settings class="w-4 h-4" /> 系统配置
      </button>
      <button :class="['tab-btn', activeTab === 'default' ? 'active' : '']" @click="activeTab = 'default'">
        <Star class="w-4 h-4" /> 默认模型
      </button>
    </div>

    <div v-if="loading && !vllmDefaultConfig" class="loading-state">
      <Loader2 class="w-8 h-8 animate-spin text-primary" />
      <p>加载中...</p>
    </div>

    <div v-if="activeTab === 'vllm' && vllmDefaultConfig" class="config-panel card-base">
      <h3 class="section-title"><Settings class="w-5 h-5" /> vLLM 默认配置</h3>
      <div class="config-row">
        <span class="config-label">GPU 显存利用率</span>
        <span class="config-value">{{ vllmDefaultConfig.gpu_memory_utilization }}</span>
      </div>
      <div class="config-row">
        <span class="config-label">最大模型长度</span>
        <span class="config-value">{{ vllmDefaultConfig.max_model_len }}</span>
      </div>
      <div class="config-row">
        <span class="config-label">最大并发序列</span>
        <span class="config-value">{{ vllmDefaultConfig.max_num_seqs }}</span>
      </div>
      <div class="config-row">
        <span class="config-label">最大批处理Token</span>
        <span class="config-value">{{ vllmDefaultConfig.max_num_batched_tokens }}</span>
      </div>
      <div class="config-row">
        <span class="config-label">Tensor并行数</span>
        <span class="config-value">{{ vllmDefaultConfig.tensor_parallel_size }}</span>
      </div>
    </div>

    <div v-if="activeTab === 'engine' && engineConfig" class="config-panel card-base">
      <h3 class="section-title"><Settings class="w-5 h-5" /> 引擎配置</h3>
      <div v-for="(conf, name) in engineConfig" :key="name" class="config-block">
        <h4 class="engine-name">{{ name }}</h4>
        <div class="config-row">
          <span class="config-label">command</span>
          <span class="config-value">{{ conf.command }}</span>
        </div>
        <pre class="config-pre">{{ JSON.stringify(conf.default_params, null, 2) }}</pre>
      </div>
    </div>

    <div v-if="activeTab === 'system'" class="config-panel card-base">
      <h3 class="section-title"><Settings class="w-5 h-5" /> 系统配置</h3>
      <div v-if="!systemConfig" class="empty-state">
        <Settings class="w-12 h-12 text-muted" />
        <p>无法获取系统配置</p>
      </div>
      <div v-else-if="!editingSystem" class="config-display">
        <div class="config-row">
          <span class="config-label">健康检查间隔</span>
          <span class="config-value">{{ systemConfig.health_check_interval_seconds }} 秒</span>
        </div>
        <div class="config-row">
          <span class="config-label">缓存 TTL</span>
          <span class="config-value">{{ systemConfig.cache_ttl_seconds }} 秒</span>
        </div>
        <div class="config-row">
          <span class="config-label">日志级别</span>
          <span class="config-value">{{ systemConfig.log_level }}</span>
        </div>
        <div class="config-row">
          <span class="config-label">GPU轮询间隔</span>
          <span class="config-value">{{ systemConfig.gpu_poll_interval_seconds }} 秒</span>
        </div>
        <div class="config-row">
          <span class="config-label">WS推送间隔</span>
          <span class="config-value">{{ systemConfig.ws_push_interval_seconds }} 秒</span>
        </div>
        <button class="btn btn-primary" @click="startEditSystem">
          <Save class="w-4 h-4" /> 编辑配置
        </button>
      </div>
      <div v-else class="config-editor">
        <div class="form-row">
          <label class="form-label">健康检查间隔(秒)</label>
          <input v-model.number="editSystem.health_check_interval_seconds" type="number" class="form-input" />
        </div>
        <div class="form-row">
          <label class="form-label">缓存 TTL(秒)</label>
          <input v-model.number="editSystem.cache_ttl_seconds" type="number" class="form-input" />
        </div>
        <div class="form-row">
          <label class="form-label">日志级别</label>
          <select v-model="editSystem.log_level" class="form-input">
            <option value="DEBUG">DEBUG</option>
            <option value="INFO">INFO</option>
            <option value="WARNING">WARNING</option>
            <option value="ERROR">ERROR</option>
          </select>
        </div>
        <div class="form-row">
          <label class="form-label">GPU轮询间隔(秒)</label>
          <input v-model.number="editSystem.gpu_poll_interval_seconds" type="number" class="form-input" />
        </div>
        <div class="form-row">
          <label class="form-label">WS推送间隔(秒)</label>
          <input v-model.number="editSystem.ws_push_interval_seconds" type="number" class="form-input" />
        </div>
        <div class="editor-actions">
          <button class="btn btn-primary" @click="saveSystem">保存</button>
          <button class="btn btn-ghost" @click="editingSystem = false">取消</button>
        </div>
      </div>
    </div>

    <div v-if="activeTab === 'default'" class="config-panel card-base">
      <h3 class="section-title"><Star class="w-5 h-5" /> 默认模型管理</h3>
      <div v-if="defaultModel" class="current-default">
        <span class="default-label">当前默认模型</span>
        <span class="default-name">{{ defaultModel }}</span>
        <button class="btn btn-sm btn-danger" @click="handleClearDefault">
          <Trash2 class="w-3.5 h-3.5" /> 清除
        </button>
      </div>
      <div v-else class="no-default">
        <span class="default-label">未设置默认模型</span>
      </div>
      <div class="set-default-form">
        <input v-model="setDefaultInput" class="form-input" placeholder="输入模型名称" />
        <button class="btn btn-primary" :disabled="!setDefaultInput" @click="handleSetDefault">
          <Star class="w-4 h-4" /> 设置默认
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.config-page {
  padding: 24px;
  max-width: 1200px;
}

.page-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 24px;
}

.header-title {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-title h1 {
  font-size: 24px;
  color: var(--text-primary);
}

.header-subtitle {
  color: var(--text-muted);
  font-size: 14px;
  margin-left: auto;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(239, 68, 68, 0.1);
  color: var(--color-danger);
  padding: 10px 16px;
  border-radius: 8px;
  margin-bottom: 16px;
  font-size: 14px;
}

.tab-controls {
  display: flex;
  gap: 8px;
  margin-bottom: 24px;
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  font-size: 14px;
  color: var(--text-muted);
  background: var(--bg-secondary);
  border: 1px solid rgba(255, 255, 255, 0.05);
  cursor: pointer;
  transition: all 0.2s;
}

.tab-btn.active {
  background: var(--color-primary);
  color: white;
  border-color: var(--color-primary);
}

.loading-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 60px 0;
  color: var(--text-muted);
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--text-primary);
  margin-bottom: 16px;
  font-size: 16px;
}

.card-base {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 20px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.config-row {
  display: flex;
  justify-content: space-between;
  padding: 8px 0;
  font-size: 14px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.config-label { color: var(--text-muted); }
.config-value { color: var(--text-primary); }

.config-block {
  margin-bottom: 24px;
}

.engine-name {
  color: var(--text-primary);
  margin-bottom: 8px;
  font-size: 15px;
  font-weight: 600;
}

.config-pre {
  font-size: 12px;
  background: var(--bg-secondary);
  padding: 8px;
  border-radius: 8px;
  color: var(--text-primary);
  overflow-x: auto;
}

.form-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.form-label {
  font-size: 14px;
  color: var(--text-muted);
  min-width: 120px;
}

.form-input {
  background: var(--bg-input);
  border: 1px solid rgba(255, 255, 255, 0.1);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 8px 12px;
  font-size: 14px;
  flex: 1;
}

.editor-actions {
  display: flex;
  gap: 8px;
  margin-top: 12px;
}

.current-default {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px;
  background: rgba(74, 222, 128, 0.1);
  border-radius: 8px;
  margin-bottom: 16px;
}

.default-label { color: var(--text-muted); font-size: 14px; }
.default-name { color: var(--text-primary); font-weight: 600; }

.no-default {
  display: flex;
  align-items: center;
  padding: 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  margin-bottom: 16px;
}

.set-default-form {
  display: flex;
  gap: 8px;
}

.btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.btn-sm {
  padding: 4px 10px;
  font-size: 12px;
}

.btn-primary {
  background: var(--color-primary);
  color: white;
}

.btn-primary:hover {
  background: var(--color-primary-dark);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-ghost {
  background: transparent;
  color: var(--text-muted);
  border-color: rgba(255, 255, 255, 0.1);
}

.btn-ghost:hover {
  background: rgba(255, 255, 255, 0.05);
  color: var(--text-primary);
}

.btn-danger {
  background: rgba(239, 68, 68, 0.1);
  color: #f87171;
  border-color: rgba(239, 68, 68, 0.2);
}
</style>
