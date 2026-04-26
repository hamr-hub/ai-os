<script setup lang="ts">
import { computed } from 'vue'
import type { SystemStatus, SystemHistoryEntry } from '@/types'
import { formatRelativeTime, formatTimeLabel } from '@/utils/format'
import { getProgressColor, getStatusLevel } from '@/utils/theme'
import LineChart from '@/components/LineChart.vue'
import { Cpu, MemoryStick, HardDrive, Server } from 'lucide-vue-next'

const props = defineProps<{
  systemStatus: SystemStatus | null
  systemHistory: SystemHistoryEntry[]
}>()

const timeLabels = computed(() => props.systemHistory.map((e) => formatTimeLabel(e.timestamp)))
const lastUpdatedLabel = computed(() => formatRelativeTime(props.systemStatus?.timestamp))

const sparklineDatasets = (
  key: 'cpu_percent' | 'memory_percent',
  color: string,
  bgColor: string
) => [
  {
    label: '',
    data: props.systemHistory.map((e) => Number(e[key]) || 0),
    borderColor: color,
    backgroundColor: bgColor,
    fill: true,
    tension: 0.4,
    pointRadius: 0,
    borderWidth: 2,
  },
]
</script>

<template>
  <div class="card-header">
    <div class="icon-wrap primary"><Server class="card-icon-inner" /></div>
    <span class="card-title">系统状态</span>
    <span class="card-meta">更新 {{ lastUpdatedLabel }}</span>
  </div>
  <template v-if="systemStatus">
    <div class="system-grid">
      <div class="sys-item">
        <Cpu
          class="sys-icon"
          :style="{ color: getProgressColor(systemStatus.cpu.percent) }"
        />
        <div class="sys-info">
          <span class="sys-label">CPU</span>
          <span class="sys-val" :class="getStatusLevel(systemStatus.cpu.percent)"
            >{{ systemStatus.cpu.percent.toFixed(1) }}%</span
          >
        </div>
        <span class="sys-meta"
          >{{ systemStatus.cpu.cores_physical }}核 / {{ systemStatus.cpu.cores }}线程</span
        >
        <div v-if="systemHistory.length >= 2" class="sys-chart">
          <LineChart
            :labels="timeLabels"
            :datasets="sparklineDatasets('cpu_percent', '#fbbf24', 'rgba(251,191,36,0.05)')"
            :height="60"
            :show-legend="false"
            :animate="false"
            y-unit="%"
            :y-min="0"
            :y-max="100"
          />
        </div>
      </div>
      <div class="sys-item">
        <MemoryStick
          class="sys-icon"
          :style="{ color: getProgressColor(systemStatus.memory.percent) }"
        />
        <div class="sys-info">
          <span class="sys-label">内存</span>
          <span class="sys-val" :class="getStatusLevel(systemStatus.memory.percent)"
            >{{ systemStatus.memory.percent.toFixed(1) }}%</span
          >
        </div>
        <span class="sys-meta"
          >{{ (systemStatus.memory.used_mb / 1024).toFixed(1) }} /
          {{ (systemStatus.memory.total_mb / 1024).toFixed(1) }} GB</span
        >
        <div v-if="systemHistory.length >= 2" class="sys-chart">
          <LineChart
            :labels="timeLabels"
            :datasets="sparklineDatasets('memory_percent', '#22d3ee', 'rgba(34,211,238,0.05)')"
            :height="60"
            :show-legend="false"
            :animate="false"
            y-unit="%"
            :y-min="0"
            :y-max="100"
          />
        </div>
      </div>
      <div class="sys-item">
        <HardDrive
          class="sys-icon"
          :style="{ color: getProgressColor(systemStatus.disk.percent) }"
        />
        <div class="sys-info">
          <span class="sys-label">磁盘</span>
          <div class="sys-bar-track">
            <div
              class="sys-bar-fill"
              :style="{
                width: `${systemStatus.disk.percent}%`,
                background: getProgressColor(systemStatus.disk.percent),
              }"
            ></div>
          </div>
          <span class="sys-val" :class="getStatusLevel(systemStatus.disk.percent)"
            >{{ systemStatus.disk.percent.toFixed(1) }}%</span
          >
        </div>
        <span class="sys-meta"
          >{{ systemStatus.disk.used_gb }} / {{ systemStatus.disk.total_gb }} GB</span
        >
      </div>
    </div>
  </template>
  <div v-else class="empty-state">
    <Server class="empty-icon" />
    <p>系统数据不可用</p>
    <span class="empty-hint">请检查管理后端连接状态</span>
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

.icon-wrap.primary {
  background: rgba(99, 102, 241, 0.15);
  color: #6366f1;
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

.card-meta {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-muted);
}

.empty-state {
  text-align: center;
  color: var(--text-muted);
  padding: 24px 0;
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.empty-icon {
  width: 40px;
  height: 40px;
  color: var(--text-muted);
}

.empty-hint {
  font-size: 11px;
  color: var(--text-tertiary);
}

.system-grid {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.sys-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.sys-icon {
  width: 16px;
  height: 16px;
}

.sys-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.sys-label {
  font-size: 11px;
  color: var(--text-muted);
}

.sys-val {
  font-size: 13px;
  font-weight: 600;
}

.sys-meta {
  font-size: 10px;
  color: var(--text-muted);
}

.sys-chart {
  margin-top: 4px;
}

.sys-bar-track {
  height: 4px;
  background: rgba(255, 255, 255, 0.05);
  border-radius: 2px;
  overflow: hidden;
}

.sys-bar-fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
}
</style>
