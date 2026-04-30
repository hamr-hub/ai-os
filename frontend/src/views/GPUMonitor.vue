<script setup lang="ts">
import { ref, watch, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Activity, Cpu } from 'lucide-vue-next'
import MonitorView from '@/views/MonitorView.vue'
import GPUManage from '@/views/GPUManage.vue'

const route = useRoute()
const router = useRouter()

const tabs = [
  { key: 'performance', label: '实时性能', icon: Activity },
  { key: 'manage', label: 'GPU 管理', icon: Cpu },
]

const activeTab = ref((route.query.tab as string) || 'performance')

watch(activeTab, (tab) => {
  router.replace({ name: 'gpumonitor', query: { tab } })
})

watch(() => route.query.tab, (tab) => {
  if (tab && tab !== activeTab.value) {
    activeTab.value = tab as string
  }
})

const currentIcon = computed(() => {
  const t = tabs.find(t => t.key === activeTab.value)
  return t?.icon ?? Activity
})
</script>

<template>
  <div class="gpu-monitor">
    <div class="page-header">
      <div class="header-left">
        <component :is="currentIcon" class="header-icon" />
        <div class="header-title">
          <h1>GPU 监控</h1>
          <p class="header-subtitle">实时性能 · 硬件管理 — GPU 全状态洞察</p>
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
      <MonitorView v-show="activeTab === 'performance'" />
      <GPUManage v-show="activeTab === 'manage'" />
    </div>
  </div>
</template>

<style scoped>
.gpu-monitor {
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
