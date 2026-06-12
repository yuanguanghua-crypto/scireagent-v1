<script setup>
import { ref, reactive, computed, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { searchOrganizations, createOrganization } from '@/api/organizations'

const router = useRouter()
const authStore = useAuthStore()

/* ── State ── */
const currentStep = ref(1)
const serverError = ref('')
const successMessage = ref('')
const loading = ref(false)

/* Step 1: Basic info */
const form = reactive({
  username: '',
  email: '',
  password: '',
  password_confirm: '',
})

const errors = reactive({
  username: '',
  email: '',
  password: '',
  password_confirm: '',
})

/* Step 2: Role selection */
const selectedRole = ref('')
const selectedOrgChoice = ref('')

/* Step 3: Organization */
const orgTab = ref('join') // 'join' | 'create'
const orgSearchQuery = ref('')
const orgSearchResults = ref([])
const orgSearchLoading = ref(false)
const selectedOrgId = ref(null)
const selectedOrgName = ref('')
const newOrg = reactive({
  name: '',
  org_type: 'academic',
})
const orgErrors = reactive({
  name: '',
  org_type: '',
})
let searchDebounceTimer = null

/* ── Role cards data ── */
const roleCards = [
  {
    id: 'independent',
    icon: '🧪',
    title: 'Independent Researcher',
    description: 'I order and pay for reagents myself',
    footnote: '→ Solo organization',
    role: 'researcher',
    orgChoice: 'solo',
  },
  {
    id: 'team-researcher',
    icon: '🔬',
    title: 'Researcher (Team)',
    description: 'My organization has a procurement manager',
    footnote: '→ Join / create org',
    role: 'researcher',
    orgChoice: 'join',
  },
  {
    id: 'procurement',
    icon: '📋',
    title: 'Procurement Manager',
    description: 'I manage procurement and approve orders for my organization',
    footnote: '→ Join / create org',
    role: 'procurement',
    orgChoice: 'join',
  },
]

/* ── Computed ── */
const showStep3 = computed(() => selectedOrgChoice.value && selectedOrgChoice.value !== 'solo')

const canProceedStep1 = computed(() => {
  return form.username.trim().length >= 3 &&
    /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) &&
    form.password.length >= 8 &&
    form.password === form.password_confirm
})

const canProceedStep2 = computed(() => {
  return selectedRole.value && selectedOrgChoice.value
})

const canCompleteStep3 = computed(() => {
  if (orgTab.value === 'join') {
    return selectedOrgId.value !== null
  }
  return newOrg.name.trim().length >= 2 && newOrg.org_type
})

/* ── Methods ── */
function clearErrors() {
  errors.username = ''
  errors.email = ''
  errors.password = ''
  errors.password_confirm = ''
  serverError.value = ''
}

/* Real-time field validation (called on blur) */
function validateField(field) {
  switch (field) {
    case 'username':
      if (!form.username.trim()) {
        errors.username = 'Please enter a username'
      } else if (form.username.trim().length < 3) {
        errors.username = 'Username must be at least 3 characters'
      } else if (!/^[a-zA-Z0-9_-]+$/.test(form.username.trim())) {
        errors.username = 'Only letters, numbers, hyphens and underscores allowed'
      } else {
        errors.username = ''
      }
      break
    case 'email':
      if (!form.email.trim()) {
        errors.email = 'Please enter your email'
      } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim())) {
        errors.email = 'Please enter a valid email address (e.g. you@example.com)'
      } else {
        errors.email = ''
      }
      break
    case 'password':
      if (!form.password) {
        errors.password = 'Please enter a password'
      } else if (form.password.length < 8) {
        errors.password = 'Password must be at least 8 characters'
      } else {
        errors.password = ''
      }
      // Also re-validate confirm if it has a value
      if (form.password_confirm) validateField('password_confirm')
      break
    case 'password_confirm':
      if (!form.password_confirm) {
        errors.password_confirm = 'Please confirm your password'
      } else if (form.password !== form.password_confirm) {
        errors.password_confirm = 'Passwords do not match'
      } else {
        errors.password_confirm = ''
      }
      break
  }
}

