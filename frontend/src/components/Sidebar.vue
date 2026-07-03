<template>
  <aside class="sidebar">
    <div class="sidebar-logo">
      <svg class="sidebar-logo-icon" viewBox="0 0 28 28" fill="none">
        <rect x="2" y="2" width="24" height="24" rx="6" stroke="#00BCD4" stroke-width="1.5"/>
        <path d="M8 14L12 18L20 10" stroke="#00BCD4" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        <circle cx="20" cy="8" r="2" fill="#00BCD4" opacity="0.6"/>
      </svg>
      <span class="sidebar-logo-text">
        麒麟OS<br><span class="logo-accent">安全智能运维</span>
      </span>
    </div>

    <nav class="sidebar-nav">
      <router-link
        v-for="item in navItems"
        :key="item.path"
        :to="item.path"
        class="nav-item"
        :class="{ active: isActive(item.path) }"
      >
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" v-html="item.icon" />
        <span class="nav-label">{{ item.label }}</span>
        <span v-if="item.badge" class="nav-badge">{{ item.badge }}</span>
      </router-link>
    </nav>

    <div class="sidebar-footer">
      <div class="sidebar-avatar">{{ userInitial }}</div>
      <div class="sidebar-user-info">
        <div class="sidebar-user-name">{{ userName }}</div>
        <div class="sidebar-user-role">{{ userRole }}</div>
      </div>
      <button class="topbar-icon-btn" @click="handleLogout" title="退出登录">
        <svg viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
          <path d="M7 3H4a1 1 0 0 0-1 1v10a1 1 0 0 0 1 1h3"/>
          <path d="M12 12l3-3-3-3"/>
          <path d="M9 9h6"/>
        </svg>
      </button>
    </div>
  </aside>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const navItems = [
  {
    path: '/dashboard',
    label: '仪表盘',
    badge: 0,
    icon: '<rect x="1" y="1" width="6" height="7" rx="1"/><rect x="11" y="1" width="6" height="4" rx="1"/><rect x="1" y="12" width="6" height="5" rx="1"/><rect x="11" y="9" width="6" height="8" rx="1"/>',
  },
  {
    path: '/alerts',
    label: '告警管理',
    badge: 42,
    icon: '<path d="M9 1v16M1 9h16"/><circle cx="9" cy="9" r="6"/><circle cx="9" cy="9" r="2" fill="currentColor" fill-opacity="0.4"/>',
  },
  {
    path: '/agents',
    label: 'Agent 管理',
    badge: 0,
    icon: '<rect x="2" y="1" width="4" height="6" rx="1"/><rect x="12" y="1" width="4" height="4" rx="1"/><rect x="2" y="11" width="4" height="6" rx="1"/><rect x="12" y="9" width="4" height="8" rx="1"/><path d="M4 8v3M14 6v3" stroke="currentColor" stroke-width="1.2"/>',
  },
  {
    path: '/policies',
    label: '策略配置',
    badge: 0,
    icon: '<circle cx="9" cy="9" r="7.5"/><circle cx="9" cy="9" r="4.5"/><circle cx="9" cy="9" r="1.5" fill="currentColor" fill-opacity="0.4"/><path d="M9 1.5v3M9 13.5v3M1.5 9h3M13.5 9h3"/>',
  },
  {
    path: '/system',
    label: '系统管理',
    badge: 0,
    icon: '<rect x="2" y="2" width="14" height="14" rx="2"/><path d="M5 6h8M5 9h8M5 12h5"/>',
  },
  {
    path: '/ai',
    label: 'AI 助手',
    badge: 0,
    icon: '<circle cx="9" cy="9" r="6"/><circle cx="9" cy="9" r="2" fill="currentColor" fill-opacity="0.4"/><path d="M9 1.5v3M1.5 9h3M14.5 9h3M9 13.5v3"/>',
  },
]

const isActive = (path: string) => route.path === path || route.path.startsWith(path + '/')

const userName = computed(() => authStore.user?.display_name || '用户')
const userRole = computed(() => {
  const roles = authStore.user?.roles
  return roles?.length ? roles[0].display_name : '安全运维工程师'
})
const userInitial = computed(() => userName.value.charAt(0))

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.sidebar {
  width: var(--layout-sidebar-width);
  min-width: var(--layout-sidebar-width);
  background: var(--color-bg-surface);
  border-right: 1px solid var(--color-border-default);
  display: flex;
  flex-direction: column;
  z-index: var(--z-sticky);
  overflow: hidden;
}

.sidebar-logo {
  height: var(--layout-topbar-height);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-5);
  border-bottom: 1px solid var(--color-border-subtle);
  flex-shrink: 0;
}

.sidebar-logo-icon {
  width: 28px;
  height: 28px;
  flex-shrink: 0;
}

.sidebar-logo-text {
  font-size: var(--text-h4);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  letter-spacing: 0.3px;
  white-space: nowrap;
}

.sidebar-logo-text .logo-accent {
  color: var(--color-accent-500);
}

.sidebar-nav {
  flex: 1;
  padding: var(--space-3) var(--space-2);
  display: flex;
  flex-direction: column;
  gap: 2px;
  overflow-y: auto;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-2) var(--space-3);
  border-radius: 8px;
  cursor: pointer;
  color: var(--color-text-secondary);
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  transition: all 0.2s ease;
  border: none;
  background: transparent;
  text-decoration: none;
  width: 100%;
  text-align: left;
  font-family: inherit;
}

.nav-item:hover {
  background: var(--color-bg-hover);
  color: var(--color-text-primary);
}

.nav-item:hover svg {
  color: var(--color-accent-500);
}

.nav-item.active {
  background: rgba(0, 188, 212, 0.12);
  color: var(--color-accent-500);
  box-shadow: inset 3px 0 0 var(--color-accent-500);
}

.nav-item.active svg {
  color: var(--color-accent-500);
}

.nav-item svg {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
  transition: color 0.2s ease;
}

.nav-label {
  flex: 1;
}

.nav-badge {
  background: var(--color-critical);
  color: #fff;
  font-size: var(--text-label);
  font-weight: var(--font-weight-bold);
  padding: 1px 6px;
  border-radius: 10px;
  min-width: 18px;
  text-align: center;
  line-height: 1.4;
}

.sidebar-footer {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--color-border-subtle);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-shrink: 0;
}

.sidebar-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background: var(--color-accent-purple);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-semibold);
  color: #fff;
  flex-shrink: 0;
}

.sidebar-user-info {
  flex: 1;
  min-width: 0;
}

.sidebar-user-name {
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.sidebar-user-role {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
}
</style>