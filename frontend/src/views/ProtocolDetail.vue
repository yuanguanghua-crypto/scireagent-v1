<script setup>
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProtocolsStore } from '@/stores/protocols'
import { formatDate, getStatusType } from '@/utils/helpers'
import ContextCards from '@/components/navigation/ContextCards.vue'
import ResearchPathCard from '@/components/navigation/ResearchPathCard.vue'
import UnifiedCTA from '@/components/navigation/UnifiedCTA.vue'
import ResearchBreadcrumb from '@/components/navigation/ResearchBreadcrumb.vue'
import ResearchPathChips from '@/components/navigation/ResearchPathChips.vue'
import { useResearchPathStore } from '@/stores/researchPath'
import { AppButton } from '@/components/common'
import ExpandableSection from './admin/components/ExpandableSection.vue'

const route = useRoute()
const router = useRouter()
const store = useProtocolsStore()
const researchCart = useResearchPathStore()
/** 协议的材料/设备/试剂是否任一有内容（三个全空时不显示 tab 内容，改给空态）。 */
const hasMaterialsInfo = computed(() => {
  const p = store.currentProtocol || {}
  return !!(p.materials || p.equipment || p.reagents)
})

const activeTab = ref('steps')

const protocol = computed(() => store.currentProtocol)

/**
 * 溯源链接（2026-10-30）：语料里的 DOI / protocols.io 原文地址已回填到后端，
 * 98.5% 的协议都能点到原文。空就不渲染，不占版面。
 */
const sourceLink = computed(() => {
  const p = store.currentProtocol
  if (!p || !p.source_url) return null
  return { url: p.source_url, doi: p.doi || '' }
})

/* ── 材料清单（2026-10-30）──
 * 后端 materials_items 是从语料 input 解析出的逐条材料（Bio-protocol 一份协议最多 268 条）。
 * 按 kind 分组渲染，顺序固定：生物材料 → 试剂 → 溶液配方 → 耗材 → 设备 → 软件 → 未细分 → 说明。
 * 空分组不渲染（沿用 2026-10-29 定下的「空就整块不显示」原则）。
 * ⚠️ 覆盖边界：Protocol-io 来源的协议（库内 62.4%）语料本身没有 input 字段，
 *    这里为空数组是正常状态，不是缺陷。
 */
const MATERIAL_KIND_ORDER = [
  'biological_material', 'reagent', 'solution_recipe', 'consumable',
  'equipment', 'software', 'material_or_reagent', 'note',
]
const MATERIAL_KIND_LABELS = {
  biological_material: 'Biological materials',
  reagent: 'Reagents',
  solution_recipe: 'Solutions & recipes',
  consumable: 'Consumables',
  equipment: 'Equipment',
  software: 'Software & data',
  material_or_reagent: 'Materials & reagents',
  note: 'Notes',
}
const materialGroups = computed(() => {
  const items = store.currentProtocol?.materials_items || []
  if (!items.length) return []
  const by = {}
  for (const it of items) (by[it.kind] = by[it.kind] || []).push(it)
  return MATERIAL_KIND_ORDER
    .filter((k) => by[k] && by[k].length)
    .map((k) => ({ kind: k, label: MATERIAL_KIND_LABELS[k] || k, items: by[k] }))
})

/* ── Facet 分类（route B 加法，范围 A）──
 * 后端 ProtocolDetailSerializer 返回 facets：{ facet_type: [{id, facet_type, kind, value}] }
 * 仅含非空组。value 全英文（用户决策）；组标签用中文。
 */
const FACET_TYPE_ORDER = ['application', 'method', 'biological_context', 'study_type']
const FACET_TYPE_LABELS = {
  application: '研究域',
  method: '方法',
  biological_context: '物种·细胞·疾病',
  study_type: '研究类型',
}
const KIND_ORDER = ['species', 'cell', 'disease']
const KIND_LABELS = { species: '物种', cell: '细胞', disease: '疾病' }

const facetGroups = computed(() => {
  const facets = protocol.value?.facets || {}
  const groups = []
  for (const ft of FACET_TYPE_ORDER) {
    const items = facets[ft]
    if (!items || !items.length) continue
    if (ft === 'biological_context') {
      const byKind = {}
      for (const it of items) {
        ;(byKind[it.kind] = byKind[it.kind] || []).push(it)
      }
      const sub = KIND_ORDER.filter((k) => byKind[k]).map((k) => ({
        kind: k,
        kindLabel: KIND_LABELS[k],
        items: byKind[k],
      }))
      groups.push({ type: ft, label: FACET_TYPE_LABELS[ft], sub })
    } else {
      groups.push({ type: ft, label: FACET_TYPE_LABELS[ft], items })
    }
  }
  return groups
})

