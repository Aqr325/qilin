<template>
  <div class="error-view">
    <div class="error-content">
      <div class="error-code">403</div>
      <h2 class="error-title">权限不足</h2>
      <p class="error-desc">您没有访问此页面的权限，请联系管理员</p>
      <div class="error-actions">
        <router-link to="/dashboard" class="btn-primary">返回仪表盘</router-link>
        <router-link to="/profile" class="action-btn">联系管理员</router-link>
      </div>
    </div>
  </div>
</template>

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
  color: var(--color-critical);
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