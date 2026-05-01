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
    path: '/modelcenter',
    name: 'modelcenter',
    component: () => import('@/views/ModelCenter.vue'),
  },
  {
    path: '/gpumonitor',
    name: 'gpumonitor',
    component: () => import('@/views/GPUMonitor.vue'),
  },
  {
    path: '/systemops',
    name: 'systemops',
    component: () => import('@/views/SystemOps.vue'),
  },
  {
    path: '/agent',
    name: 'agent',
    component: () => import('@/views/AgentView.vue'),
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
    path: '/models',
    redirect: { name: 'modelcenter', query: { tab: 'schedule' } },
  },
  {
    path: '/modelhub',
    redirect: { name: 'modelcenter', query: { tab: 'search' } },
  },
  {
    path: '/modelpool',
    redirect: { name: 'modelcenter', query: { tab: 'pool' } },
  },
  {
    path: '/benchmarks',
    redirect: { name: 'modelcenter', query: { tab: 'benchmark' } },
  },
  {
    path: '/monitor',
    redirect: { name: 'gpumonitor', query: { tab: 'performance' } },
  },
  {
    path: '/gpumanage',
    redirect: { name: 'gpumonitor', query: { tab: 'manage' } },
  },
  {
    path: '/engines',
    redirect: { name: 'systemops', query: { tab: 'engine' } },
  },
  {
    path: '/ratelimit',
    redirect: { name: 'systemops', query: { tab: 'ratelimit' } },
  },
  {
    path: '/config',
    redirect: { name: 'systemops', query: { tab: 'config' } },
  },
  {
    path: '/health',
    redirect: { name: 'systemops', query: { tab: 'health' } },
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
    redirect: { name: 'dashboard' },
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
