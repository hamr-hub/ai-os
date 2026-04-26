/**
 * ============================================
 * AI OS - 应用入口文件
 * ============================================
 * 作用：
 * - 初始化 Vue 3 应用实例
 * - 配置 Pinia 状态管理
 * - 配置 Vue Router 路由系统
 * - 注册全局错误处理器和未捕获 Promise 异常处理器
 * - 挂载应用到 DOM
 * 
 * 加载顺序：
 * 1. 导入 Vue 核心模块
 * 2. 创建应用实例
 * 3. 创建 Pinia 实例
 * 4. 配置错误处理器
 * 5. 注册插件
 * 6. 挂载到 #app 元素
 * ============================================
 */
import { createApp } from 'vue'
import { createPinia } from 'pinia'
import router from '@/router'
import './style.css'
import App from './App.vue'

// 创建 Vue 应用实例
const app = createApp(App)
// 创建 Pinia 状态管理实例
const pinia = createPinia()

// 配置全局错误处理器：捕获 Vue 组件运行时错误
app.config.errorHandler = (_err, _instance, info) => {
  console.error('[Vue Error]', info)
}

// 配置全局警告处理器：捕获 Vue 警告信息（如属性类型不匹配）
app.config.warnHandler = (_msg, _instance, trace) => {
  console.warn('[Vue Warn]', trace)
}

// 监听未处理的 Promise rejection，防止静默失败
window.addEventListener('unhandledrejection', (event) => {
  console.error('[Unhandled Promise]', event.reason)
  event.preventDefault()
})

// 注册 Pinia 状态管理插件
app.use(pinia)
// 注册 Vue Router 路由插件
app.use(router)
// 挂载应用到 DOM 的 #app 元素，启动应用
app.mount('#app')
