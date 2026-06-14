<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  title: { type: String, default: 'SciReagent' },
  subtitle: { type: String, default: '' },
  suggestedSearches: { type: Array, default: () => [] },
})

const router = useRouter()
const searchQuery = ref('')

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/search', query: { q: searchQuery.value } })
  }
}

function handlePopularSearch(term) {
  searchQuery.value = term
  handleSearch()
}

const researchShortcuts = [
  { label: 'RNA Labeling', query: 'RNA labeling' },
  { label: 'Click Chemistry', query: 'Click chemistry' },
  { label: 'NGS Library Prep', query: 'NGS library prep' },
  { label: 'mRNA Synthesis', query: 'mRNA synthesis' },
  { label: 'Protein Bioconjugation', query: 'Protein bioconjugation' },
]
</script>

<template>
  <section class="hero-section" aria-label="Platform introduction">
    <div class="hero-pattern" aria-hidden="true">
      <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
        <defs>
          <pattern id="hex-pattern" width="60" height="52" patternUnits="userSpaceOnUse" patternTransform="scale(1.2)">
            <polygon points="30,2 54,15 54,37 30,50 6,37 6,15" fill="none" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>
          </pattern>
        </defs>
        <rect width="100%" height="100%" fill="url(#hex-pattern)"/>
      </svg>
    </div>
    <div class="hero-glow" aria-hidden="true"></div>

    <div class="hero-content">
      <div class="hero-badge">
        <span class="hero-badge-dot" aria-hidden="true"></span>
        AI-Native Scientific Commerce Platform
      </div>
      <h1 class="hero-title">{{ title }}</h1>
      <p class="hero-subtitle">{{ subtitle || 'Discover reagents by research intent. Search by application, method, protocol, CAS, or catalog number.' }}</p>

      <!-- Search Bar -->
      <div class="hero-search-wrapper">
        <input
          v-model="searchQuery"
          type="text"
          placeholder="Search products, methods, protocols, applications..."
          class="hero-search-input"
          aria-label="Search the platform"
          @keyup.enter="handleSearch"
        />
        <button class="hero-search-btn" @click="handleSearch">Search</button>
      </div>

      <!-- Research Shortcuts -->
      <div class="hero-shortcuts" aria-label="Research shortcuts">
        <span class="hero-shortcuts-label">Popular research areas:</span>
        <button
          v-for="s in researchShortcuts"
          :key="s.label"
          class="hero-shortcut-chip"
          @click="handlePopularSearch(s.query)"
        >
          {{ s.label }}
        </button>
      </div>

      <!-- Trending Searches -->
      <div v-if="suggestedSearches.length" class="hero-popular" aria-label="Suggested searches">
        <span class="hero-popular-label">Trending:</span>
        <button
          v-for="term in suggestedSearches"
          :key="term"
          class="hero-popular-chip"
          @click="handlePopularSearch(term)"
        >
          {{ term }}
        </button>
      </div>

      <!-- Quick CTAs -->
      <div class="hero-ctas">
        <button class="hero-cta-btn hero-cta-primary" @click="router.push('/applications')">Browse Applications</button>
        <button class="hero-cta-btn hero-cta-outline" @click="router.push('/quote-request')">Custom Synthesis</button>
        <button class="hero-cta-btn hero-cta-outline" @click="router.push('/products')">View Catalog</button>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero-section {
  position: relative;
  padding: 48px 20px;
  background: linear-gradient(135deg, #0f766e 0%, #134e4a 100%);
  border-radius: var(--radius-lg);
  overflow: hidden;
  text-align: center;
}
.hero-pattern { position: absolute; inset: 0; opacity: 0.3; }
.hero-glow {
  position: absolute;
  top: -50%;
  left: 50%;
  transform: translateX(-50%);
  width: 600px;
  height: 600px;
  background: radial-gradient(circle, rgba(255,255,255,0.08) 0%, transparent 70%);
  pointer-events: none;
}
.hero-content { position: relative; z-index: 1; max-width: 720px; margin: 0 auto; }
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  background: rgba(255,255,255,0.12);
  border-radius: 20px;
  font-size: 12px;
  font-weight: 600;
  color: rgba(255,255,255,0.9);
  margin-bottom: 12px;
}
.hero-badge-dot {
  width: 6px;
  height: 6px;
  background: #5eead4;
  border-radius: 50%;
}
.hero-title {
  font-size: 34px;
  font-weight: 800;
  color: white;
  margin: 0 0 8px;
  letter-spacing: -0.02em;
}
.hero-subtitle {
  font-size: 15px;
  color: rgba(255,255,255,0.75);
  margin: 0 0 24px;
  line-height: 1.5;
}

