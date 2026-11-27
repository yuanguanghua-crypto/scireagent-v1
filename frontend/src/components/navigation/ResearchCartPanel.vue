<script setup>
/**
 * ResearchCartPanel — Floating sidebar showing the user's research path.
 * Persists across pages via localStorage.
 */
import { useRouter } from 'vue-router'
import { useResearchPathStore } from '@/stores/researchPath'
import { toast } from '@/components/common'

const router = useRouter()
const cart = useResearchPathStore()

const TYPE_COLORS = {
  research_goal: 'var(--color-entity-rg)',
  application: 'var(--color-entity-app)',
  method: 'var(--color-entity-met)',
  protocol: 'var(--color-entity-protocol)',
  product: 'var(--color-entity-product)',
}

const TYPE_ROUTES = {
  research_goal: (id) => `/research-goals/${id}`,
  application: (id) => `/applications/${id}`,
  method: (id) => `/methods/${id}`,
  protocol: (id) => `/protocols/${id}`,
  product: (id) => `/products/${id}`,
}

function goTo(step) {
  const routeFn = TYPE_ROUTES[step.type]
  if (routeFn && step.id) router.push(routeFn(step.id))
}

function goToRFQ() {
  const products = cart.steps.filter(s => s.type === 'product')
  const query = products.length ? { product_id: products[0].id } : {}
  router.push({ path: '/quote-request', query })
}

function copyToClipboard() {
  const text = cart.toText()
  // ★ 2026-11-18（S4）：`alert` → `toast`。原生 alert 会阻塞主线程、按钮文案随
  // 浏览器语言走，且不进 DOM ⇒ e2e/单测都断言不到。
  navigator.clipboard?.writeText(text).then(() => {
    toast.success('Research path copied to clipboard!')
  })
}
</script>

<template>
  <!-- Floating trigger button -->
  <!-- ★ 2026-11-27（A-120 / A-182）：这是个**没有文字**的圆形图标 + 数字，
       页面里可读名称只有一个 "1"，没人知道它是 "My Research Path"（点开才知道）。
       改成胶囊：图标 + 文字标签 + 计数，并补 aria-label/title。 -->
  <button
    class="rc-trigger"
    v-if="cart.hasSteps"
    @click="cart.toggle()"
    :class="{ 'rc-trigger-open': cart.isOpen }"
    :aria-label="`My Research Path (${cart.count} item${cart.count === 1 ? '' : 's'})`"
    :title="`My Research Path (${cart.count})`"
  >
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2L2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>
    <span class="rc-trigger-label">My Research Path</span>
    <span class="rc-trigger-count">{{ cart.count }}</span>
  </button>

  <!-- Panel -->
  <Transition name="rc-slide">
    <div class="rc-panel" v-if="cart.isOpen">
      <div class="rc-header">
        <h3 class="rc-title">My Research Path</h3>
        <button class="rc-close" @click="cart.close()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>

      <div class="rc-steps">
        <div v-for="(step, idx) in cart.steps" :key="step.type + step.id" class="rc-step">
          <span class="rc-dot" :style="{ background: TYPE_COLORS[step.type] || 'var(--color-text-secondary)' }"></span>
          <div class="rc-step-info" @click="goTo(step)">
            <span class="rc-step-type">{{ step.type.replace('_', ' ') }}</span>
            <span class="rc-step-name">{{ step.name }}</span>
          </div>
          <button class="rc-step-remove" @click="cart.removeStep(step.type, step.id)" title="Remove">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
          </button>
        </div>
      </div>

      <div class="rc-actions">
        <button class="rc-btn rc-btn-primary" @click="goToRFQ">
          Request Quote
        </button>
        <button class="rc-btn rc-btn-outline" @click="copyToClipboard">
          Copy Path
        </button>
        <button class="rc-btn rc-btn-ghost" @click="cart.clear()">
          Clear
        </button>
      </div>
    </div>
  </Transition>
</template>

