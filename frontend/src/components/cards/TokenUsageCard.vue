<script setup lang="ts">
import type { TokenStats } from '@/types'
import { formatRelativeTime } from '@/utils/format'
import { Activity, Coins, Zap } from 'lucide-vue-next'

const props = defineProps<{
  stats: TokenStats | null
  totalTokens: number
  promptTokens: number
  completionTokens: number
  modelStats: Record<string, { total_tokens: number }>
  formatTokens: (n: number) => string
}>()
</script>

<template>
  <div class="card-header">
    <div class="icon-wrap purple"><Coins class="card-icon-inner" /></div>
    <span class="card-title">Token 用量</span>
    <span class="card-meta">更新 {{ formatRelativeTime(props.stats?.timestamp) }}</span>
    <span v-if="stats" class="count-badge">{{ formatTokens(totalTokens) }}</span>
  </div>
  <div v-if="stats" class="token-grid">
    <div class="token-item">
      <Activity class="token-icon blue" />
      <div class="token-info">
        <span class="token-value">{{ formatTokens(promptTokens) }}</span>
        <span class="token-label">Prompt</span>
      </div>
    </div>
    <div class="token-item">
      <Coins class="token-icon green" />
      <div class="token-info">
        <span class="token-value">{{ formatTokens(completionTokens) }}</span>
        <span class="token-label">Completion</span>
      </div>
    </div>
    <div class="token-item">
      <Zap class="token-icon purple" />
      <div class="token-info">
        <span class="token-value">{{ formatTokens(totalTokens) }}</span>
        <span class="token-label">Total</span>
      </div>
    </div>
  </div>
  <div v-if="stats && Object.keys(modelStats).length" class="model-token-list">
    <div v-for="(s, name) in modelStats" :key="name" class="model-token-row">
      <span class="mt-name">{{ name }}</span>
      <div class="mt-bar-track">
        <div
          class="mt-bar-fill"
          :style="{
            width: `${Math.min(100, (s.total_tokens / Math.max(totalTokens, 1)) * 100)}%`,
          }"
        ></div>
      </div>
      <span class="mt-count">{{ formatTokens(s.total_tokens) }}</span>
    </div>
  </div>
  <div v-if="!stats" class="empty-state">
    <p>暂无 Token 统计</p>
    <span class="empty-hint">等待请求产生后将自动更新</span>
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

.icon-wrap.purple {
  background: rgba(139, 92, 246, 0.15);
  color: #8b5cf6;
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

.empty-state p {
  margin: 0;
}

.empty-hint {
  display: block;
  margin-top: 6px;
  font-size: 11px;
  color: var(--text-tertiary);
}

.token-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
  margin-bottom: 12px;
}

.token-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px;
  background: var(--bg-secondary);
  border-radius: 8px;
}

.token-icon {
  width: 16px;
  height: 16px;
}

.token-icon.blue {
  color: #60a5fa;
}

.token-icon.green {
  color: #4ade80;
}

.token-icon.purple {
  color: #a78bfa;
}

.token-info {
  display: flex;
  flex-direction: column;
}

.token-value {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.token-label {
  font-size: 11px;
  color: var(--text-muted);
}

.model-token-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.model-token-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.mt-name {
  font-size: 12px;
  color: var(--text-secondary);
  min-width: 80px;
}

.mt-bar-track {
  flex: 1;
  height: 4px;
  background: var(--bg-tertiary);
  border-radius: 2px;
  overflow: hidden;
}

.mt-bar-fill {
  height: 100%;
  background: linear-gradient(90deg, #8b5cf6, #7c3aed);
  border-radius: 2px;
  transition: width 0.5s ease;
  min-width: 2px;
}

.mt-count {
  font-size: 11px;
  color: var(--text-muted);
  min-width: 40px;
  text-align: right;
}
</style>
