<script setup>
import { ref, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { useBasketStore } from '@/stores/basket'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const basketStore = useBasketStore()

const emit = defineEmits(['toggle-sidebar'])

const showDropdown = ref(false)
const userMenuRef = ref(null)
const globalSearchQuery = ref('')

function handleToggleSidebar() {
  emit('toggle-sidebar')
}

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
}

function closeDropdown() {
  showDropdown.value = false
}

// Close dropdown when clicking outside
function handleClickOutside(e) {
  if (userMenuRef.value && !userMenuRef.value.contains(e.target)) {
    closeDropdown()
  }
}

function handleGlobalSearch() {
  const q = globalSearchQuery.value.trim()
  if (q) {
    router.push({ path: '/search', query: { q } })
  }
}

onMounted(() => {
  document.addEventListener('click', handleClickOutside)
  basketStore.loadBasket()
})
onUnmounted(() => document.removeEventListener('click', handleClickOutside))

// Sync search input with route query
watch(() => route.query.q, (val) => {
  globalSearchQuery.value = val || ''
}, { immediate: true })

async function handleLogout() {
  closeDropdown()
  await authStore.logout()
  router.push('/login')
}
</script>

<template>
  <header class="app-header">
    <div class="header-left">
      <button class="sidebar-toggle" @click="handleToggleSidebar">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M4 6h16M4 12h16M4 18h16" />
        </svg>
      </button>
      <h1 class="page-title">{{ route.meta.title || 'SciReagent' }}</h1>
    </div>
    <div class="header-right">
      <div class="search-box">
        <svg class="search-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="11" cy="11" r="8" />
          <path d="M21 21l-4.35-4.35" />
        </svg>
        <input
          v-model="globalSearchQuery"
          type="text"
          placeholder="Search products, methods, protocols..."
          class="search-input"
          @keyup.enter="handleGlobalSearch"
        />
      </div>
      <button class="header-btn" title="Notifications">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
        </svg>
      </button>

      <router-link to="/cart" class="header-btn cart-btn" title="Shopping Cart">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
          <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
        </svg>
        <span v-if="basketStore.count > 0" class="cart-badge">{{ basketStore.count }}</span>
      </router-link>

      <!-- Authenticated: avatar with dropdown -->
      <div v-if="authStore.isAuthenticated" ref="userMenuRef" class="user-menu">
        <button class="user-avatar" @click="toggleDropdown" :title="authStore.username">
          <span>{{ authStore.userInitial }}</span>
        </button>
        <Transition name="fade">
          <div v-if="showDropdown" class="user-dropdown">
            <div class="dropdown-header">
              <div class="dropdown-avatar">{{ authStore.userInitial }}</div>
              <div class="dropdown-info">
                <span class="dropdown-name">{{ authStore.username }}</span>
                <span class="dropdown-email">{{ authStore.email }}</span>
              </div>
            </div>
            <div class="dropdown-divider"></div>
            <!-- Admin links (visible only to admins) -->
            <router-link v-if="authStore.role === 'admin' || authStore.isOrgAdmin || authStore.user?.is_superuser" to="/admin/products" class="dropdown-item" @click="closeDropdown">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
              </svg>
              Product Management
            </router-link>
            <router-link v-if="authStore.role === 'admin' || authStore.isOrgAdmin || authStore.user?.is_superuser" to="/admin/orders" class="dropdown-item" @click="closeDropdown">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Order Management
            </router-link>
            <div v-if="authStore.role === 'admin' || authStore.isOrgAdmin || authStore.user?.is_superuser" class="dropdown-divider"></div>
            <router-link to="/settings" class="dropdown-item" @click="closeDropdown">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <circle cx="12" cy="12" r="3" />
                <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83 0 2 2 0 010-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z" />
              </svg>
              Settings
            </router-link>
            <router-link to="/orders" class="dropdown-item" @click="closeDropdown">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              My Orders
            </router-link>
            <button class="dropdown-item dropdown-item--danger" @click="handleLogout">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="16" height="16">
                <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4" />
                <polyline points="16 17 21 12 16 7" />
                <line x1="21" y1="12" x2="9" y2="12" />
              </svg>
              Sign Out
            </button>
          </div>
        </Transition>
      </div>

      <!-- Unauthenticated: login/register buttons -->
      <template v-else>
        <router-link to="/login" class="btn btn-ghost btn-sm header-auth-btn">Sign In</router-link>
        <router-link to="/register" class="btn btn-primary btn-sm header-auth-btn">Register</router-link>
      </template>
    </div>
  </header>