/* ── Navigation data ── */
const upstreamEntities = computed(() => {
  const items = []
  for (const m of (protocol.value?.methods || [])) {
    items.push({ type: 'method', id: m.id, name: m.name || 'Method' })
  }
  return items
})
const downstreamEntities = computed(() => {
  return (protocol.value?.products || []).map(p => ({ type: 'product', id: p.id, name: p.name, catalog_no: p.catalog_no }))
})
const researchPath = computed(() => {
  // #534 B方案：单一代表分支上溯（RG→AP→Method→Protocol），对齐 ProductDetail slice(0,1)。
  // 上溯字段来自后端 get_methods 新返回的 application_id/application_name/
  // research_goal_id/research_goal_name；protocol 自身无 RG/AP 字段。
  const path = []
  const m0 = (protocol.value?.methods || [])[0]
  if (m0?.research_goal_id) {
    path.push({ type: 'research_goal', id: m0.research_goal_id, name: m0.research_goal_name || 'Research Goal' })
  }
  if (m0?.application_id) {
    path.push({ type: 'application', id: m0.application_id, name: m0.application_name || 'Application' })
  }
  for (const m of (protocol.value?.methods || []).slice(0, 1)) {
    path.push({ type: 'method', id: m.id, name: m.name || 'Method' })
  }
  if (protocol.value) path.push({ type: 'protocol', id: protocol.value.id, name: protocol.value.name })
  return path
})

async function loadProtocol(id) {
  await store.fetchProtocol(id)
  if (protocol.value) researchCart.addStep('protocol', protocol.value.id, protocol.value.name, protocol.value.slug)
}

onMounted(() => loadProtocol(route.params.id))
watch(() => route.params.id, (newId) => { if (newId) loadProtocol(newId) })
onUnmounted(() => { store.clearCurrent() })

/**
 * Format duration in seconds to a human-readable string.
 * @param {number} seconds - Duration in seconds.
 * @returns {string} Formatted duration string.
 */
function formatDuration(seconds) {
  if (!seconds) return '-'
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return m > 0 ? `${m}m ${s}s` : `${s}s`
}
</script>

