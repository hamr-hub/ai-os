<script setup lang="ts">
import ChatWindow from '@/components/ChatWindow.vue'
</script>

<template>
  <div class="chat-view">
    <ChatWindow />
  </div>
</template>

<style scoped>
.chat-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: var(--bg-primary);
}
</style>
