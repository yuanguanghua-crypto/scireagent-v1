<script setup>
/**
 * 统一的**持久错误横幅**（D10）。
 *
 * ## 为什么需要它
 * 全站此前有两类错误提示，且不统一：
 *   · 列表页（`/orders`、`/ops/orders`）与详情**加载失败**只 `console.error` + 全局 4 秒 toast
 *     ⇒ 接口挂了页面直接落到「No orders yet」空态，**看起来就像"你真的没有订单"**（静默失败）。
 *   · 动作失败（`/ops/orders/:id`、`/checkout`）有持久 `.error-banner`，但**样式各自内联**两份。
 *
 * ⇒ 抽成公共组件：一处样式、一处语义，加载失败与动作失败都用它，靠 `kind` 区分
 *   （E2E 用 `.error-banner[data-kind="load"]` / `[data-kind="action"]` 分别断言）。
 *
 * ## 文案口径
 * `message` 由调用方用 `extractErrorMessage(err.response?.data, fallback)` 提取
 * ⇒ 与全局 toast **同一句后端文案**，不会出现"toast 说 A、横幅说 B"。
 */
defineProps({
  /** 错误文案；为空时不渲染 */
  message: { type: String, default: '' },
  /** 可选标题（如 "Couldn't load orders"） */
  title: { type: String, default: '' },
  /** 'load' = 加载失败；'action' = 动作失败。仅用于断言与样式微调 */
  kind: { type: String, default: 'load' },
})
</script>

<template>
  <div v-if="message || title" class="error-banner" :data-kind="kind" role="alert">
    <strong v-if="title" class="error-banner-title">{{ title }}</strong>
    <span v-if="message" class="error-banner-msg">{{ message }}</span>
    <slot />
  </div>
</template>

<style scoped>
.error-banner {
  padding: 12px 16px;
  background: var(--color-danger-bg);
  border: 1px solid var(--color-danger);
  border-radius: var(--radius-md);
  color: var(--color-danger);
  font-size: 14px;
  margin-bottom: 16px;
}
.error-banner-title { margin-right: 8px; }
</style>
