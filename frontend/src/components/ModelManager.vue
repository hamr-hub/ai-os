<script setup lang="ts">
import { useModels } from '@/composables/useModels'
import { Server, Play, Square, CheckCircle, Loader2, Star, StarOff, Zap } from 'lucide-vue-next'

const { modelStatus, defaultModel, loading, error, actionLoading, handleStartModel, handleStopModel, handleSwitchAndSetDefault, handleSetDefaultModel, handleClearDefaultModel } = useModels()
</script>

<template>
  <div class="bg-slate-800 rounded-xl p-6">
    <div class="flex items-center justify-between mb-6">
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 bg-purple-600 rounded-lg flex items-center justify-center">
          <Server class="w-6 h-6 text-white" />
        </div>
        <div>
          <h2 class="text-xl font-semibold text-white">模型管理</h2>
          <p class="text-slate-400 text-sm">管理和控制 AI 模型服务</p>
        </div>
      </div>
      <div v-if="defaultModel" class="flex items-center gap-2 bg-yellow-500/20 text-yellow-400 px-3 py-1 rounded-full text-sm">
        <Star class="w-4 h-4 fill-current" />
        <span>默认: {{ defaultModel }}</span>
        <button @click="handleClearDefaultModel" class="hover:text-yellow-300 transition-colors">
          <StarOff class="w-4 h-4" />
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex items-center justify-center py-12">
      <div class="w-8 h-8 border-4 border-purple-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <div v-else-if="error" class="text-red-400 text-center py-8">
      <p class="font-medium">{{ error }}</p>
    </div>

    <div v-else-if="!modelStatus || Object.keys(modelStatus).length === 0" class="text-center py-8">
      <div class="w-16 h-16 bg-slate-700 rounded-full flex items-center justify-center mx-auto mb-4">
        <Server class="w-8 h-8 text-slate-500" />
      </div>
      <p class="text-slate-400">暂无可用模型</p>
    </div>

    <div v-else>
      <div class="space-y-4">
        <div
          v-for="(status, modelName) in modelStatus"
          :key="modelName"
          class="bg-slate-700/50 rounded-lg p-4 hover:bg-slate-700 transition-colors"
        >
          <div class="flex items-center justify-between mb-3">
            <div class="flex items-center gap-3">
              <div
                class="w-3 h-3 rounded-full"
                :class="status.running ? 'bg-green-500 animate-pulse' : 'bg-slate-500'"
              ></div>
              <span class="text-white font-medium">{{ modelName }}</span>
              <span v-if="defaultModel === modelName" class="text-yellow-400 text-xs flex items-center gap-1">
                <Star class="w-3 h-3 fill-current" />
                默认
              </span>
            </div>
            <span
              class="px-3 py-1 rounded-full text-xs font-medium"
              :class="status.running ? 'bg-green-500/20 text-green-400' : 'bg-slate-600 text-slate-300'"
            >
              {{ status.running ? '运行中' : '已停止' }}
            </span>
          </div>

          <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4 text-sm">
            <div>
              <span class="text-slate-500">端口</span>
              <p class="text-slate-300">{{ status.port || '-' }}</p>
            </div>
            <div>
              <span class="text-slate-500">服务</span>
              <p class="text-slate-300">{{ status.service || '-' }}</p>
            </div>
            <div>
              <span class="text-slate-500">活跃请求</span>
              <p class="text-slate-300">{{ status.active_requests }}</p>
            </div>
            <div>
              <span class="text-slate-500">预加载</span>
              <p class="text-slate-300">{{ status.preloaded ? '是' : '否' }}</p>
            </div>
          </div>

          <div class="flex gap-2">
            <button
              v-if="!status.running"
              @click="handleStartModel(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-green-600 hover:bg-green-700 disabled:bg-green-600/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Play v-else class="w-4 h-4" />
              <span>启动</span>
            </button>

            <button
              v-if="status.running"
              @click="handleStopModel(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-600/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Square v-else class="w-4 h-4" />
              <span>停止</span>
            </button>

            <button
              @click="handleSwitchAndSetDefault(modelName as string)"
              :disabled="actionLoading === modelName"
              class="flex-1 flex items-center justify-center gap-2 px-4 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-purple-600/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              title="切换模型并设为默认"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Zap v-else class="w-4 h-4" />
              <span>一键切换</span>
            </button>

            <button
              @click="handleSetDefaultModel(modelName as string)"
              :disabled="actionLoading === modelName || defaultModel === modelName"
              class="flex items-center justify-center gap-2 px-3 py-2 bg-yellow-600 hover:bg-yellow-700 disabled:bg-yellow-600/50 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
              :title="defaultModel === modelName ? '已是默认模型' : '设为默认模型'"
            >
              <Loader2 v-if="actionLoading === modelName" class="w-4 h-4 animate-spin" />
              <Star v-else class="w-4 h-4" :class="defaultModel === modelName ? 'fill-current' : ''" />
            </button>
          </div>
        </div>
      </div>

      <div class="mt-6 pt-6 border-t border-slate-700">
        <div class="flex flex-wrap items-center justify-center gap-6 text-sm">
          <div class="flex items-center gap-2">
            <div class="w-3 h-3 rounded-full bg-green-500"></div>
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
