<template>
  <div class="login-page">
    <!-- Particle background canvas -->
    <canvas id="login-particles"></canvas>

    <div class="login-card">
      <div class="login-header">
        <svg class="login-icon" viewBox="0 0 48 48" fill="none">
          <rect x="4" y="4" width="40" height="40" rx="10" stroke="#00BCD4" stroke-width="2"/>
          <path d="M16 24l6 6 10-10" stroke="#00BCD4" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
          <circle cx="36" cy="12" r="3" fill="#00BCD4" opacity="0.5"/>
        </svg>
        <h1>麒麟OS 安全智能运维</h1>
        <p>Kylin SecOps Intelligent Agent</p>
      </div>

      <form class="login-form" @submit.prevent="handleLogin">
        <div class="field-group">
          <label for="username">用户名</label>
          <div class="input-wrap" :class="{ focused: focusUser, 'has-error': error }">
            <svg class="input-icon" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <circle cx="9" cy="6" r="3"/><path d="M3 16c0-3.3 2.7-6 6-6s6 2.7 6 6"/>
            </svg>
            <input
              id="username"
              v-model="username"
              type="text"
              placeholder="admin"
              @focus="focusUser = true"
              @blur="focusUser = false"
              :disabled="loading"
              autocomplete="username"
            />
          </div>
        </div>

        <div class="field-group">
          <label for="password">密码</label>
          <div class="input-wrap" :class="{ focused: focusPass, 'has-error': error }">
            <svg class="input-icon" viewBox="0 0 18 18" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
              <rect x="3" y="8" width="12" height="8" rx="1.5"/><path d="M6 8V5a3 3 0 0 1 6 0v3"/>
            </svg>
            <input
              id="password"
              v-model="password"
              type="password"
              placeholder="请输入密码"
              @focus="focusPass = true"
              @blur="focusPass = false"
              :disabled="loading"
              autocomplete="current-password"
            />
          </div>
        </div>

        <div v-if="error" class="error-msg">
          <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <circle cx="8" cy="8" r="6.5"/><path d="M8 5v3.5M8 11v.5"/>
          </svg>
          {{ error }}
        </div>

        <button type="submit" class="login-btn" :disabled="loading || !username || !password">
          <span v-if="loading" class="spinner"></span>
          <span v-else>登 录</span>
        </button>

        <div class="login-footer">
          <span>默认账号：admin / admin123</span>
        </div>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { initParticleBg } from '@/services/particles'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')
const focusUser = ref(false)
const focusPass = ref(false)

let cleanupParticles: (() => void) | null = null

onMounted(() => {
  // If already authenticated, go straight to dashboard
  if (authStore.isAuthenticated) {
    router.replace('/dashboard')
    return
  }
  cleanupParticles = initParticleBg()
})

onUnmounted(() => {
  if (cleanupParticles) cleanupParticles()
})

async function handleLogin() {
  if (!username.value || !password.value) return
  loading.value = true
  error.value = ''

  try {
    const success = await authStore.login(username.value, password.value)
    if (success) {
      router.replace('/dashboard')
    } else {
      error.value = '用户名或密码错误'
    }
  } catch (e: any) {
    error.value = e?.message || '登录失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-page {
  height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-canvas);
  position: relative;
  overflow: hidden;
}

#login-particles {
  position: fixed;
  inset: 0;
  z-index: 0;
  pointer-events: none;
  opacity: 0.4;
}

.login-card {
  position: relative;
  z-index: 1;
  width: 400px;
  max-width: 90vw;
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 16px;
  padding: var(--space-10) var(--space-8);
  animation: fadeInUp 0.6s ease;
  box-shadow: var(--shadow-xl);
}

.login-header {
  text-align: center;
  margin-bottom: var(--space-8);
}

.login-icon {
  width: 48px;
  height: 48px;
  margin-bottom: var(--space-4);
}

.login-header h1 {
  font-size: var(--text-h2);
  font-weight: var(--font-weight-bold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-1);
}

.login-header p {
  font-size: var(--text-body-sm);
  color: var(--color-text-tertiary);
  letter-spacing: 1px;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.field-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.field-group label {
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  font-weight: var(--font-weight-medium);
  letter-spacing: 0.3px;
}

.input-wrap {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 0 var(--space-3);
  height: 44px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-default);
  border-radius: 10px;
  transition: all 0.2s ease;
}

.input-wrap.focused {
  border-color: var(--color-accent-500);
  box-shadow: var(--glow-accent);
}

.input-wrap.has-error {
  border-color: var(--color-critical);
  box-shadow: 0 0 20px rgba(255, 59, 92, 0.12);
}

.input-icon {
  width: 18px;
  height: 18px;
  color: var(--color-text-tertiary);
  flex-shrink: 0;
}

.input-wrap.focused .input-icon {
  color: var(--color-accent-500);
}

.input-wrap input {
  flex: 1;
  background: transparent;
  border: none;
  outline: none;
  color: var(--color-text-primary);
  font-size: var(--text-body);
  font-family: inherit;
  height: 100%;
}

.input-wrap input::placeholder {
  color: var(--color-text-disabled);
}

.error-msg {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--text-body-sm);
  color: var(--color-critical);
  padding: var(--space-2) var(--space-3);
  background: rgba(255, 59, 92, 0.08);
  border-radius: 8px;
}

.error-msg svg {
  width: 16px;
  height: 16px;
  flex-shrink: 0;
}

.login-btn {
  height: 46px;
  border-radius: 10px;
  border: none;
  background: var(--color-accent-500);
  color: #fff;
  font-size: var(--text-body);
  font-weight: var(--font-weight-semibold);
  font-family: inherit;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  letter-spacing: 4px;
}

.login-btn:hover:not(:disabled) {
  background: var(--color-accent-600);
  box-shadow: var(--glow-accent-strong);
  transform: translateY(-1px);
}

.login-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: var(--shadow-btn-press);
}

.login-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.login-footer {
  text-align: center;
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  padding-top: var(--space-2);
}
</style>
