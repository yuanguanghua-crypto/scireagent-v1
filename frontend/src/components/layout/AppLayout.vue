<script setup>
import { ref } from 'vue'
import { useRoute } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import AppHeader from './AppHeader.vue'
import AppFooter from './AppFooter.vue'
import PublicNav from './PublicNav.vue'

const route = useRoute()
const authStore = useAuthStore()

// Public pages (no auth needed, transparent nav): Home, Login, Register, Product lists, Knowledge pages
const isPublicPage = () => route.meta?.nav === 'public'

// Workspace has its own sidebar via AdminLayout — hide nav entirely
const isWorkspace = () => route.path.startsWith('/workspace')

// Home is a full-bleed marketing page (dark hero under transparent/white nav) — no content padding
const isHome = () => route.path === '/'

// 匿名用户在 public 页面会渲染固定浮层 PublicNav（position:fixed, 高 68px）。
// quote-request / search 等内容区顶部留白不足会被遮挡，故在此补上顶部间距。
const NAV_PAD_PAGES = ['/quote-request', '/search']
const needsNavPad = () => !authStore.isAuthenticated && isPublicPage() && NAV_PAD_PAGES.includes(route.path)
</script>

<template>
  <div class="app-layout" :class="{ 'layout-workspace': isWorkspace(), 'home-layout': isHome(), 'public-nav-pad': needsNavPad() }">
    <!-- Public pages (home/login/register/products/knowledge…) ALWAYS show the
         marketing nav (PublicNav) regardless of login state. Logged-in users still
         get the user menu inside PublicNav; AppHeader is reserved for the workspace. -->
    <PublicNav v-if="isPublicPage()" />

    <!-- Authenticated pages (incl. logged-in users on public pages): full AppHeader -->
    <AppHeader v-else-if="!isWorkspace()" />

    <main class="content-area">
      <slot />
    </main>

    <AppFooter v-if="!isWorkspace()" />
  </div>
</template>

<style scoped>
.app-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background-color: var(--color-bg);
}

.layout-workspace {
  /* Workspace (AdminLayout) owns a full-height 100vh flex layout with its own
     scroll region (.workspace-main). The outer app-layout must NOT add height
     or its own scroll, otherwise the page gets a second (window) scrollbar. */
  height: 100vh;
  overflow: hidden;
}

.layout-workspace .content-area {
  flex: 1 1 auto;
  min-height: 0;
  padding: 0;
  overflow: hidden;
}

.content-area {
  flex: 1;
  padding: 20px 24px;
  overflow-y: auto;
}

/* Home is full-bleed: hero sits flush under the nav (no content padding).
   Inner sections (.home > .content-area) keep their own max-width + padding. */
.home-layout .content-area {
  padding: 0;
}

/* 匿名 public 页面（PublicNav 固定浮层）下，为内容区补足顶部间距，
   避免固定导航遮挡页面标题（如 /quote-request 的 "Request a Quote"）。 */
.public-nav-pad .content-area {
  padding-top: 72px;
}

@media (max-width: 768px) {
  .content-area {
    padding: 16px;
  }
}
</style>
