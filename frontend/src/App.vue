<template>
  <div class="app-shell">
    <router-view />
    <ForceChangePasswordModal v-if="needsPasswordChange" />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onErrorCaptured } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAlertsStore } from '@/stores/alerts'
import { showToast } from '@/utils/toast'
import { needsPasswordChange } from '@/stores/forceChange'
import ForceChangePasswordModal from '@/components/ForceChangePasswordModal.vue'

const authStore = useAuthStore()
const alertsStore = useAlertsStore()

onMounted(async () => {
  // 监听桌面端后端启动超时降级通知
  if (window.electronAPI && typeof window.electronAPI.onBackendTimeout === 'function') {
    window.electronAPI.onBackendTimeout(() => {
      showToast('后端服务启动超时，部分功能可能暂不可用，请稍后重试或重启应用', 'warning')
    })
  }
  try {
    await authStore.fetchCurrentUser()
  } catch (e) {
    console.warn('Failed to fetch current user, starting poll anyway:', e)
  }
  alertsStore.startPolling()
})

onErrorCaptured((err: Error, instance: any, info: string) => {
  console.error('[Global Error Boundary]', err, info)
  showToast(`页面异常: ${err.message}`, 'error')
  return false
})
</script>

<style scoped>
.app-shell {
  height: 100%;
  width: 100%;
}
</style>
