<script setup>
/**
 * 合规文档实时预览弹窗（COA / SDS 共用）。
 *
 * 方案：iframe 加载 /coa-preview.html 或 /sds-preview.html（含 bridge 脚本），
 * 通过 postMessage 把真实 serializer 数据送进模板渲染。
 *
 * ★ 2026-11-20（A-052 / A-150）投递可靠性改造 —— 起因：QA 看到 SDS/COA 预览里
 *   显示的是**另一个产品**（模板里的 SC8001 硬编码样本）的完整文档。实测确认：
 *     · 模板侧 bridge 契约正常（一条消息就能把样本全覆盖）；
 *     · 生产 dist 的模板与仓库 md5 完全一致，不是陈旧构建；
 *     · 本地真实页面首次打开（SDS、COA）都正确。
 *   ⇒ 触发条件未能复现，但**失效形态是确定的**：单次 fire-and-forget `postMessage`，
 *     没有任何确认；一旦消息没送达/没被应用，模板就回落成别人的文档，且**无声无息**。
 *
 *   本组件因此改成握手协议 + 显式状态，并把"投递失败"变成可见的失败：
 *     1. 模板就绪后先发 `{__type, __ready}`，父侧收到即投递（不再只靠 @load 一次机会）；
 *     2. 投递后模板回 `{__type, __ack}`，父侧收到才算成功；
 *     3. 700ms 未回执自动重投，最多 3 次；仍失败 ⇒ status='failed'，界面写明
 *        「数据未送达，请重试或改用 Download」，**绝不把空白/他人数据当成功**；
 *     4. payload 走 JSON 深拷贝：Vue 的 reactive 代理**无法被结构化克隆**
 *        （实测 `postMessage(reactive)` 抛 DataCloneError），深拷贝顺带消除这类失败；
 *     5. 模板本身已内置中性占位、不含任何产品样本（见 public/*-preview.html 头注）。
 *
 *   ⚠️ 模板与父侧是**成对**的协议：改一边必须改另一边。回归用例
 *      `frontend/test/verify-preview-consistency.cjs` 同时覆盖"送达"与"未送达"两种形态。
 */
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  visible: { type: Boolean, default: false },
  type: { type: String, default: 'coa' }, // 'coa' | 'sds'
  previewData: { type: Object, default: () => ({}) },
})
const emit = defineEmits(['close'])

const frame = ref(null)
const previewUrl = computed(() =>
  props.type === 'sds' ? '/sds-preview.html' : '/coa-preview.html'
)

// idle | loading | ok | failed —— 界面据此显示投递结果，不再静默
const status = ref('idle')
const MAX_RETRY = 3
const RETRY_MS = 700
let retryTimer = null
let attempts = 0

function clearRetry() {
  if (retryTimer) { clearTimeout(retryTimer); retryTimer = null }
}

/** 与旧实现载荷等价，但先做 JSON 深拷贝：reactive 代理不可结构化克隆。 */
function buildPayload() {
  let plain
  try {
    plain = JSON.parse(JSON.stringify(props.previewData || {}))
  } catch (_) {
    // 含循环引用等极端情况：退回浅拷贝（旧行为，至少不比之前差）
    plain = { ...(props.previewData || {}) }
  }
  return { ...plain, __type: props.type }
}

function send() {
  const win = frame.value && frame.value.contentWindow
  if (!win) return
  clearRetry()
  status.value = 'loading'
  try {
    win.postMessage(buildPayload(), location.origin)
  } catch (e) {
    // 理论上深拷贝后不会再抛；真抛了就明确失败，不假装成功
    status.value = 'failed'
    return
  }
  retryTimer = setTimeout(() => {
    attempts += 1
    if (attempts >= MAX_RETRY) { status.value = 'failed'; return }
    send()
  }, RETRY_MS)
}

function onLoad() {
  attempts = 0
  send()
}

/** 模板 → 父侧：__ready（就绪）/ __ack（已渲染）。只认当前 iframe 的消息。 */
function onMessage(e) {
  const win = frame.value && frame.value.contentWindow
  if (!win || e.source !== win) return
  const d = e.data
  if (!d || typeof d !== 'object' || d.__type !== props.type) return
  if (d.__ready) {
    attempts = 0
    send()
    return
  }
  if (Object.prototype.hasOwnProperty.call(d, '__ack')) {
    clearRetry()
    status.value = d.__ack === false ? 'failed' : 'ok'
    if (d.__ack !== false) attempts = 0
  }
}

function close() {
  emit('close')
}

onMounted(() => window.addEventListener('message', onMessage))
onUnmounted(() => {
  window.removeEventListener('message', onMessage)
  clearRetry()
})

// 弹窗打开后若数据变化，重新投递
watch(
  () => props.previewData,
  () => {
    if (props.visible) { attempts = 0; send() }
  },
  { deep: true }
)

const statusText = computed(() => {
  if (status.value === 'loading') return 'Loading document data…'
  if (status.value === 'ok') return 'Document data delivered'
  if (status.value === 'failed') return 'Document data was not delivered — close and retry, or use Download.'
  return ''
})
</script>

<template>
  <div v-if="visible" class="preview-overlay" @click.self="close">
    <div class="preview-dialog" role="dialog" aria-modal="true">
      <div class="preview-header">
        <h3>{{ type === 'sds' ? 'SDS Live Preview' : 'COA Live Preview' }}</h3>
        <span
          v-if="statusText"
          class="preview-status"
          :class="`preview-status--${status}`"
          role="status"
          data-testid="preview-status"
        >{{ statusText }}</span>
        <button class="preview-close" type="button" @click="close" aria-label="Close">✕</button>
      </div>
      <div class="preview-body">
        <iframe ref="frame" :src="previewUrl" @load="onLoad" title="document preview"></iframe>
      </div>
    </div>
  </div>
</template>

<style scoped>
.preview-overlay {
  position: fixed;
  inset: 0;
  background: rgba(15, 23, 42, 0.6);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: 24px;
}
.preview-dialog {
  background: #fff;
  border-radius: 10px;
  width: min(920px, 96vw);
  max-height: 92vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.3);
}
.preview-header {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.preview-header h3 {
  margin: 0;
  font-size: 15px;
  color: var(--color-text);
  flex: 0 0 auto;
}
.preview-status {
  flex: 1 1 auto;
  font-size: 11px;
  color: var(--color-text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.preview-status--ok { color: #15803d; }
.preview-status--failed { color: #b91c1c; font-weight: 600; }
.preview-close {
  border: none;
  background: transparent;
  font-size: 16px;
  cursor: pointer;
  color: var(--color-text-secondary);
  line-height: 1;
  flex: 0 0 auto;
}
.preview-close:hover { color: var(--color-text); }
.preview-body {
  flex: 1;
  overflow: auto;
  background: var(--color-border);
}
.preview-body iframe {
  width: 100%;
  height: 80vh;
  border: none;
  background: var(--color-surface);
}
</style>
