<template>
  <div class="force-modal-mask">
    <div class="force-modal">
      <div class="force-header">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
          <rect x="4" y="10" width="16" height="10" rx="2" />
          <path d="M8 10V7a4 4 0 0 1 8 0v3" />
        </svg>
        <h2>首次登录必须修改密码</h2>
      </div>
      <p class="force-tip">为保障账户安全，使用初始密码登录后必须立即修改密码，完成后方可使用系统。</p>

      <form class="force-form" @submit.prevent="submit">
        <label>当前密码
          <input v-model="oldPassword" type="password" autocomplete="current-password" :disabled="loading" placeholder="请输入当前密码" />
        </label>
        <label>新密码
          <input v-model="newPassword" type="password" autocomplete="new-password" :disabled="loading" placeholder="至少 12 位" />
        </label>
        <label>确认新密码
          <input v-model="confirmPassword" type="password" autocomplete="new-password" :disabled="loading" placeholder="再次输入新密码" />
        </label>

        <p v-if="errorMsg" class="force-error">{{ errorMsg }}</p>

        <button type="submit" class="force-btn" :disabled="loading">
          <span v-if="loading" class="spinner"></span>
          <span v-else>确认修改并进入系统</span>
        </button>
      </form>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import api from '@/services/api'
import { showToast } from '@/utils/toast'

const oldPassword = ref('')
const newPassword = ref('')
const confirmPassword = ref('')
const loading = ref(false)
const errorMsg = ref('')

const PASSWORD_MIN_LENGTH = 12

async function submit() {
  errorMsg.value = ''
  if (newPassword.value.length < PASSWORD_MIN_LENGTH) {
    errorMsg.value = `新密码长度至少 ${PASSWORD_MIN_LENGTH} 位`
    return
  }
  if (newPassword.value !== confirmPassword.value) {
    errorMsg.value = '两次输入的新密码不一致'
    return
  }
  loading.value = true
  try {
    await api.put('/auth/me/password', {
      old_password: oldPassword.value,
      new_password: newPassword.value,
    })
    showToast('密码修改成功，正在进入系统...', 'success')
    setTimeout(() => window.location.reload(), 600)
  } catch (e: any) {
    errorMsg.value = e?.message || '密码修改失败，请重试'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.force-modal-mask {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: rgba(8, 12, 18, 0.82);
  backdrop-filter: blur(4px);
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 16px;
}
.force-modal {
  width: 420px;
  max-width: 92vw;
  background: var(--color-bg-surface, #151b24);
  border: 1px solid var(--color-border-default, #2a3340);
  border-radius: 16px;
  padding: 28px 26px;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
}
.force-header {
  display: flex;
  align-items: center;
  gap: 10px;
  color: var(--color-accent-500, #00bcd4);
  margin-bottom: 10px;
}
.force-header svg {
  width: 26px;
  height: 26px;
}
.force-header h2 {
  font-size: 18px;
  margin: 0;
  color: var(--color-text-primary, #e6edf3);
}
.force-tip {
  font-size: 13px;
  color: var(--color-text-tertiary, #8b97a7);
  line-height: 1.6;
  margin: 0 0 18px;
}
.force-form {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.force-form label {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
  color: var(--color-text-secondary, #b6c0cc);
}
.force-form input {
  height: 42px;
  padding: 0 12px;
  background: var(--color-bg-elevated, #0f141b);
  border: 1px solid var(--color-border-default, #2a3340);
  border-radius: 9px;
  color: var(--color-text-primary, #e6edf3);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color 0.2s ease;
}
.force-form input:focus {
  border-color: var(--color-accent-500, #00bcd4);
}
.force-error {
  font-size: 13px;
  color: var(--color-critical, #ff3b5c);
  background: rgba(255, 59, 92, 0.08);
  padding: 8px 12px;
  border-radius: 8px;
  margin: 0;
}
.force-btn {
  height: 46px;
  border: none;
  border-radius: 10px;
  background: var(--color-accent-500, #00bcd4);
  color: #04141a;
  font-size: 15px;
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s ease;
}
.force-btn:hover:not(:disabled) {
  background: var(--color-accent-600, #0098a8);
}
.force-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
.spinner {
  width: 18px;
  height: 18px;
  border: 2px solid rgba(4, 20, 26, 0.3);
  border-top-color: #04141a;
  border-radius: 50%;
  animation: spin 0.6s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
