<script setup>
import { onMounted, onUnmounted, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMethodsStore } from '@/stores/methods'
import ContextCards from '@/components/navigation/ContextCards.vue'
import ResearchPathCard from '@/components/navigation/ResearchPathCard.vue'
import UnifiedCTA from '@/components/navigation/UnifiedCTA.vue'
import ResearchBreadcrumb from '@/components/navigation/ResearchBreadcrumb.vue'
import ResearchPathChips from '@/components/navigation/ResearchPathChips.vue'
import { useResearchPathStore } from '@/stores/researchPath'
import { useAuthStore } from '@/stores/auth'
import { LoadingSpinner } from '@/components/common'
import {
  costBandLabel,
  timelineLabel,
  splitSpecLines,
} from '@/utils/methodSpecs'
import ExpandableSection from './admin/components/ExpandableSection.vue'

const route = useRoute()
const router = useRouter()
const store = useMethodsStore()
const researchCart = useResearchPathStore()
const auth = useAuthStore()

const method = computed(() => store.currentMethod)
const methodId = computed(() => route.params.id)

/**
 * ★ A-116（2026-11-18 / S4，拍板 ①(b)）：「未审的 AI 初稿不对外」。
 *
 * ## 背景与决策链（两轮口径，别按其中一轮单看）
 * · 2026-10-30：**有意披露** —— AI 生成的描述必须标注 "AI-generated draft · pending
 *   expert review"，不能让客户把未审初稿当定论。QA 把这条标注当成缺陷报了（A-116）。
 * · 2026-11-18（本轮拍板 ①(b)）：**升级为不展示内容本身**。理由：给未审内容打个补丁式
 *   标注，仍然是"对外发布了未审内容"；不审的内容不对外，比"对外但加标注"干净，
 *   也正是 QA 的原始诉求。staff 照常看到全部内容 + 标注（内部要能审）。
 *
 * ## 两组字段的边界（按后端语义，不是按页面视觉）
 * `description_status` 管 **summary + purpose**（同一批「方法名 + 协议标题」产物）；
 * `specs_status` 管 **advantages / limitations / timeline**（另一批「原文证据 + 正则耗时
 * + LLM 判档」产物）。两批独立审核、各自有时间戳 ⇒ 必须**分开判**：
 * 专家可能确认了描述却没看四字段，合并成一个开关会让未审规格以「已审」面貌出现。
 * `cost_band` 不属于任何一批，不在此列。
 */
const descVisible = computed(
  () => auth.isStaff || method.value?.description_status !== 'ai_draft',
)
const specsVisible = computed(
  () => auth.isStaff || method.value?.specs_status !== 'ai_draft',
)

/* ── Navigation data ── */
const upstreamEntities = computed(() => {
  const items = []
  const n = method.value?.applications_count || 0
  // ★ 2026-10-30（P2）：M:N 下 `application_id/name` 只是「挑一个当代表」——
  //   实测 Genomic DNA Extraction 关联 1,346 个应用，返回的是 display_order
  //   最小的那个（「复制时序数值分配」），页面 "PART OF 那个" 是**任意的**。
  //   83 个方法全部关联 >1 个应用 ⇒ 多应用时改说「被 N 个应用使用」，
  //   点进去看列表；只有恰好 1 个应用时才显示具体的 PART OF。
  if (n > 1) {
    items.push({
      type: 'applications',
      name: `${n.toLocaleString('en-US')} applications`,
      route: '/applications',
    })
  } else if (method.value?.application_id) {
    items.push({
      type: 'application',
      id: method.value.application_id,
      name: method.value.application_name || 'Application',
    })
  }
  return items
})
/**
 * ★ 2026-10-30 修：原来把**全部** protocols 映射成 chip，实测 PCR 关联 585 条
 *   ⇒ ContextCards 渲染 585 个 chip，页面被撑到 **8,325 px**，
 *   方法名 h1 和 summary 被埋在协议列表下面（用户滚 8000px 才看到方法叫什么）。
 *   与协议详情页 2026-10-29 的 PROTOCOL_PREVIEW_LIMIT=20 同口径：详情页只展示代表项，
 *   完整清单走 /protocols 索引页（那里有分页与筛选）。
 */
