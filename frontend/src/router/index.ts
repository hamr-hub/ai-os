import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

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
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
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
    path: '/:pathMatch(.*)*',
    name: 'not-found',
    component: () => import('@/views/Dashboard.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
