<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Zap, Gauge, Settings, Heart } from 'lucide-vue-next'
import EngineManagementPage from '@/views/EngineManagementPage.vue'
import RateLimitPage from '@/views/RateLimitPage.vue'
import ConfigManagementPage from '@/views/ConfigManagementPage.vue'
import HealthOpsPage from '@/views/HealthOpsPage.vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { key: 'engine', label: '引擎管理', icon: Zap },
  { key: 'ratelimit', label: '限流控制', icon: Gauge },
  { key: 'config', label: '配置中心', icon: Settings },
  { key: 'health', label: '健康运维', icon: Heart },
]

const activeTab = ref((route.query.tab as string) || 'engine')

watch(activeTab, (tab) => {
  router.replace({ name: 'systemops', query: { tab } })
})

watch(() => route.query.tab, (tab) => {
  if (tab && tab !== activeTab.value) {
    activeTab.value = tab as string
  }
})

const currentIcon = computed(() => {
  const t = tabs.find(t => t.key === activeTab.value)
  return t?.icon ?? Zap
})
</script>

<template>
  <div class="system-ops">
    <div class="page-header">
      <div class="header-left">
        <component :is="currentIcon" class="header-icon" />
        <div class="header-title">
          <h1>系统运维</h1>
          <p class="header-subtitle">引擎 · 限流 · 配置 · 健康 — 全栈运维管控</p>
        </div>
      </div>
    </div>

    <div class="tab-controls">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        class="tab-btn"
        :class="{ active: activeTab === tab.key }"
        @click="activeTab = tab.key"
      >
        <component :is="tab.icon" class="tab-icon" />
        <span>{{ tab.label }}</span>
      </button>
    </div>

    <div class="tab-content">
      <EngineManagementPage v-show="activeTab === 'engine'" />
      <RateLimitPage v-show="activeTab === 'ratelimit'" />
      <ConfigManagementPage v-show="activeTab === 'config'" />
      <HealthOpsPage v-show="activeTab === 'health'" />
    </div>
  </div>
</template>

<style scoped>
.system-ops {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.header-icon {
  width: 28px;
  height: 28px;
  color: var(--color-primary-light);
}

.header-title h1 {
  font-size: 22px;
  font-weight: 800;
  color: var(--text-primary);
  margin: 0;
  line-height: 1.2;
}

.header-subtitle {
  font-size: 13px;
  color: var(--text-muted);
  margin: 4px 0 0;
}

.tab-controls {
  display: flex;
  gap: 4px;
  padding: 0 24px 16px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
}

.tab-btn {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 18px;
  border-radius: 10px;
  border: 1px solid transparent;
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.2s;
}

.tab-btn:hover {
  background: rgba(99, 102, 241, 0.06);
  color: var(--text-primary);
}

.tab-btn.active {
  background: rgba(99, 102, 241, 0.12);
  border-color: rgba(99, 102, 241, 0.25);
  color: var(--color-primary-light);
}

.tab-icon {
  width: 16px;
  height: 16px;
}

.tab-content {
  flex: 1;
  overflow: hidden;
}
</style>
