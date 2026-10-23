<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const email = ref('')
const submitting = ref(false)
const sent = ref(false)
const serverError = ref('')

async function handleSubmit() {
  serverError.value = ''
  if (!email.value.trim()) {
    serverError.value = 'Please enter your email address.'
    return
  }
  submitting.value = true
  try {
    await authStore.requestPasswordReset(email.value.trim())
  } catch (err) {
    // 后端对「邮箱存在/不存在」返回完全一致的响应，正常不会进这里；
    // 走到这里一般是限流或网络问题，仍然给出同样的中性提示，不泄露账号是否存在。
    serverError.value =
      err?.response?.data?.meta?.error?.message ||
      err?.response?.data?.detail ||
      ''
  } finally {
    submitting.value = false
    // 无论成功或失败都进入"已受理"状态：这是防用户枚举的最后一环
    sent.value = true
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <div class="auth-logo">
        <span class="auth-logo-text">SciReagent</span>
      </div>

      <h1 class="auth-title">Forgot password</h1>
      <p class="auth-subtitle">We'll email you a link to choose a new password</p>

      <div v-if="sent" class="auth-success-banner">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
          <path d="M5.5 8l2 2 3.5-4" stroke="currentColor" stroke-width="1.5"
                stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>
          If that email address is registered, a reset link is on its way.
          Check your inbox and spam folder.
        </span>
      </div>

      <div v-if="serverError" class="auth-error-banner">
        <span>{{ serverError }}</span>
      </div>

      <form v-if="!sent" class="auth-form" @submit.prevent="handleSubmit">
        <div class="form-group">
          <label for="email">Email address</label>
          <input
            id="email"
            v-model="email"
            type="email"
            autocomplete="email"
            placeholder="you@lab.edu"
            :disabled="submitting"
          />
        </div>

        <button type="submit" class="auth-submit" :disabled="submitting">
          <span v-if="submitting">Sending…</span>
          <span v-else>Send reset link</span>
        </button>
      </form>

      <p class="auth-footer-link">
        <button type="button" class="link-btn" @click="router.push('/login')">
          Back to sign in
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
}
.auth-submit:disabled { opacity: 0.6; cursor: not-allowed; }
</style>
