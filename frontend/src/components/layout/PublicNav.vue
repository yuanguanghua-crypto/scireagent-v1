<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
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
        <router-link to="/login" class="nav-btn nav-btn-outline">Sign In</router-link>
        <router-link to="/register" class="nav-btn nav-btn-solid">Register</router-link>
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
  background: rgba(10, 22, 40, 0.25);
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
  max-width: 1280px;
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
.public-nav:not(.scrolled) .nav-brand { color: #F1F5F9; }
.public-nav.scrolled .nav-brand { color: var(--color-text); }
.brand-accent { color: var(--color-teal-600); }

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
.public-nav:not(.scrolled) .nav-link { color: #CBD5E1; }
.public-nav:not(.scrolled) .nav-link:hover { color: #fff; background: rgba(255,255,255,0.1); }
.public-nav.scrolled .nav-link { color: var(--color-text-secondary); }
.public-nav.scrolled .nav-link:hover { color: var(--color-text); background: var(--color-gray-100); }

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
  color: #F1F5F9;
}
.public-nav:not(.scrolled) .nav-search input::placeholder { color: #64748B; }
.public-nav:not(.scrolled) .nav-search input:focus {
  border-color: rgba(94, 234, 212, 0.3);
  background: rgba(255,255,255,0.15);
}
.public-nav.scrolled .nav-search input {
  background: var(--color-gray-100);
  color: var(--color-text);
}
.public-nav.scrolled .nav-search input:focus { border-color: var(--color-primary); }

.nav-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  border-radius: 6px;
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
  transition: all 0.2s;
  white-space: nowrap;
}
.nav-btn-outline {
  border: 1.5px solid;
}
.public-nav:not(.scrolled) .nav-btn-outline {
  color: #E2E8F0;
  border-color: rgba(255,255,255,0.2);
}
.public-nav:not(.scrolled) .nav-btn-outline:hover {
  border-color: rgba(255,255,255,0.4);
  background: rgba(255,255,255,0.08);
}
.public-nav.scrolled .nav-btn-outline {
  color: var(--color-text-secondary);
  border-color: var(--color-border);
}
.public-nav.scrolled .nav-btn-outline:hover {
  border-color: var(--color-border-hover);
  color: var(--color-text);
}
.nav-btn-solid {
  border: none;
}
.public-nav:not(.scrolled) .nav-btn-solid {
  background: var(--color-teal-600);
  color: #fff;
}
.public-nav:not(.scrolled) .nav-btn-solid:hover {
  background: var(--color-teal-500);
  box-shadow: 0 0 24px rgba(13, 109, 105, 0.25);
}
.public-nav.scrolled .nav-btn-solid {
  background: var(--color-primary);
  color: #fff;
}
.public-nav.scrolled .nav-btn-solid:hover {
  background: var(--color-primary-hover);
}

@media (max-width: 768px) {
  .nav-inner { padding: 0 20px; }
  .nav-links, .nav-search, .nav-btn-outline { display: none; }
}
</style>
