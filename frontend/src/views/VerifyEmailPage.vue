<script setup>
import { ref, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

// 'verifying' | 'success' | 'error'
const status = ref('verifying')
const errorMessage = ref('')
const email = ref('')
const resending = ref(false)
const resendMessage = ref('')

onMounted(async () => {
  const token = route.query.token
  if (!token) {
    status.value = 'error'
    errorMessage.value = 'Missing verification token in the link.'
    return
  }
  try {
    const result = await authStore.verifyEmail(token)
    // 验证成功即自动登录（后端签发 token 并由 store 写入 localStorage）
    status.value = 'success'
    email.value = result?.user?.email || ''
    setTimeout(() => {
      const redirect = route.query.redirect
      if (redirect) router.push(redirect)
      else router.push('/')
    }, 1800)
  } catch (err) {
    status.value = 'error'
    errorMessage.value =
      err?.response?.data?.detail ||
      err?.data?.detail ||
      'Verification failed. The link may be invalid or expired.'
  }
})

async function handleResend() {
  if (!email.value || resending.value) return
  resending.value = true
  resendMessage.value = ''
  try {
    await authStore.resendVerification(email.value)
    resendMessage.value = 'A new verification link has been sent. Please check your inbox.'
    errorMessage.value = ''
  } catch {
    // 错误 toast 已由 http 拦截器统一弹出
  } finally {
    resending.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card auth-card--verify">
      <div class="auth-logo">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="24" cy="24" r="22" stroke="var(--color-primary)" stroke-width="2.5" fill="none" />
          <path d="M18 14v10l-4 8h20l-4-8V14" stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
          <path d="M18 14h12" stroke="var(--color-primary)" stroke-width="2" stroke-linecap="round" />
          <circle cx="20" cy="26" r="1.5" fill="var(--color-primary)" />
          <circle cx="28" cy="28" r="1" fill="var(--color-primary)" />
          <circle cx="24" cy="30" r="1" fill="var(--color-primary)" />
        </svg>
        <span class="auth-logo-text">SciReagent</span>
      </div>

      <h1 class="auth-title">
        {{ status === 'success' ? 'Email verified' : status === 'error' ? 'Verification failed' : 'Verifying your email' }}
      </h1>
      <p class="auth-subtitle">
        {{ status === 'success' ? 'You are now signed in' : status === 'error' ? "We couldn't verify this link" : 'Please wait a moment…' }}
      </p>

      <!-- Verifying -->
      <div v-if="status === 'verifying'" class="verify-state">
        <svg class="spinner spinner--lg" width="36" height="36" viewBox="0 0 36 36" fill="none">
          <circle cx="18" cy="18" r="15" stroke="var(--color-primary)" stroke-width="3" stroke-dasharray="70" stroke-dashoffset="25" stroke-linecap="round" />
        </svg>
        <p class="verify-state__text">Verifying your email address…</p>
      </div>

      <!-- Success -->
      <div v-else-if="status === 'success'" class="verify-state verify-state--success">
        <div class="verify-state__icon">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2" />
            <path d="M10 16l4 4 8-8" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
        </div>
        <p class="verify-state__text">Email verified! Taking you to the site…</p>
      </div>

      <!-- Error -->
      <div v-else class="verify-state verify-state--error">
        <div class="verify-state__icon verify-state__icon--error">
          <svg width="32" height="32" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2" />
            <path d="M16 9v10" stroke="currentColor" stroke-width="2" stroke-linecap="round" />
            <circle cx="16" cy="23" r="1.4" fill="currentColor" />
          </svg>
        </div>
        <p class="verify-state__error">{{ errorMessage }}</p>
        <div v-if="resendMessage" class="auth-success-banner">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
            <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
            <path d="M5.5 8l2 2 3.5-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          <span>{{ resendMessage }}</span>
        </div>
        <div v-if="email" class="verify-resend">
          <p class="verify-resend__label">Need a new link?</p>
          <button type="button" class="verify-resend__btn" :disabled="resending" @click="handleResend">
            <svg v-if="resending" class="spinner" width="16" height="16" viewBox="0 0 18 18" fill="none">
              <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="2" stroke-dasharray="31.4" stroke-dashoffset="10" stroke-linecap="round" />
            </svg>
            <span v-else>Resend verification email</span>
          </button>
        </div>
        <router-link to="/login" class="auth-link verify-resend__back">Back to sign in</router-link>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-page {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: var(--color-bg);
  padding: var(--spacing-6);
}

.auth-card {
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: 12px;
  padding: 40px;
  width: 100%;
  max-width: 440px;
  box-shadow: var(--shadow-card);
  text-align: center;
}

.auth-logo {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-6);
}

.auth-logo-text {
  font-size: var(--text-h3);
  font-weight: 700;
  color: var(--color-primary);
  letter-spacing: -0.01em;
}

.auth-title {
  font-size: 24px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 var(--spacing-1) 0;
  line-height: 1.3;
}

.auth-subtitle {
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  margin: 0 0 var(--spacing-6) 0;
}

/* ── Verify state ── */
.verify-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-4) 0;
}

.verify-state__icon {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  background: var(--color-success-light);
  color: var(--color-success);
  display: flex;
  align-items: center;
  justify-content: center;
}

.verify-state__icon--error {
  background: var(--color-danger-light);
  color: var(--color-danger);
}

.verify-state__text {
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  line-height: 1.55;
  margin: 0;
}

.verify-state__error {
  font-size: var(--text-body-sm);
  color: var(--color-danger);
  line-height: 1.55;
  margin: 0;
}

.verify-resend {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-2);
  margin-top: var(--spacing-2);
}

.verify-resend__label {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  margin: 0;
}

.verify-resend__btn {
  height: 42px;
  padding: 0 var(--spacing-5);
  background: var(--color-surface);
  color: var(--color-primary);
  border: 1px solid var(--color-primary);
  border-radius: var(--radius-lg);
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s ease;
}

.verify-resend__btn:hover:not(:disabled) {
  background: var(--color-primary-subtle);
}

.verify-resend__btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.verify-resend__back {
  margin-top: var(--spacing-3);
  font-size: var(--text-body-sm);
  display: inline-block;
}

/* ── Shared success banner ── */
.auth-success-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  background: var(--color-success-light);
  color: var(--color-primary-active);
  border-radius: var(--radius-md);
  font-size: var(--text-body-sm);
  margin-bottom: var(--spacing-5);
  line-height: 1.5;
  text-align: left;
}

.auth-success-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
}

/* ── Auth link ── */
.auth-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}

.auth-link:hover {
  text-decoration: underline;
}

/* ── Spinner ── */
.spinner {
  animation: spin 0.8s linear infinite;
}

.spinner--lg {
  width: 36px;
  height: 36px;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
