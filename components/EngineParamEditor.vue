<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { getEngineParamSchema, getModelEngineParams, updateModelEngineParams } from '@/api/client'
import { Settings, Save, RotateCcw, Loader2, AlertTriangle, ChevronDown, ChevronRight, Info } from 'lucide-vue-next'
import type { EngineType, EngineParamSchema, EngineParamDef, EngineParamGroup } from '@/types'

const props = defineProps<{
  modelName: string
  engineType: EngineType
}>()

const emit = defineEmits<{
  saved: [params: Record<string, unknown>]
  error: [msg: string]
}>()

const schema = ref<EngineParamSchema | null>(null)
const currentParams = ref<Record<string, unknown>>({})
const editedParams = ref<Record<string, unknown>>({})
const loading = ref(false)
const saving = ref(false)
const error = ref<string | null>(null)
const expandedGroups = ref<Record<string, boolean>>({})
const dirty = computed(() => {
  return JSON.stringify(editedParams.value) !== JSON.stringify(currentParams.value)
})

const engineGroups = computed<EngineParamGroup[]>(() => {
  if (!schema.value) return []
  const keys = props.engineType === 'llama_cpp'
    ? ['llama_cpp', 'llamacpp']
    : [props.engineType]
  for (const key of keys) {
    const groups = schema.value[key]?.groups
    if (groups?.length) return groups
  }
  return []
})

const engineLabel = computed(() => {
  const labels: Record<EngineType, string> = { vllm: 'vLLM', sglang: 'SGLang', llama_cpp: 'llama.cpp' }
  return labels[props.engineType] || props.engineType
})

onMounted(async () => {
  loading.value = true
  try {
    schema.value = await getEngineParamSchema()
    const result = await getModelEngineParams(props.modelName)
    currentParams.value = result.params || {}
    editedParams.value = { ...currentParams.value }
    engineGroups.value.forEach(g => { expandedGroups.value[g.name] = g.name === '核心参数' })
  } catch (e: unknown) {
    error.value = (e as Error).message || '加载参数失败'
    emit('error', error.value)
  } finally {
    loading.value = false
  }
})

watch(() => props.engineType, () => {
  editedParams.value = { ...currentParams.value }
  engineGroups.value.forEach(g => { expandedGroups.value[g.name] = g.name === '核心参数' })
})

const getParamValue = (param: EngineParamDef): unknown => {
  if (editedParams.value[param.key] !== undefined) return editedParams.value[param.key]
  return param.default
}

const setParamValue = (param: EngineParamDef, value: unknown) => {
  if (value === param.default || (param.default === null && (value === '' || value === null))) {
    delete editedParams.value[param.key]
  } else {
    editedParams.value[param.key] = value
  }
}

const resetParams = () => {
  editedParams.value = { ...currentParams.value }
}

const resetToDefaults = () => {
  editedParams.value = {}
}

const saveParams = async () => {
  saving.value = true
  error.value = null
  try {
    const result = await updateModelEngineParams(props.modelName, props.engineType, editedParams.value)
    currentParams.value = result.params || editedParams.value
    editedParams.value = { ...currentParams.value }
    emit('saved', currentParams.value)
  } catch (e: unknown) {
    error.value = (e as Error).message || '保存参数失败'
    emit('error', error.value)
  } finally {
    saving.value = false
  }
}

const toggleGroup = (name: string) => {
  expandedGroups.value[name] = !expandedGroups.value[name]
}

const formatDefault = (param: EngineParamDef): string => {
  if (param.default === null) return '(None/自动)'
  if (param.type === 'bool') return param.default ? 'true' : 'false'
  return String(param.default)
}
</script>

