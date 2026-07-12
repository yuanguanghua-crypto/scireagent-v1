import { watch, onUnmounted } from 'vue'

/**
 * Composable to inject JSON-LD structured data into the page head.
 *
 * Accepts either a Vue Ref or a plain object. When a Ref is provided,
 * the injected script tag is automatically updated whenever the Ref changes
 * and cleaned up on component unmount.
 *
 * @param {import('vue').Ref<Object>|Object} data - Reactive JSON-LD data or plain object.
 *
 * @example
 * // Usage with a Ref:
 * const jsonLd = ref({ '@type': 'Product', name: 'My Product' })
 * useJsonLd(jsonLd)
 *
 * @example
 * // Usage with a plain object:
 * useJsonLd({ '@type': 'Product', name: 'My Product' })
 */
export function useJsonLd(data) {
  const scriptId = 'scireagent-jsonld'

  /**
   * Inject a JSON-LD script tag into the document head.
   * Removes any previous instance first.
   * @param {Object|null} jsonLd - The JSON-LD data to serialize.
   */
  function inject(jsonLd) {
    remove()
    if (!jsonLd) {
      return
    }
    const script = document.createElement('script')
    script.id = scriptId
    script.type = 'application/ld+json'
    script.textContent = JSON.stringify(jsonLd)
    document.head.appendChild(script)
  }

  /**
   * Remove the injected JSON-LD script tag from the document head.
   */
  function remove() {
    const existing = document.getElementById(scriptId)
    if (existing) {
      existing.remove()
    }
  }

  // Determine if data is a Vue Ref (has .value property) or a plain object
  if (data && typeof data === 'object' && 'value' in data) {
    // It's a Ref — watch for changes
    watch(data, (val) => inject(val), { immediate: true })
  } else {
    // Plain object — inject once immediately
    inject(data)
  }

  // Cleanup on unmount
  onUnmounted(remove)
}
