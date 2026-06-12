<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'

const authStore = useAuthStore()

/* ── State ── */
const activeTab = ref('profile')
const saving = ref(false)
const saveMessage = ref('')
const saveMessageType = ref('success') // 'success' | 'error'

const tabs = [
  { id: 'profile', label: 'Profile', icon: '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>' },
  { id: 'contact', label: 'Contact', icon: '<path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/>' },
  { id: 'security', label: 'Security', icon: '<rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0110 0v4"/>' },
  { id: 'account', label: 'Account', icon: '<path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm0 3c1.66 0 3 1.34 3 3s-1.34 3-3 3-3-1.34-3-3 1.34-3 3-3zm0 14.2c-2.5 0-4.71-1.28-6-3.22.03-1.99 4-3.08 6-3.08 1.99 0 5.97 1.09 6 3.08-1.29 1.94-3.5 3.22-6 3.22z"/>' },
]

/* ── Profile form ── */
const profileForm = reactive({
  nickname: '',
  phone: '',
  department: '',
  title: '',
  avatar_url: '',
})

/* ── Contact form ── */
const contactForm = reactive({
  alternate_email: '',
  default_shipping_address: '',
})

/* ── Security form ── */
const securityForm = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

const securityErrors = reactive({
  current_password: '',
  new_password: '',
  confirm_password: '',
})

/* ── Computed ── */
const user = computed(() => authStore.user)

const roleLabel = computed(() => {
  const r = user.value?.role || ''
  switch (r) {
    case 'researcher': return 'Researcher'
    case 'procurement': return 'Procurement Manager'
    case 'editor': return 'Editor'
    default: return r || 'N/A'
  }
})

const roleBadgeClass = computed(() => {
  const r = user.value?.role || ''
  switch (r) {
    case 'researcher': return 'badge-role--researcher'
    case 'procurement': return 'badge-role--procurement'
    case 'editor': return 'badge-role--editor'
    default: return 'badge-role--default'
  }
})

const orgDisplayName = computed(() => {
  const org = user.value?.organization
  if (!org) return 'None'
  if (typeof org === 'string') return org
  return org.name || 'None'
})

