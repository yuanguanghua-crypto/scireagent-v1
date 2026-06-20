<script setup>
import { ref, computed } from 'vue'

const props = defineProps({
  title: { type: String, required: true },
  items: { type: Array, default: () => [] },
  defaultShow: { type: Number, default: 3 },
  itemType: { type: String, default: '' },
  fallbackMsg: { type: String, default: '' },
  fallbackLink: { type: String, default: '' },
  fallbackLinkText: { type: String, default: '' },
})

const expanded = ref(false)

const visibleItems = computed(() => {
  if (expanded.value || props.items.length <= props.defaultShow) return props.items
  return props.items.slice(0, props.defaultShow)
})

const hiddenCount = computed(() => Math.max(0, props.items.length - props.defaultShow))

function toggle() {
  expanded.value = !expanded.value
}
</script>

<template>
  <section class="pd-section">
    <h2 class="pd-section-title">{{ title }}</h2>

    <!-- Items present -->
    <div v-if="items.length" class="pd-card-grid">
      <slot
        v-for="item in visibleItems"
        :key="item.id"
        name="item"
        :item="item"
      >
        <!-- fallback: plain text item -->
        <div class="pd-card">{{ item.name || item.title }}</div>
      </slot>
    </div>

    <!-- Show all / collapse toggle -->
    <button
      v-if="hiddenCount > 0"
      class="expand-toggle"
      @click="toggle"
    >
      {{ expanded ? 'Show less' : `Show all ${items.length} →` }}
    </button>

    <!-- Empty state -->
    <div v-if="!items.length && fallbackMsg" class="pd-fallback">
      <p>{{ fallbackMsg }}</p>
      <router-link v-if="fallbackLink" :to="fallbackLink" class="pd-fallback-link">{{ fallbackLinkText || 'Browse all' }} &rarr;</router-link>
    </div>
  </section>
</template>

<style scoped>
.expand-toggle {
  display: block; margin-top: 8px; padding: 6px 16px;
  background: transparent; border: 1px solid var(--color-border);
  border-radius: var(--radius-md); font-size: 13px; font-weight: 500;
  color: var(--color-primary); cursor: pointer; font-family: var(--font-sans);
  transition: all 0.15s;
}
.expand-toggle:hover {
  border-color: var(--color-primary);
  background: var(--color-primary-subtle);
}
</style>
