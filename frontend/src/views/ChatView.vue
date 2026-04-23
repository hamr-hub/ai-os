<script setup lang="ts">
import { ref } from 'vue'
import ChatWindow from '@/components/ChatWindow.vue'
import { useChatStore } from '@/stores/chat'
import { useModels } from '@/composables/useModels'
import { PanelLeftClose, PanelLeft, Plus, MessageSquare, Trash2, X } from 'lucide-vue-next'

const chatStore = useChatStore()
const { defaultModel } = useModels()
const showSidebar = ref(true)

const handleNewChat = () => {
  chatStore.createConversation('新会话', defaultModel.value)
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
</script>

<template>
  <div class="chat-view">
    <transition name="slide">
      <div v-if="showSidebar" class="chat-sidebar">
        <div class="sidebar-header">
          <button @click="handleNewChat" class="new-chat-btn">
            <Plus class="w-4 h-4" />
            <span>新会话</span>
          </button>
          <button @click="showSidebar = false" class="close-btn" title="收起侧栏">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="sidebar-list scrollbar-thin">
          <div
            v-for="conv in chatStore.conversations"
            :key="conv.id"
            @click="chatStore.selectConversation(conv.id)"
            class="conv-item"
            :class="{ active: chatStore.activeConversation === conv.id }"
          >
            <MessageSquare class="w-4 h-4 flex-shrink-0" />
            <div class="conv-info">
              <p class="conv-title">{{ conv.title || '新会话' }}</p>
              <p class="conv-sub">
                {{ conv.messages.length > 0
                  ? conv.messages[conv.messages.length - 1].content.slice(0, 25)
                  : formatTime(conv.updatedAt) }}
              </p>
            </div>
            <button @click.stop="chatStore.deleteConversation(conv.id)" class="conv-delete" title="删除">
              <Trash2 class="w-3.5 h-3.5" />
            </button>
          </div>

          <div v-if="chatStore.conversations.length === 0" class="sidebar-empty">
            <MessageSquare class="w-6 h-6 opacity-40" />
            <p>暂无会话</p>
          </div>
        </div>

        <div class="sidebar-footer">
          <span>共 {{ chatStore.conversations.length }} 个会话</span>
        </div>
      </div>
    </transition>

    <div class="chat-main">
      <button
        v-if="!showSidebar"
        class="sidebar-toggle"
        @click="showSidebar = true"
        title="展开会话列表"
      >
        <PanelLeft class="w-5 h-5" />
      </button>
      <ChatWindow />
    </div>
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  display: flex;
  background: var(--bg-primary);
}

.chat-sidebar {
  width: 280px;
  flex-shrink: 0;
  background: var(--bg-card);
  border-right: 1px solid var(--border-primary);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.sidebar-header {
  padding: 12px;
  border-bottom: 1px solid var(--border-primary);
  display: flex;
  align-items: center;
  gap: 8px;
}

.new-chat-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 8px 12px;
  border-radius: 10px;
  border: none;
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: 0 2px 8px rgba(99, 102, 241, 0.2);
}
.new-chat-btn:hover { opacity: 0.9; transform: translateY(-1px); box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3); }

.close-btn {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  border: 1px solid var(--border-primary);
  background: transparent;
  color: var(--text-muted);
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}
.close-btn:hover { color: var(--text-primary); background: var(--bg-secondary); }

.sidebar-list {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.conv-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-radius: 10px;
  cursor: pointer;
  transition: all 0.2s;
  color: var(--text-secondary);
  border: 1px solid transparent;
}
.conv-item:hover { background: var(--bg-secondary); border-color: var(--border-primary); }
.conv-item.active {
  background: linear-gradient(135deg, #6366f1, #4f46e5);
  color: #fff;
  box-shadow: 0 2px 10px rgba(99, 102, 241, 0.25);
}

.conv-info { flex: 1; min-width: 0; }
.conv-title { font-size: 13px; font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.conv-sub { font-size: 11px; margin-top: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; opacity: 0.7; }
.conv-item.active .conv-sub { color: rgba(255,255,255,0.7); }

.conv-delete {
  padding: 4px;
  border-radius: 6px;
  border: none;
  background: transparent;
  color: inherit;
  opacity: 0;
  cursor: pointer;
  transition: all 0.2s;
}
.conv-item:hover .conv-delete { opacity: 0.5; }
.conv-delete:hover { opacity: 1; background: rgba(239,68,68,0.15); color: #ef4444; }
.conv-item.active .conv-delete:hover { color: #fca5a5; background: rgba(255,255,255,0.15); }

.sidebar-empty {
  padding: 32px 16px;
  text-align: center;
  color: var(--text-muted);
  font-size: 13px;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
}

.sidebar-footer {
  padding: 10px 12px;
  border-top: 1px solid var(--border-primary);
  font-size: 11px;
  color: var(--text-muted);
  text-align: center;
}

.chat-main {
  flex: 1;
  min-width: 0;
  position: relative;
  display: flex;
  flex-direction: column;
}

.sidebar-toggle {
  position: absolute;
  top: 12px;
  left: 12px;
  z-index: 10;
  width: 36px;
  height: 36px;
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-card);
  border: 1px solid var(--border-primary);
  color: var(--text-muted);
  cursor: pointer;
  transition: all 0.2s;
  box-shadow: var(--shadow-sm);
}
.sidebar-toggle:hover {
  color: var(--text-primary);
  background: var(--bg-secondary);
}

.slide-enter-active,
.slide-leave-active {
  transition: width 0.25s ease, opacity 0.2s ease;
}
.slide-enter-from,
.slide-leave-to {
  width: 0;
  opacity: 0;
}
</style>
