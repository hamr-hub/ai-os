<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Server, Search, Database, ShieldCheck } from 'lucide-vue-next'
import ModelManagement from '@/views/ModelManagement.vue'
import ModelHubPage from '@/views/ModelHubPage.vue'
import ModelPoolPage from '@/views/ModelPoolPage.vue'
import ModelBenchmarks from '@/views/ModelBenchmarks.vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { key: 'schedule', label: '模型调度', icon: Server },
  { key: 'search', label: '模型搜索', icon: Search },
  { key: 'pool', label: '模型池', icon: Database },
  { key: 'benchmark', label: '模型评测', icon: ShieldCheck },
]

const activeTab = ref((route.query.tab as string) || 'schedule')

watch(activeTab, (tab) => {
  router.replace({ name: 'modelcenter', query: { tab } })
})

watch(() => route.query.tab, (tab) => {
  if (tab && tab !== activeTab.value) {
    activeTab.value = tab as string
  }
})

const currentIcon = computed(() => {
  const t = tabs.find(t => t.key === activeTab.value)
  return t?.icon ?? Server
})
</script>

<template>
  <div class="model-center">
    <div class="page-header">
      <div class="header-left">
        <component :is="currentIcon" class="header-icon" />
        <div class="header-title">
          <h1>模型中心</h1>
          <p class="header-subtitle">调度 · 搜索 · 池 · 评测 — 一站式模型管理</p>
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
      <ModelManagement v-show="activeTab === 'schedule'" />
      <ModelHubPage v-show="activeTab === 'search'" />
      <ModelPoolPage v-show="activeTab === 'pool'" />
      <ModelBenchmarks v-show="activeTab === 'benchmark'" />
    </div>
  </div>
</template>

<style scoped>
.model-center {
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
