<script setup lang="ts">
import { ref, computed } from 'vue'
import type { HealthAlert } from '@/types'
import { getHealthStatusConfig } from '@/utils/theme'
import { ShieldCheck, AlertTriangle, ChevronDown, ChevronUp } from 'lucide-vue-next'

const props = defineProps<{
  healthAlert: HealthAlert | null
}>()

const alertExpanded = ref(false)

const healthStatusColor = computed(() =>
  getHealthStatusConfig(props.healthAlert?.status ?? 'critical')
)
</script>

<template>
  <div class="card-header">
    <div class="icon-wrap green"><ShieldCheck class="card-icon-inner" /></div>
    <span class="card-title">健康告警</span>
    <span
      v-if="healthAlert"
      class="badge"
      :style="{ background: healthStatusColor.bg, color: healthStatusColor.color }"
    >
      {{ healthStatusColor.label }}
    </span>
  </div>
  <template v-if="healthAlert">
    <div class="health-score-row">
      <div
        class="health-score"
        :class="
          healthAlert.health_score >= 70
            ? 'good'
            : healthAlert.health_score >= 50
              ? 'degraded'
              : 'bad'
        "
      >
        {{ healthAlert.health_score.toFixed(0) }}
      </div>
      <div class="health-score-bar">
        <div
          class="hs-fill"
          :style="{
            width: `${healthAlert.health_score}%`,
            background:
              healthAlert.health_score >= 70
                ? '#22c55e'
                : healthAlert.health_score >= 50
                  ? '#f59e0b'
                  : '#ef4444',
          }"
        ></div>
      </div>
    </div>
    <div v-if="healthAlert.alert_reasons?.length" class="alert-reasons">
      <button class="alert-toggle" @click="alertExpanded = !alertExpanded">
        <AlertTriangle
          class="alert-toggle-icon"
          :style="{ color: healthAlert.should_alert ? '#f59e0b' : '#22c55e' }"
        />
        <span>{{ healthAlert.alert_reasons.length }} 条告警</span>
        <ChevronDown v-if="!alertExpanded" class="chevron-icon" />
        <ChevronUp v-else class="chevron-icon" />
      </button>
      <div v-if="alertExpanded" class="alert-list">
        <div
          v-for="(reason, idx) in healthAlert.alert_reasons"
          :key="idx"
          class="alert-item"
        >
          <span
            class="alert-dot"
            :class="healthAlert.should_alert ? 'warning' : 'info'"
          ></span>
          <span>{{ reason }}</span>
        </div>
      </div>
    </div>
  </template>
  <div v-else class="empty-state">
    <ShieldCheck class="empty-icon" />
    <p>健康数据不可用</p>
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

.badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 10px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: 500;
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

.health-score-row {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 16px;
}

.health-score {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 22px;
  font-weight: 700;
}

.health-score.good {
  background: rgba(34, 197, 94, 0.15);
  color: #22c55e;
}

.health-score.degraded {
  background: rgba(245, 158, 11, 0.15);
  color: #f59e0b;
}

.health-score.bad {
  background: rgba(239, 68, 68, 0.15);
  color: #ef4444;
}

.health-score-bar {
  flex: 1;
  height: 6px;
  background: var(--bg-tertiary);
  border-radius: 3px;
  overflow: hidden;
}

.hs-fill {
  height: 100%;
  border-radius: 3px;
  transition: width 0.5s ease;
}

.alert-reasons {
  margin-top: 12px;
}

.alert-toggle {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  background: var(--bg-secondary);
  border: 1px solid var(--border-primary);
  cursor: pointer;
  width: 100%;
  transition: all 0.2s;
}

.alert-toggle:hover {
  background: var(--bg-tertiary);
  color: var(--text-primary);
}

.alert-toggle-icon {
  width: 16px;
  height: 16px;
}

.chevron-icon {
  width: 12px;
  height: 12px;
}

.alert-list {
  margin-top: 8px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.alert-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  background: var(--bg-secondary);
  border-radius: 6px;
  font-size: 13px;
}

.alert-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.alert-dot.warning {
  background: #f59e0b;
}

.alert-dot.info {
  background: #22c55e;
}
</style>
