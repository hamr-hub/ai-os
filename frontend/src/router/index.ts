import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
  },
  {
    path: '/monitor',
    name: 'monitor',
    component: () => import('@/views/MonitorView.vue'),
  },
  {
    path: '/models',
    name: 'models',
    component: () => import('@/views/ModelManagement.vue'),
  },
  {
    path: '/agent',
    name: 'agent',
    component: () => import('@/views/AgentView.vue'),
  },
  {
    path: '/benchmarks',
    name: 'benchmarks',
    component: () => import('@/views/ModelBenchmarks.vue'),
  },
  {
    path: '/docs',
    name: 'docs',
    component: () => import('@/views/DocsView.vue'),
  },
  {
    path: '/docs/:slug',
    name: 'docs-slug',
    component: () => import('@/views/DocsView.vue'),
  },
  {
    path: '/gpumanage',
    name: 'gpumanage',
    component: () => import('@/views/GPUManage.vue'),
  },
  {
    path: '/modelhub',
    name: 'modelhub',
    component: () => import('@/views/ModelHubPage.vue'),
  },
  {
    path: '/modelpool',
    name: 'modelpool',
    component: () => import('@/views/ModelPoolPage.vue'),
  },
  {
    path: '/engines',
    name: 'engines',
    component: () => import('@/views/EngineManagementPage.vue'),
  },
  {
    path: '/ratelimit',
    name: 'ratelimit',
    component: () => import('@/views/RateLimitPage.vue'),
  },
  {
    path: '/config',
    name: 'config',
    component: () => import('@/views/ConfigManagementPage.vue'),
  },
  {
    path: '/health',
    name: 'health',
    component: () => import('@/views/HealthOpsPage.vue'),
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('@/views/AuthPage.vue'),
    meta: { noAuth: true },
  },
  {
    path: '/blocked',
    name: 'blocked',
    component: () => import('@/views/WhitelistBlocked.vue'),
    meta: { noAuth: true },
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/Dashboard.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.beforeEach((to) => {
  if (to.meta.noAuth) return true
  const authStore = useAuthStore()
  if (!authStore.isAuthenticated) {
    return { name: 'login' }
  }
  return true
})

export default router
