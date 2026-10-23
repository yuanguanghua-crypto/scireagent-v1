<script setup>
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const token = ref('')
const password = ref('')
const confirm = ref('')
const submitting = ref(false)
const done = ref(false)
const serverError = ref('')

onMounted(() => {
  token.value = (route.query.token || '').toString()
})

const tokenMissing = computed(() => !token.value)

const mismatch = computed(
  () => confirm.value.length > 0 && password.value !== confirm.value
)

const tooShort = computed(
  () => password.value.length > 0 && password.value.length < 8
)

async function handleSubmit() {
  serverError.value = ''
  if (tokenMissing.value) {
    serverError.value = 'This reset link is missing its token. Please request a new one.'
    return
  }
  if (!password.value || tooShort.value) {
    serverError.value = 'Password must be at least 8 characters.'
    return
  }
  if (password.value !== confirm.value) {
    serverError.value = 'The two passwords do not match.'
    return
  }

  submitting.value = true
  try {
    await authStore.resetPassword(token.value, password.value)
    // 后端已吊销该用户全部 token，本地过期态一并清掉，避免带着死 token 进站
    localStorage.removeItem('token')
    done.value = true
  } catch (err) {
    serverError.value =
      err?.response?.data?.meta?.error?.message ||
      err?.response?.data?.detail ||
      'This reset link is invalid or has expired. Please request a new one.'
  } finally {
    submitting.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <span class="auth-logo-text">SciReagent</span>
      </div>

      <h1 class="auth-title">Choose a new password</h1>

      <!-- 成功态 -->
      <template v-if="done">
        <div class="auth-success-banner">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
            <path d="M5.5 8l2 2 3.5-4" stroke="currentColor" stroke-width="1.5"
                  stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span>Password updated. Please sign in with your new password.</span>
        </div>
        <button type="button" class="auth-submit" @click="router.push('/login')">
          Go to sign in
        </button>
      </template>

      <!-- token 缺失 -->
      <template v-else-if="tokenMissing">
        <div class="auth-error-banner">
          <span>This reset link is incomplete. Please request a new one.</span>
        </div>
        <button type="button" class="auth-submit" @click="router.push('/forgot-password')">
          Request a new link
        </button>
      </template>

      <!-- 表单 -->
      <template v-else>
        <p class="auth-subtitle">Pick something you haven't used before</p>

        <div v-if="serverError" class="auth-error-banner">
          <span>{{ serverError }}</span>
        </div>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <div class="form-group">
            <label for="password">New password</label>
            <input
              id="password"
              v-model="password"
              type="password"
              autocomplete="new-password"
              :disabled="submitting"
            />
            <small v-if="tooShort" class="field-hint">At least 8 characters</small>
          </div>

          <div class="form-group">
            <label for="confirm">Confirm new password</label>
            <input
              id="confirm"
              v-model="confirm"
              type="password"
              autocomplete="new-password"
              :disabled="submitting"
            />
            <small v-if="mismatch" class="field-hint">Passwords do not match</small>
          </div>

          <button type="submit" class="auth-submit" :disabled="submitting">
            <span v-if="submitting">Updating…</span>
            <span v-else>Set new password</span>
          </button>
        </form>
      </template>

      <p class="auth-footer-link">
        <button type="button" class="link-btn" @click="router.push('/forgot-password')">
          Request a new link
        </button>
      </p>
    </div>
  </div>
</template>

<style scoped>
.link-btn {
  background: none;
  border: none;
  padding: 0;
  color: var(--color-primary);
  cursor: pointer;
  font-size: inherit;
}
.link-btn:hover { text-decoration: underline; }
.auth-footer-link { text-align: center; margin-top: 16px; }
.auth-form { display: flex; flex-direction: column; gap: 14px; }
.form-group { display: flex; flex-direction: column; gap: 6px; }
.form-group label { font-size: 13px; color: var(--color-text-secondary); }
.form-group input {
  padding: 10px 12px;
  border: 1px solid var(--color-border);
  border-radius: 6px;
  font-size: 14px;
  background: var(--color-bg);
  color: var(--color-text);
}
.form-group input:focus {
  outline: none;
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.12);
}
.field-hint { color: var(--color-error, #dc2626); font-size: 12px; }
.auth-submit {
  margin-top: 6px;
  padding: 11px;
  border: none;
  border-radius: 6px;
  background: var(--color-primary);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  width: 100%;
}
.auth-submit:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
