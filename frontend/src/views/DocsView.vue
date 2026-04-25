<script setup lang="ts">
import { ref, computed, watch, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { docTree, getDocLoader, type DocItem } from '@/docs'
import { BookOpen, ChevronRight, ChevronDown, FileText, FolderOpen } from 'lucide-vue-next'

const route = useRoute()
const router = useRouter()

const expandedGroups = ref<Set<string>>(new Set(['deployment']))
const currentDoc = ref<string>('deployment-guide')
const currentComponent = ref<unknown>(null)
const loading = ref(false)

const slugFromRoute = computed(() => {
  const s = route.params.slug as string
  return s || 'deployment-guide'
})

function findDocItem(slug: string): { item: DocItem; category: string } | null {
  for (const group of docTree) {
    if (group.slug === slug) return { item: group, category: group.category }
    if (group.children) {
      for (const child of group.children) {
        if (child.slug === slug) return { item: child, category: group.category }
      }
    }
  }
  return null
}

async function loadDoc(slug: string) {
  const found = findDocItem(slug)
  if (!found) return

  const { category } = found
  const loader = getDocLoader(category, slug)
  if (!loader) return

  loading.value = true
  currentDoc.value = slug

  try {
    const mod = await loader()
    currentComponent.value = mod.default
  } catch (e) {
    console.error('Failed to load doc:', e)
    currentComponent.value = null
  } finally {
    loading.value = false
  }

  if (route.params.slug !== slug) {
    router.push({ name: 'docs-slug', params: { slug } })
  }
}

function toggleGroup(slug: string) {
  if (expandedGroups.value.has(slug)) {
    expandedGroups.value.delete(slug)
  } else {
    expandedGroups.value.add(slug)
  }
}

function isActive(slug: string) {
  return currentDoc.value === slug
}

onMounted(() => {
  loadDoc(slugFromRoute.value)
})

watch(slugFromRoute, (newSlug) => {
  if (newSlug !== currentDoc.value) {
    loadDoc(newSlug)
  }
})
</script>

<template>
  <div class="docs-page">
    <aside class="docs-sidebar">
      <div class="sidebar-header">
        <BookOpen class="w-5 h-5" style="color: var(--color-primary)" />
        <span class="sidebar-title">项目文档</span>
      </div>
      <nav class="sidebar-nav">
        <div v-for="group in docTree" :key="group.slug" class="nav-group">
          <button class="nav-group-title" @click="toggleGroup(group.slug)">
            <component
              :is="expandedGroups.has(group.slug) ? ChevronDown : ChevronRight"
              class="w-4 h-4"
            />
            <FolderOpen class="w-4 h-4" style="color: var(--color-primary); opacity: 0.7" />
            <span>{{ group.title }}</span>
          </button>
          <transition name="slide">
            <div v-if="expandedGroups.has(group.slug)" class="nav-children">
              <button
                v-for="child in group.children"
                :key="child.slug"
                class="nav-child"
                :class="{ active: isActive(child.slug) }"
                @click="loadDoc(child.slug)"
              >
                <FileText class="w-3.5 h-3.5" />
                <span>{{ child.title }}</span>
              </button>
            </div>
          </transition>
        </div>
      </nav>
    </aside>
    <main class="docs-content">
      <div v-if="loading" class="docs-loading">
        <div class="spinner" />
        <span>加载中...</span>
      </div>
      <div v-else-if="currentComponent" class="markdown-body">
        <component :is="currentComponent" />
      </div>
      <div v-else class="docs-empty">
        <BookOpen class="w-12 h-12" style="color: var(--text-muted)" />
        <p>选择左侧文档开始阅读</p>
      </div>
    </main>
  </div>
</template>

<style scoped>
.docs-page {
  display: flex;
  height: 100%;
  overflow: hidden;
  background: var(--bg-primary);
}

.docs-sidebar {
  width: 260px;
  flex-shrink: 0;
  border-right: 1px solid var(--border-card);
  background: var(--bg-card);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 16px 20px;
  border-bottom: 1px solid var(--border-primary);
}

.sidebar-title {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-primary);
}

.sidebar-nav {
  flex: 1;
  overflow-y: auto;
  padding: 8px 0;
}

.nav-group {
  margin-bottom: 2px;
}

.nav-group-title {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
  padding: 10px 16px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: background 0.2s;
  text-align: left;
}

.nav-group-title:hover {
  background: var(--bg-hover);
}

.nav-children {
  padding-left: 12px;
}

.nav-child {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
  padding: 8px 16px 8px 36px;
  font-size: 13px;
  color: var(--text-secondary);
  background: transparent;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
  text-align: left;
  border-radius: 6px;
  margin: 1px 8px 1px 0;
}

.nav-child:hover {
  color: var(--text-primary);
  background: var(--bg-hover);
}

.nav-child.active {
  color: var(--color-primary);
  background: rgba(var(--color-primary-rgb), 0.1);
  font-weight: 500;
  box-shadow: 0 1px 4px rgba(var(--color-primary-rgb), 0.15);
}

.docs-content {
  flex: 1;
  overflow-y: auto;
  padding: 32px 48px;
  min-width: 0;
}

.docs-loading {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  height: 300px;
  color: var(--text-muted);
  font-size: 14px;
}

.spinner {
  width: 28px;
  height: 28px;
  border: 3px solid var(--border-primary);
  border-top-color: var(--color-primary);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.docs-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 300px;
  color: var(--text-muted);
  font-size: 14px;
}

.slide-enter-active {
  transition: all 0.2s ease;
}
.slide-leave-active {
  transition: all 0.15s ease;
}
.slide-enter-from,
.slide-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
