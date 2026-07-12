<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useBasketStore } from '@/stores/basket'
import { AppButton } from '@/components/common'

const router = useRouter()
const basketStore = useBasketStore()
const scrolled = ref(false)
const searchQuery = ref('')

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/search', query: { q: searchQuery.value } })
  }
}

function onScroll() {
  scrolled.value = window.scrollY > 60
}

onMounted(() => {
  window.addEventListener('scroll', onScroll, { passive: true })
})
onUnmounted(() => {
  window.removeEventListener('scroll', onScroll)
})

// Dark mode
const isDark = ref(false)

function toggleDarkMode() {
  isDark.value = !isDark.value
  document.documentElement.classList.toggle('dark', isDark.value)
  localStorage.setItem('scireagent_theme', isDark.value ? 'dark' : 'light')
}

onMounted(() => {
  const saved = localStorage.getItem('scireagent_theme')
  if (saved === 'dark' || (!saved && window.matchMedia('(prefers-color-scheme: dark)').matches)) {
    isDark.value = true
    document.documentElement.classList.add('dark')
  }
})
</script>

<template>
  <nav class="public-nav" :class="{ scrolled }" aria-label="Main navigation">
    <div class="nav-inner">
      <!-- Logo -->
      <router-link to="/" class="nav-brand">
        <svg width="24" height="24" viewBox="0 0 28 28" fill="none">
          <defs>
            <filter id="nav-logo-glow" x="-50%" y="-50%" width="200%" height="200%">
              <feGaussianBlur stdDeviation="1.4" result="b"/>
              <feMerge>
                <feMergeNode in="b"/>
                <feMergeNode in="SourceGraphic"/>
              </feMerge>
            </filter>
          </defs>
          <circle cx="14" cy="14" r="12" stroke="currentColor" stroke-width="1.5" opacity="0.5"/>
          <g filter="url(#nav-logo-glow)">
            <circle cx="10" cy="10" r="3" fill="#5EEAD4"/>
            <circle cx="18" cy="10" r="3" fill="#38BDF8"/>
            <circle cx="14" cy="19" r="3" fill="#FBBF24"/>
          </g>
        </svg>
        Sci<span class="brand-accent">Reagent</span>
      </router-link>

      <!-- Nav Links -->
      <div class="nav-links">
        <router-link to="/products" class="nav-link">Products</router-link>
        <router-link to="/research-goals" class="nav-link">Knowledge</router-link>
        <router-link to="/about" class="nav-link">About</router-link>
      </div>

      <!-- Right side -->
      <div class="nav-right">
        <div class="nav-search">
          <input
            v-model="searchQuery"
            type="text"
            placeholder="Search…"
            @keyup.enter="handleSearch"
          />
        </div>
        <div class="cart-indicator">
          <AppButton variant="ghost" icon to="/cart" title="Shopping Cart">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="20" height="20">
              <circle cx="9" cy="21" r="1"/><circle cx="20" cy="21" r="1"/>
              <path d="M1 1h4l2.68 13.39a2 2 0 002 1.61h9.72a2 2 0 002-1.61L23 6H6"/>
            </svg>
          </AppButton>
          <span v-if="basketStore.count > 0" class="cart-badge">{{ basketStore.count }}</span>
        </div>
        <button type="button" class="nav-btn theme-toggle" @click="toggleDarkMode" :title="isDark ? 'Switch to light mode' : 'Switch to dark mode'">
          <svg v-if="isDark" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <circle cx="12" cy="12" r="5"/>
            <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/>
          </svg>
          <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" width="18" height="18">
            <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
          </svg>
        </button>
        <AppButton variant="outline" size="sm" to="/login">Sign In</AppButton>
        <AppButton variant="primary" size="sm" to="/register">Register</AppButton>
      </div>
    </div>
  </nav>
</template>