/* Password strength indicator */
const passwordStrength = computed(() => {
  const p = form.password
  if (!p) return { level: 0, label: '', color: '' }
  let score = 0
  if (p.length >= 8) score++
  if (p.length >= 12) score++
  if (/[A-Z]/.test(p)) score++
  if (/[0-9]/.test(p)) score++
  if (/[^a-zA-Z0-9]/.test(p)) score++
  if (score <= 1) return { level: 1, label: 'Weak', color: 'var(--color-danger)' }
  if (score <= 2) return { level: 2, label: 'Fair', color: 'var(--color-warning)' }
  if (score <= 3) return { level: 3, label: 'Good', color: 'var(--color-success)' }
  return { level: 4, label: 'Strong', color: 'var(--color-success)' }
})

function validateStep1() {
  let valid = true
  clearErrors()

  validateField('username')
  validateField('email')
  validateField('password')
  validateField('password_confirm')

  if (errors.username || errors.email || errors.password || errors.password_confirm) {
    valid = false
  }

  return valid
}

function nextStep() {
  serverError.value = ''

  if (currentStep.value === 1) {
    if (!validateStep1()) return
    currentStep.value = 2
  } else if (currentStep.value === 2) {
    if (!canProceedStep2.value) return
    if (selectedOrgChoice.value === 'solo') {
      // Skip step 3, go straight to submit
      handleSubmit()
    } else {
      currentStep.value = 3
    }
  }
}

function prevStep() {
  serverError.value = ''
  if (currentStep.value > 1) {
    currentStep.value--
  }
}

function selectCard(card) {
  selectedRole.value = card.role
  selectedOrgChoice.value = card.orgChoice
}

/* Organization search */
async function handleOrgSearch() {
  const q = orgSearchQuery.value.trim()
  if (!q) {
    orgSearchResults.value = []
    return
  }

  orgSearchLoading.value = true
  try {
    const result = await searchOrganizations({ q })
    orgSearchResults.value = result.data || result || []
  } catch {
    orgSearchResults.value = []
  } finally {
    orgSearchLoading.value = false
  }
}

function onOrgSearchInput() {
  selectedOrgId.value = null
  selectedOrgName.value = ''
  clearTimeout(searchDebounceTimer)
  searchDebounceTimer = setTimeout(handleOrgSearch, 400)
}

function selectOrganization(org) {
  selectedOrgId.value = org.id
  selectedOrgName.value = org.name
}

/* Submit */
async function handleSubmit() {
  serverError.value = ''
  loading.value = true

  try {
    const payload = {
      username: form.username.trim(),
      email: form.email.trim(),
      password: form.password,
      password_confirm: form.password_confirm,
      role: selectedRole.value,
      organization_choice: selectedOrgChoice.value,
    }

    if (selectedOrgChoice.value === 'join' && orgTab.value === 'join') {
      payload.organization_id = selectedOrgId.value
    }

    if (selectedOrgChoice.value === 'join' && orgTab.value === 'create') {
      payload.organization_name = newOrg.name.trim()
      payload.organization_type = newOrg.org_type
    }

    // For 'join' org choice with create tab, use 'create' as the choice
    if (selectedOrgChoice.value === 'join' && orgTab.value === 'create') {
      payload.organization_choice = 'create'
    }

    await authStore.register(payload)
    successMessage.value = 'Account created successfully! Redirecting to login...'
    setTimeout(() => {
      router.push({ path: '/login', query: { registered: '1' } })
    }, 1500)
  } catch (err) {
    // Parse backend error into user-friendly message
    const errData = err?.data?.meta?.error?.details || err?.response?.data
    if (errData) {
      // Field-specific errors → show under the field
      if (errData.username) {
        errors.username = Array.isArray(errData.username) ? errData.username[0] : errData.username
      }
      if (errData.email) {
        errors.email = Array.isArray(errData.email) ? errData.email[0] : errData.email
      }
      if (errData.password) {
        errors.password = Array.isArray(errData.password) ? errData.password[0] : errData.password
      }
      // Generic message for the banner
      const fieldErrors = [errData.username, errData.email, errData.password].filter(Boolean)
      if (fieldErrors.length > 0) {
        serverError.value = 'Please fix the errors below and try again.'
      } else {
        serverError.value =
          err?.data?.meta?.error?.message ||
          errData.detail ||
          errData.non_field_errors?.[0] ||
          'Registration failed. Please try again.'
      }
    } else {
      serverError.value = err?.message || 'Registration failed. Please try again.'
    }
  } finally {
    loading.value = false
  }
}