const PROTOCOL_PREVIEW = 20
const downstreamEntities = computed(() => {
  return (method.value?.protocols || []).slice(0, PROTOCOL_PREVIEW)
    .map(p => ({ type: 'protocol', id: p.id, name: p.name }))
})
const protocolTotal = computed(() => (method.value?.protocols || []).length)
const researchPath = computed(() => {
  const path = []
  if (method.value?.research_goal_id) {
    path.push({ type: 'research_goal', id: method.value.research_goal_id, name: method.value.research_goal_name || 'Research Goal' })
  }
  // 同上：多应用时「代表应用」无意义，不写进面包屑，路径降为 Home / Method
  if ((method.value?.applications_count || 0) <= 1 && method.value?.application_id) {
    path.push({ type: 'application', id: method.value.application_id, name: method.value.application_name || 'Application' })
  }
  if (method.value) path.push({ type: 'method', id: method.value.id, name: method.value.name })
  for (const p of (method.value?.protocols || []).slice(0, 1)) {
    path.push({ type: 'protocol', id: p.id, name: p.name })
  }
  return path
})

async function loadMethod(id) {
  await store.fetchMethod(id)
  if (method.value) researchCart.addStep('method', method.value.id, method.value.name, method.value.slug)
}

onMounted(() => loadMethod(route.params.id))
watch(() => route.params.id, (newId) => { if (newId) loadMethod(newId) })
onUnmounted(() => { store.clearCurrent() })
</script>

