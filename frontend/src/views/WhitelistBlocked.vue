<script setup lang="ts">
import { ShieldAlert, ArrowLeft } from 'lucide-vue-next'
import { useRouter } from 'vue-router'

const router = useRouter()

const goBack = () => {
  router.push({ name: 'dashboard' })
}
</script>

<template>
  <div class="whitelist-blocked-page">
    <div class="blocked-container card-base">
      <ShieldAlert class="w-12 h-12 text-warning" />
      <h1 class="digital-font">访问受限</h1>
      <p class="blocked-desc">
        当前 IP 不在管理白名单中，写操作（启动/停止/切换模型等）已被限制。
        仅允许读取操作（查看状态、监控等）。
      </p>
      <p class="blocked-tip">请联系管理员将您的 IP 加入白名单，或从内网环境访问。</p>
      <button class="btn btn-secondary" @click="goBack">
        <ArrowLeft class="w-4 h-4" /> 返回首页
      </button>
    </div>
  </div>
</template>

<style scoped>
.whitelist-blocked-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-primary);
}

.blocked-container {
  width: 480px;
  max-width: 90vw;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.blocked-container h1 {
  font-size: 20px;
  color: var(--text-primary);
}

.blocked-desc {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.blocked-tip {
  font-size: 12px;
  color: var(--text-muted);
}

.text-warning {
  color: #f59e0b;
}

.card-base {
  background: var(--bg-card);
  border-radius: 12px;
  padding: 32px;
  border: 1px solid rgba(255, 255, 255, 0.05);
}

.btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 16px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 14px;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.btn-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border-color: rgba(255, 255, 255, 0.1);
}
</style>