/* Clear org search when switching tabs */
watch(orgTab, () => {
  orgSearchQuery.value = ''
  orgSearchResults.value = []
  selectedOrgId.value = null
  selectedOrgName.value = ''
  orgErrors.name = ''
})
</script>

<template>
  <div class="auth-page">
    <div class="auth-card" :class="{ 'auth-card--wide': currentStep === 2 }">
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

      <h1 class="auth-title">Create Account</h1>
      <p class="auth-subtitle">Join the SciReagent platform</p>

      <!-- Step Indicator -->
      <div class="step-indicator">
        <div class="step-item" :class="{ 'step-item--active': currentStep >= 1, 'step-item--done': currentStep > 1 }">
          <div class="step-dot">
            <svg v-if="currentStep > 1" width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 7l3 3 5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span v-else>1</span>
          </div>
          <span class="step-label">Basics</span>
        </div>
        <div class="step-line" :class="{ 'step-line--active': currentStep > 1 }"></div>
        <div class="step-item" :class="{ 'step-item--active': currentStep >= 2, 'step-item--done': currentStep > 2 || (currentStep === 2 && !showStep3 && canCompleteStep3) }">
          <div class="step-dot">
            <svg v-if="currentStep > 2 || (currentStep === 2 && !showStep3)" width="14" height="14" viewBox="0 0 14 14" fill="none">
              <path d="M3 7l3 3 5-5" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span v-else>2</span>
          </div>
          <span class="step-label">Identity</span>
        </div>
        <div v-if="showStep3" class="step-line" :class="{ 'step-line--active': currentStep > 2 }"></div>
        <div v-if="showStep3" class="step-item" :class="{ 'step-item--active': currentStep >= 3 }">
          <div class="step-dot"><span>3</span></div>
          <span class="step-label">Organization</span>
        </div>
      </div>

      <!-- Success Message -->
      <div v-if="successMessage" class="auth-success-banner">
        <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
          <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
          <path d="M5.5 8l2 2 3.5-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
        </svg>
        <span>{{ successMessage }}</span>
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

      <!-- ========== Step 1: Basic Info ========== -->
      <div v-if="currentStep === 1" class="step-content">
        <form class="auth-form" @submit.prevent="nextStep" novalidate>
          <div class="form-group">
            <label for="reg-username" class="form-label">Username</label>
            <input
              id="reg-username"
              v-model="form.username"
              type="text"
              class="form-input"
              :class="{ 'form-input--error': errors.username, 'form-input--valid': !errors.username && form.username.trim().length >= 3 }"
              placeholder="Choose a username"
              autocomplete="username"
              @blur="validateField('username')"
            />
            <span class="form-hint">3+ characters, letters, numbers, hyphens (-) and underscores (_) only</span>
            <span v-if="errors.username" class="form-error">{{ errors.username }}</span>
          </div>

          <div class="form-group">
            <label for="reg-email" class="form-label">Email</label>
            <input
              id="reg-email"
              v-model="form.email"
              type="email"
              class="form-input"
              :class="{ 'form-input--error': errors.email, 'form-input--valid': !errors.email && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(form.email.trim()) }"
              placeholder="you@example.com"
              autocomplete="email"
              @blur="validateField('email')"
            />
            <span class="form-hint">We'll send a verification link to this address</span>
            <span v-if="errors.email" class="form-error">{{ errors.email }}</span>
          </div>

          <div class="form-group">
            <label for="reg-password" class="form-label">Password</label>
            <input
              id="reg-password"
              v-model="form.password"
              type="password"
              class="form-input"
              :class="{ 'form-input--error': errors.password, 'form-input--valid': !errors.password && form.password.length >= 8 }"
              placeholder="Create a password"
              autocomplete="new-password"
              @blur="validateField('password')"
            />
            <div class="password-meta">
              <span class="form-hint">At least 8 characters. Mix uppercase, numbers & symbols for a stronger password.</span>
              <span v-if="form.password" class="password-strength" :style="{ color: passwordStrength.color }">
                {{ passwordStrength.label }}
              </span>
            </div>
            <div v-if="form.password" class="password-bar">
              <div class="password-bar__fill" :style="{ width: (passwordStrength.level * 25) + '%', backgroundColor: passwordStrength.color }"></div>
            </div>
            <span v-if="errors.password" class="form-error">{{ errors.password }}</span>
          </div>

          <div class="form-group">
            <label for="reg-password-confirm" class="form-label">Confirm Password</label>
            <input
              id="reg-password-confirm"
              v-model="form.password_confirm"
              type="password"
              class="form-input"
              :class="{ 'form-input--error': errors.password_confirm, 'form-input--valid': !errors.password_confirm && form.password_confirm && form.password === form.password_confirm }"
              placeholder="Re-enter your password"
              autocomplete="new-password"
              @blur="validateField('password_confirm')"
            />
            <span class="form-hint">Must match the password above</span>
            <span v-if="errors.password_confirm" class="form-error">{{ errors.password_confirm }}</span>
          </div>

          <button type="submit" class="auth-submit" :disabled="!canProceedStep1">
            <span>Next</span>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
          </button>
        </form>
      </div>

      <!-- ========== Step 2: Role Selection ========== -->
      <div v-if="currentStep === 2" class="step-content">
        <p class="step-description">How will you use SciReagent?</p>

        <div class="role-cards">
          <div
            v-for="card in roleCards"
            :key="card.id"
            class="role-card"
            :class="{ 'role-card--selected': selectedRole === card.role && selectedOrgChoice === card.orgChoice }"
            @click="selectCard(card)"
          >
            <div class="role-card__icon">{{ card.icon }}</div>
            <div class="role-card__body">
              <div class="role-card__title">{{ card.title }}</div>
              <div class="role-card__desc">{{ card.description }}</div>
              <div class="role-card__footnote">{{ card.footnote }}</div>
            </div>
            <div class="role-card__check">
              <svg
                v-if="selectedRole === card.role && selectedOrgChoice === card.orgChoice"
                width="20" height="20" viewBox="0 0 20 20" fill="none"
              >
                <circle cx="10" cy="10" r="10" fill="var(--color-primary)" />
                <path d="M6 10l3 3 5-5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
              </svg>
              <div v-else class="role-card__check-empty"></div>
            </div>
          </div>
        </div>

        <div class="step-actions">
          <button type="button" class="btn-back" @click="prevStep">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 4l-4 4 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span>Back</span>
          </button>
          <button type="button" class="auth-submit" :disabled="!canProceedStep2" @click="nextStep">
            <span>{{ selectedOrgChoice === 'solo' ? 'Complete Registration' : 'Next' }}</span>
            <svg v-if="selectedOrgChoice !== 'solo'" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M6 4l4 4-4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-if="loading" class="spinner" width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="2" stroke-dasharray="31.4" stroke-dashoffset="10" stroke-linecap="round" />
            </svg>
          </button>
        </div>
      </div>

      <!-- ========== Step 3: Organization ========== -->
      <div v-if="currentStep === 3 && showStep3" class="step-content">
        <p class="step-description">Find or create your organization</p>

        <!-- Tabs -->
        <div class="org-tabs">
          <button
            type="button"
            class="org-tab"
            :class="{ 'org-tab--active': orgTab === 'join' }"
            @click="orgTab = 'join'"
          >
            Join Existing
          </button>
          <button
            type="button"
            class="org-tab"
            :class="{ 'org-tab--active': orgTab === 'create' }"
            @click="orgTab = 'create'"
          >
            Create New
          </button>
        </div>

        <!-- Join existing -->
        <div v-if="orgTab === 'join'" class="org-panel">
          <div class="form-group">
            <label class="form-label">Search Organizations</label>
            <div class="org-search-wrapper">
              <svg class="org-search-icon" width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="1.5" />
                <path d="M13 13l3.5 3.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              </svg>
              <input
                v-model="orgSearchQuery"
                type="text"
                class="form-input org-search-input"
                placeholder="Type organization name..."
                @input="onOrgSearchInput"
              />
            </div>
          </div>

          <!-- Search results -->
          <div class="org-results">
            <div v-if="orgSearchLoading" class="org-loading">
              <svg class="spinner" width="18" height="18" viewBox="0 0 18 18" fill="none">
                <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="2" stroke-dasharray="31.4" stroke-dashoffset="10" stroke-linecap="round" />
              </svg>
              <span>Searching...</span>
            </div>
            <div v-else-if="orgSearchQuery.trim() && orgSearchResults.length === 0" class="org-empty">
              No organizations found. Try a different search or create a new one.
            </div>
            <div v-else-if="orgSearchResults.length > 0" class="org-list">
              <div
                v-for="org in orgSearchResults"
                :key="org.id"
                class="org-item"
                :class="{ 'org-item--selected': selectedOrgId === org.id }"
                @click="selectOrganization(org)"
              >
                <div class="org-item__info">
                  <div class="org-item__name">{{ org.name }}</div>
                  <div class="org-item__type">{{ org.org_type || 'Organization' }}</div>
                </div>
                <svg
                  v-if="selectedOrgId === org.id"
                  width="18" height="18" viewBox="0 0 18 18" fill="none"
                >
                  <circle cx="9" cy="9" r="9" fill="var(--color-primary)" />
                  <path d="M5 9l3 3 5-5" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        <!-- Create new -->
        <div v-if="orgTab === 'create'" class="org-panel">
          <div class="form-group">
            <label for="org-name" class="form-label">Organization Name</label>
            <input
              id="org-name"
              v-model="newOrg.name"
              type="text"
              class="form-input"
              :class="{ 'form-input--error': orgErrors.name }"
              placeholder="e.g. MIT Chemistry Lab"
            />
            <span v-if="orgErrors.name" class="form-error">{{ orgErrors.name }}</span>
          </div>

          <div class="form-group">
            <label for="org-type" class="form-label">Organization Type</label>
            <select
              id="org-type"
              v-model="newOrg.org_type"
              class="form-input form-select"
            >
              <option value="academic">Academic / University</option>
              <option value="enterprise">Enterprise / Company</option>
              <option value="government">Government / Institute</option>
              <option value="hospital">Hospital / Medical</option>
            </select>
          </div>
        </div>

        <!-- Actions -->
        <div class="step-actions">
          <button type="button" class="btn-back" @click="prevStep">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path d="M10 4l-4 4 4 4" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <span>Back</span>
          </button>
          <button
            type="button"
            class="auth-submit"
            :disabled="!canCompleteStep3 || loading"
            @click="handleSubmit"
          >
            <svg v-if="loading" class="spinner" width="18" height="18" viewBox="0 0 18 18" fill="none">
              <circle cx="9" cy="9" r="7" stroke="currentColor" stroke-width="2" stroke-dasharray="31.4" stroke-dashoffset="10" stroke-linecap="round" />
            </svg>
            <span v-else>Complete Registration</span>
          </button>
        </div>
      </div>

      <p class="auth-footer">
        Already have an account?
        <router-link to="/login" class="auth-link">Sign in</router-link>
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
  max-width: 440px;
  box-shadow: var(--shadow-card);
  transition: max-width 0.3s var(--ease-default);
}

