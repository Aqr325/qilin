<template>
  <div class="app-shell">
    <router-view />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useAlertsStore } from '@/stores/alerts'

const authStore = useAuthStore()
const alertsStore = useAlertsStore()

onMounted(async () => {
  try {
    await authStore.fetchCurrentUser()
  } catch (e) {
    console.warn('Failed to fetch current user, starting poll anyway:', e)
  }
  alertsStore.startPolling()
})
</script>

<style scoped>
.app-shell {
  height: 100%;
  width: 100%;
}
</style>
