<script setup lang="ts">
import { computed } from 'vue'
import type { QueueStatus } from '@/types'
import { ListOrdered } from 'lucide-vue-next'

const props = defineProps<{
  queueStatus: QueueStatus | null
}>()

const totalActive = computed(() => {
  if (!props.queueStatus) return 0
  return Object.values(props.queueStatus).reduce((sum, e) => sum + e.active_requests, 0)
})

const maxConcurrency = computed(() => {
  if (!props.queueStatus) return 0
  const entries = Object.values(props.queueStatus)
  return entries.length > 0 ? entries[0].concurrency_limit : 0
})

const entries = computed(() => {
  if (!props.queueStatus) return []
  return Object.entries(props.queueStatus).map(([name, e]) => ({ name, ...e }))
})
</script>

<template>
  <div class="card-header">
    <div class="icon-wrap blue"><ListOrdered class="card-icon-inner" /></div>
    <span class="card-title">请求队列</span>
    <span class="card-meta">{{ totalActive }} / {{ maxConcurrency }}</span>
  </div>
  <template v-if="entries.length">
    <div class="queue-entries">
      <div v-for="entry in entries" :key="entry.name" class="queue-row">
        <span class="queue-name">{{ entry.name }}</span>
        <div class="queue-bar-wrap">
          <div
            class="queue-bar-fill"
            :style="{ width: maxConcurrency ? Math.min((entry.active_requests / maxConcurrency) * 100, 100) + '%' : '0%' }"
            :class="{ full: !entry.can_accept }"
          ></div>
        </div>
        <span class="queue-count" :class="{ full: !entry.can_accept }">
          {{ entry.active_requests }}/{{ maxConcurrency }}
        </span>
      </div>
    </div>
  </template>
  <template v-else>
    <div class="empty-msg">暂无队列数据</div>
  </template>
</template>

<style scoped>
.queue-entries {
  display: flex;
  flex-direction: column;
  gap: 6px;
}
.queue-row {
  display: flex;
  align-items: center;
  gap: 8px;
}
.queue-name {
  font-size: 11px;
  color: #9ca3af;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1;
}
.queue-bar-wrap {
  width: 60px;
  height: 4px;
  background: #1f2937;
  border-radius: 2px;
  overflow: hidden;
  flex-shrink: 0;
}
.queue-bar-fill {
  height: 100%;
  background: #3b82f6;
  border-radius: 2px;
  transition: width 0.3s;
}
.queue-bar-fill.full {
  background: #ef4444;
}
.queue-count {
  font-size: 11px;
  color: #9ca3af;
  flex-shrink: 0;
  font-variant-numeric: tabular-nums;
}
.queue-count.full {
  color: #ef4444;
}
.empty-msg {
  font-size: 12px;
  color: #6b7280;
  text-align: center;
  padding: 8px 0;
}
</style>