.auth-card--wide {
  max-width: 560px;
}

/* ── Logo ── */
.auth-logo {
  display: flex;
  align-items: center;
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
  margin: 0 0 var(--spacing-5) 0;
}

/* ── Step Indicator ── */
.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0;
  margin-bottom: var(--spacing-6);
}

.step-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--spacing-1);
}

.step-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--color-text-tertiary);
  background: var(--color-surface);
  transition: all 0.2s ease;
}

.step-item--active .step-dot {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.step-item--done .step-dot {
  border-color: var(--color-primary);
  background: var(--color-primary);
  color: white;
}

.step-label {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  font-weight: 500;
}

.step-item--active .step-label {
  color: var(--color-primary);
}

.step-line {
  width: 48px;
  height: 2px;
  background: var(--color-border);
  margin: 0 var(--spacing-2);
  margin-bottom: 20px;
  transition: background 0.2s ease;
}

.step-line--active {
  background: var(--color-primary);
}

/* ── Messages ── */
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

/* ── Step content ── */
.step-content {
  animation: fadeSlideUp 0.25s var(--ease-decelerate);
}

@keyframes fadeSlideUp {
  from {
    opacity: 0;
    transform: translateY(8px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.step-description {
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  margin: 0 0 var(--spacing-4) 0;
}

/* ── Form ── */
.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
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

.form-select {
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='%2364748B' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
  cursor: pointer;
}

.form-error {
  font-size: var(--text-caption);
  color: var(--color-danger);
}

.form-hint {
  font-size: var(--text-caption);
  color: var(--color-text-tertiary);
  line-height: 1.4;
}

.form-input--valid {
  border-color: var(--color-success);
}

.form-input--valid:focus {
  border-color: var(--color-success);
  box-shadow: 0 0 0 3px var(--color-success-light);
}

.password-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--spacing-2);
}

.password-strength {
  font-size: var(--text-caption);
  font-weight: 600;
  white-space: nowrap;
}

.password-bar {
  height: 3px;
  background: var(--color-border);
  border-radius: 2px;
  overflow: hidden;
}

.password-bar__fill {
  height: 100%;
  border-radius: 2px;
  transition: width 0.3s ease, background-color 0.3s ease;
}

/* ── Role Cards ── */
.role-cards {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-3);
  margin-bottom: var(--spacing-5);
}

.role-card {
  display: flex;
  align-items: flex-start;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
  background: var(--color-surface);
  border: 2px solid var(--color-border);
  border-radius: var(--radius-lg);
  cursor: pointer;
  transition: all var(--duration-normal) var(--ease-default);
}

.role-card:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-subtle);
}

