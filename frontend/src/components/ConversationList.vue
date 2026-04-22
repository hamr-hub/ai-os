<script setup lang="ts">
import { ref, computed } from 'vue'
import { Plus, MessageSquare, Trash2, Edit2, Check, X, MoreVertical } from 'lucide-vue-next'
import { useChatStore } from '@/stores/chat'

const chatStore = useChatStore()

const editingId = ref<string | null>(null)
const editingTitle = ref('')
const showMenuFor = ref<string | null>(null)

const startEditing = (id: string, title: string) => {
  editingId.value = id
  editingTitle.value = title
  showMenuFor.value = null
}

const saveEdit = (id: string) => {
  if (editingTitle.value.trim()) {
    chatStore.updateConversationTitle(id, editingTitle.value.trim())
  }
  editingId.value = null
  editingTitle.value = ''
}

const cancelEdit = () => {
  editingId.value = null
  editingTitle.value = ''
}

const deleteConversation = (id: string) => {
  chatStore.deleteConversation(id)
  showMenuFor.value = null
}

const toggleMenu = (id: string) => {
  showMenuFor.value = showMenuFor.value === id ? null : id
}

const closeMenu = () => {
  showMenuFor.value = null
}

const formatTime = (date: Date) => {
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  const minutes = Math.floor(diff / 60000)
  const hours = Math.floor(diff / 3600000)
  const days = Math.floor(diff / 86400000)

  if (minutes < 1) return '刚刚'
  if (minutes < 60) return `${minutes}分钟前`
  if (hours < 24) return `${hours}小时前`
  if (days < 7) return `${days}天前`
  return date.toLocaleDateString('zh-CN')
}

const truncateText = (text: string, maxLength: number) => {
  if (text.length <= maxLength) return text
  return text.slice(0, maxLength) + '...'
}

defineExpose({ closeMenu })
</script>

<template>
  <div class="flex flex-col h-full">
    <div class="p-3 border-b border-primary">
      <button
        @click="chatStore.createConversation()"
        class="w-full flex items-center justify-center gap-2 px-3 py-2.5 gradient-primary hover:opacity-90 text-white rounded-xl transition-all btn-glow shadow-md"
      >
        <Plus class="w-4 h-4" />
        <span class="text-sm font-medium">新会话</span>
      </button>
    </div>

    <div class="flex-1 overflow-y-auto p-2 space-y-1 scrollbar-thin">
      <div
        v-for="conv in chatStore.conversations"
        :key="conv.id"
        @click="editingId !== conv.id && chatStore.selectConversation(conv.id)"
        class="group relative flex items-center gap-2 px-3 py-3 rounded-xl cursor-pointer transition-all duration-200 hover:scale-[1.02]"
        :class="[
          chatStore.activeConversation === conv.id
            ? 'gradient-primary text-white shadow-lg scale-[1.02]'
            : 'text-secondary hover:bg-hover'
        ]"
      >
        <MessageSquare class="w-4 h-4 flex-shrink-0" />

        <div v-if="editingId === conv.id" class="flex-1 flex items-center gap-1" @click.stop>
          <input
            v-model="editingTitle"
            @keydown.enter="saveEdit(conv.id)"
            @keydown.esc="cancelEdit"
            type="text"
            class="flex-1 px-2 py-1 text-sm bg-input text-primary rounded-lg border border-secondary/50 focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
            autofocus
          />
          <button
            @click="saveEdit(conv.id)"
            class="p-1.5 hover:bg-green-500/20 text-green-500 rounded-lg transition-colors"
          >
            <Check class="w-3.5 h-3.5" />
          </button>
          <button
            @click="cancelEdit"
            class="p-1.5 hover:bg-red-500/20 text-red-500 rounded-lg transition-colors"
          >
            <X class="w-3.5 h-3.5" />
          </button>
        </div>

        <div v-else class="flex-1 min-w-0">
          <p class="text-sm font-medium truncate">
            {{ conv.title || '新会话' }}
          </p>
          <p
            v-if="conv.messages.length > 0"
            class="text-xs truncate mt-0.5"
            :class="chatStore.activeConversation === conv.id ? 'text-white/70' : 'text-muted'"
          >
            {{ truncateText(conv.messages[conv.messages.length - 1].content, 25) }}
          </p>
          <p
            v-else
            class="text-xs truncate mt-0.5"
            :class="chatStore.activeConversation === conv.id ? 'text-white/50' : 'text-muted'"
          >
            {{ formatTime(conv.updatedAt) }}
          </p>
        </div>

        <div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity" v-if="editingId !== conv.id">
          <button
            @click.stop="startEditing(conv.id, conv.title)"
            class="p-1.5 hover:bg-white/10 rounded-lg transition-colors"
            :class="chatStore.activeConversation === conv.id ? 'text-white/70 hover:text-white' : 'text-muted hover:text-primary'"
          >
            <Edit2 class="w-3.5 h-3.5" />
          </button>
          <button
            @click.stop="deleteConversation(conv.id)"
            class="p-1.5 hover:bg-red-500/20 rounded-lg transition-colors"
            :class="chatStore.activeConversation === conv.id ? 'text-white/70 hover:text-red-300' : 'text-muted hover:text-red-500'"
          >
            <Trash2 class="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div v-if="chatStore.conversations.length === 0" class="text-center py-10 text-muted">
        <div class="w-12 h-12 mx-auto mb-3 rounded-xl bg-tertiary flex items-center justify-center">
          <MessageSquare class="w-6 h-6 opacity-50" />
        </div>
        <p class="text-sm">暂无会话</p>
        <p class="text-xs mt-1">点击上方按钮创建新会话</p>
      </div>
    </div>

    <div class="p-3 border-t border-primary">
      <p class="text-xs text-center text-muted">
        共 {{ chatStore.conversations.length }} 个会话
      </p>
    </div>
  </div>
</template>
