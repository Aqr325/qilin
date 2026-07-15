import { ref } from 'vue'

// 强制改密全局状态（leaf 模块，仅依赖 vue，避免与 auth store 形成循环依赖）
export const needsPasswordChange = ref(false)

export function triggerForcePasswordChange() {
  needsPasswordChange.value = true
}

export function clearForcePasswordChange() {
  needsPasswordChange.value = false
}