.role-card--selected {
  border-color: var(--color-primary);
  background: var(--color-primary-subtle);
  box-shadow: 0 0 0 1px var(--color-primary);
}

.role-card__icon {
  font-size: 24px;
  line-height: 1;
  flex-shrink: 0;
  margin-top: 2px;
}

.role-card__body {
  flex: 1;
  min-width: 0;
}

.role-card__title {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-text);
  margin-bottom: var(--spacing-0-5);
}

.role-card__desc {
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  line-height: 1.4;
  margin-bottom: var(--spacing-1);
}

.role-card__footnote {
  font-size: var(--text-micro);
  color: var(--color-primary);
  font-weight: 500;
}

.role-card__check {
  flex-shrink: 0;
  margin-top: 2px;
}

.role-card__check-empty {
  width: 20px;
  height: 20px;
  border-radius: 50%;
  border: 2px solid var(--color-border);
}

/* ── Organization ── */
.org-tabs {
  display: flex;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  overflow: hidden;
  margin-bottom: var(--spacing-4);
}

.org-tab {
  flex: 1;
  height: 40px;
  border: none;
  background: var(--color-surface);
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
}

.org-tab:first-child {
  border-right: 1px solid var(--color-border);
}

.org-tab--active {
  background: var(--color-primary);
  color: white;
}

