<script setup>
/**
 * 合规文档实时预览弹窗（COA / SDS 共用）。
 *
 * 方案：iframe 加载 /coa-preview.html 或 /sds-preview.html（含 bridge 脚本），
 * @load 后向 iframe postMessage 真实 serializer 数据（携带 __type 标记）。
 * 模板侧 bridge 脚本监听 message 渲染真实字段；未收到消息时保持硬编码样本。
 */
import { ref, computed, watch } from 'vue'

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

function onLoad() {
  if (!frame.value || !frame.value.contentWindow) return
  const payload = { ...props.previewData, __type: props.type }
  frame.value.contentWindow.postMessage(payload, location.origin)
}

function close() {
  emit('close')
}

// 弹窗打开后若数据变化，重新 postMessage 给 iframe
watch(
  () => props.previewData,
  () => {
    if (props.visible) onLoad()
  },
  { deep: true }
)
</script>

<template>
  <div v-if="visible" class="preview-overlay" @click.self="close">
    <div class="preview-dialog" role="dialog" aria-modal="true">
      <div class="preview-header">
        <h3>{{ type === 'sds' ? 'SDS 实时预览' : 'COA 实时预览' }}</h3>
        <button class="preview-close" type="button" @click="close" aria-label="关闭">✕</button>
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
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid var(--color-border);
}
.preview-header h3 {
  margin: 0;
  font-size: 15px;
  color: var(--color-text);
}
.preview-close {
  border: none;
  background: transparent;
  font-size: 16px;
  cursor: pointer;
  color: var(--color-text-secondary);
  line-height: 1;
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