<template>
  <div class="detail-page" v-if="method">
    <ResearchBreadcrumb :items="researchPath.slice(0, -1)" :current-name="method.name" />
    <ResearchPathChips :path="researchPath" current-type="method" />

    <!-- Context Cards -->
    <ContextCards
      :upstream="upstreamEntities"
      :upstream-label="(method?.applications_count || 0) > 1 ? 'Used in' : 'Part of'"
      :downstream="downstreamEntities"
      downstream-label="Protocols"
      fallback-message="Protocol data is being curated for this method."
    />

    <div class="detail-hero">
      <h1 class="detail-title">{{ method.name }}</h1>
      <span class="detail-badge" :class="`badge-${method.status}`">{{ method.status }}</span>
      <!-- ★ A-116：summary / purpose 属 `description_status` 批次；未审时对非 staff 不渲染 -->
      <p v-if="method.summary && descVisible" class="detail-summary">{{ method.summary }}</p>
      <p v-if="method.purpose && descVisible" class="detail-purpose"><strong>Purpose:</strong> {{ method.purpose }}</p>
      <!-- ★ 2026-10-30 的标注**保留给 staff**（内部审阅要看）。
           2026-11-18（A-116 / ①(b)）：非 staff 现在看不到未审内容本身 ⇒ 这条标注对他们
           既无对象也无意义，故只对 staff 显示。 -->
      <p v-if="method.description_status === 'ai_draft' && auth.isStaff" class="desc-draft-note">
        AI-generated draft · pending expert review
      </p>
    </div>

    <!-- Specs -->
    <div class="specs-row" v-if="method.cost_band || (method.timeline && specsVisible)">
      <div class="spec" v-if="method.cost_band">
        <span class="spec-label">Cost Band</span>
        <span class="spec-val">{{ costBandLabel(method.cost_band) }}</span>
      </div>
      <div class="spec" v-if="method.timeline && specsVisible">
        <span class="spec-label">Timeline</span>
        <span class="spec-val">{{ timelineLabel(method.timeline) }}</span>
      </div>
    </div>

    <!-- ★ 2026-10-31：四字段与 summary 是两批独立生成的内容，各自有审核时间戳。
         只要 specs_status 是 ai_draft，就必须显式告知 —— 不能让模型常识以「事实」面貌出现。 -->
    <!-- ★ 2026-10-31（决策 1B）：通用步骤说明 -->
    <p v-if="method.is_step_tag" class="step-tag-note">
      Common step — this technique appears inside other methods rather than standing alone
    </p>

    <!-- ★ A-116（①(b)）：非 staff 看不到未审四字段本身 ⇒ 同 description 的处理，标注只给 staff -->
    <p v-if="method.specs_status === 'ai_draft' && auth.isStaff" class="spec-draft-note">
      Advantages, limitations and timeline are AI-generated drafts · pending expert review
    </p>

    <!-- Advantages / Limitations -->
    <div class="detail-columns" v-if="specsVisible && (method.advantages || method.limitations)">
      <section class="detail-col" v-if="method.advantages">
        <h3 class="col-title">Advantages</h3>
        <ul class="col-list">
          <li v-for="(line, i) in splitSpecLines(method.advantages)" :key="i">{{ line }}</li>
        </ul>
      </section>
      <section class="detail-col" v-if="method.limitations">
        <h3 class="col-title">Limitations</h3>
        <ul class="col-list">
          <li v-for="(line, i) in splitSpecLines(method.limitations)" :key="i">{{ line }}</li>
        </ul>
      </section>
    </div>

    <!-- Protocols -->
    <section class="detail-section">
      <h2 class="section-title">
        Protocols
        <span v-if="protocolTotal" class="proto-count">{{ protocolTotal }}</span>
      </h2>
      <ExpandableSection
        title=""
        :items="method.protocols || []"
        :default-show="3"
        item-type="protocol"
        fallback-msg="Protocols are being documented for this method."
        fallback-link="/protocols"
        fallback-link-text="Browse all protocols"
      >
        <template #item="{ item }">
          <router-link :to="`/protocols/${item.id}`" class="link-card">
            <div class="card-icon icon-protocol">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><polyline points="14 2 14 8 20 8"/></svg>
            </div>
            <div class="card-body">
              <h3 class="card-name">{{ item.name }}</h3>
              <span v-if="item.version" class="card-meta">v{{ item.version }}</span>
            </div>
            <span class="card-arrow">&rarr;</span>
          </router-link>
        </template>
      </ExpandableSection>
    </section>

    <!-- Products -->
    <section class="detail-section">
      <h2 class="section-title">Products</h2>
      <ExpandableSection
        title=""
        :items="method.products || []"
        :default-show="3"
        item-type="product"
        fallback-msg="No products linked to this method yet."
        fallback-link="/products"
        fallback-link-text="Browse all products"
      >
        <template #item="{ item }">
          <router-link :to="`/products/${item.id}`" class="link-card">
            <div class="card-icon icon-product">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 002 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
            </div>
            <div class="card-body">
              <h3 class="card-name">{{ item.name }}</h3>
              <span v-if="item.catalog_no" class="card-meta">{{ item.catalog_no }}</span>
            </div>
            <span class="card-arrow">&rarr;</span>
          </router-link>
        </template>
      </ExpandableSection>
    </section>

    <!-- Research Path Card -->
    <ResearchPathCard v-if="researchPath.length > 1" :path="researchPath" current-type="method" />

    <!-- Unified CTA -->
    <UnifiedCTA
      title="Ready to use this method?"
      subtitle="Find protocols and reagents, or request a custom quote."
      :show-rfq="true"
      :show-explore="true"
    />
  </div>

  <LoadingSpinner v-else-if="store.loading" text="Loading..." />
  <div v-else class="empty">Method not found</div>
</template>

