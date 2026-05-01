<script setup lang="ts">
/**
 * ============================================
 * App.vue - 根组件（应用布局容器）
 * ============================================
 * 作用：
 * - 作为整个应用的最外层容器组件
 * - 管理全局布局结构（顶栏 + 侧边栏 + 主内容区）
 * - 初始化应用级状态（主题、服务器连接）
 * - 提供页面切换动画效果
 * 
 * 布局结构：
 * ┌─────────────────────────┐
 * │        TopBar           │  <- 顶部导航栏
 * ├────────┬────────────────┤
 * │        │                │
 * │Sidebar │   RouterView   │  <- 侧边栏 + 动态路由内容
 * │        │                │
 * └────────┴────────────────┘
 * ============================================
 */
import { computed, onMounted } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import Sidebar from '@/components/Sidebar.vue'
import TopBar from '@/components/TopBar.vue'
import ToastContainer from '@/components/ToastContainer.vue'
import { useAppStore } from '@/stores/app'
import { useServerStore } from '@/stores/server'

// 获取应用级状态管理器（主题、Toast 提示等）
const store = useAppStore()
// 获取服务器连接状态管理器（后端连接、健康检查等）
const serverStore = useServerStore()
// 获取当前路由信息
const route = useRoute()

// 组件挂载时执行初始化操作
onMounted(async () => {
  // 初始化主题设置（从 localStorage 读取或设置默认值）
  store.initTheme()
  // 从本地存储恢复服务器连接配置
  serverStore.initFromStorage()
  // 检查后端服务连接状态
  await serverStore.checkConnection()
})

// 根据侧边栏折叠状态动态计算主内容区的左边距
const mainMargin = computed(() =>
  store.sidebarCollapsed ? 'var(--sidebar-collapsed-width)' : 'var(--sidebar-width)'
)

// 判断当前页面是否需要全屏显示（不需要侧边栏和顶栏）
const isFullscreenPage = computed(() => route.meta?.noAuth === true)
</script>

<template>
  <!-- 应用最外层容器 -->
  <div class="app-shell">
    <!-- Toast 消息提示容器：显示全局通知 -->
    <ToastContainer />
    
    <!-- 需要认证的页面显示布局元素 -->
    <template v-if="!isFullscreenPage">
      <!-- 顶部导航栏：显示服务器状态、连接管理等 -->
      <TopBar />
      <!-- 左侧边栏：导航菜单、GPU 状态等 -->
      <Sidebar />
      <!-- 主内容区域：根据路由动态渲染不同页面 -->
      <main class="app-main" :style="{ marginLeft: mainMargin }">
        <!-- RouterView 插槽：渲染当前路由对应的组件 -->
        <RouterView v-slot="{ Component }">
          <!-- 页面切换过渡动画 -->
          <transition name="page" mode="out-in">
            <component :is="Component" class="app-page" />
          </transition>
        </RouterView>
      </main>
    </template>
    
    <!-- 不需要认证的页面（如登录）全屏显示 -->
    <template v-else>
      <RouterView v-slot="{ Component }">
        <component :is="Component" />
      </RouterView>
    </template>
  </div>
</template>

<style scoped>
/* 应用整体布局容器 */
.app-shell {
  min-height: 100vh;
  background-color: var(--bg-primary);
  color: var(--text-primary);
  display: flex;
}

/* 主内容区域：占据剩余空间 */
.app-main {
  flex: 1;
  min-height: 100vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  background-color: var(--bg-primary);
  /* 侧边栏折叠/展开时的平滑过渡动画 */
  transition: margin-left 0.3s cubic-bezier(0.4, 0, 0.2, 1);
  padding-top: var(--topbar-height);
}

/* 页面内容区域：填充整个主内容区 */
.app-page {
  flex: 1;
  height: 100%;
  min-height: 0;
  overflow: hidden;
}

/* 页面进入/离开动画定义 */
.page-enter-active,
.page-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

/* 页面进入起点：淡入 + 从下方滑入 */
.page-enter-from {
  opacity: 0;
  transform: translateY(8px);
}

/* 页面离开终点：淡出 + 向上方滑出 */
.page-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