.org-tab:not(.org-tab--active):hover {
  background: var(--color-bg);
}

.org-panel {
  margin-bottom: var(--spacing-4);
}

.org-search-wrapper {
  position: relative;
}

.org-search-icon {
  position: absolute;
  left: 14px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--color-text-tertiary);
  pointer-events: none;
}

.org-search-input {
  padding-left: 40px !important;
}

.org-results {
  margin-top: var(--spacing-3);
}

.org-loading,
.org-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  padding: var(--spacing-5);
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
}

.org-list {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-2);
  max-height: 240px;
  overflow-y: auto;
}

.org-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--spacing-3);
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all 0.15s ease;
}

.org-item:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-subtle);
}

.org-item--selected {
  border-color: var(--color-primary);
  background: var(--color-primary-subtle);
}

.org-item__info {
  min-width: 0;
}

.org-item__name {
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.org-item__type {
  font-size: var(--text-micro);
  color: var(--color-text-secondary);
  text-transform: capitalize;
}

/* ── Buttons ── */
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
  flex: 1;
}

.auth-submit:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.auth-submit:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.step-actions {
  display: flex;
  gap: var(--spacing-3);
  margin-top: var(--spacing-2);
}

.btn-back {
  height: 44px;
  padding: 0 var(--spacing-5);
  background: var(--color-surface);
  color: var(--color-text-secondary);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  font-weight: 500;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: var(--spacing-1);
  transition: all 0.15s ease;
}

.btn-back:hover {
  border-color: var(--color-border-hover);
  color: var(--color-text);
  background: var(--color-bg);
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
  margin: var(--spacing-5) 0 0 0;
}

.auth-link {
  color: var(--color-primary);
  text-decoration: none;
  font-weight: 500;
}

.auth-link:hover {
  text-decoration: underline;
}

/* ── Responsive ── */
@media (max-width: 480px) {
  .auth-card {
    padding: var(--spacing-5);
  }

  .auth-card--wide {
    max-width: 100%;
  }

  .step-line {
    width: 32px;
  }

  .role-card {
    padding: var(--spacing-3);
  }
}
</style>
