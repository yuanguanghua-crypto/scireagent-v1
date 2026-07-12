<script setup>
import { watch } from 'vue'

const props = defineProps({
  /** JSON-LD structured data object to inject into document head. */
  data: {
    type: Object,
    required: true,
  },
})

/**
 * Inject a JSON-LD <script> tag into the document <head>.
 * Replaces any existing tag with the same id to avoid duplicates.
 * @param {Object} jsonLd - The JSON-LD data to serialize.
 */
function injectJsonLd(jsonLd) {
  const scriptId = 'scireagent-jsonld-head'
  const existing = document.getElementById(scriptId)
  if (existing) {
    existing.remove()
  }

  if (!jsonLd) {
    return
  }

  const script = document.createElement('script')
  script.id = scriptId
  script.type = 'application/ld+json'
  script.textContent = JSON.stringify(jsonLd, null, 2)
  document.head.appendChild(script)
}

/**
 * Remove the injected JSON-LD tag from the document head.
 */
function removeJsonLd() {
  const scriptId = 'scireagent-jsonld-head'
  const existing = document.getElementById(scriptId)
  if (existing) {
    existing.remove()
  }
}

// Watch for data changes and re-inject
watch(
  () => props.data,
  (val) => {
    injectJsonLd(val)
  },
  { immediate: true }
)
</script>

<template>
  <!-- Renders nothing visible; JSON-LD is injected into <head> -->
</template>
