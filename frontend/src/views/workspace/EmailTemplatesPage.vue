<script setup>
/**
 * 邮件模板编辑 —— 替代 Django admin 改文案。
 *
 * 三个刻意的设计：
 * 1. **预览不写库**：先看效果再保存。`_SafeDict` 会把缺失的占位符静默渲染成空串，
 *    所以"渲染成功"不等于"没问题" —— 预览会显式报出缺失键和残留花括号。
 * 2. **预览默认用真实历史上下文**：后端自动取最近一条同模板 outbox 的 context_json，
 *    比手编 `{order_no: "X"}` 可靠得多（真实字段名、真实格式）。
 * 3. **试发只能发给自己**：收件人由后端固定为当前登录邮箱，前端不提供输入框 ——
 *    否则这个页面就成了"用公司域名给任意人发信"的通道。
 */
import { onMounted, ref, computed } from 'vue'
import {
  getEmailTemplates, getEmailTemplate, updateEmailTemplate,
  previewEmailTemplate, sendTestEmail,
} from '@/api/system'
import { extractErrorMessage } from '@/utils/http'

const list = ref([])
const loadingList = ref(false)
const error = ref('')
const flash = ref('')

const current = ref(null)          // 原始模板（库里的版本）
const draft = ref({ subject: '', body_html: '', body_text: '' })
const loadingDetail = ref(false)
const saving = ref(false)
const sending = ref(false)
const previewing = ref(false)
const preview = ref(null)

const dirty = computed(() => {
  if (!current.value) return false
  const d = draft.value
  const t = current.value
  return d.subject !== t.subject || d.body_html !== t.body_html || d.body_text !== t.body_text
})

function say(msg) {
  flash.value = msg
  window.setTimeout(() => { flash.value = '' }, 3500)
}

async function loadList() {
  loadingList.value = true
  error.value = ''
  try {
    const res = await getEmailTemplates()
    list.value = res.data ?? res
    if (!current.value && list.value.length) await select(list.value[0].key)
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load templates.")
  } finally {
    loadingList.value = false
  }
}

async function select(key) {
  if (dirty.value && !window.confirm('当前有未保存的修改，切换模板会丢失。继续？')) return
  loadingDetail.value = true
  preview.value = null
  error.value = ''
  try {
    const res = await getEmailTemplate(key)
    const d = res.data ?? res
    current.value = d
    draft.value = { subject: d.subject, body_html: d.body_html, body_text: d.body_text }
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't load this template.")
  } finally {
    loadingDetail.value = false
  }
}

async function doPreview() {
  if (!current.value) return
  previewing.value = true
  error.value = ''
  try {
    const res = await previewEmailTemplate(current.value.key, {
      // 传草稿而不是库里的版本 —— 才能预览"改到一半"的效果
      subject_override: draft.value.subject,
      body_html_override: draft.value.body_html,
      body_text_override: draft.value.body_text,
    })
    preview.value = res.data ?? res
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Preview failed.")
  } finally {
    previewing.value = false
  }
}

async function save() {
  if (!current.value) return
  saving.value = true
  error.value = ''
  try {
    const res = await updateEmailTemplate(current.value.key, {
      subject: draft.value.subject,
      body_html: draft.value.body_html,
      body_text: draft.value.body_text,
    })
    current.value = res.data ?? res
    say('已保存')
    await loadList()
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't save.")
  } finally {
    saving.value = false
  }
}

async function sendTest() {
  if (!current.value) return
  if (!window.confirm('发一封测试邮件到你自己的邮箱？\n（使用当前草稿内容，不改动已保存的版本）')) return
  sending.value = true
  error.value = ''
  try {
    const res = await sendTestEmail(current.value.key, {
      subject_override: draft.value.subject,
      body_html_override: draft.value.body_html,
      body_text_override: draft.value.body_text,
    })
    const d = res.data ?? res
    say(`已入队，发往 ${d.to}（cron 1 分钟内投递）`)
  } catch (e) {
    error.value = extractErrorMessage(e?.response?.data ?? e, "Couldn't queue the test email.")
  } finally {
    sending.value = false
  }
}

onMounted(loadList)
</script>

