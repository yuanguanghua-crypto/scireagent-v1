<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useProtocolsStore } from '@/stores/protocols'
import { formatDate, getStatusType } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const store = useProtocolsStore()
const activeTab = ref('steps')

onMounted(() => {
  store.fetchProtocol(route.params.id)
})

onUnmounted(() => {
  store.clearCurrent()
})

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
      <!-- Breadcrumb -->
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/protocols' }">Protocols</el-breadcrumb-item>
        <el-breadcrumb-item>{{ store.currentProtocol.name }}</el-breadcrumb-item>
      </el-breadcrumb>

      <!-- Header -->
      <div class="detail-header">
        <div class="header-left">
          <h1 class="detail-title">{{ store.currentProtocol.name }}</h1>
          <el-tag size="small" class="version-tag">v{{ store.currentProtocol.version }}</el-tag>
          <el-tag :type="getStatusType(store.currentProtocol.status)" size="small">
            {{ store.currentProtocol.status }}
          </el-tag>
        </div>
        <span class="detail-meta">Method ID: {{ store.currentProtocol.method_id }}</span>
      </div>

      <!-- Objective & Principle -->
      <section class="detail-section">
        <h2 class="section-title">Objective</h2>
        <p class="section-content">{{ store.currentProtocol.objective || 'No objective specified.' }}</p>
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
        <el-tab-pane label="Materials" name="materials">
          <div class="two-column">
            <section class="detail-section">
              <h2 class="section-title">Materials</h2>
              <p class="section-content pre-wrap">{{ store.currentProtocol.materials || 'N/A' }}</p>
            </section>
            <section class="detail-section">
              <h2 class="section-title">Equipment</h2>
              <p class="section-content pre-wrap">{{ store.currentProtocol.equipment || 'N/A' }}</p>
            </section>
          </div>
          <section class="detail-section">
            <h2 class="section-title">Reagents</h2>
            <p class="section-content pre-wrap">{{ store.currentProtocol.reagents || 'N/A' }}</p>
          </section>
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
          <div v-if="store.currentProtocol.reference_ids?.length">
            <p class="info-text">{{ store.currentProtocol.reference_ids.length }} reference(s) linked</p>
            <el-table :data="store.currentProtocol.reference_ids.map(id => ({ id }))" stripe>
              <el-table-column prop="id" label="Reference ID" width="120" />
              <el-table-column label="Action" width="120">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="router.push(`/references/${row.id}`)">
                    View →
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="No references linked" />
        </el-tab-pane>

        <!-- Products Tab -->
        <el-tab-pane label="Products" name="products">
          <div v-if="store.currentProtocol.product_ids?.length">
            <p class="info-text">{{ store.currentProtocol.product_ids.length }} product(s) required</p>
            <el-table :data="store.currentProtocol.product_ids.map(id => ({ id }))" stripe>
              <el-table-column prop="id" label="Product ID" width="120" />
              <el-table-column label="Action" width="120">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="router.push(`/products/${row.id}`)">
                    View →
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="No products linked" />
        </el-tab-pane>
      </el-tabs>
    </template>

    <div v-else class="empty-container">
      <el-empty description="Protocol not found">
        <el-button @click="router.push('/protocols')">Back to Protocols</el-button>
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
.detail-tabs { margin-top: 8px; }
.detail-section { margin-bottom: 24px; }
.section-title { font-size: 18px; font-weight: 600; color: var(--color-text); margin: 0 0 8px 0; border-bottom: 1px solid var(--color-border); padding-bottom: 6px; }
.section-content { font-size: 15px; line-height: 1.6; color: var(--color-text); }
.pre-wrap { white-space: pre-wrap; }
.two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.steps-container { padding: 8px 0; }
.step-card { margin-bottom: 0; }
.step-header { display: flex; justify-content: space-between; align-items: center; }
.step-title { font-size: 16px; font-weight: 600; color: var(--color-text); margin: 0; }
.step-body { font-size: 14px; line-height: 1.6; color: var(--color-text); margin: 8px 0; }
.step-warning { margin-top: 8px; }
.info-text { color: var(--color-text-secondary); font-size: 14px; margin-bottom: 12px; }
.loading-container, .empty-container { padding: 60px 0; text-align: center; }
</style>
