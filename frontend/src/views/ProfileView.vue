<template>
  <div class="profile-view">
    <div class="page-header">
      <div class="page-header-left">
        <h1>个人设置</h1>
        <p>管理个人资料、安全设置与偏好</p>
      </div>
    </div>

    <div class="profile-grid">
      <!-- Profile Card -->
      <div class="profile-card">
        <div class="profile-avatar-section">
          <div class="profile-avatar">{{ userInitial }}</div>
          <div>
            <div class="profile-name">{{ authStore.user?.display_name || '用户' }}</div>
            <div class="profile-role">{{ userRole }}</div>
          </div>
        </div>

        <div class="profile-form">
          <div class="form-group">
            <label>用户名</label>
            <input v-model="profileForm.username" class="form-input" disabled />
          </div>
          <div class="form-group">
            <label>显示名称</label>
            <input v-model="profileForm.display_name" class="form-input" />
          </div>
          <div class="form-group">
            <label>邮箱</label>
            <input v-model="profileForm.email" type="email" class="form-input" />
          </div>
          <div class="form-group">
            <label>手机号</label>
            <input v-model="profileForm.phone" class="form-input" />
          </div>
          <div class="form-actions">
            <button class="btn-primary" @click="saveProfile">保存资料</button>
          </div>
        </div>
      </div>

      <!-- Security Card -->
      <div class="profile-card">
        <h3 class="card-title">安全设置</h3>

        <div class="profile-form">
          <div class="form-group">
            <label>当前密码</label>
            <input v-model="passwordForm.current_password" type="password" class="form-input" />
          </div>
          <div class="form-group">
            <label>新密码</label>
            <input v-model="passwordForm.new_password" type="password" class="form-input" />
          </div>
          <div class="form-group">
            <label>确认新密码</label>
            <input v-model="passwordForm.confirm_password" type="password" class="form-input" />
          </div>
          <div v-if="passwordError" class="form-error">{{ passwordError }}</div>
          <div class="form-actions">
            <button class="btn-primary" @click="changePassword">修改密码</button>
          </div>
        </div>

        <div class="security-section">
          <div class="sec-row">
            <div>
              <div class="sec-row-label">多因素认证 (MFA)</div>
              <div class="sec-row-desc">增加账户安全性，登录时需要额外验证</div>
            </div>
            <label class="toggle-switch">
              <input type="checkbox" v-model="mfaEnabled" @change="toggleMFA" :disabled="mfaLoading" />
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import api from '@/services/api'

const authStore = useAuthStore()
const mfaLoading = ref(false)
const passwordError = ref('')

const profileForm = ref({
  username: '',
  display_name: '',
  email: '',
  phone: '',
})

const passwordForm = ref({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const mfaEnabled = ref(false)

const userInitial = computed(() => (authStore.user?.display_name || '用').charAt(0))
const userRole = computed(() => {
  const roles = authStore.user?.roles
  return roles?.length ? roles[0].display_name : '安全运维工程师'
})

async function saveProfile() {
  try {
    await api.put('/auth/profile', {
      display_name: profileForm.value.display_name,
      email: profileForm.value.email,
      phone: profileForm.value.phone,
    })
  } catch {
    // silently fail
  }
}

async function changePassword() {
  passwordError.value = ''
  if (passwordForm.value.new_password !== passwordForm.value.confirm_password) {
    passwordError.value = '两次输入的新密码不一致'
    return
  }
  if (passwordForm.value.new_password.length < 8) {
    passwordError.value = '新密码长度至少8位'
    return
  }
  try {
    await api.post('/auth/change-password', {
      current_password: passwordForm.value.current_password,
      new_password: passwordForm.value.new_password,
    })
    passwordForm.value = { current_password: '', new_password: '', confirm_password: '' }
  } catch {
    passwordError.value = '密码修改失败，请检查当前密码是否正确'
  }
}

async function toggleMFA() {
  mfaLoading.value = true
  try {
    await api.put('/auth/mfa', { enabled: mfaEnabled.value })
  } catch {
    mfaEnabled.value = !mfaEnabled.value
  } finally {
    mfaLoading.value = false
  }
}

onMounted(() => {
  if (authStore.user) {
    profileForm.value = {
      username: authStore.user.username || '',
      display_name: authStore.user.display_name || '',
      email: authStore.user.email || '',
      phone: authStore.user.phone || '',
    }
    mfaEnabled.value = authStore.user.mfa_enabled || false
  }
})
</script>

<style scoped>
.profile-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-6);
}

.profile-card {
  background: var(--color-bg-surface);
  border: 1px solid var(--color-border-default);
  border-radius: 12px;
  padding: var(--space-6);
}

.profile-avatar-section {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  margin-bottom: var(--space-6);
  padding-bottom: var(--space-5);
  border-bottom: 1px solid var(--color-border-subtle);
}

.profile-avatar {
  width: 56px;
  height: 56px;
  border-radius: 50%;
  background: linear-gradient(135deg, var(--color-accent-500), var(--color-accent-purple));
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-h2);
  font-weight: var(--font-weight-bold);
  color: #fff;
  flex-shrink: 0;
}

.profile-name {
  font-size: var(--text-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
}

.profile-role {
  font-size: var(--text-body-sm);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.card-title {
  font-size: var(--text-h3);
  font-weight: var(--font-weight-semibold);
  color: var(--color-text-primary);
  margin-bottom: var(--space-5);
}

.profile-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.form-group label {
  font-size: var(--text-caption);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.3px;
}

.form-input {
  height: 38px;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 8px;
  padding: 0 var(--space-3);
  color: var(--color-text-primary);
  font-size: var(--text-body-sm);
  font-family: inherit;
  outline: none;
}

.form-input:focus { border-color: var(--color-accent-500); }
.form-input:disabled { opacity: 0.5; cursor: not-allowed; }

.form-error {
  color: var(--color-critical);
  font-size: var(--text-caption);
  padding: var(--space-2) var(--space-3);
  background: rgba(244,67,54,0.08);
  border-radius: 6px;
}

.form-actions {
  padding-top: var(--space-2);
}

.security-section {
  margin-top: var(--space-6);
  padding-top: var(--space-5);
  border-top: 1px solid var(--color-border-subtle);
}

.sec-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.sec-row-label {
  font-size: var(--text-body-sm);
  font-weight: var(--font-weight-medium);
  color: var(--color-text-primary);
}

.sec-row-desc {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  margin-top: 2px;
}

.toggle-switch {
  position: relative;
  display: inline-block;
  width: 40px;
  height: 22px;
  cursor: pointer;
}

.toggle-switch input { opacity: 0; width: 0; height: 0; }

.toggle-slider {
  position: absolute;
  inset: 0;
  background: var(--color-bg-elevated);
  border: 1px solid var(--color-border-subtle);
  border-radius: 22px;
  transition: all 0.3s;
}

.toggle-slider::before {
  content: '';
  position: absolute;
  width: 16px;
  height: 16px;
  left: 2px;
  bottom: 2px;
  background: var(--color-text-tertiary);
  border-radius: 50%;
  transition: all 0.3s;
}

.toggle-switch input:checked + .toggle-slider {
  background: rgba(0, 188, 212, 0.2);
  border-color: var(--color-accent-500);
}

.toggle-switch input:checked + .toggle-slider::before {
  transform: translateX(18px);
  background: var(--color-accent-500);
}

@media (max-width: 900px) {
  .profile-grid { grid-template-columns: 1fr; }
}
</style>