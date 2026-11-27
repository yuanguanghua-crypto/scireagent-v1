<script setup>
import { ref, reactive, watch } from 'vue'
import { useRouter } from 'vue-router'
import StarDot from '@/components/common/StarDot.vue'

const props = defineProps({
  stats: {
    type: Object,
    // ★ 2026-11-27（A-121 顺带）：默认值原本是一组**编造的**数字
    //   （118 / 293 / 10 / 88 / 8）—— 数据没到时页面会煞有介事地显示这些假数。
    //   宁可显示 0 也不编。
    default: () => ({ products: 0, skus: 0, methods: 0, protocols: 0, areas: 0 }),
  },
})

const router = useRouter()
const rootEl = ref(null)

/**
 * ★ 2026-11-27（A-121）：**初值就是真实计数，不再从 0 往上滚。**
 *
 * 原实现 `display` 全为 0，靠 IntersectionObserver 在滚动入视口时把
 * 0 → 真实值 数上去。后果有三个，都不是审美问题：
 *   1. 首屏/静态快照读到的是 "0 Products · 0 SKUs / 0 Methods / 0 Protocols"，
 *      看起来像站点没有数据（访客回归 D-01 报的就是这个）；
 *   2. 有人截图、打印、或 JS 动画被 `prefers-reduced-motion` 之类挡住时，
 *      看到的永久是 0；
 *   3. 计数过程中还会出现 11,035 这类**从未真实存在过**的中间值。
 * 计数动画属于锦上添花，不该拿"先撒谎再纠正"来换。
 * 现在：直接渲染 props 的真实值，并在 props 变化时同步（异步取数后立刻更新）。
 */
const display = reactive({ products: 0, skus: 0, methods: 0, protocols: 0, areas: 0 })

function sync() {
  display.products = props.stats?.products || 0
  display.skus = props.stats?.skus || 0
  display.methods = props.stats?.methods || 0
  display.protocols = props.stats?.protocols || 0
  display.areas = props.stats?.areas || 0
}
sync()
watch(() => props.stats, sync, { deep: true })

// 千分位：14065 → 14,065（原样输出在四位数以上很难一眼读数）
const fmt = (n) => Number(n || 0).toLocaleString('en-US')
</script>

<template>
  <section ref="rootEl" class="stats-section" aria-label="Platform statistics">
    <div class="stats-grid">
      <!-- ★ 2026-10-30：原来 Products 与 SKUs 是**两个独立格子**，都 push('/products')，
           但数字不同（67 vs 370）⇒ 用户点 SKUs 进去看到 67 个产品，以为数据错乱。
           SKU 是产品的规格维度，不是独立浏览对象（站内也没有 SKU 列表页），
           所以合并成一格：「67 Products · 370 SKUs」。信息零丢失，跳转不再自相矛盾。 -->
      <button class="stat-item" @click="router.push('/products')">
        <StarDot class="stat-star" :size="4" color="#5EEAD4" pulse />
        <div class="stat-number">{{ fmt(display.products) }}</div>
        <div class="stat-label">
          Products<span class="stat-sub">· {{ fmt(display.skus) }} SKUs</span>
        </div>
      </button>
      <button class="stat-item" @click="router.push('/methods')">
        <StarDot class="stat-star" :size="4" color="#8FE8FF" pulse />
        <div class="stat-number">{{ fmt(display.methods) }}</div>
        <div class="stat-label">Methods</div>
      </button>
      <button class="stat-item" @click="router.push('/protocols')">
        <StarDot class="stat-star" :size="4" color="#A6D7FF" pulse />
        <div class="stat-number">{{ fmt(display.protocols) }}</div>
        <div class="stat-label">Protocols</div>
      </button>
      <button class="stat-item" @click="router.push('/research-goals')">
        <StarDot class="stat-star" :size="4" color="#B2B0FF" pulse />
        <div class="stat-number">{{ fmt(display.areas) }}</div>
        <div class="stat-label">Research Areas</div>
      </button>
    </div>
  </section>
</template>

<style scoped>
.stats-section {
  padding: 32px 0 48px;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 1px;
  background: var(--color-border);
  border-radius: 10px;
  overflow: hidden;
  border: 1.5px solid var(--color-border);
}
.stat-item {
  position: relative;
  background: var(--color-surface);
  padding: 28px 20px;
  text-align: center;
  border: none;
  cursor: pointer;
  transition: background 0.15s;
  font-family: var(--font-sans);
}
.stat-item:hover {
  background: var(--color-gray-50);
}
.stat-star {
  position: absolute;
  top: 10px;
  right: 12px;
  opacity: 0.55;
  transition: opacity 0.2s;
}
.stat-item:hover .stat-star {
  opacity: 1;
}
.stat-number {
  font-family: var(--font-display);
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  line-height: 1;
  margin-bottom: 4px;
}
.stat-label {
  font-size: 13px;
  color: var(--color-text-secondary);
  font-weight: 500;
}
.stat-sub {
  margin-left: 5px;
  font-size: 12px;
  font-weight: 400;
  opacity: 0.72;
  white-space: nowrap;
}

@media (max-width: 768px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 480px) {
  .stats-grid { grid-template-columns: repeat(2, 1fr); }
  .stat-sub { display: block; margin-left: 0; }
}
</style>
