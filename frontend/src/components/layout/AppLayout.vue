<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'

const route = useRoute()
const sidebarCollapsed = ref(false)

function toggleSidebar() {
  sidebarCollapsed.value = !sidebarCollapsed.value
}

const navItems = [
  {
    section: 'Discover',
    items: [
      { path: '/', label: 'Home', icon: '<path d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"/>' },
      { path: '/applications', label: 'Applications', icon: '<path d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10"/>' },
      { path: '/methods', label: 'Methods', icon: '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-6 9l2 2 4-4"/>' },
    ],
  },
  {
    section: 'Resources',
    items: [
      { path: '/protocols', label: 'Protocols', icon: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/>' },
      { path: '/research-goals', label: 'Research Goals', icon: '<path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2m-3 7h3m-3 4h3m-6-4h.01M9 16h.01"/>' },
      { path: '/products', label: 'Products', icon: '<path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4"/>' },
    ],
  },
]
</script>

<template>
  <div class="app-layout">
    <aside class="sidebar" :class="{ collapsed: sidebarCollapsed }">
      <!-- Logo -->
      <div class="sidebar-header">
        <div class="logo">
          <svg class="logo-icon" viewBox="0 0 32 32" fill="none">
            <circle cx="16" cy="16" r="14" stroke="currentColor" stroke-width="2" />
            <circle cx="16" cy="16" r="6" fill="currentColor" />
          </svg>
          <span class="logo-text" v-show="!sidebarCollapsed">SciReagent</span>
        </div>
      </div>

      <!-- Navigation -->
      <nav class="sidebar-nav" aria-label="Main navigation">
        <template v-for="(group, idx) in navItems" :key="group.section">
          <div v-if="!sidebarCollapsed" class="nav-section-label">{{ group.section }}</div>
          <div v-else-if="idx > 0" class="nav-divider"></div>
          <router-link
            v-for="item in group.items"
            :key="item.path"
            :to="item.path"
            class="nav-item"
            :class="{ active: item.path === '/' ? route.path === '/' : route.path.startsWith(item.path) }"
          >
            <svg class="nav-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" v-html="item.icon"></svg>
            <span class="nav-text" v-show="!sidebarCollapsed">{{ item.label }}</span>
          </router-link>
        </template>
      </nav>

      <!-- Sidebar footer -->
      <div class="sidebar-footer" v-show="!sidebarCollapsed">
        <div class="sidebar-version">v1.0.0-beta</div>
      </div>
    </aside>

    <div class="main-wrapper">
      <AppHeader @toggle-sidebar="toggleSidebar" />

      <main class="content-area">
        <slot />
      </main>

      <AppFooter />
    </div>
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  min-height: 100vh;
  background-color: var(--color-bg);
}

/* ========== Sidebar ========== */
.sidebar {
  width: 220px;
  background-color: var(--color-surface);
  border-right: 1px solid var(--color-border);
  transition: width 0.2s var(--ease-out);
  display: flex;
  flex-direction: column;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  height: 100vh;
  overflow-y: auto;
}

.sidebar.collapsed {
  width: 56px;
}

/* Header */
.sidebar-header {
  padding: 14px 16px;
  display: flex;
  align-items: center;
  border-bottom: 1px solid var(--color-border);
  height: 52px;
  flex-shrink: 0;
}

.logo {
  display: flex;
  align-items: center;
  gap: 8px;
}

.logo-icon {
  width: 24px;
  height: 24px;
  color: var(--color-primary);
  flex-shrink: 0;
}

.logo-text {
  font-size: 16px;
  font-weight: 700;
  color: var(--color-text);
  white-space: nowrap;
  letter-spacing: -0.01em;
}

/* Navigation */
.sidebar-nav {
  padding: 10px 8px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 1px;
}

.nav-section-label {
  font-size: 10px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  color: var(--color-text-tertiary);
  padding: 12px 12px 6px;
}

.nav-divider {
  height: 1px;
  background: var(--color-border);
  margin: 6px 8px;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 12px;
  border-radius: var(--radius-md);
  color: var(--color-text-secondary);
  text-decoration: none;
  font-size: 13px;
  font-weight: 500;
  transition: all 0.12s ease;
  position: relative;
}

.nav-item:hover {
  background-color: var(--color-bg);
  color: var(--color-text);
}

.nav-item.active {
  background-color: var(--color-primary);
  color: white;
  font-weight: 600;
}

.nav-item.active::before {
  content: '';
  position: absolute;
  left: -8px;
  top: 6px;
  bottom: 6px;
  width: 3px;
  background: var(--color-primary);
  border-radius: 0 2px 2px 0;
}

.nav-icon {
  width: 18px;
  height: 18px;
  flex-shrink: 0;
}

.nav-text {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Footer */
.sidebar-footer {
  padding: 10px 16px;
  border-top: 1px solid var(--color-border);
  flex-shrink: 0;
}

.sidebar-version {
  font-size: 11px;
  color: var(--color-text-tertiary);
  font-family: var(--font-mono);
}

/* ========== Main area ========== */
.main-wrapper {
  flex: 1;
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.content-area {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
}

@media (max-width: 768px) {
  .sidebar {
    position: fixed;
    z-index: 40;
    transform: translateX(-100%);
  }
  .sidebar:not(.collapsed) {
    transform: translateX(0);
    box-shadow: var(--shadow-modal);
  }
}
</style>
