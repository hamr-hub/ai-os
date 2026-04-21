import { createRouter, createWebHistory } from 'vue-router'
import type { RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/',
    name: 'dashboard',
    component: () => import('@/views/Dashboard.vue'),
  },
  {
    path: '/gpu',
    name: 'gpu',
    component: () => import('@/views/GPUView.vue'),
  },
  {
    path: '/models',
    name: 'models',
    component: () => import('@/views/ModelsView.vue'),
  },
  {
    path: '/chat',
    name: 'chat',
    component: () => import('@/views/ChatView.vue'),
  },
  {
    path: '/test',
    name: 'test',
    component: () => import('@/views/TestView.vue'),
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

export default router
