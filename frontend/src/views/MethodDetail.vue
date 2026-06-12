<script setup>
import { onMounted, onUnmounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useMethodsStore } from '@/stores/methods'
import { formatDate, getStatusType, truncate } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const store = useMethodsStore()
const activeTab = ref('overview')

onMounted(() => {
  store.fetchMethod(route.params.id)
})

onUnmounted(() => {
  store.clearCurrent()
})

const method = store.currentMethod
</script>

<template>
  <div class="method-detail">
    <div v-if="store.loading" class="loading-container">
      <el-skeleton :rows="8" animated />
    </div>

    <template v-else-if="store.currentMethod">
      <!-- Breadcrumb -->
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/methods' }">Methods</el-breadcrumb-item>
        <el-breadcrumb-item>{{ store.currentMethod.name }}</el-breadcrumb-item>
      </el-breadcrumb>

      <!-- Header -->
      <div class="detail-header">
        <div class="header-left">
          <h1 class="detail-title">{{ store.currentMethod.name }}</h1>
          <el-tag :type="getStatusType(store.currentMethod.status)" size="small">
            {{ store.currentMethod.status }}
          </el-tag>
        </div>
        <span class="detail-meta">
          Application ID: {{ store.currentMethod.application_id }}
        </span>
      </div>

      <!-- Tabs -->
      <el-tabs v-model="activeTab" class="detail-tabs">
        <!-- Overview Tab -->
        <el-tab-pane label="Overview" name="overview">
          <section class="detail-section">
            <h2 class="section-title">Summary</h2>
            <p class="section-content">{{ store.currentMethod.summary || 'No summary available.' }}</p>
          </section>

          <section class="detail-section">
            <h2 class="section-title">Purpose</h2>
            <p class="section-content">{{ store.currentMethod.purpose || 'No purpose description.' }}</p>
          </section>

          <div class="two-column">
            <section class="detail-section">
              <h2 class="section-title">Advantages</h2>
              <p class="section-content">{{ store.currentMethod.advantages || 'N/A' }}</p>
            </section>

            <section class="detail-section">
              <h2 class="section-title">Limitations</h2>
              <p class="section-content">{{ store.currentMethod.limitations || 'N/A' }}</p>
            </section>
          </div>

          <el-descriptions :column="2" border class="meta-descriptions">
            <el-descriptions-item label="Cost Band">{{ store.currentMethod.cost_band || 'N/A' }}</el-descriptions-item>
            <el-descriptions-item label="Timeline">{{ store.currentMethod.timeline || 'N/A' }}</el-descriptions-item>
            <el-descriptions-item label="Created">{{ formatDate(store.currentMethod.created_at) }}</el-descriptions-item>
            <el-descriptions-item label="Updated">{{ formatDate(store.currentMethod.updated_at) }}</el-descriptions-item>
          </el-descriptions>
        </el-tab-pane>

        <!-- Protocols Tab -->
        <el-tab-pane label="Protocols" name="protocols">
          <div v-if="store.currentMethod.protocol_ids?.length" class="protocol-list">
            <p class="info-text">{{ store.currentMethod.protocol_ids.length }} protocol(s) linked</p>
            <el-table :data="store.currentMethod.protocol_ids.map(id => ({ id }))" stripe>
              <el-table-column prop="id" label="Protocol ID" width="120" />
              <el-table-column label="Action" width="120">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="router.push(`/protocols/${row.id}`)">
                    View →
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="No protocols linked yet" />
        </el-tab-pane>

        <!-- Products Tab -->
        <el-tab-pane label="Products" name="products">
          <div v-if="store.currentMethod.product_ids?.length" class="product-list">
            <p class="info-text">{{ store.currentMethod.product_ids.length }} product(s) linked</p>
            <el-table :data="store.currentMethod.product_ids.map(id => ({ id }))" stripe>
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
          <el-empty v-else description="No products linked yet" />
        </el-tab-pane>
      </el-tabs>
    </template>

    <div v-else class="empty-container">
      <el-empty description="Method not found">
        <el-button @click="router.push('/methods')">Back to Methods</el-button>
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
.detail-meta { font-size: 13px; color: var(--color-text-secondary); }
.detail-tabs { margin-top: 8px; }
.detail-section { margin-bottom: 24px; }
.section-title { font-size: 18px; font-weight: 600; color: var(--color-text); margin: 0 0 8px 0; border-bottom: 1px solid var(--color-border); padding-bottom: 6px; }
.section-content { font-size: 15px; line-height: 1.6; color: var(--color-text); }
.two-column { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
.meta-descriptions { margin-top: 16px; }
.info-text { color: var(--color-text-secondary); font-size: 14px; margin-bottom: 12px; }
.loading-container, .empty-container { padding: 60px 0; text-align: center; }
</style>