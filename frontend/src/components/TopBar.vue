<template>
  <header class="topbar">
    <div class="topbar-breadcrumb">
      <span>麒麟OS</span>
      <svg class="sep" width="12" height="12" viewBox="0 0 12 12" fill="none" stroke="currentColor" stroke-width="1.2">
        <path d="M4.5 2.5L8 6L4.5 9.5"/>
      </svg>
      <span class="current">{{ currentPage }}</span>
    </div>
    <div class="topbar-spacer"></div>
    <div class="topbar-actions">
      <div class="topbar-search">
        <svg class="search-icon" viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
          <circle cx="7" cy="7" r="4.5"/>
          <path d="M10.5 10.5L14 14"/>
        </svg>
        <input
          type="text"
          v-model="searchQuery"
          :placeholder="searchPlaceholder"
          @keyup.enter="handleSearch"
        />
      </div>
      <button class="topbar-icon-btn" @click="toggleTheme" title="切换主题">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 2.5v1M14.5 4.5l-0.7 0.7M16 9h-1M4 9H3M4.2 5.2l-0.7-0.7"/>
          <path d="M13.5 9a4.5 4.5 0 0 1-9 0"/>
          <path d="M9 13.5v2"/>
        </svg>
      </button>
      <button class="topbar-icon-btn" @click="showNotifications = !showNotifications" title="通知">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M14 7a5 5 0 0 0-10 0c0 3-1.5 4.5-2 5h14c-0.5-0.5-2-2-2-5"/>
          <path d="M10.5 14a1.5 1.5 0 0 1-3 0"/>
        </svg>
        <span v-if="notificationCount > 0" class="badge-dot"></span>
      </button>
      <div class="topbar-user-avatar" @click="router.push('/profile')" style="cursor:pointer;">{{ userInitial }}</div>
    </div>
  </header>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const searchQuery = ref('')
const showNotifications = ref(false)
const notificationCount = ref(0)

const currentPage = computed(() => (route.meta.title as string) || '未知页面')

const searchPlaceholder = computed(() => {
  const page = currentPage.value
  if (page.includes('告警')) return '搜索告警名称、来源IP...'
  if (page.includes('Agent')) return '搜索 Agent 名称、IP...'
  if (page.includes('策略')) return '搜索策略名称...'
  if (page.includes('系统')) return '搜索用户、资源...'
  return '搜索告警、Agent...'
})

const userInitial = computed(() => {
  return authStore.user?.display_name?.charAt(0) || '用'
})

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push(`/alerts?search=${encodeURIComponent(searchQuery.value.trim())}`)
  }
}

function toggleTheme() {
  document.documentElement.classList.toggle('light-theme')
}
</script>

<style scoped>
.topbar {
  height: var(--layout-topbar-height);
  min-height: var(--layout-topbar-height);
  background: var(--color-bg-surface);
  border-bottom: 1px solid var(--color-border-default);
  display: flex;
  align-items: center;
  padding: 0 var(--space-6);
  gap: var(--space-4);
}

.topbar-breadcrumb {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-body-sm);
  color: var(--color-text-tertiary);
}

.topbar-breadcrumb .sep {
  color: var(--color-text-disabled);
}

.topbar-breadcrumb .current {
  color: var(--color-text-secondary);
}

.topbar-spacer {
  flex: 1;
}

.topbar-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.topbar-search {
  position: relative;
}

.topbar-search input {
  width: 200px;
  height: 34px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: 0 var(--space-3) 0 34px;
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
  transition: all 0.2s ease;
}

.topbar-search input::placeholder {
  color: var(--color-text-tertiary);
}

.topbar-search input:focus {
  border-color: var(--color-accent-500);
  box-shadow: var(--glow-accent);
}

.topbar-search .search-icon {
  position: absolute;
  left: 10px;
  top: 50%;
  transform: translateY(-50%);
  width: 16px;
  height: 16px;
  color: var(--color-text-tertiary);
  pointer-events: none;
}

.topbar-icon-btn {
  position: relative;
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 8px;
  background: transparent;
  border: none;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.2s ease;
}

.topbar-icon-btn:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.topbar-icon-btn .badge-dot {
  position: absolute;
  top: 6px;
  right: 6px;
  width: 7px;
  height: 7px;
  background: var(--color-critical);
  border-radius: 50%;
  border: 2px solid var(--color-bg-surface);
}

.topbar-icon-btn svg {
  width: 18px;
  height: 18px;
}

.topbar-user-avatar {
  width: 30px;
  height: 30px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-accent-500), var(--color-accent-purple));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-caption);
  font-weight: var(--font-weight-bold);
  color: #fff;
  cursor: pointer;
}
</style>