<style scoped>
.detail-page { max-width: var(--content-max-width); margin: 0 auto; padding: 24px; }
.breadcrumb { display: flex; align-items: center; gap: 6px; font-size: 13px; margin-bottom: 16px; }
.breadcrumb a { color: var(--color-primary); text-decoration: none; }
.breadcrumb a:hover { text-decoration: underline; }
.sep { color: var(--color-text-tertiary); }
.cur { color: var(--color-text-secondary); }
.detail-hero { margin-bottom: 24px; }
.detail-title { font-size: 28px; font-weight: 800; color: var(--color-text); margin: 0 0 8px; }
.detail-badge { display: inline-flex; align-items: center; gap: 4px; font-size: 11px; font-weight: 600; padding: 2px 8px; border-radius: 10px; text-transform: capitalize; background: var(--color-bg); color: var(--color-text-secondary); border: 1px solid var(--color-border-light); }
.detail-badge::before { content: ''; width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; background: #9CA3AF; }
.badge-active::before { background: #22C55E; }
.badge-draft::before { background: #F59E0B; }
.detail-summary { font-size: 15px; color: var(--color-text-secondary); line-height: 1.6; margin: 10px 0 0; }
.detail-purpose { font-size: 14px; color: var(--color-text); margin: 8px 0 0; }
.proto-count {
  display: inline-block; margin-left: 8px; padding: 1px 8px;
  font-size: 12px; font-weight: 500; font-family: var(--font-mono);
  color: var(--color-text-tertiary);
  background: var(--color-bg-subtle, #f3f4f6); border-radius: 10px;
  vertical-align: middle;
}
.desc-draft-note, .spec-draft-note {
  display: inline-block; margin: 8px 0 0; padding: 2px 8px;
  font-size: 11px; font-weight: 600;
  color: var(--color-text-tertiary);
  background: var(--color-bg-subtle, #f3f4f6);
  border-radius: 4px;
}
.spec-draft-note { margin: -14px 0 20px; }
.step-tag-note {
  display: inline-block; margin: 0 0 16px; padding: 3px 10px;
  font-size: 12px; font-weight: 600;
  color: var(--color-text-secondary);
  background: var(--color-bg-subtle, #f3f4f6);
  border-radius: 6px;
}
.specs-row { display: flex; gap: 24px; margin-bottom: 24px; }
.spec { display: flex; flex-direction: column; gap: 2px; }
.spec-label { font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--color-text-tertiary); }
.spec-val { font-size: 14px; font-weight: 500; color: var(--color-text); }
.detail-columns { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 24px; }
.detail-col { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); padding: 16px; }
.col-title { font-size: 14px; font-weight: 700; margin: 0 0 8px; color: var(--color-text); }
.col-text { font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; margin: 0; }
.col-list { margin: 0; padding-left: 18px; font-size: 13px; color: var(--color-text-secondary); line-height: 1.6; }
.col-list li { margin-bottom: 4px; }
.col-list li:last-child { margin-bottom: 0; }
.detail-section { margin-bottom: 28px; }
.section-title { font-size: 16px; font-weight: 700; color: var(--color-text); margin: 0 0 12px; padding-bottom: 6px; border-bottom: 2px solid var(--color-primary); display: inline-block; }
.card-grid { display: flex; flex-direction: column; gap: 8px; }
.link-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); text-decoration: none; color: var(--color-text); transition: all 0.15s; }
.link-card:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }
.card-icon { width: 36px; height: 36px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.icon-protocol { background: #F5F0E0; color: #C9A34E; }
.icon-product { background: #F5E8E8; color: #D47C7C; }
.card-body { flex: 1; min-width: 0; }
.card-name { font-size: 14px; font-weight: 600; margin: 0; }
.card-meta { font-size: 12px; color: var(--color-text-secondary); font-family: var(--font-mono); }
.card-arrow { font-size: 16px; color: var(--color-text-tertiary); }
.fallback { padding: 16px; background: var(--color-bg); border: 1px dashed var(--color-border); border-radius: var(--radius-md); text-align: center; }
.fallback p { font-size: 13px; color: var(--color-text-secondary); margin: 0 0 6px; }
.fallback-link { font-size: 13px; color: var(--color-primary); text-decoration: none; font-weight: 500; }
.fallback-link:hover { text-decoration: underline; }
.loading, .empty { text-align: center; padding: 60px 0; color: var(--color-text-secondary); }
@media (max-width: 768px) { .detail-columns { grid-template-columns: 1fr; } }
</style>