<template>
  <div class="param-editor card-base tech-border fade-in">
    <div class="editor-header">
      <div class="header-left">
        <div class="icon-box gradient-primary">
          <Settings class="w-4 h-4" />
        </div>
        <h3>{{ engineLabel }} 参数配置</h3>
        <span class="model-label tag tag-blue">{{ modelName }}</span>
      </div>
      <div class="header-actions">
        <button class="btn btn-secondary btn-sm" title="重置为默认值" @click="resetToDefaults">
          <RotateCcw class="w-3.5 h-3.5" /> 默认值
        </button>
        <button class="btn btn-secondary btn-sm" title="撤销修改" @click="resetParams">
          <RotateCcw class="w-3.5 h-3.5" /> 撤销
        </button>
        <button class="btn btn-primary btn-sm" :disabled="!dirty || saving" @click="saveParams">
          <Save v-if="!saving" class="w-3.5 h-3.5" />
          <Loader2 v-else class="w-3.5 h-3.5 animate-spin" />
          {{ saving ? '保存中...' : '保存' }}
        </button>
      </div>
    </div>

    <div v-if="error" class="error-banner toast-error">
      <AlertTriangle class="w-4 h-4" /> {{ error }}
    </div>

    <div v-if="loading" class="loading-state">
      <Loader2 class="w-6 h-6 animate-spin text-primary" />
      <span>加载参数定义...</span>
    </div>

    <div v-else-if="!schema" class="empty-state">
      <Settings class="w-8 h-8 text-muted" /> 无法获取参数定义
    </div>

    <div v-else class="param-groups">
      <div v-for="group in engineGroups" :key="group.name" class="param-group">
        <button class="group-header" @click="toggleGroup(group.name)">
          <ChevronDown v-if="expandedGroups[group.name]" class="w-4 h-4" />
          <ChevronRight v-else class="w-4 h-4" />
          <span class="group-name">{{ group.name }}</span>
          <span class="group-count tag tag-cyan">{{ group.params.length }}项</span>
        </button>

        <div v-if="expandedGroups[group.name]" class="group-body">
          <div v-for="param in group.params" :key="param.key" class="param-row">
            <div class="param-info">
              <label class="param-label" :title="param.description">
                {{ param.key }}
                <Info v-if="param.note" class="w-3 h-3 text-muted inline" :title="param.note" />
              </label>
              <span class="param-desc">{{ param.description }}</span>
              <span v-if="param.cli_arg" class="param-cli">CLI: {{ param.cli_arg }}</span>
            </div>

            <div class="param-input">
              <template v-if="param.type === 'bool'">
                <select :value="getParamValue(param)" class="param-select" @change="setParamValue(param, ($event.target as HTMLSelectElement).value === 'true')">
                  <option value="undefined">默认({{ formatDefault(param) }})</option>
                  <option value="true">true</option>
                  <option value="false">false</option>
                </select>
              </template>

              <template v-else-if="param.choices && param.choices.length > 0">
                <select :value="getParamValue(param) ?? ''" class="param-select" @change="setParamValue(param, ($event.target as HTMLSelectElement).value || null)">
                  <option value="">默认({{ formatDefault(param) }})</option>
                  <option v-for="choice in param.choices" :key="choice" :value="choice">{{ choice }}</option>
                </select>
              </template>

              <template v-else-if="param.type === 'int' || param.type === 'float'">
                <input
                  type="number"
                  :value="getParamValue(param) ?? ''"
                  :min="param.min"
                  :max="param.max"
                  :step="param.type === 'float' ? 0.01 : 1"
                  class="param-number"
                  placeholder="默认"
                  @input="setParamValue(param, ($event.target as HTMLInputElement).value === '' ? null : Number(($event.target as HTMLInputElement).value))"
                />
              </template>

              <template v-else>
                <input
                  type="text"
                  :value="getParamValue(param) ?? ''"
                  class="param-text"
                  placeholder="默认"
                  @input="setParamValue(param, ($event.target as HTMLInputElement).value === '' ? null : ($event.target as HTMLInputElement).value)"
                />
              </template>

              <span class="param-default">默认: {{ formatDefault(param) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.param-editor {
  padding: 24px;
  animation: fade-in 0.25s ease-out;
}

.editor-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 10px;
}

.icon-box {
  width: 30px;
  height: 30px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: 0 2px 8px rgba(var(--color-primary-rgb), 0.3);
}

.header-left h3 {
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 6px;
}

.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  margin-bottom: 12px;
}

.loading-state, .empty-state {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 40px;
  color: var(--text-muted);
}

.param-groups {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.param-group {
  border: 1px solid var(--border-secondary);
  border-radius: 12px;
  transition: border-color 0.2s;
}

.param-group:hover {
  border-color: var(--border-primary);
}

.group-header {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 14px;
  cursor: pointer;
  background: var(--bg-secondary);
  border-radius: 12px 12px 0 0;
  width: 100%;
  color: var(--text-primary);
  font-size: 14px;
  border: none;
  transition: background 0.2s;
}

.group-header:hover {
  background: var(--bg-tertiary);
}

.group-name {
  font-weight: 600;
}

.group-count {
  margin-left: auto;
}

.group-body {
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.param-row {
  display: flex;
  gap: 14px;
  align-items: start;
  padding: 8px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.03);
}

.param-row:last-child {
  border-bottom: none;
}

.param-info {
  min-width: 200px;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.param-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  display: flex;
  align-items: center;
  gap: 4px;
}

.param-desc {
  font-size: 12px;
  color: var(--text-muted);
}

.param-cli {
  font-size: 11px;
  color: rgba(99, 102, 241, 0.6);
  font-family: 'JetBrains Mono', 'Fira Code', monospace;
}

.param-input {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.param-select, .param-number, .param-text {
  background: var(--bg-input);
  border: 1px solid var(--border-primary);
  color: var(--text-primary);
  border-radius: 8px;
  padding: 7px 12px;
  font-size: 13px;
  min-width: 160px;
  transition: border-color 0.2s;
}

.param-select:focus, .param-number:focus, .param-text:focus {
  border-color: var(--color-primary);
  outline: none;
  box-shadow: 0 0 0 3px rgba(var(--color-primary-rgb), 0.1);
}

.param-default {
  font-size: 11px;
  color: var(--text-muted);
}

.btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 13px;
  border: 1px solid transparent;
  transition: all 0.2s ease;
}

.btn-sm {
  padding: 5px 10px;
  font-size: 12px;
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
</style>
