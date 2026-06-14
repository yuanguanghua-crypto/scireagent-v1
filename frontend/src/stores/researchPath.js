import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

/**
 * Research Path Store — Tracks the user's research journey.
 * Persists to localStorage so the path survives page refreshes.
 */
export const useResearchPathStore = defineStore('researchPath', () => {
  const STORAGE_KEY = 'scireagent_research_path'

  /* ── State ── */
  const steps = ref([]) // Array of { type, id, name, slug?, timestamp }
  const isOpen = ref(false) // Sidebar visibility

  /* ── Load from localStorage on init ── */
  function load() {
    try {
      const saved = localStorage.getItem(STORAGE_KEY)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) steps.value = parsed
      }
    } catch {}
  }

  /* ── Save to localStorage ── */
  function save() {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(steps.value))
    } catch {}
  }

  /* ── Add a step (deduplicate by type+id) ── */
  function addStep(type, id, name, slug = '') {
    const key = `${type}_${id}`
    // Remove existing entry with same key
    steps.value = steps.value.filter(s => `${s.type}_${s.id}` !== key)
    // Add to end
    steps.value.push({ type, id, name, slug, timestamp: Date.now() })
    save()
  }

  /* ── Remove a step ── */
  function removeStep(type, id) {
    steps.value = steps.value.filter(s => !(s.type === type && s.id === id))
    save()
  }

  /* ── Clear all steps ── */
  function clear() {
    steps.value = []
    save()
  }

  /* ── Toggle sidebar ── */
  function toggle() { isOpen.value = !isOpen.value }
  function open() { isOpen.value = true }
  function close() { isOpen.value = false }

  /* ── Computed ── */
  const count = computed(() => steps.value.length)
  const hasSteps = computed(() => steps.value.length > 0)
  const lastStep = computed(() => steps.value[steps.value.length - 1] || null)

  /* ── Export as text (for clipboard/PDF) ── */
  function toText() {
    if (!steps.value.length) return ''
    const lines = ['SciReagent Research Path', '========================', '']
    for (const step of steps.value) {
      lines.push(`${step.type.replace('_', ' ')}: ${step.name}`)
    }
    lines.push('', `Generated: ${new Date().toLocaleString()}`)
    return lines.join('\n')
  }

  /* ── Export as RFQ payload ── */
  function toRFQPayload() {
    return {
      products: steps.value.filter(s => s.type === 'product').map(s => ({ id: s.id, name: s.name })),
      research_context: steps.value.map(s => `${s.type}: ${s.name}`).join(' > '),
    }
  }

  // Auto-load on store creation
  load()

  return {
    steps, isOpen, count, hasSteps, lastStep,
    addStep, removeStep, clear, toggle, open, close,
    toText, toRFQPayload, load, save,
  }
})
