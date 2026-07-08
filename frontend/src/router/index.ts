import { createRouter, createWebHashHistory, type RouteRecordRaw } from 'vue-router'
import MainLayout from '@/layouts/MainLayout.vue'
import { useAuthStore } from '@/stores/auth'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginView.vue'),
    meta: { title: '登录', guest: true },
  },
  {
    path: '/403',
    name: 'Forbidden',
    component: () => import('@/views/ForbiddenView.vue'),
    meta: { title: '无权限' },
  },
  {
    path: '/',
    component: MainLayout,
    meta: { requiresAuth: true },
    children: [
      {
        path: '',
        redirect: '/dashboard',
      },
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/DashboardView.vue'),
        meta: { title: '安全仪表盘' },
      },
      {
        path: 'alerts',
        name: 'Alerts',
        component: () => import('@/views/AlertsView.vue'),
        meta: { title: '告警管理' },
      },
      {
        path: 'agents',
        name: 'Agents',
        component: () => import('@/views/AgentsView.vue'),
        meta: { title: 'Agent 管理' },
      },
      {
        path: 'policies',
        name: 'Policies',
        component: () => import('@/views/PoliciesView.vue'),
        meta: { title: '策略配置' },
      },
      {
        path: 'system',
        name: 'System',
        component: () => import('@/views/SystemView.vue'),
        meta: { title: '系统管理' },
      },
      {
        path: 'profile',
        name: 'Profile',
        component: () => import('@/views/ProfileView.vue'),
        meta: { title: '个人设置' },
      },
      {
        path: 'ai',
        name: 'AI',
        component: () => import('@/views/AIView.vue'),
        meta: { title: 'AI 智能助手' },
      },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFoundView.vue'),
    meta: { title: '404' },
  },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

// Navigation guard — redirect to login if not authenticated
router.beforeEach(async (to, _from, next) => {
  // Try loading the current user silently if we haven't yet
  const authStore = useAuthStore()

  // If we don't have a user yet, try loading from stored token
  if (!authStore.isAuthenticated && !to.meta.guest) {
    try {
      await authStore.fetchCurrentUser()
    } catch {
      authStore.logout()
      return next('/login')
    }
  }

  // 如果token存在但获取用户信息失败（401场景）
  if (to.meta.requiresAuth !== false && !authStore.isAuthenticated) {
    try {
      await authStore.fetchCurrentUser()
    } catch {
      authStore.logout()
      return next({ path: '/login', query: { redirect: to.fullPath } })
    }
  }

  if (to.meta.requiresAuth && !authStore.isAuthenticated) {
    next('/login')
  } else if (to.path === '/login' && authStore.isAuthenticated) {
    next('/dashboard')
  } else {
    next()
  }
})

export default router