<template>
  <div class="et-page">
    <div class="et-header">
      <div>
        <h1 class="et-title">Email Templates</h1>
        <p class="et-sub">改文案 → 预览（不写库）→ 保存 / 试发到自己邮箱</p>
      </div>
      <button class="et-btn" :disabled="loadingList" @click="loadList">
        {{ loadingList ? 'Refreshing…' : 'Refresh' }}
      </button>
    </div>

    <div v-if="error" class="et-alert et-alert--err">{{ error }}</div>
    <div v-if="flash" class="et-alert et-alert--ok">{{ flash }}</div>

    <div class="et-grid">
      <!-- 左：模板列表 -->
      <aside class="et-list">
        <button
          v-for="t in list" :key="t.key"
          class="et-list-item"
          :class="{ 'is-active': current && current.key === t.key }"
          @click="select(t.key)"
        >
          <span class="et-list-key">{{ t.key }}</span>
          <span class="et-list-subj">{{ t.subject }}</span>
        </button>
        <p v-if="!list.length && !loadingList" class="et-empty">No templates.</p>
      </aside>

      <!-- 右：编辑器 -->
      <section class="et-editor" v-if="loadingDetail">
        <p class="et-empty">Loading…</p>
      </section>
      <section class="et-editor" v-else-if="current">
        <div class="et-editor-head">
          <code class="et-key">{{ current.key }}</code>
          <span v-if="dirty" class="et-dirty">unsaved</span>
        </div>

        <label class="et-field">
          <span>Subject</span>
          <input v-model="draft.subject" class="et-input" />
        </label>

        <label class="et-field">
          <span>HTML body</span>
          <textarea v-model="draft.body_html" class="et-textarea" rows="10" spellcheck="false"></textarea>
        </label>

        <label class="et-field">
          <span>Plain text body</span>
          <textarea v-model="draft.body_text" class="et-textarea" rows="5" spellcheck="false"></textarea>
        </label>

        <div class="et-actions">
          <button class="et-btn" :disabled="previewing" @click="doPreview">
            {{ previewing ? 'Rendering…' : 'Preview' }}
          </button>
          <button class="et-btn et-btn--primary" :disabled="saving || !dirty" @click="save">
            {{ saving ? 'Saving…' : (dirty ? 'Save changes' : 'Saved') }}
          </button>
          <button class="et-btn" :disabled="sending" @click="sendTest">
            {{ sending ? 'Queueing…' : 'Send test to me' }}
          </button>
        </div>

        <!-- 预览结果 -->
        <div v-if="preview" class="et-preview">
          <div class="et-preview-head">
            <b>Preview</b>
            <span class="et-ctx-src">
              context: {{ preview.ctx_source === 'request' ? 'provided' : 'last real email' }}
            </span>
          </div>

          <div v-if="(preview.warnings || []).length" class="et-warn">
            <div v-for="(w, i) in preview.warnings" :key="i">⚠ {{ w }}</div>
          </div>

          <dl class="et-kv">
            <dt>Subject</dt><dd>{{ preview.subject.rendered }}</dd>
            <dt>Placeholders</dt>
            <dd class="et-mono">{{ (preview.text.placeholders || []).join(', ') || '—' }}</dd>
            <dt>Missing in ctx</dt>
            <dd class="et-mono">
              {{ [...new Set([...(preview.text.missing_in_ctx || []), ...(preview.html.missing_in_ctx || [])])].join(', ') || '—' }}
            </dd>
          </dl>

          <!-- 用 iframe 隔离样式：模板里的 CSS 不该影响这个页面 -->
          <p class="et-preview-label">HTML</p>
          <iframe
            class="et-frame"
            title="Email preview"
            sandbox=""
            :srcdoc="preview.html.rendered"
          ></iframe>

          <p class="et-preview-label">Plain text</p>
          <pre class="et-pre">{{ preview.text.rendered }}</pre>

          <details class="et-ctx">
            <summary>Context used ({{ Object.keys(preview.ctx_used || {}).length }} keys)</summary>
            <pre class="et-pre">{{ JSON.stringify(preview.ctx_used, null, 2) }}</pre>
          </details>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.et-page { padding: 24px; max-width: 1320px; }