</template>

<style scoped>
.app-header {
  height: 64px;
  background-color: var(--color-surface);
  border-bottom: 1px solid var(--color-border);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  flex-shrink: 0;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 16px;
}

.sidebar-toggle {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  color: var(--color-text-secondary);
  border-radius: var(--radius-md);
  transition: background-color 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.sidebar-toggle:hover {
  background-color: var(--color-bg);
  color: var(--color-text);
}

.sidebar-toggle svg {
  width: 20px;
  height: 20px;
}

.page-title {
  font-size: 20px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}

.search-box {
  display: flex;
  align-items: center;
  background-color: var(--color-bg);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  padding: 6px 12px;
  gap: 8px;
  transition: border-color 0.2s ease;
}

.search-box:focus-within {
  border-color: var(--color-primary);
}

.search-icon {
  width: 16px;
  height: 16px;
  color: var(--color-text-secondary);
  flex-shrink: 0;
}

.search-input {
  border: none;
  background: transparent;
  outline: none;
  font-size: 14px;
  color: var(--color-text);
  width: 200px;
  font-family: var(--font-sans);
}

.search-input::placeholder {
  color: var(--color-text-secondary);
}

.header-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 8px;
  color: var(--color-text-secondary);
  border-radius: var(--radius-md);
  transition: background-color 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
}

.header-btn:hover {
  background-color: var(--color-bg);
  color: var(--color-text);
}

.header-btn svg {
  width: 20px;
  height: 20px;
}

.header-auth-btn {
  text-decoration: none;
  white-space: nowrap;
}

/* User Avatar */
.user-menu {
  position: relative;
}

.user-avatar {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  background-color: var(--color-primary);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s ease;
  border: none;
  padding: 0;
  font-family: var(--font-sans);
}

.user-avatar:hover {
  opacity: 0.9;
}

/* Dropdown */
.user-dropdown {
  position: absolute;
  top: calc(100% + 8px);
  right: 0;
  width: 240px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-dropdown);
  z-index: 100;
  overflow: hidden;
}

.dropdown-header {
  display: flex;
  align-items: center;
  gap: var(--spacing-3);
  padding: var(--spacing-4);
}

.dropdown-avatar {
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background-color: var(--color-primary-light);
  color: var(--color-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 15px;
  font-weight: 600;
  flex-shrink: 0;
}

.dropdown-info {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.dropdown-name {
  font-size: var(--text-body-sm);
  font-weight: 600;
  color: var(--color-text);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-email {
  font-size: var(--text-caption);
  color: var(--color-text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.dropdown-divider {
  height: 1px;
  background: var(--color-border);
  margin: 0;
}

.dropdown-item {
  display: flex;
  align-items: center;
  gap: var(--spacing-2);
  width: 100%;
  padding: var(--spacing-3) var(--spacing-4);
  border: none;
  background: none;
  cursor: pointer;
  font-family: var(--font-sans);
  font-size: var(--text-body-sm);
  color: var(--color-text-secondary);
  transition: background-color 0.15s ease, color 0.15s ease;
  text-align: left;
}

.dropdown-item:hover {
  background-color: var(--color-bg);
  color: var(--color-text);
}

/* Cart button */
.cart-btn {
  position: relative;
  text-decoration: none;
}

.cart-badge {
  position: absolute;
  top: -2px;
  right: -2px;
  background: var(--color-danger);
  color: white;
  font-size: 10px;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
  line-height: 1;
  pointer-events: none;
}

.dropdown-item--danger {
  color: var(--color-danger);
}

.dropdown-item--danger:hover {
  background-color: var(--color-danger-light);
  color: var(--color-danger);
}
</style>
