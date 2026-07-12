import { defineStore } from 'pinia'
import { ref, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'

/**
 * Research Path Store - Tracks the user's research journey.
 *
 * 存储隔离策略：
 *  - 未登录游客：sessionStorage（仅当前会话有效，关闭浏览器即清空，不跨会话残留）
 *  - 登录用户：localStorage，按 user id 隔离（`scireagent_research_path_user_<id>`）
 *  - 登录瞬间：把游客会话期间收集的路径合并到用户持久存储，避免登录即丢失
 *  - 登出瞬间：清空内存路径，回到游客会话空状态
 */
export const useResearchPathStore = defineStore('researchPath', () => {
  const GUEST_KEY = 'scireagent_research_path_guest'
  const LEGACY_KEY = 'scireagent_research_path' // 旧未隔离 key，一次性清理

  function userKey(userId) {
    return `scireagent_research_path_user_${userId}`
  }

  /* ── State ── */
  const steps = ref([]) // Array of { type, id, name, slug?, timestamp }
  const isOpen = ref(false) // Sidebar visibility

  /* ── 根据登录态决定存储位置与 key ── */
  function getStorageInfo() {
    const auth = useAuthStore()
    const userId = auth.user?.id
    if (userId) {
      return { storage: localStorage, key: userKey(userId) }
    }
    return { storage: sessionStorage, key: GUEST_KEY }
  }

  /* ── Load from current storage ── */
  function load() {
    try {
      const { storage, key } = getStorageInfo()
      const saved = storage.getItem(key)
      if (saved) {
        const parsed = JSON.parse(saved)
        if (Array.isArray(parsed)) {
          steps.value = parsed
          return
        }
      }
    } catch {}
    steps.value = []
  }

  /* ── Save to current storage ── */
  function save() {
    try {
      const { storage, key } = getStorageInfo()
      storage.setItem(key, JSON.stringify(steps.value))
    } catch {}
  }

  /* ── Add a step (deduplicate by type+id) ── */
  function addStep(type, id, name, slug = '') {
    const key = `${type}_${id}`
    steps.value = steps.value.filter(s => `${s.type}_${s.id}` !== key)
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

  /* ── 一次性清理旧的未隔离存储 ── */
  try { localStorage.removeItem(LEGACY_KEY) } catch {}

  /* ── 初始加载 ── */
  load()

  /* ── 登录态变化：切换存储并迁移/清空 ── */
  watch(
    () => useAuthStore().user?.id || null,
    (newId, oldId) => {
      if (newId === oldId) return
      if (newId) {
        // 登录：把游客会话期间收集的路径合并到用户持久存储
        const guestSteps = steps.value
        try {
          const { storage, key } = getStorageInfo() // 此时为用户存储
          let userSteps = []
          const saved = storage.getItem(key)
          if (saved) {
            const parsed = JSON.parse(saved)
            if (Array.isArray(parsed)) userSteps = parsed
          }
          const existing = new Set(userSteps.map(s => `${s.type}_${s.id}`))
          const merged = [...userSteps]
          for (const s of guestSteps) {
            if (!existing.has(`${s.type}_${s.id}`)) merged.push(s)
          }
          steps.value = merged
          save()
          try { sessionStorage.removeItem(GUEST_KEY) } catch {}
        } catch {
          load()
        }
      } else {
        // 登出：清空内存，回到游客会话空状态
        steps.value = []
        try { sessionStorage.removeItem(GUEST_KEY) } catch {}
      }
    }
  )

  return {
    steps, isOpen, count, hasSteps, lastStep,
    addStep, removeStep, clear, toggle, open, close,
    toText, toRFQPayload, load, save,
  }
})