<template>
  <div class="protocol-detail">
    <div v-if="store.loading" class="loading-container">
      <el-skeleton :rows="10" animated />
    </div>

    <template v-else-if="store.currentProtocol">
      <!-- Research Breadcrumb + Path Chips (P1) -->
      <ResearchBreadcrumb :items="researchPath.slice(0, -1)" :current-name="protocol.name" />
      <ResearchPathChips :path="researchPath" current-type="protocol" />

      <!-- Context Cards -->
      <ContextCards
        :upstream="upstreamEntities"
        :downstream="downstreamEntities"
        downstream-label="Required Products"
        fallback-message="Product requirements are being documented."
        :request-support-link="!downstreamEntities.length"
      />

      <!-- Header -->
      <div class="detail-header">
        <div class="header-left">
          <h1 class="detail-title">{{ store.currentProtocol.name }}</h1>
          <el-tag size="small" class="version-tag">v{{ store.currentProtocol.version }}</el-tag>
          <el-tag :type="getStatusType(store.currentProtocol.status)" size="small">
            {{ store.currentProtocol.status }}
          </el-tag>
        </div>
        <span class="detail-meta" v-if="protocol?.methods?.length">Methods: {{ protocol.methods.map(m => m.name).join(', ') }}</span>
      </div>

      <!-- 溯源（2026-10-30）：客户可一键跳到原始协议页面，自行核对，不必只信本站转述 -->
      <div v-if="sourceLink" class="source-link-row" data-testid="protocol-source-link">
        <a :href="sourceLink.url" target="_blank" rel="noopener noreferrer" class="source-link">
          View original protocol <span aria-hidden="true">↗</span>
        </a>
        <span v-if="sourceLink.doi" class="source-doi">DOI: {{ sourceLink.doi }}</span>
      </div>

      <!-- 研究分类（route B 加法，范围 A） -->
      <section v-if="facetGroups.length" class="detail-section classification">
        <h2 class="section-title">研究分类</h2>
        <div class="facet-groups">
          <div v-for="g in facetGroups" :key="g.type" class="facet-group">
            <span class="facet-group-label">{{ g.label }}</span>
            <template v-if="g.sub">
              <span v-for="s in g.sub" :key="s.kind" class="facet-subgroup">
                <span class="facet-kind-label">{{ s.kindLabel }}</span>
                <el-tag
                  v-for="it in s.items"
                  :key="it.id"
                  size="small"
                  type="info"
                  effect="plain"
                  class="facet-tag"
                >{{ it.value }}</el-tag>
              </span>
            </template>
            <template v-else>
              <el-tag
                v-for="it in g.items"
                :key="it.id"
                size="small"
                type="info"
                effect="plain"
                class="facet-tag"
              >{{ it.value }}</el-tag>
            </template>
          </div>
        </div>
      </section>

      <!-- Objective & Principle -->
      <!-- ★ 2026-10-29：空就整块不显示。实测这批协议的 objective 几乎全空，
           原来每页都打一行 "No objective specified."，看起来像数据没导入成功。 -->
      <section v-if="store.currentProtocol.objective" class="detail-section">
        <h2 class="section-title">Objective</h2>
        <p class="section-content">{{ store.currentProtocol.objective }}</p>
      </section>

      <section v-if="store.currentProtocol.principle" class="detail-section">
        <h2 class="section-title">Principle</h2>
        <p class="section-content">{{ store.currentProtocol.principle }}</p>
      </section>

      <!-- Tabs -->
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- Steps Tab -->
        <el-tab-pane label="Steps" name="steps">
          <div v-if="store.currentProtocol.steps?.length" class="steps-container">
            <el-timeline>
              <el-timeline-item
                v-for="step in store.currentProtocol.steps"
                :key="step.id"
                :timestamp="`Step ${step.step_no}`"
                placement="top"
                :type="step.warnings ? 'warning' : 'primary'"
              >
                <el-card shadow="never" class="step-card">
                  <div class="step-header">
                    <h3 class="step-title">{{ step.title }}</h3>
                    <el-tag v-if="step.duration_seconds" size="small" type="info">
                      {{ formatDuration(step.duration_seconds) }}
                    </el-tag>
                  </div>
                  <p class="step-body">{{ step.body }}</p>
                  <el-alert
                    v-if="step.warnings"
                    :title="step.warnings"
                    type="warning"
                    :closable="false"
                    show-icon
                    class="step-warning"
                  />
                </el-card>
              </el-timeline-item>
            </el-timeline>
          </div>
          <el-empty v-else description="No steps defined yet" />
        </el-tab-pane>

        <!-- Materials Tab -->
        <!-- ★ 2026-10-29：原来三个字段全空时会渲染成三行 "N/A"（实测这批协议
             materials/equipment/reagents 均为空）⇒ 客户点开这个 tab 看到三个 N/A，以为系统坏了。
             现在有什么显什么；全空就给一句说人话的提示。 -->
        <!-- ★ 2026-10-30：改为**优先读结构化条目**（materials_items，从语料 input 解析）。
             旧的 materials/reagents/equipment 三个 TextField 保留作 fallback ——
             它们只有 157 条 curated 协议有值，直接删会让那些协议的前台内容消失。 -->
        <el-tab-pane label="Materials" name="materials">
          <template v-if="materialGroups.length">
            <section v-for="g in materialGroups" :key="g.kind" class="detail-section">
              <h2 class="section-title">
                {{ g.label }}
                <span class="material-count">{{ g.items.length }}</span>
              </h2>
              <ul class="material-list">
                <li v-for="it in g.items" :key="it.id" class="material-item">
                  <span class="material-name">{{ it.name }}</span>
                  <span v-if="it.vendor || it.catalog_no || it.model_no" class="material-meta">
                    <template v-if="it.vendor">{{ it.vendor }}</template>
                    <template v-if="it.catalog_no"> · Cat. {{ it.catalog_no }}</template>
                    <template v-else-if="it.model_no"> · Model {{ it.model_no }}</template>
                  </span>
                </li>
              </ul>
            </section>
          </template>
          <template v-else-if="hasMaterialsInfo">
            <div v-if="store.currentProtocol.materials || store.currentProtocol.equipment"
                 class="two-column">
              <section v-if="store.currentProtocol.materials" class="detail-section">
                <h2 class="section-title">Materials</h2>
                <p class="section-content pre-wrap">{{ store.currentProtocol.materials }}</p>
              </section>
              <section v-if="store.currentProtocol.equipment" class="detail-section">
                <h2 class="section-title">Equipment</h2>
                <p class="section-content pre-wrap">{{ store.currentProtocol.equipment }}</p>
              </section>
            </div>
            <section v-if="store.currentProtocol.reagents" class="detail-section">
              <h2 class="section-title">Reagents</h2>
              <p class="section-content pre-wrap">{{ store.currentProtocol.reagents }}</p>
            </section>
          </template>
          <!-- ★ 2026-10-30（走查 P2-C）：原来所有空材料都显示同一句
               "This protocol does not list materials, equipment or reagents." ——
               但 8,887 条空里 8,384 条（protocol_io）是**语料源本身没有独立清单**，
               材料信息混在 Steps 正文里。统一说"未提供"会误导用户以为这条协议没写材料。
               现在按后端给的 materials_status 分开说。 -->
          <el-empty v-else
                    :description="store.currentProtocol.materials_status === 'no_separate_list'
                      ? 'This corpus source does not provide a separate materials list — preparation details are inside the Steps tab.'
                      : 'This protocol does not list materials, equipment or reagents.'" />
        </el-tab-pane>

        <!-- Troubleshooting Tab -->
        <el-tab-pane label="Troubleshooting" name="troubleshooting">
          <section v-if="store.currentProtocol.troubleshooting" class="detail-section">
            <p class="section-content pre-wrap">{{ store.currentProtocol.troubleshooting }}</p>
          </section>
          <el-empty v-else description="No troubleshooting information" />
        </el-tab-pane>

        <!-- Expected Results Tab -->
        <el-tab-pane label="Expected Results" name="results">
          <section v-if="store.currentProtocol.expected_results" class="detail-section">
            <p class="section-content pre-wrap">{{ store.currentProtocol.expected_results }}</p>
          </section>
          <el-empty v-else description="No expected results specified" />
        </el-tab-pane>

        <!-- References Tab -->
        <el-tab-pane label="References" name="references">
          <ExpandableSection
            title=""
            :items="store.currentProtocol.references || []"
            :default-show="5"
            item-type=""
            fallback-msg="No references linked"
          >
            <template #item="{ item }">
              <div class="ref-item">
                <div class="ref-body">
                  <h4 class="ref-title">{{ item.title }}</h4>
                  <div class="ref-meta">
                    <span v-if="item.journal" class="ref-journal">{{ item.journal }}</span>
                    <span v-if="item.year">{{ item.year }}</span>
                  </div>
                </div>
                <a v-if="item.doi" :href="`https://doi.org/${item.doi}`" target="_blank" rel="noopener" class="ref-doi">DOI &rarr;</a>
              </div>
            </template>
          </ExpandableSection>
        </el-tab-pane>

        <!-- Products Tab -->
        <el-tab-pane label="Products" name="products">
          <ExpandableSection
            title=""
            :items="store.currentProtocol.products || []"
            :default-show="5"
            item-type="product"
            fallback-msg="No products linked"
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
        </el-tab-pane>
      </el-tabs>

      <!-- Research Path Card -->
      <ResearchPathCard v-if="researchPath.length > 1" :path="researchPath" current-type="protocol" />

      <!-- Unified CTA -->
      <UnifiedCTA
        title="Ready to run this protocol?"
        subtitle="Get all required reagents or request a custom quote."
        :show-rfq="true"
        :show-explore="true"
      />
    </template>

    <div v-else class="empty-container">
      <el-empty description="Protocol not found">
        <AppButton variant="ghost" @click="router.push('/protocols')">Back to Protocols</AppButton>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.detail-header {
  display: flex; justify-content: space-between; align-items: flex-start;
  margin: 20px 0 24px 0;
}
.header-left { display: flex; align-items: center; gap: 12px; }
.detail-title { font-size: 28px; font-weight: 700; color: var(--color-text); margin: 0; }
.version-tag { font-family: var(--font-mono); }
.detail-meta { font-size: 13px; color: var(--color-text-secondary); }

