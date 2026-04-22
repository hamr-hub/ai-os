<script setup lang="ts">
import { useModels } from '@/composables/useModels'
import { Server, RefreshCw, Pause, Play as PlayIcon, Star, StarOff, Loader2, Play, Square, Zap, CheckCircle } from 'lucide-vue-next'

const { modelStatus, defaultModel, loading, error, actionLoading, isRefreshing, isAutoRefreshEnabled, refresh, toggleAutoRefresh, handleStartModel, handleStopModel, handleSwitchAndSetDefault, handleSetDefaultModel, handleClearDefaultModel } = useModels()
</script>

<template>
  <div class="bg-card backdrop-blur-sm rounded-2xl p-6 border border-primary card-hover noise-overlay">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center gradient-purple shadow-lg">
          <Server class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-primary">模型管理</h2>
          <p class="text-secondary text-sm">管理和控制 AI 模型服务</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="refresh"
          :disabled="isRefreshing"
          class="flex items-center gap-1.5 px-3 py-1.5 bg-hover hover:opacity-80 disabled:opacity-50 text-secondary rounded-lg text-sm transition-all"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
          <span>{{ isRefreshing ? '刷新中' : '刷新' }}</span>
        </button>
        <button
          @click="toggleAutoRefresh"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all"
          :class="isAutoRefreshEnabled ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' : 'bg-hover text-muted'"
        >
          <Pause v-if="isAutoRefreshEnabled" class="w-4 h-4" />
          <PlayIcon v-else class="w-4 h-4" />
        </button>
        <div v-if="defaultModel" class="flex items-center gap-2 bg-yellow-500/20 text-yellow-400 px-3 py-1.5 rounded-lg text-sm">
          <Star class="w-4 h-4 fill-current" />
          <span>默认: {{ defaultModel }}</span>
          <button @click="handleClearDefaultModel" class="hover:text-yellow-300 transition-colors">
            <StarOff class="w-4 h-4" />
          </button>
        </div>
      </div>
    </div>

    <div v-if="loading" class="flex flex-col items-center justify-center py-12">
      <div class="w-12 h-12 border-4 border-purple-500 border-t-transparent rounded-full animate-spin mb-4"></div>
      <p class="text-secondary">正在加载模型...</p>
    </div>

    <div v-else-if="error" class="text-center py-8">
      <div class="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
        <Server class="w-8 h-8 text-red-400" />
      </div>
      <p class="text-red-400 font-medium">{{ error }}</p>
    </div>

    <div v-else-if="!modelStatus || Object.keys(modelStatus).length === 0" class="text-center py-8">
      <div class="w-16 h-16 bg-tertiary rounded-full flex items-center justify-center mx-auto mb-4">
        <Server class="w-8 h-8 text-muted" />
      </div>
      <p class="text-secondary">暂无可用模型</p>
    </div>

    <div v-else>
      <div class="space-y-3 stagger-fade-in">
        <div
          v-for="(status, modelName) in modelStatus"
          :key="modelName"
          class="bg-tertiary rounded-xl p-4 hover:bg-hover transition-all duration-200 border border-primary/30"
        >
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div
                class="w-3 h-3 rounded-full transition-all duration-300 shadow-md"
                :class="status.running ? 'bg-green-500 animate-pulse shadow-lg shadow-green-500/50' : 'bg-gray-500'"
              ></div>
              <span class="text-primary font-medium">{{ modelName }}</span>
              <span v-if="defaultModel === modelName" class="text-yellow-400 text-xs flex items-center gap-1 px-2 py-0.5 bg-yellow-500/20 rounded-full">
                <Star class="w-3 h-3 fill-current" />
                默认
              </span>
              <span v-if="status.preloaded" class="text-green-400 text-xs flex items-center gap-1 px-2 py-0.5 bg-green-500/20 rounded-full">
                <CheckCircle class="w-3 h-3" />
                预加载
              </span>
            </div>
            <span
              class="px-3 py-1.5 rounded-full text-xs font-medium transition-all"
              :class="status.running ? 'bg-green-500/20 text-green-400' : 'bg-secondary text-secondary'"
            >
              {{ status.running ? '运行中' : '已停止' }}
            </span>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-sm">
            <div class="bg-secondary rounded-lg p-3 border border-primary/20">
              <span class="text-muted text-xs">端口</span>
              <p class="text-primary font-medium">{{ status.port || '-' }}</p>
            </div>
            <div class="bg-secondary rounded-lg p-3 border border-primary/20">
              <span class="text-muted text-xs">服务</span>
              <p class="text-primary font-medium truncate">{{ status.service || '-' }}</p>
            </div>
            <div class="bg-secondary rounded-lg p-3 border border-primary/20">
              <span class="text-muted text-xs">活跃请求</span>
              <p class="text-primary font-medium">{{ status.active_requests }}</p>
            </div>
            <div class="bg-secondary rounded-lg p-3 border border-primary/20">
              <span class="text-muted text-xs">预加载</span>
              <p class="text-primary font-medium">{{ status.preloaded ? '是' : '否' }}</p>
            </div>
          </div>

          <div class="flex gap-2">
            <button
              v-if="!status.running"
              @click="handleStartModel(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 gradient-green hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200 btn-glow shadow-md"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Play v-else class="w-4 h-4" />
              <span>启动</span>
            </button>

            <button
              v-if="status.running"
              @click="handleStopModel(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-red-600 hover:bg-red-700 disabled:bg-red-600/50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200 shadow-md"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Square v-else class="w-4 h-4" />
              <span>停止</span>
            </button>

            <button
              @click="handleSwitchAndSetDefault(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 gradient-purple hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200 btn-glow shadow-md"
              title="切换模型并设为默认"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Zap v-else class="w-4 h-4" />
              <span>一键切换</span>
            </button>

            <button
              @click="handleSetDefaultModel(modelName as string)"
              :disabled="actionLoading === modelName || defaultModel === modelName"
              class="flex items-center justify-center gap-2 px-3 py-2.5 bg-yellow-600 hover:bg-yellow-700 disabled:bg-yellow-600/50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200 shadow-md"
              :title="defaultModel === modelName ? '已是默认模型' : '设为默认模型'"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Star v-else class="w-4 h-4" :class="defaultModel === modelName ? 'fill-current' : ''" />
            </button>
          </div>
        </div>
      </div>

      <div class="mt-6 pt-6 border-t border-primary">
        <div class="flex flex-wrap items-center justify-center gap-6 text-sm">
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-green-500 animate-pulse shadow-md"></div>
            <span class="text-secondary">运行中</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-gray-500"></div>
            <span class="text-secondary">已停止</span>
          </div>
          <div class="flex items-center gap-2">
            <CheckCircle class="w-4 h-4 text-green-400" />
            <span class="text-secondary">预加载</span>
          </div>
          <div class="flex items-center gap-2">
            <Star class="w-4 h-4 text-yellow-400 fill-current" />
            <span class="text-secondary">默认模型</span>
          </div>
          <div class="flex items-center gap-2">
            <Zap class="w-4 h-4 text-purple-400" />
            <span class="text-secondary">一键切换</span>
          </div>
        </div>
        <p class="text-center text-muted text-xs mt-3">
          点击「一键切换」后，AIClient 调用时可不指定模型名，自动使用默认模型
        </p>
      </div>
    </div>
  </div>
</template>
