<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import ParticleField from '@/components/hero/ParticleField.vue'

const props = defineProps({
  title: { type: String, default: 'SciReagent' },
  subtitle: { type: String, default: '' },
  suggestedSearches: { type: Array, default: () => [] },
  stats: { type: Object, default: () => ({ products: 118, skus: 293, methods: 10, protocols: 88, areas: 8 }) },
})

const router = useRouter()
const searchQuery = ref('')

function handleSearch() {
  if (searchQuery.value.trim()) {
    router.push({ path: '/search', query: { q: searchQuery.value } })
  }
}

function handleTagSearch(term) {
  searchQuery.value = term
  handleSearch()
}

const hotTags = ['ATP', 'PCR', 'Click Chemistry', 'Fluorescent Probes', 'Cell Assay']
const tags = props.suggestedSearches.length ? props.suggestedSearches : hotTags
</script>

<template>
  <section class="hero" aria-label="Platform introduction">
    <ParticleField class="hero-bg-canvas" />
    <div class="hero-container">
      <div class="hero-text">
        <div class="hero-badge">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><circle cx="12" cy="12" r="4" fill="currentColor"/></svg>
          Knowledge Graph · Powered Discovery
        </div>
        <h1 class="hero-title">
          From research goal to<br>
          <span class="hero-gradient">precision reagent</span>
        </h1>
        <p class="hero-subtitle">{{ subtitle || '118 high-purity products connected to 10 core methods and 88 standard protocols. Search by product, CAS, or method.' }}</p>

        <div class="hero-search">
          <div class="search-box">
            <input
              v-model="searchQuery"
              type="text"
              placeholder="Search products, CAS, methods…"
              @keyup.enter="handleSearch"
            />
            <button @click="handleSearch">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
              Search
            </button>
          </div>
          <div class="search-tags">
            <span>Popular:</span>
            <button v-for="tag in tags" :key="tag" class="tag" @click="handleTagSearch(tag)">{{ tag }}</button>
          </div>
        </div>

        <div class="hero-stats">
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.products || 0 }}</span>
            <span class="hero-stat-label">Products</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.skus || 0 }}</span>
            <span class="hero-stat-label">SKUs</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.methods || 0 }}</span>
            <span class="hero-stat-label">Methods</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.protocols || 0 }}</span>
            <span class="hero-stat-label">Protocols</span>
          </div>
          <div class="hero-stat">
            <span class="hero-stat-num">{{ stats.areas || 0 }}</span>
            <span class="hero-stat-label">Areas</span>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.hero {
  position: relative;
  overflow: hidden;
  background: linear-gradient(180deg, #0A1628 0%, #0F1F3D 60%, #0A1628 100%);
  padding: 100px 0 40px;
}
.hero::after {
  content: '';
  position: absolute;
  bottom: -2px;
  left: 0;
  right: 0;
  height: 160px;
  background: linear-gradient(to bottom, transparent 20%, var(--color-bg) 90%);
  pointer-events: none;
}
.hero-container {
  max-width: 1280px;
  margin: 0 auto;
  padding: 0 32px;
  position: relative;
  z-index: 2;
}
.hero-bg-canvas {
  position: absolute;
  inset: 0;
  z-index: 1;
}
.hero-text {
  max-width: 640px;
}
.hero-badge {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 5px 16px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  color: #CCFBF1;
  background: rgba(13, 109, 105, 0.2);
  border: 1px solid rgba(13, 109, 105, 0.3);
  margin-bottom: 20px;
  letter-spacing: 0.03em;
  text-transform: uppercase;
}
.hero-title {
  font-family: var(--font-display);
  font-size: clamp(34px, 4.5vw, 50px);
  font-weight: 700;
  line-height: 1.12;
  letter-spacing: -0.03em;
  color: #F1F5F9;
  margin: 0 0 16px;
}
.hero-gradient {
  background: linear-gradient(135deg, #5EEAD4 0%, #38BDF8 60%);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}
.hero-subtitle {
  font-size: 16px;
  color: #94A3B8;
  line-height: 1.7;
  margin: 0 0 32px;
  max-width: 520px;
}

/* Search */
.hero-search { max-width: 540px; }
.search-box {
  display: flex;
  align-items: center;
  background: rgba(255, 255, 255, 0.06);
  border: 1.5px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 4px;
  transition: all 0.25s cubic-bezier(0.16, 1, 0.3, 1);
  backdrop-filter: blur(8px);
}
.search-box:focus-within {
  border-color: rgba(94, 234, 212, 0.4);
  background: rgba(255, 255, 255, 0.09);
  box-shadow: 0 0 30px rgba(13, 109, 105, 0.15);
}
.search-box input {
  flex: 1;
  border: none;
  outline: none;
  padding: 13px 0 13px 18px;
  font-size: 15px;
  font-family: var(--font-body);
  color: #F1F5F9;
  background: transparent;
}
.search-box input::placeholder {
  color: #94A3B8;
  opacity: 0.6;
}
.search-box button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 10px 24px;
  border: none;
  border-radius: 8px;
  background: var(--color-teal-700);
  color: #fff;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: background 0.15s;
  font-family: var(--font-body);
}
.search-box button:hover {
  background: var(--color-teal-600);
}

/* Tags */
.search-tags {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 14px;
  flex-wrap: wrap;
}
.search-tags span {
  font-size: 13px;
  color: #64748B;
}
.tag {
  display: inline-flex;
  padding: 4px 14px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 500;
  color: #94A3B8;
  background: rgba(255, 255, 255, 0.06);
  border: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
  transition: all 0.15s;
  font-family: var(--font-body);
}
.tag:hover {
  color: #E2E8F0;
  background: rgba(255, 255, 255, 0.1);
}

/* Stats */
.hero-stats {
  display: flex;
  gap: 28px;
  margin-top: 36px;
}
.hero-stat {
  text-align: left;
}
.hero-stat-num {
  font-family: var(--font-display);
  font-size: 20px;
  font-weight: 700;
  color: #F1F5F9;
  line-height: 1;
  display: block;
}
.hero-stat-label {
  font-size: 12px;
  color: #64748B;
  font-weight: 500;
  margin-top: 2px;
  display: block;
}

@media (max-width: 768px) {
  .hero { padding: 80px 0 32px; }
  .hero-container { padding: 0 20px; }
  .hero-title { font-size: 28px; }
  .hero-stats { gap: 16px; flex-wrap: wrap; }
  .hero-stat-num { font-size: 18px; }
}
</style>
