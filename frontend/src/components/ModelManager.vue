<script setup lang="ts">
import { useModels } from '@/composables/useModels'
import { Server, RefreshCw, Pause, Play as PlayIcon, Star, StarOff, Loader2, Play, Square, Zap, CheckCircle } from 'lucide-vue-next'

const { modelStatus, defaultModel, loading, error, actionLoading, isRefreshing, isAutoRefreshEnabled, refresh, toggleAutoRefresh, handleStartModel, handleStopModel, handleSwitchAndSetDefault, handleSetDefaultModel, handleClearDefaultModel } = useModels()
</script>

<template>
  <div class="bg-slate-800/80 backdrop-blur-sm rounded-2xl p-6 border border-slate-700/50 card-hover">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 rounded-xl flex items-center justify-center gradient-purple">
          <Server class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-white">模型管理</h2>
          <p class="text-slate-400 text-sm">管理和控制 AI 模型服务</p>
        </div>
      </div>
      <div class="flex items-center gap-2">
        <button
          @click="refresh"
          :disabled="isRefreshing"
          class="flex items-center gap-1.5 px-3 py-1.5 bg-slate-700/50 hover:bg-slate-700 disabled:bg-slate-700/50 disabled:opacity-50 text-slate-300 rounded-lg text-sm transition-all"
        >
          <RefreshCw class="w-4 h-4" :class="{ 'animate-spin': isRefreshing }" />
          <span>{{ isRefreshing ? '刷新中' : '刷新' }}</span>
        </button>
        <button
          @click="toggleAutoRefresh"
          class="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm transition-all"
          :class="isAutoRefreshEnabled ? 'bg-green-500/20 text-green-400 hover:bg-green-500/30' : 'bg-slate-700/50 text-slate-400 hover:bg-slate-700'"
          :title="isAutoRefreshEnabled ? '暂停自动刷新' : '开启自动刷新'"
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
      <p class="text-slate-400">正在加载模型...</p>
    </div>

    <div v-else-if="error" class="text-center py-8">
      <div class="w-16 h-16 bg-red-500/10 rounded-full flex items-center justify-center mx-auto mb-4">
        <Server class="w-8 h-8 text-red-400" />
      </div>
      <p class="text-red-400 font-medium">{{ error }}</p>
    </div>

    <div v-else-if="!modelStatus || Object.keys(modelStatus).length === 0" class="text-center py-8">
      <div class="w-16 h-16 bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
        <Server class="w-8 h-8 text-slate-500" />
      </div>
      <p class="text-slate-400">暂无可用模型</p>
    </div>

    <div v-else>
      <div class="space-y-3">
        <div
          v-for="(status, modelName) in modelStatus"
          :key="modelName"
          class="bg-slate-700/30 rounded-xl p-4 hover:bg-slate-700/50 transition-all duration-200 scale-in"
        >
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div
                class="w-3 h-3 rounded-full transition-all duration-300"
                :class="status.running ? 'bg-green-500 animate-pulse shadow-lg shadow-green-500/50' : 'bg-slate-500'"
              ></div>
              <span class="text-white font-medium">{{ modelName }}</span>
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
              :class="status.running ? 'bg-green-500/20 text-green-400' : 'bg-slate-600 text-slate-300'"
            >
              {{ status.running ? '运行中' : '已停止' }}
            </span>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4 text-sm">
            <div class="bg-slate-600/30 rounded-lg p-3">
              <span class="text-slate-500 text-xs">端口</span>
              <p class="text-slate-300 font-medium">{{ status.port || '-' }}</p>
            </div>
            <div class="bg-slate-600/30 rounded-lg p-3">
              <span class="text-slate-500 text-xs">服务</span>
              <p class="text-slate-300 font-medium">{{ status.service || '-' }}</p>
            </div>
            <div class="bg-slate-600/30 rounded-lg p-3">
              <span class="text-slate-500 text-xs">活跃请求</span>
              <p class="text-slate-300 font-medium">{{ status.active_requests }}</p>
            </div>
            <div class="bg-slate-600/30 rounded-lg p-3">
              <span class="text-slate-500 text-xs">预加载</span>
              <p class="text-slate-300 font-medium">{{ status.preloaded ? '是' : '否' }}</p>
            </div>
          </div>

          <div class="flex gap-2">
            <button
              v-if="!status.running"
              @click="handleStartModel(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 gradient-green hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200 btn-glow"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Play v-else class="w-4 h-4" />
              <span>启动</span>
            </button>

            <button
              v-if="status.running"
              @click="handleStopModel(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 bg-red-600 hover:bg-red-700 disabled:bg-red-600/50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Square v-else class="w-4 h-4" />
              <span>停止</span>
            </button>

            <button
              @click="handleSwitchAndSetDefault(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 gradient-purple hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200 btn-glow"
              title="切换模型并设为默认"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Zap v-else class="w-4 h-4" />
              <span>一键切换</span>
            </button>

            <button
              @click="handleSetDefaultModel(modelName as string)"
              :disabled="actionLoading === modelName || defaultModel === modelName"
              class="flex items-center justify-center gap-2 px-3 py-2.5 bg-yellow-600 hover:bg-yellow-700 disabled:bg-yellow-600/50 disabled:cursor-not-allowed text-white rounded-xl transition-all duration-200"
              :title="defaultModel === modelName ? '已是默认模型' : '设为默认模型'"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Star v-else class="w-4 h-4" :class="defaultModel === modelName ? 'fill-current' : ''" />
            </button>
          </div>
        </div>
      </div>

      <div class="mt-6 pt-6 border-t border-slate-700/50">
        <div class="flex flex-wrap items-center justify-center gap-6 text-sm">
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-green-500 animate-pulse"></div>
            <span class="text-slate-400">运行中</span>
          </div>
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-slate-500"></div>
            <span class="text-slate-400">已停止</span>
          </div>
          <div class="flex items-center gap-2">
            <CheckCircle class="w-4 h-4 text-green-400" />
            <span class="text-slate-400">预加载</span>
          </div>
          <div class="flex items-center gap-2">
            <Star class="w-4 h-4 text-yellow-400 fill-current" />
            <span class="text-slate-400">默认模型</span>
          </div>
          <div class="flex items-center gap-2">
            <Zap class="w-4 h-4 text-purple-400" />
            <span class="text-slate-400">一键切换</span>
          </div>
        </div>
        <p class="text-center text-slate-500 text-xs mt-3">
          点击「一键切换」后，AIClient 调用时可不指定模型名，自动使用默认模型
        </p>
      </div>
    </div>
  </div>
</template>
