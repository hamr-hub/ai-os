<script setup lang="ts">
import { computed } from 'vue'
import type { QueueModelEntry } from '@/types'
import { Layers } from 'lucide-vue-next'

const props = defineProps<{
  queueStatus: Record<string, QueueModelEntry> | null
  defaultModel: string | null
}>()

const totalQueueRequests = computed(() => {
  if (!props.queueStatus) return 0
  return Object.values(props.queueStatus).reduce(
    (sum, q) => sum + q.active_requests,
    0
  )
})

const activeQueueEntries = computed(() => {
  if (!props.queueStatus) return []
  const entries = Object.entries(props.queueStatus)
    .filter(([, entry]) => entry.active_requests > 0)
    .sort(([, a], [, b]) => b.active_requests - a.active_requests)
  if (!entries.length) return []
  const target = props.defaultModel || entries[0][0]
  return entries
    .filter(([name]) => name === target)
    .slice(0, 1)
    .map(([name, entry]) => ({ name, ...entry }))
})
</script>

<template>
  <div class="card-header">
    <div class="icon-wrap primary"><Layers class="card-icon-inner" /></div>
    <span class="card-title">请求队列</span>
    <span v-if="queueStatus" class="count-badge">{{ totalQueueRequests }} 请求</span>
  </div>
  <template v-if="queueStatus">
    <div v-if="activeQueueEntries.length" class="queue-list">
      <div v-for="entry in activeQueueEntries" :key="entry.name" class="queue-row warning">
        <span class="q-name">{{ entry.name }}</span>
        <div class="q-info">
          <span class="q-count warning">{{ entry.active_requests }}</span>
          <span class="q-limit">/ {{ entry.concurrency_limit }}</span>
        </div>
        <span class="q-status" :class="entry.can_accept ? 'success' : 'danger'">{{
          entry.can_accept ? '可接受' : '已满'
        }}</span>
      </div>
    </div>
    <div v-else class="empty-state">
      <Layers class="empty-icon" />
      <p>当前无活跃请求</p>
    </div>
  </template>
  <div v-else class="empty-state">
    <Layers class="empty-icon-lg" />
    <p>队列数据不可用</p>
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
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.empty-icon {
  width: 32px;
  height: 32px;
  color: var(--text-muted);
}

.empty-icon-lg {
  width: 40px;
  height: 40px;
  color: var(--text-muted);
}

.queue-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.queue-row {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  background: var(--bg-secondary);
  border-radius: 8px;
  border-left: 3px solid;
}

.queue-row.warning {
  border-left-color: #f59e0b;
}

.q-name {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-primary);
}

.q-info {
  display: flex;
  align-items: center;
  gap: 4px;
}

.q-count.warning {
  color: #f59e0b;
  font-weight: 600;
}

.q-limit {
  font-size: 11px;
  color: var(--text-muted);
}

.q-status {
  margin-left: auto;
  font-size: 12px;
  font-weight: 500;
}

.q-status.success {
  color: #22c55e;
}

.q-status.danger {
  color: #ef4444;
}
</style>
