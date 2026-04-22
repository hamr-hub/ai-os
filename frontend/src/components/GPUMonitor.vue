<script setup lang="ts">
import { useGPU } from '@/composables/useGPU'
import { Activity, Thermometer, Zap, Cpu, MemoryStick, Fan, RefreshCw, Pause, Play } from 'lucide-vue-next'

const { gpuSummary, loading, error, isRefreshing, isAutoRefreshEnabled, refresh, toggleAutoRefresh, formatMemory } = useGPU()

const getStatusColor = (value: number, warning = 70, danger = 90): string => {
  if (value >= danger) return 'text-red-500'
  if (value >= warning) return 'text-yellow-500'
  return 'text-green-500'
}

const getProgressColor = (value: number, warning = 70, danger = 90): string => {
  if (value >= danger) return 'bg-red-500'
  if (value >= warning) return 'bg-yellow-500'
  return 'bg-green-500'
}
</script>

<template>
  <div class="gpu-monitor">
    <div class="monitor-header">
      <div class="header-left">
        <div class="icon-wrapper">
          <Cpu class="w-5 h-5 text-white" />
        </div>
        <div>
          <h2 class="monitor-title">GPU 监控</h2>
          <p class="monitor-subtitle">实时监控 GPU 状态和性能指标</p>
        </div>
      </div>
      <div class="header-actions">
        <button
          @click="refresh"
          :disabled="isRefreshing"
          class="action-btn"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
          <span>刷新</span>
        </button>
        <button
          @click="toggleAutoRefresh"
          class="toggle-btn"
          :class="{ active: isAutoRefreshEnabled }"
        >
          <Pause v-if="isAutoRefreshEnabled" class="w-4 h-4" />
          <Play v-else class="w-4 h-4" />
        </button>
      </div>
    </div>

    <div v-if="loading" class="loading-state">
      <div class="loading-spinner"></div>
      <p>正在检测 GPU...</p>
    </div>

    <div v-else-if="error" class="error-state">
      <div class="error-icon">
        <Cpu class="w-8 h-8 text-red-500" />
      </div>
      <p>{{ error }}</p>
    </div>

    <div v-else-if="gpuSummary?.status === 'unavailable'" class="empty-state">
      <div class="empty-icon">
        <Cpu class="w-8 h-8 text-gray-400" />
      </div>
      <p>未检测到 GPU</p>
    </div>

    <div v-else class="monitor-content">
      <!-- Stats Grid -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-header">
            <MemoryStick class="w-5 h-5 text-blue-500" />
            <span class="stat-label">显存使用</span>
          </div>
          <p class="stat-value">
            {{ formatMemory(gpuSummary?.current?.used_memory || 0) }}
          </p>
          <p class="stat-sub">
            / {{ formatMemory(gpuSummary?.current?.total_memory || 0) }}
          </p>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <Activity class="w-5 h-5 text-green-500" />
            <span class="stat-label">GPU 利用率</span>
          </div>
          <p class="stat-value" :class="getStatusColor(gpuSummary?.current?.utilization || 0)">
            {{ gpuSummary?.current?.utilization || 0 }}%
          </p>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <Thermometer class="w-5 h-5 text-orange-500" />
            <span class="stat-label">温度</span>
          </div>
          <p class="stat-value" :class="getStatusColor(gpuSummary?.current?.temperature || 0, 75, 90)">
            {{ gpuSummary?.current?.temperature || 0 }}°C
          </p>
        </div>

        <div class="stat-card">
          <div class="stat-header">
            <Zap class="w-5 h-5 text-yellow-500" />
            <span class="stat-label">功耗</span>
          </div>
          <p class="stat-value">
            {{ gpuSummary?.current?.power_draw || 0 }}W
          </p>
          <p class="stat-sub">
            / {{ gpuSummary?.current?.power_limit || 0 }}W
          </p>
        </div>
      </div>

      <!-- Progress Bars -->
      <div class="progress-section">
        <div class="progress-item">
          <div class="progress-header">
            <div class="progress-label">
              <MemoryStick class="w-4 h-4 text-blue-500" />
              <span>显存占用</span>
            </div>
            <span class="progress-value">{{ gpuSummary?.current?.memory_utilization || 0 }}%</span>
          </div>
          <div class="progress-track">
            <div
              class="progress-fill"
              :class="getProgressColor(gpuSummary?.current?.memory_utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.memory_utilization || 0}%` }"
            ></div>
          </div>
        </div>

        <div class="progress-item">
          <div class="progress-header">
            <div class="progress-label">
              <Activity class="w-4 h-4 text-green-500" />
              <span>GPU 利用率</span>
            </div>
            <span class="progress-value">{{ gpuSummary?.current?.utilization || 0 }}%</span>
          </div>
          <div class="progress-track">
            <div
              class="progress-fill"
              :class="getProgressColor(gpuSummary?.current?.utilization || 0)"
              :style="{ width: `${gpuSummary?.current?.utilization || 0}%` }"
            ></div>
          </div>
        </div>
      </div>

      <!-- Details Grid -->
      <div class="details-section">
        <div class="details-header">
          <Fan class="w-4 h-4" />
          <span>详细信息</span>
        </div>
        <div class="details-grid">
          <div class="detail-item">
            <span class="detail-label">GPU 名称</span>
            <p class="detail-value">{{ gpuSummary?.current?.name || '-' }}</p>
          </div>
          <div class="detail-item">
            <span class="detail-label">GPU 数量</span>
            <p class="detail-value">{{ gpuSummary?.current?.gpu_count || 0 }}</p>
          </div>
          <div class="detail-item">
            <span class="detail-label">风扇转速</span>
            <p class="detail-value">{{ gpuSummary?.current?.fan_speed || 0 }}%</p>
          </div>
          <div class="detail-item">
            <span class="detail-label">可用显存</span>
            <p class="detail-value">{{ formatMemory(gpuSummary?.current?.available_memory || 0) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.gpu-monitor {
  background: #ffffff;
  border-radius: 12px;
  border: 1px solid #e2e8f0;
  padding: 20px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.04);
}

.monitor-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 20px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.icon-wrapper {
  width: 40px;
  height: 40px;
  border-radius: 10px;
  background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(59, 130, 246, 0.3);
}

.monitor-title {
  font-size: 16px;
  font-weight: 600;
  color: #0f172a;
}

.monitor-subtitle {
  font-size: 12px;
  color: #94a3b8;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 6px;
  font-size: 13px;
  color: #64748b;
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  cursor: pointer;
  transition: all 0.2s;
}

.action-btn:hover {
  background: #f1f5f9;
  color: #0f172a;
}

.action-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.toggle-btn {
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  border: 1px solid #e2e8f0;
  background: #f8fafc;
  color: #64748b;
  cursor: pointer;
  transition: all 0.2s;
}

.toggle-btn.active {
  background: #ecfdf5;
  border-color: #22c55e;
  color: #059669;
}

/* Loading State */
.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #64748b;
}