/* 溯源链接（2026-10-30） */
.source-link-row {
  display: flex; align-items: center; gap: 14px; flex-wrap: wrap;
  margin: -12px 0 20px 0;
}
.source-link {
  font-size: 13px; font-weight: 600;
  color: var(--color-primary, #2563eb);
  text-decoration: none;
}
.source-link:hover { text-decoration: underline; }
.source-doi {
  font-family: var(--font-mono); font-size: 12px;
  color: var(--color-text-tertiary);
}

/* 材料清单（2026-10-30） */
.material-count {
  display: inline-block; margin-left: 8px; padding: 1px 8px;
  font-size: 12px; font-weight: 500; font-family: var(--font-mono);
  color: var(--color-text-tertiary);
  background: var(--color-bg-subtle, #f3f4f6);
  border-radius: 10px;
  vertical-align: middle;
}
.material-list { margin: 0; padding-left: 20px; }
.material-item { margin: 5px 0; font-size: 14px; line-height: 1.5; color: var(--color-text); }
.material-item::marker { color: var(--color-text-tertiary); }
.material-name { font-weight: 500; }
.material-meta {
  margin-left: 6px;
  font-size: 12px; font-family: var(--font-mono);
  color: var(--color-text-tertiary);
  white-space: nowrap;
}

/* 研究分类（route B 加法） */
.facet-groups { display: flex; flex-direction: column; gap: 10px; }
.facet-group { display: flex; align-items: flex-start; gap: 12px; flex-wrap: wrap; }
.facet-group-label { flex-shrink: 0; width: 96px; font-size: 13px; font-weight: 600; color: var(--color-text-secondary); padding-top: 2px; }
.facet-subgroup { display: inline-flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.facet-kind-label { font-size: 12px; color: var(--color-text-tertiary); padding: 1px 6px; border: 1px dashed var(--color-border); border-radius: 4px; }
.facet-tag { font-family: var(--font-mono); }
.detail-tabs { margin-top: 8px; }
.detail-section { margin-bottom: 24px; }
.section-title { font-size: 18px; font-weight: 600; color: var(--color-text); margin: 0 0 8px 0; border-bottom: 1px solid var(--color-border); padding-bottom: 6px; }
.section-content { font-size: 15px; line-height: 1.6; color: var(--color-text); }
.pre-wrap { white-space: pre-wrap; }
.two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.steps-container { padding: 8px 0; }
.step-card { margin-bottom: 0; overflow: visible; }
.step-header { display: flex; justify-content: space-between; align-items: center; }
.step-title { font-size: 16px; font-weight: 600; color: var(--color-text); margin: 0; }
.step-body { font-size: 14px; line-height: 1.6; color: var(--color-text); margin: 8px 0; }
.step-warning { margin-top: 8px; }
.info-text { color: var(--color-text-secondary); font-size: 14px; margin-bottom: 12px; }

/* References */
.refs-list { display: flex; flex-direction: column; gap: 8px; }
.ref-item { display: flex; align-items: flex-start; justify-content: space-between; gap: 12px; padding: 10px 14px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); }
.ref-body { flex: 1; min-width: 0; }
.ref-title { font-size: 13px; font-weight: 600; margin: 0 0 4px; color: var(--color-text); line-height: 1.4; }
.ref-meta { display: flex; gap: 8px; font-size: 12px; color: var(--color-text-secondary); }
.ref-journal { font-style: italic; }
.ref-doi { font-size: 12px; color: var(--color-primary); text-decoration: none; font-weight: 600; white-space: nowrap; flex-shrink: 0; }
.ref-doi:hover { text-decoration: underline; }

/* Card grid */
.card-grid { display: flex; flex-direction: column; gap: 8px; }
.link-card { display: flex; align-items: center; gap: 12px; padding: 12px 16px; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-md); text-decoration: none; color: var(--color-text); transition: all 0.15s; }
.link-card:hover { border-color: var(--color-primary); background: var(--color-primary-subtle); }
.card-icon { width: 36px; height: 36px; border-radius: var(--radius-md); display: flex; align-items: center; justify-content: center; flex-shrink: 0; }
.icon-product { background: #F5E8E8; color: #D47C7C; }
.card-body { flex: 1; min-width: 0; }
.card-name { font-size: 14px; font-weight: 600; margin: 0; }
.card-meta { font-size: 12px; color: var(--color-text-secondary); font-family: var(--font-mono); }
.card-arrow { font-size: 16px; color: var(--color-text-tertiary); }
.loading-container, .empty-container { padding: 60px 0; text-align: center; }
</style>