<style scoped>
/* Trigger button — fixed bottom-right */
.rc-trigger {
  position: fixed;
  bottom: 24px;
  right: 24px;
  z-index: 1000;
  /* ★ 2026-11-27（A-120/A-182）：由 48×48 圆形改为胶囊，让文字标签放得下 */
  height: 44px;
  padding: 0 14px;
  gap: 8px;
  border-radius: 999px;
  background: var(--color-primary, #059669);
  color: white;
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
  transition: all 0.2s;
}
.rc-trigger:hover { transform: scale(1.05); box-shadow: 0 6px 16px rgba(0,0,0,0.2); }
.rc-trigger-open { background: var(--color-text, #1e293b); }
.rc-trigger-label {
  font-size: 13px;
  font-weight: 600;
  font-family: var(--font-sans);
  white-space: nowrap;
}
/* 计数改为行内徽标（原先是 -4px 绝对定位，胶囊形态下会盖住文字） */
.rc-trigger-count {
  min-width: 20px;
  height: 20px;
  padding: 0 5px;
  background: var(--color-danger);
  color: white;
  font-size: 11px;
  font-weight: 700;
  border-radius: 999px;
  display: flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
}

/* 窄屏只留图标 + 计数：文字标签隐藏，但 aria-label/title 仍在（可读名称不丢） */
@media (max-width: 640px) {
  .rc-trigger { padding: 0 12px; }
  .rc-trigger-label { display: none; }
}

/* Panel — fixed right sidebar */
.rc-panel {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  width: 320px;
  z-index: 1001;
  background: var(--color-surface, #fff);
  border-left: 1px solid var(--color-border, #e2e8f0);
  box-shadow: -4px 0 24px rgba(0,0,0,0.1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}
.rc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 16px 20px;
  border-bottom: 1px solid var(--color-border, #e2e8f0);
}
.rc-title { font-size: 16px; font-weight: 700; margin: 0; color: var(--color-text, #1e293b); }
.rc-close {
  width: 28px; height: 28px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: none; cursor: pointer;
  color: var(--color-text-secondary, #64748b);
  border-radius: var(--radius-sm, 4px);
}
.rc-close:hover { background: var(--color-bg, #f8fafc); }

/* Steps */
.rc-steps { flex: 1; overflow-y: auto; padding: 12px 16px; }
.rc-step {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 8px 10px;
  border-radius: var(--radius-md, 8px);
  transition: background 0.15s;
}
.rc-step:hover { background: var(--color-bg, #f8fafc); }
.rc-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; }
.rc-step-info { flex: 1; min-width: 0; cursor: pointer; display: flex; flex-direction: column; gap: 1px; }
.rc-step-type { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em; color: var(--color-text-tertiary, #94a3b8); }
.rc-step-name { font-size: 13px; font-weight: 500; color: var(--color-text, #1e293b); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.rc-step-remove {
  width: 24px; height: 24px;
  display: flex; align-items: center; justify-content: center;
  background: none; border: none; cursor: pointer;
  color: var(--color-text-tertiary, #94a3b8);
  border-radius: var(--radius-sm, 4px);
  flex-shrink: 0;
}
.rc-step-remove:hover { background: var(--color-danger-bg); color: var(--color-danger); }

/* Actions */
.rc-actions {
  padding: 16px 20px;
  border-top: 1px solid var(--color-border, #e2e8f0);
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rc-btn {
  height: 36px;
  border-radius: var(--radius-md, 8px);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  font-family: var(--font-sans, system-ui);
  transition: all 0.15s;
}
.rc-btn-primary { background: var(--color-primary, #059669); color: white; border: none; }
.rc-btn-primary:hover { opacity: 0.9; }
.rc-btn-outline { background: transparent; color: var(--color-primary, #059669); border: 1px solid var(--color-primary, #059669); }
.rc-btn-outline:hover { background: var(--color-primary-subtle, #f0fdf4); }
.rc-btn-ghost { background: transparent; color: var(--color-text-secondary, #64748b); border: none; }
.rc-btn-ghost:hover { color: var(--color-text, #1e293b); }

/* Transition */
.rc-slide-enter-active, .rc-slide-leave-active { transition: transform 0.3s ease; }
.rc-slide-enter-from, .rc-slide-leave-to { transform: translateX(100%); }

@media (max-width: 768px) {
  .rc-panel { width: 100%; }
}
</style>
