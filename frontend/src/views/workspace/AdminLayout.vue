<script setup>
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'

const auth = useAuthStore()
const router = useRouter()

if (!auth.isStaff) {
  router.replace('/')
}
</script>

<template>
  <div class="workspace-layout">
    <aside class="workspace-sidebar">
      <div class="sidebar-header">
        <router-link to="/workspace" class="sidebar-brand">
          <span class="brand-icon">🧪</span>
          <span class="brand-text">SciReAgent</span>
        </router-link>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-group">
          <div class="nav-group-title">Overview</div>
          <router-link to="/workspace" class="nav-item" exact-active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
            </svg>
            Dashboard
          </router-link>
        </div>

        <div class="nav-group">
          <div class="nav-group-title">Products</div>
          <router-link to="/workspace/products" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            Products
          </router-link>
        </div>

        <div class="nav-group">
          <div class="nav-group-title">Knowledge</div>
          <router-link to="/workspace/goals" class="nav-item nav-item--disabled" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="16" /><line x1="8" y1="12" x2="16" y2="12" />
            </svg>
            Research Goals
          </router-link>
          <router-link to="/workspace/applications" class="nav-item nav-item--disabled" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
            </svg>
            Applications
          </router-link>
          <router-link to="/workspace/methods" class="nav-item nav-item--disabled" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
            </svg>
            Methods
          </router-link>
          <router-link to="/workspace/protocols" class="nav-item nav-item--disabled" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
              <rect x="9" y="3" width="6" height="4" rx="1" />
            </svg>
            Protocols
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
        <router-link to="/" class="nav-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          Back to Site
        </router-link>
      </div>
    </aside>

    <main class="workspace-main">
      <header class="workspace-header">
        <h1 class="workspace-title">{{ $route.meta.title || 'Workspace' }}</h1>
      </header>
      <div class="workspace-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex; height: 100vh; background: var(--color-bg);
}
.workspace-sidebar {
  width: 240px; background: var(--color-surface); border-right: 1px solid var(--color-border);
  display: flex; flex-direction: column; flex-shrink: 0; overflow-y: auto;
}
.sidebar-header { padding: 20px; border-bottom: 1px solid var(--color-border); }
.sidebar-brand { display: flex; align-items: center; gap: 10px; text-decoration: none; }
.brand-icon { font-size: 24px; }
.brand-text { font-size: 18px; font-weight: 700; color: var(--color-text); }
.sidebar-nav { flex: 1; padding: 12px 8px; }
.nav-group { margin-bottom: 8px; }
.nav-group-title { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-secondary); padding: 8px 12px 4px; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; text-decoration: none; font-size: 14px; color: var(--color-text-secondary); transition: background 0.15s, color 0.15s; }
.nav-item:hover { background: var(--color-bg); color: var(--color-text); }
.nav-item.active { background: var(--color-primary-light); color: var(--color-primary); font-weight: 600; }
.nav-item--disabled { pointer-events: none; opacity: 0.4; }
.nav-icon { width: 18px; height: 18px; flex-shrink: 0; }
.sidebar-footer { padding: 12px 8px; border-top: 1px solid var(--color-border); }
.workspace-main { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
.workspace-header { padding: 16px 24px; border-bottom: 1px solid var(--color-border); background: var(--color-surface); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.workspace-title { font-size: 20px; font-weight: 600; color: var(--color-text); margin: 0; }
.workspace-content { flex: 1; padding: 24px; max-width: 1200px; width: 100%; }
</style>