/* Search */
.hero-search-wrapper {
  display: flex;
  gap: 8px;
  max-width: 560px;
  margin: 0 auto 16px;
}
.hero-search-input {
  flex: 1;
  height: 46px;
  padding: 0 16px;
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: var(--radius-md);
  background: rgba(255,255,255,0.1);
  color: white;
  font-size: 14px;
  font-family: var(--font-sans);
  outline: none;
  backdrop-filter: blur(8px);
}
.hero-search-input::placeholder { color: rgba(255,255,255,0.5); }
.hero-search-input:focus {
  border-color: rgba(255,255,255,0.4);
  background: rgba(255,255,255,0.15);
}
.hero-search-btn {
  height: 46px;
  padding: 0 22px;
  background: white;
  color: #0f766e;
  border: none;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 700;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: opacity 0.15s;
}
.hero-search-btn:hover { opacity: 0.9; }

/* Research Shortcuts */
.hero-shortcuts {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 10px;
}
.hero-shortcuts-label {
  font-size: 12px;
  color: rgba(255,255,255,0.5);
}
.hero-shortcut-chip {
  padding: 3px 10px;
  background: rgba(255,255,255,0.15);
  border: 1px solid rgba(255,255,255,0.2);
  border-radius: 16px;
  color: rgba(255,255,255,0.9);
  font-size: 12px;
  font-weight: 500;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: all 0.15s;
}
.hero-shortcut-chip:hover {
  background: rgba(255,255,255,0.25);
  border-color: rgba(255,255,255,0.4);
}

/* Trending */
.hero-popular {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}
.hero-popular-label {
  font-size: 12px;
  color: rgba(255,255,255,0.45);
}
.hero-popular-chip {
  padding: 2px 10px;
  background: rgba(255,255,255,0.08);
  border: 1px solid rgba(255,255,255,0.1);
  border-radius: 16px;
  color: rgba(255,255,255,0.7);
  font-size: 12px;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: all 0.15s;
}
.hero-popular-chip:hover {
  background: rgba(255,255,255,0.18);
  border-color: rgba(255,255,255,0.25);
}

/* Quick CTAs */
.hero-ctas {
  display: flex;
  justify-content: center;
  gap: 10px;
  flex-wrap: wrap;
}
.hero-cta-btn {
  height: 36px;
  padding: 0 18px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-sans);
  transition: all 0.15s;
}
.hero-cta-primary {
  background: rgba(255,255,255,0.95);
  color: #0f766e;
  border: none;
}
.hero-cta-primary:hover { background: white; }
.hero-cta-outline {
  background: transparent;
  color: rgba(255,255,255,0.9);
  border: 1px solid rgba(255,255,255,0.3);
}
.hero-cta-outline:hover {
  background: rgba(255,255,255,0.1);
  border-color: rgba(255,255,255,0.5);
}

@media (max-width: 768px) {
  .hero-section { padding: 32px 16px; }
  .hero-title { font-size: 26px; }
  .hero-search-wrapper { flex-direction: column; }
  .hero-search-btn { width: 100%; }
  .hero-ctas { flex-direction: column; align-items: center; }
}
</style>
