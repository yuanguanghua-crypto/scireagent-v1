<script setup>
defineProps({
  references: { type: Array, default: () => [] },
})
</script>

<template>
  <section v-if="references.length" class="section" aria-label="Recent Publications">
    <div class="section-header">
      <h2 class="section-title">Recent Publications</h2>
    </div>
    <div class="refs-list">
      <div v-for="ref in references" :key="ref.id" class="ref-item">
        <h4 class="ref-title">{{ ref.title }}</h4>
        <div class="ref-meta">
          <span v-if="ref.journal" class="ref-journal">{{ ref.journal }}</span>
          <span v-if="ref.year" class="ref-year">{{ ref.year }}</span>
        </div>
        <a v-if="ref.doi" :href="`https://doi.org/${ref.doi}`" target="_blank" rel="noopener" class="ref-doi">
          DOI: {{ ref.doi }}
        </a>
      </div>
    </div>
  </section>
</template>

<style scoped>
.section { margin-bottom: 32px; }
.section-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;
}
.section-title {
  font-size: 20px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}
.refs-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ref-item {
  padding: 14px 16px;
  background: var(--color-surface);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  transition: border-color 0.15s;
}
.ref-item:hover { border-color: var(--color-primary); }
.ref-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 6px;
  line-height: 1.4;
}
.ref-meta {
  display: flex;
  gap: 12px;
  margin-bottom: 4px;
}
.ref-journal {
  font-size: 13px;
  color: var(--color-primary);
  font-weight: 500;
}
.ref-year {
  font-size: 13px;
  color: var(--color-text-secondary);
}
.ref-doi {
  font-size: 12px;
  color: var(--color-text-secondary);
  text-decoration: none;
  font-family: var(--font-mono);
}
.ref-doi:hover { color: var(--color-primary); text-decoration: underline; }
</style>
