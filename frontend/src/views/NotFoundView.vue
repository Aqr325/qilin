<template>
  <div class="error-view">
    <div class="error-content">
      <div class="error-code">404</div>
      <h2 class="error-title">页面未找到</h2>
      <p class="error-desc">您访问的页面不存在，请检查链接是否正确</p>
      <div class="error-actions">
        <router-link to="/dashboard" class="btn-primary">返回仪表盘</router-link>
        <button class="action-btn" @click="router.back()">返回上一页</button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<style scoped>
.error-view {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
}
.error-content {
  text-align: center;
}
.error-code {
  font-size: 96px;
  font-weight: var(--font-weight-bold);
  color: var(--color-accent-500);
  opacity: 0.6;
  line-height: 1;
  font-family: var(--font-family-mono);
  margin-bottom: var(--space-4);
}
.error-title {
  font-size: var(--text-h2);
  color: var(--color-text-primary);
  margin-bottom: var(--space-3);
}
.error-desc {
  color: var(--color-text-tertiary);
  margin-bottom: var(--space-6);
}
.error-actions {
  display: flex;
  gap: var(--space-3);
  justify-content: center;
}
</style>