const registeredAt = computed(() => {
  const d = user.value?.date_joined || user.value?.created_at
  if (!d) return 'N/A'
  return new Date(d).toLocaleDateString('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  })
})

/* ── Init ── */
onMounted(() => {
  loadUserData()
})

function loadUserData() {
  if (!user.value) return
  profileForm.nickname = user.value.nickname || ''
  profileForm.phone = user.value.phone || ''
  profileForm.department = user.value.department || ''
  profileForm.title = user.value.title || ''
  profileForm.avatar_url = user.value.avatar_url || ''

  contactForm.alternate_email = user.value.alternate_email || ''
  contactForm.default_shipping_address = user.value.default_shipping_address || ''
}

/* ── Save Profile ── */
async function saveProfile() {
  clearSaveMessage()
  saving.value = true
  try {
    await authStore.updateProfile({
      nickname: profileForm.nickname.trim(),
      phone: profileForm.phone.trim(),
      department: profileForm.department.trim(),
      title: profileForm.title.trim(),
      avatar_url: profileForm.avatar_url.trim(),
    })
    showSaveMessage('Profile updated successfully.', 'success')
  } catch (err) {
    const msg = err?.data?.meta?.error?.message || err?.message || 'Failed to update profile.'
    showSaveMessage(msg, 'error')
  } finally {
    saving.value = false
  }
}

/* ── Save Contact ── */
async function saveContact() {
  clearSaveMessage()
  saving.value = true
  try {
    await authStore.updateProfile({
      alternate_email: contactForm.alternate_email.trim(),
      default_shipping_address: contactForm.default_shipping_address.trim(),
    })
    showSaveMessage('Contact info updated successfully.', 'success')
  } catch (err) {
    const msg = err?.data?.meta?.error?.message || err?.message || 'Failed to update contact info.'
    showSaveMessage(msg, 'error')
  } finally {
    saving.value = false
  }
}

/* ── Update Password ── */
function clearSecurityErrors() {
  securityErrors.current_password = ''
  securityErrors.new_password = ''
  securityErrors.confirm_password = ''
}

function updatePassword() {
  clearSecurityErrors()
  clearSaveMessage()

  let valid = true

  if (!securityForm.current_password) {
    securityErrors.current_password = 'Please enter your current password'
    valid = false
  }

  if (!securityForm.new_password) {
    securityErrors.new_password = 'Please enter a new password'
    valid = false
  } else if (securityForm.new_password.length < 8) {
    securityErrors.new_password = 'Password must be at least 8 characters'
    valid = false
  }

  if (!securityForm.confirm_password) {
    securityErrors.confirm_password = 'Please confirm your new password'
    valid = false
  } else if (securityForm.new_password !== securityForm.confirm_password) {
    securityErrors.confirm_password = 'Passwords do not match'
    valid = false
  }

  if (!valid) return

  // Password change UI only - backend API to be implemented later
  showSaveMessage('Password update feature will be available soon.', 'success')
  securityForm.current_password = ''
  securityForm.new_password = ''
  securityForm.confirm_password = ''
}

/* ── Helpers ── */
function showSaveMessage(msg, type) {
  saveMessage.value = msg
  saveMessageType.value = type
  setTimeout(clearSaveMessage, 4000)
}

function clearSaveMessage() {
  saveMessage.value = ''
}

function switchTab(id) {
  activeTab.value = id
  clearSaveMessage()
  clearSecurityErrors()
}
</script>

<template>
  <div class="settings-page">
    <div class="settings-header">
      <h1 class="settings-title">Settings</h1>
      <p class="settings-subtitle">Manage your account preferences</p>
    </div>

    <div class="settings-layout">
      <!-- Sidebar tabs -->
      <aside class="settings-sidebar">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="sidebar-tab"
          :class="{ 'sidebar-tab--active': activeTab === tab.id }"
          @click="switchTab(tab.id)"
        >
          <svg class="sidebar-tab__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="tab.icon"></svg>
          <span>{{ tab.label }}</span>
        </button>
      </aside>

      <!-- Content area -->
      <div class="settings-content">
        <!-- Save message -->
        <Transition name="fade">
          <div v-if="saveMessage" class="save-message" :class="`save-message--${saveMessageType}`">
            <svg v-if="saveMessageType === 'success'" width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
              <path d="M5.5 8l2 2 3.5-4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" />
            </svg>
            <svg v-else width="16" height="16" viewBox="0 0 16 16" fill="none">
              <circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5" />
              <path d="M8 4.5v4" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" />
              <circle cx="8" cy="11" r="0.75" fill="currentColor" />
            </svg>
            <span>{{ saveMessage }}</span>
          </div>
        </Transition>

        <!-- ===== Profile Tab ===== -->
        <div v-if="activeTab === 'profile'" class="tab-panel">
          <div class="tab-header">
            <h2 class="tab-title">Profile</h2>
            <p class="tab-description">Your personal information displayed on the platform.</p>
          </div>

          <form class="settings-form" @submit.prevent="saveProfile" novalidate>
            <div class="form-group">
              <label for="avatar-url" class="form-label">Avatar URL</label>
              <input
                id="avatar-url"
                v-model="profileForm.avatar_url"
                type="text"
                class="form-input"
                placeholder="https://example.com/avatar.png"
              />
              <span class="form-hint">Paste a URL to your profile picture</span>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="nickname" class="form-label">Nickname</label>
                <input
                  id="nickname"
                  v-model="profileForm.nickname"
                  type="text"
                  class="form-input"
                  placeholder="Your display name"
                />
              </div>

              <div class="form-group">
                <label for="phone" class="form-label">Phone</label>
                <input
                  id="phone"
                  v-model="profileForm.phone"
                  type="text"
                  class="form-input"
                  placeholder="+86 138-0000-0000"
                />
              </div>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="department" class="form-label">Department / Lab</label>
                <input
                  id="department"
                  v-model="profileForm.department"
                  type="text"
                  class="form-input"
                  placeholder="e.g. Chemistry Department"
                />
              </div>

              <div class="form-group">
                <label for="title" class="form-label">Title</label>
                <input
                  id="title"
                  v-model="profileForm.title"
                  type="text"
                  class="form-input"
                  placeholder="e.g. PhD Student, Lab Manager"
                />
              </div>
            </div>

            <div class="form-actions">
              <button type="submit" class="btn-save" :disabled="saving">
                <svg v-if="saving" class="spinner" width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="2" stroke-dasharray="25" stroke-dashoffset="8" stroke-linecap="round" />
                </svg>
                <span>Save Changes</span>
              </button>
            </div>
          </form>
        </div>

        <!-- ===== Contact Tab ===== -->
        <div v-if="activeTab === 'contact'" class="tab-panel">
          <div class="tab-header">
            <h2 class="tab-title">Contact</h2>
            <p class="tab-description">Additional contact details and shipping preferences.</p>
          </div>

          <form class="settings-form" @submit.prevent="saveContact" novalidate>
            <div class="form-group">
              <label for="alt-email" class="form-label">Alternate Email</label>
              <input
                id="alt-email"
                v-model="contactForm.alternate_email"
                type="email"
                class="form-input"
                placeholder="backup@example.com"
              />
              <span class="form-hint">Used as a fallback contact method</span>
            </div>

            <div class="form-group">
              <label for="shipping-addr" class="form-label">Default Shipping Address</label>
              <textarea
                id="shipping-addr"
                v-model="contactForm.default_shipping_address"
                class="form-textarea"
                rows="4"
                placeholder="Province / City / District / Street / Building / Room"
              ></textarea>
            </div>

            <div class="form-actions">
              <button type="submit" class="btn-save" :disabled="saving">
                <svg v-if="saving" class="spinner" width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="6" stroke="currentColor" stroke-width="2" stroke-dasharray="25" stroke-dashoffset="8" stroke-linecap="round" />
                </svg>
                <span>Save Changes</span>
              </button>
            </div>
          </form>
        </div>

        <!-- ===== Security Tab ===== -->
        <div v-if="activeTab === 'security'" class="tab-panel">
          <div class="tab-header">
            <h2 class="tab-title">Security</h2>
            <p class="tab-description">Update your password to keep your account secure.</p>
          </div>

          <form class="settings-form" @submit.prevent="updatePassword" novalidate>
            <div class="form-group">
              <label for="current-pwd" class="form-label">Current Password</label>
              <input
                id="current-pwd"
                v-model="securityForm.current_password"
                type="password"
                class="form-input"
                :class="{ 'form-input--error': securityErrors.current_password }"
                placeholder="Enter current password"
                autocomplete="current-password"
              />
              <span v-if="securityErrors.current_password" class="form-error">{{ securityErrors.current_password }}</span>
            </div>

            <div class="form-row">
              <div class="form-group">
                <label for="new-pwd" class="form-label">New Password</label>
                <input
                  id="new-pwd"
                  v-model="securityForm.new_password"
                  type="password"
                  class="form-input"
                  :class="{ 'form-input--error': securityErrors.new_password }"
                  placeholder="At least 8 characters"
                  autocomplete="new-password"
                />
                <span v-if="securityErrors.new_password" class="form-error">{{ securityErrors.new_password }}</span>
              </div>

              <div class="form-group">
                <label for="confirm-pwd" class="form-label">Confirm New Password</label>
                <input
                  id="confirm-pwd"
                  v-model="securityForm.confirm_password"
                  type="password"
                  class="form-input"
                  :class="{ 'form-input--error': securityErrors.confirm_password }"
                  placeholder="Re-enter new password"
                  autocomplete="new-password"
                />
                <span v-if="securityErrors.confirm_password" class="form-error">{{ securityErrors.confirm_password }}</span>
              </div>
            </div>

            <div class="form-actions">
              <button type="submit" class="btn-save">
                <span>Update Password</span>
              </button>
            </div>
          </form>
        </div>

        <!-- ===== Account Tab ===== -->
        <div v-if="activeTab === 'account'" class="tab-panel">
          <div class="tab-header">
            <h2 class="tab-title">Account</h2>
            <p class="tab-description">Your account details and organization membership.</p>
          </div>

          <div class="account-info">
            <div class="info-row">
              <span class="info-label">Username</span>
              <span class="info-value">{{ user?.username || 'N/A' }}</span>
            </div>

            <div class="info-row">
              <span class="info-label">Email</span>
              <span class="info-value">{{ user?.email || 'N/A' }}</span>
            </div>

            <div class="info-row">
              <span class="info-label">Role</span>
              <div class="info-value info-value--inline">
                <span class="badge-role" :class="roleBadgeClass">{{ roleLabel }}</span>
                <span class="role-locked">
                  <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                    <rect x="3" y="6" width="8" height="6" rx="1.5" stroke="currentColor" stroke-width="1.3" />
                    <path d="M5 6V4.5a2 2 0 014 0V6" stroke="currentColor" stroke-width="1.3" stroke-linecap="round" />
                  </svg>
                  <span>Role cannot be changed</span>
                </span>
              </div>
            </div>

            <div class="info-row">
              <span class="info-label">Organization</span>
              <span class="info-value">{{ orgDisplayName }}</span>
            </div>

            <div class="info-row">
              <span class="info-label">Organization Admin</span>
              <span class="info-value">
                <span v-if="authStore.isOrgAdmin" class="badge badge-success badge-dot">Admin</span>
                <span v-else class="text-muted">No</span>
              </span>
            </div>

            <div class="info-row">
              <span class="info-label">Registered</span>
              <span class="info-value">{{ registeredAt }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.settings-page {
  max-width: 960px;
  margin: 0 auto;
}

/* ── Header ── */
.settings-header {
  margin-bottom: var(--spacing-6);
}

.settings-title {
  font-size: var(--text-h2);
  font-weight: 700;
  color: var(--color-text);
  margin: 0 0 var(--spacing-1) 0;
}

.settings-subtitle {
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  margin: 0;
}

/* ── Layout ── */
.settings-layout {
  display: flex;
  gap: var(--spacing-6);
  align-items: flex-start;
}

/* ── Sidebar ── */
.settings-sidebar {
  width: 200px;
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  gap: var(--spacing-1);
  position: sticky;
  top: 20px;
}

.sidebar-tab {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-2-5, 10px) var(--spacing-3);
  border: none;
  background: none;
  border-radius: var(--radius-md);
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
  cursor: pointer;
  transition: all 0.15s ease;
  text-align: left;
}

.sidebar-tab:hover {
  background: var(--color-gray-100);
  color: var(--color-text);
}

.sidebar-tab--active {
  background: var(--color-primary-light);
  color: var(--color-primary);
  font-weight: 600;
}

.sidebar-tab__icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

/* ── Content ── */
.settings-content {
  flex: 1;
  min-width: 0;
}

/* ── Save message ── */
.save-message {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  padding: var(--spacing-3);
  border-radius: var(--radius-md);
  font-size: var(--text-body-sm);
  margin-bottom: var(--spacing-5);
  line-height: 1.5;
  animation: fadeSlideUp 0.2s ease;
}

.save-message svg {
  flex-shrink: 0;
}

.save-message--success {
  background: var(--color-success-light);
  color: var(--color-success);
}

.save-message--error {
  background: var(--color-danger-light);
  color: var(--color-danger);
}

/* ── Tab Panel ── */
.tab-panel {
  animation: fadeSlideUp 0.2s var(--ease-decelerate);
}

@keyframes fadeSlideUp {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

.tab-header {
  margin-bottom: var(--spacing-5);
  padding-bottom: var(--spacing-4);
  border-bottom: 1px solid var(--color-border);
}

.tab-title {
  font-size: var(--text-h3);
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 var(--spacing-1) 0;
}

.tab-description {
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  margin: 0;
}

/* ── Form ── */
.settings-form {
  display: flex;
  flex-direction: column;
  gap: var(--spacing-4);
}

.form-row {
  display: grid;
  grid-template-columns: 1fr 1fr;
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

.form-textarea {
  padding: var(--spacing-3) var(--spacing-4);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  color: var(--color-text);
  background: var(--color-surface);
  transition: border-color var(--duration-normal) var(--ease-default),
              box-shadow var(--duration-normal) var(--ease-default);
  outline: none;
  resize: vertical;
  line-height: 1.5;
}

.form-textarea::placeholder {
  color: var(--color-text-tertiary);
}

.form-textarea:focus {
  border-color: var(--color-primary);
  box-shadow: 0 0 0 3px var(--color-primary-light);
}

.form-hint {
  font-size: var(--text-micro);
  color: var(--color-text-tertiary);
}

.form-error {
  font-size: var(--text-caption);
  color: var(--color-danger);
}

.form-actions {
  padding-top: var(--spacing-2);
}

.btn-save {
  height: 44px;
  padding: 0 var(--spacing-6);
  background: var(--color-primary);
  color: white;
  border: none;
  border-radius: var(--radius-lg);
  font-family: var(--font-sans);
  font-size: var(--text-body);
  font-weight: 600;
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--spacing-2);
  transition: background-color var(--duration-fast) var(--ease-default),
              opacity var(--duration-fast) var(--ease-default);
}

.btn-save:hover:not(:disabled) {
  background: var(--color-primary-hover);
}

.btn-save:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.spinner {
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* ── Account Info ── */
.account-info {
  display: flex;
  flex-direction: column;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  overflow: hidden;
}

.info-row {
  display: flex;
  align-items: flex-start;
  padding: var(--spacing-4);
  border-bottom: 1px solid var(--color-border-light);
}

.info-row:last-child {
  border-bottom: none;
}

.info-label {
  width: 160px;
  flex-shrink: 0;
  font-size: var(--text-body-sm);
  font-weight: 500;
  color: var(--color-text-secondary);
}

.info-value {
  flex: 1;
  font-size: var(--text-body-sm);
  color: var(--color-text);
  min-width: 0;
}

.info-value--inline {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  flex-wrap: wrap;
}

/* ── Role badges ── */
.badge-role {
  display: inline-flex;
  align-items: center;
  height: 24px;
  padding: 0 var(--spacing-2-5, 10px);
  border-radius: var(--radius-sm);
  font-size: var(--text-micro);
  font-weight: 600;
  letter-spacing: 0.01em;
}

.badge-role--researcher {
  background: var(--color-success-light);
  color: var(--color-success);
}

.badge-role--procurement {
  background: var(--color-info-light);
  color: var(--color-info);
}

.badge-role--editor {
  background: #EDE9FE;
  color: #7C3AED;
}

.badge-role--default {
  background: var(--color-gray-100);
  color: var(--color-gray-700);
}

.role-locked {
  display: inline-flex;
  align-items: center;
  gap: var(--spacing-1);
  font-size: var(--text-micro);
  color: var(--color-text-tertiary);
}

.text-muted {
  color: var(--color-text-tertiary);
  font-size: var(--text-body-sm);
}

/* ── Responsive ── */
@media (max-width: 768px) {
  .settings-layout {
    flex-direction: column;
  }

  .settings-sidebar {
    width: 100%;
    flex-direction: row;
    flex-wrap: wrap;
    position: static;
    gap: var(--spacing-1);
  }

  .sidebar-tab {
    flex: 1;
    justify-content: center;
    min-width: 0;
  }

  .form-row {
    grid-template-columns: 1fr;
  }

  .info-row {
    flex-direction: column;
    gap: var(--spacing-1);
  }

  .info-label {
    width: auto;
  }
}

/* ── Vue Transition ── */
.fade-enter-active,
.fade-leave-active {
  transition: opacity var(--duration-slow) var(--ease-default);
}
.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