.et-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 16px; }
.et-title { font-size: 20px; font-weight: 700; margin: 0 0 4px; color: var(--color-text, #111827); }
.et-sub { font-size: 13px; color: var(--color-text-tertiary, #6b7280); margin: 0; }

.et-alert { padding: 9px 14px; border-radius: 6px; font-size: 13px; margin-bottom: 12px; }
.et-alert--err { background: #fef2f2; border: 1px solid #fecaca; color: #b91c1c; }
.et-alert--ok { background: #f0fdf4; border: 1px solid #bbf7d0; color: #15803d; }

.et-grid { display: grid; grid-template-columns: 260px minmax(0, 1fr); gap: 16px; align-items: start; }
@media (max-width: 900px) { .et-grid { grid-template-columns: 1fr; } }

.et-list {
  border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; overflow: hidden;
  max-height: 70vh; overflow-y: auto;
}
.et-list-item {
  display: flex; flex-direction: column; gap: 2px; width: 100%; text-align: left;
  padding: 8px 12px; border: none; border-bottom: 1px solid var(--color-border, #f3f4f6);
  background: var(--color-bg, #fff); cursor: pointer;
}
.et-list-item:hover { background: #f9fafb; }
.et-list-item.is-active { background: #eff6ff; }
.et-list-key { font-size: 12.5px; font-family: ui-monospace, Menlo, monospace; color: var(--color-text, #111827); }
.et-list-subj {
  font-size: 11.5px; color: var(--color-text-tertiary, #6b7280);
  white-space: nowrap; overflow: hidden; text-overflow: ellipsis;
}

.et-editor { border: 1px solid var(--color-border, #e5e7eb); border-radius: 8px; padding: 16px; min-width: 0; }
.et-editor-head { display: flex; align-items: center; gap: 10px; margin-bottom: 12px; }
.et-key { font-size: 13px; background: #f3f4f6; padding: 2px 8px; border-radius: 4px; }
.et-dirty { font-size: 11px; color: #b45309; background: #fef3c7; padding: 2px 8px; border-radius: 8px; }

.et-field { display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }
.et-field > span { font-size: 12px; color: var(--color-text-tertiary, #6b7280); }
.et-input, .et-textarea {
  padding: 8px 10px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  font-size: 13px; background: var(--color-bg, #fff); color: var(--color-text, #111827);
}
.et-textarea { font-family: ui-monospace, Menlo, monospace; line-height: 1.5; resize: vertical; }

.et-actions { display: flex; gap: 8px; flex-wrap: wrap; margin: 4px 0 16px; }
.et-btn {
  padding: 7px 14px; border: 1px solid var(--color-border, #d1d5db); border-radius: 6px;
  background: var(--color-bg, #fff); color: var(--color-text, #111827); font-size: 13px; cursor: pointer;
}
.et-btn--primary { background: var(--color-primary, #2563eb); border-color: var(--color-primary, #2563eb); color: #fff; }
.et-btn:disabled { opacity: .5; cursor: not-allowed; }

.et-preview { border-top: 1px solid var(--color-border, #e5e7eb); padding-top: 14px; }
.et-preview-head { display: flex; align-items: baseline; justify-content: space-between; margin-bottom: 8px; }
.et-preview-head b { font-size: 14px; }
.et-ctx-src { font-size: 11px; color: var(--color-text-tertiary, #6b7280); }
.et-warn { background: #fffbeb; border: 1px solid #fde68a; color: #92400e; border-radius: 6px; padding: 8px 12px; font-size: 12.5px; margin-bottom: 10px; }
.et-kv { display: grid; grid-template-columns: 120px minmax(0, 1fr); gap: 4px 10px; margin: 0 0 12px; }
.et-kv dt { font-size: 12px; color: var(--color-text-tertiary, #6b7280); }
.et-kv dd { margin: 0; font-size: 12.5px; overflow-wrap: anywhere; }
.et-mono { font-family: ui-monospace, Menlo, monospace; }
.et-preview-label { font-size: 12px; color: var(--color-text-tertiary, #6b7280); margin: 10px 0 4px; }
.et-frame { width: 100%; height: 320px; border: 1px solid var(--color-border, #e5e7eb); border-radius: 6px; background: #fff; }
.et-pre {
  background: #f9fafb; border: 1px solid var(--color-border, #e5e7eb); border-radius: 6px;
  padding: 10px 12px; font-size: 12px; line-height: 1.55; white-space: pre-wrap;
  overflow-wrap: anywhere; max-height: 240px; overflow-y: auto; margin: 0;
}
.et-ctx { margin-top: 10px; }
.et-ctx summary { font-size: 12px; color: var(--color-text-tertiary, #6b7280); cursor: pointer; }
.et-empty { color: var(--color-text-tertiary, #6b7280); font-size: 13px; padding: 16px; }
@media (max-width: 720px) { .et-page { padding: 16px; } }
</style>
