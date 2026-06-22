<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const registeredSuccess = ref(!!route.query.registered)

// If there's a stale token in localStorage, clear it so the login form works.
// This handles the case where an expired/foreign token was left behind.
onMounted(() => {
  const token = localStorage.getItem('token')
  if (token && !authStore.isAuthenticated) {
    localStorage.removeItem('token')
  }
})

const form = reactive({
  username: '',
  password: '',
})

const errors = reactive({
  username: '',
  password: '',
})

const serverError = ref('')
const loading = ref(false)

function clearErrors() {
  errors.username = ''
  errors.password = ''
  serverError.value = ''
}

function validate() {
  let valid = true
  clearErrors()

  if (!form.username.trim()) {
    errors.username = 'Please enter your username'
    valid = false
  }

  if (!form.password) {
    errors.password = 'Please enter your password'
    valid = false
  }

  return valid
}

async function handleSubmit() {
  if (!validate()) return

  loading.value = true
  try {
    await authStore.login({
      username: form.username.trim(),
      password: form.password,
    })
    // Staff users → workspace; others → home; respect redirect param
    const redirect = route.query.redirect
    if (redirect) {
      router.push(redirect)
    } else if (authStore.isStaff) {
      router.push('/workspace')
    } else {
      router.push('/')
    }
  } catch (err) {
    const status = err?.response?.status || err?.status
    if (status === 401) {
      serverError.value = 'Incorrect username or password. Please check and try again.'
    } else {
      serverError.value =
        err?.data?.meta?.error?.message ||
        err?.response?.data?.detail ||
        err?.message ||
        'Login failed. Please try again.'
    }
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div class="auth-page">
    <div class="auth-card">
      <!-- Logo -->
      <div class="auth-logo">
        <svg width="48" height="48" viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
          <circle cx="24" cy="24" r="22" stroke="#0F766E" stroke-width="2.5" fill="none" />
          <path d="M18 14v10l-4 8h20l-4-8V14" stroke="#0F766E" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" fill="none" />
          <path d="M18 14h12" stroke="#0F766E" stroke-width="2" stroke-linecap="round" />
          <circle cx="20" cy="26" r="1.5" fill="#0F766E" />
          <circle cx="28" cy="28" r="1" fill="#0F766E" />
          <circle cx="24" cy="30" r="1" fill="#0F766E" />
        </svg>
        <span class="auth-logo-text">SciReagent</span>
      </div>

      <h1 class="auth-title">Welcome Back</h1>
      <p class="auth-subtitle">Sign in to your account</p>

      <!-- Registration Success -->
      <div v-if="registeredSuccess" class="auth-success-banner">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
          <path d="M5.5 8l2 2 3.5-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>Account created successfully! Please sign in.</span>
      </div>

      <!-- Server Error -->
      <div v-if="serverError" class="auth-error-banner">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
          <path d="M8 4.5v4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
          <circle cx="8" cy="11" r="0.75" fill="currentColor" />
        </svg>
        <span>{{ serverError }}</span>
      </div>

      <!-- Form -->
      <form class="auth-form" @submit.prevent="handleSubmit" novalidate>
        <div class="form-group">
          <label for="login-username" class="form-label">Username</label>
          <input
            id="login-username"
            v-model="form.username"
            type="text"
            class="form-input"
            :class="{ 'form-input--error': errors.username }"
            placeholder="Enter your username"
            autocomplete="username"
          />
          <span v-if="errors.username" class="form-error">{{ errors.username }}</span>
        </div>

        <div class="form-group">
          <label for="login-password" class="form-label">Password</label>
          <input
            id="login-password"
            v-model="form.password"
            type="password"
            class="form-input"
            :class="{ 'form-input--error': errors.password }"
            placeholder="Enter your password"
            autocomplete="current-password"
          />
          <span v-if="errors.password" class="form-error">{{ errors.password }}</span>
        </div>

        <button type="submit" class="auth-submit" :disabled="loading">
          <svg v-if="loading" class="spinner" width="18" height="18" viewBox="0 0 18 18" fill="none">
            <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="2" stroke-dasharray="31.4" stroke-dashoffset="10" stroke-linecap="round" />
          </svg>
          <span v-else>Sign In</span>
        </button>
      </form>

      <p class="auth-footer">
        Don't have an account?
        <router-link to="/register" class="auth-link">Create one</router-link>
      </p>
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
  max-width: 400px;
  box-shadow: var(--shadow-card);
}

.auth-logo {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-8);
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

.auth-success-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  background: var(--color-success-light);
  color: var(--color-success);
  border-radius: var(--radius-md);
  font-size: var(--text-body-sm);
  margin-bottom: var(--spacing-5);
  line-height: 1.5;
}

.auth-success-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.auth-error-banner {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  background: var(--color-danger-light);
  color: var(--color-danger);
  border-radius: var(--radius-md);
  font-size: var(--text-body-sm);
  margin-bottom: var(--spacing-5);
  line-height: 1.5;
}

.auth-error-banner svg {
  flex-shrink: 0;
  margin-top: 2px;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-5);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1-5);
}

.form-label {
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-text);
}

.form-input {
  height: 44px;
  padding: 0 var(--spacing-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  color: var(--color-text);
  background: var(--color-surface);
  transition: border-color var(--duration-normal) var(--ease-default),
              box-shadow var(--duration-normal) var(--ease-default);
  outline: none;
}

.form-input::placeholder {
  color: var(--color-text-tertiary);
}

.form-input:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.form-input--error {
  border-color: var(--color-danger);
}

.form-input--error:focus {
  border-color: var(--color-danger);
  box-shadow: 0 0 0 3px var(--color-danger-light);
}

.form-error {
  font-size: var(--text-caption);
  color: var(--color-danger);
}

.auth-submit {
  height: 44px;
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  font-family: var(--font-sans);
  font-size: var(--text-body);
  font-weight: 600;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  margin-top: var(--spacing-1);
  transition: background-color var(--duration-fast) var(--ease-default),
              opacity var(--duration-fast) var(--ease-default);
}

.auth-submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.auth-submit:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.spinner {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.auth-footer {
  text-align: center;
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  margin: var(--spacing-6) 0 0 0;
}

.auth-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}

.auth-link:hover {
  text-decoration: underline;
}
</style>