<style scoped>
.public-nav {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 100;
  background: rgba(15, 23, 42, 0.88);
  backdrop-filter: blur(8px);
  -webkit-backdrop-filter: blur(8px);
  border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  transition: background 0.3s cubic-bezier(0.16, 1, 0.3, 1),
              backdrop-filter 0.3s,
              border-color 0.3s;
}
.public-nav.scrolled {
  background: rgba(255, 255, 255, 0.92);
  backdrop-filter: blur(14px) saturate(1.3);
  -webkit-backdrop-filter: blur(14px) saturate(1.3);
  border-bottom: 1px solid var(--color-border);
  box-shadow: 0 1px 8px rgba(15, 23, 42, 0.06);
}

.nav-inner {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: 0 32px;
  display: flex;
  align-items: center;
  height: 68px;
}

/* Logo */
.nav-brand {
  display: flex;
  align-items: center;
  gap: 8px;
  text-decoration: none;
  font-family: var(--font-display);
  font-weight: 700;
  font-size: 19px;
  letter-spacing: -0.02em;
  flex-shrink: 0;
  margin-right: 32px;
}
.public-nav:not(.scrolled) .nav-brand { color: var(--color-bg-alt); }
.public-nav.scrolled .nav-brand { color: var(--color-text); }
.brand-accent { color: var(--color-emerald-600); }

/* Links */
.nav-links {
  display: flex;
  align-items: center;
  gap: 2px;
}
.nav-link {
  text-decoration: none;
  font-size: 14px;
  font-weight: 500;
  padding: 8px 18px;
  border-radius: 6px;
  transition: all 0.2s;
}
.public-nav:not(.scrolled) .nav-link { color: var(--color-border-hover); }
.public-nav:not(.scrolled) .nav-link:hover { color: #fff; background: rgba(255,255,255,0.1); }
.public-nav.scrolled .nav-link { color: var(--color-text-secondary); }
.public-nav.scrolled .nav-link:hover { color: var(--color-text); background: var(--color-bg-alt); }

/* Right section */
.nav-right {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-left: auto;
}

.nav-search input {
  width: 150px;
  height: 34px;
  padding: 0 12px;
  border-radius: 6px;
  border: 1.5px solid transparent;
  font-size: 13px;
  font-family: var(--font-body);
  outline: none;
  transition: all 0.2s;
}
.public-nav:not(.scrolled) .nav-search input {
  background: rgba(255,255,255,0.1);
  color: var(--color-bg-alt);
}
.public-nav:not(.scrolled) .nav-search input::placeholder { color: var(--color-text-secondary); }
.public-nav:not(.scrolled) .nav-search input:focus {
  border-color: rgba(94, 234, 212, 0.3);
  background: rgba(255,255,255,0.15);
}
.public-nav.scrolled .nav-search input {
  background: var(--color-bg-alt);
  color: var(--color-text);
}
.public-nav.scrolled .nav-search input:focus { border-color: var(--color-primary); }

@media (max-width: 768px) {
  .nav-inner { padding: 0 20px; }
  .nav-links, .nav-search { display: none; }
}

.cart-indicator {
  position: relative;
  display: inline-flex;
  align-items: center;
}

.cart-badge {
  position: absolute;
  top: -4px;
  right: -4px;
  background: var(--color-danger);
  color: white;
  font-size: 10px;
  font-weight: 700;
  min-width: 16px;
  height: 16px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  padding: 0 4px;
  pointer-events: none;
}

.public-nav .theme-toggle {
  position: relative;
  display: inline-flex;
  align-items: center;
  padding: 8px;
  border-radius: 6px;
  border: none;
  cursor: pointer;
  transition: all 0.2s;
}
.public-nav:not(.scrolled) .theme-toggle { color: #CBD5E1; background: transparent; }
.public-nav:not(.scrolled) .theme-toggle:hover { color: #fff; background: rgba(255,255,255,0.1); }
.public-nav.scrolled .theme-toggle { color: var(--color-text-secondary); background: transparent; }
.public-nav.scrolled .theme-toggle:hover { color: var(--color-text); background: var(--color-gray-100); }
</style>