.loading-spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #e2e8f0;
  border-top-color: #22c55e;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-bottom: 12px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* Error & Empty States */
.error-state,
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 40px;
  color: #64748b;
}

.error-icon,
.empty-icon {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: #fee2e2;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.empty-icon {
  background: #f1f5f9;
}

/* Stats Grid */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
  margin-bottom: 20px;
}

.stat-card {
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
}

.stat-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.stat-label {
  font-size: 13px;
  color: #64748b;
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: #0f172a;
}

.stat-sub {
  font-size: 12px;
  color: #94a3b8;
  margin-top: 2px;
}

/* Progress Section */
.progress-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 20px;
}

.progress-item {
  padding: 16px;
  background: #f8fafc;
  border-radius: 10px;
  border: 1px solid #f1f5f9;
}

.progress-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.progress-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #64748b;
}

.progress-value {
  font-size: 13px;
  font-weight: 600;
  color: #0f172a;
}

.progress-track {
  height: 8px;
  background: #e2e8f0;
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 4px;
  transition: width 0.5s ease;
}

.progress-fill.bg-green-500 {
  background: linear-gradient(90deg, #22c55e 0%, #16a34a 100%);
}

.progress-fill.bg-yellow-500 {
  background: linear-gradient(90deg, #f59e0b 0%, #ea580c 100%);
}

.progress-fill.bg-red-500 {
  background: linear-gradient(90deg, #ef4444 0%, #dc2626 100%);
}

/* Details Section */
.details-section {
  border-top: 1px solid #f1f5f9;
  padding-top: 16px;
}

.details-header {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: #64748b;
  margin-bottom: 12px;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.detail-item {
  padding: 12px;
  background: #f8fafc;
  border-radius: 8px;
}

.detail-label {
  display: block;
  font-size: 11px;
  color: #94a3b8;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 13px;
  font-weight: 500;
  color: #0f172a;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
