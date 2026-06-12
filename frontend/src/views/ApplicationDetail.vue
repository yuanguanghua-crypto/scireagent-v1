<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessageBox, ElMessage } from 'element-plus'
import { useApplicationsStore } from '@/stores/applications'
import { formatDate, getStatusType } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const store = useApplicationsStore()

const applicationId = route.params.id

onMounted(() => {
  store.fetchApplication(applicationId)
})

onUnmounted(() => {
  store.clearCurrent()
})

function handleBack() {
  router.push({ name: 'Applications' })
}

function handleEdit() {
  // TODO: Open edit dialog
}

function handleDelete() {
  ElMessageBox.confirm(
    'Are you sure you want to delete this application?',
    'Confirm Delete',
    { type: 'warning' }
  )
    .then(async () => {
      await store.removeApplication(applicationId)
      router.push({ name: 'Applications' })
      ElMessage.success('Application deleted successfully')
    })
    .catch(() => {})
}
</script>

<template>
  <div class="application-detail">
    <div class="breadcrumb">
      <el-button text @click="handleBack">
        <el-icon><ArrowLeft /></el-icon>
        Back to Applications
      </el-button>
    </div>

    <div v-if="store.loading" class="loading-state">
      <el-skeleton :rows="6" animated />
    </div>

    <template v-else-if="store.currentApplication">
      <div class="detail-header">
        <div class="header-left">
          <div class="title-row">
            <h2 class="detail-title">{{ store.currentApplication.name }}</h2>
            <el-tag :type="getStatusType(store.currentApplication.status)" size="large">
              {{ store.currentApplication.status }}
            </el-tag>
          </div>
          <p v-if="store.currentApplication.category" class="detail-category">
            {{ store.currentApplication.category }}
          </p>
        </div>
        <div class="header-actions">
          <el-button @click="handleEdit">
            <el-icon><Edit /></el-icon>
            Edit
          </el-button>
          <el-button type="danger" plain @click="handleDelete">
            <el-icon><Delete /></el-icon>
            Delete
          </el-button>
        </div>
      </div>

      <div class="detail-content">
        <el-card class="info-card">
          <template #header>
            <span class="card-header-title">Description</span>
          </template>
          <p class="description-text">
            {{ store.currentApplication.description || 'No description provided.' }}
          </p>
        </el-card>

        <div class="meta-grid">
          <el-card class="meta-card">
            <div class="meta-item">
              <span class="meta-label">Created</span>
              <span class="meta-value">{{ formatDate(store.currentApplication.created_at) }}</span>
            </div>
          </el-card>

          <el-card class="meta-card">
            <div class="meta-item">
              <span class="meta-label">Updated</span>
              <span class="meta-value">{{ formatDate(store.currentApplication.updated_at) }}</span>
            </div>
          </el-card>

          <el-card class="meta-card">
            <div class="meta-item">
              <span class="meta-label">Reagents</span>
              <span class="meta-value">{{ store.currentApplication.reagent_count || 0 }}</span>
            </div>
          </el-card>
        </div>

        <el-card v-if="store.currentApplication.reagents?.length" class="reagents-card">
          <template #header>
            <span class="card-header-title">Associated Reagents</span>
          </template>
          <el-table :data="store.currentApplication.reagents" stripe>
            <el-table-column prop="name" label="Name" />
            <el-table-column prop="cas_number" label="CAS Number" width="150" />
            <el-table-column prop="role" label="Role" width="120" />
            <el-table-column prop="concentration" label="Concentration" width="140" />
          </el-table>
        </el-card>

        <!-- Methods -->
        <section class="detail-section">
          <h2 class="section-title">Methods</h2>
          <div v-if="store.currentApplication.method_ids?.length">
            <p class="info-text">{{ store.currentApplication.method_ids.length }} method(s) linked</p>
            <el-table :data="store.currentApplication.method_ids.map(id => ({ id }))" stripe>
              <el-table-column prop="id" label="Method ID" width="120" />
              <el-table-column label="Action" width="120">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="router.push(`/methods/${row.id}`)">View →</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="No methods linked" :image-size="60" />
        </section>

        <!-- Protocols -->
        <section class="detail-section">
          <h2 class="section-title">Protocols</h2>
          <div v-if="store.currentApplication.protocol_ids?.length">
            <p class="info-text">{{ store.currentApplication.protocol_ids.length }} protocol(s) linked</p>
            <el-table :data="store.currentApplication.protocol_ids.map(id => ({ id }))" stripe>
              <el-table-column prop="id" label="Protocol ID" width="120" />
              <el-table-column label="Action" width="120">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="router.push(`/protocols/${row.id}`)">View →</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="No protocols linked" :image-size="60" />
        </section>

        <!-- Products -->
        <section class="detail-section">
          <h2 class="section-title">Products</h2>
          <div v-if="store.currentApplication.product_ids?.length">
            <p class="info-text">{{ store.currentApplication.product_ids.length }} product(s) linked</p>
            <el-table :data="store.currentApplication.product_ids.map(id => ({ id }))" stripe>
              <el-table-column prop="id" label="Product ID" width="120" />
              <el-table-column label="Action" width="120">
                <template #default="{ row }">
                  <el-button size="small" text type="primary" @click="router.push(`/products/${row.id}`)">View →</el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
          <el-empty v-else description="No products linked" :image-size="60" />
        </section>

        <!-- References -->
        <section class="detail-section">
          <h2 class="section-title">References</h2>
          <div v-if="store.currentApplication.reference_ids?.length">
            <p class="info-text">{{ store.currentApplication.reference_ids.length }} reference(s) supporting this application</p>
          </div>
          <el-empty v-else description="No references linked" :image-size="60" />
        </section>

        <!-- FAQ -->
        <section class="detail-section">
          <h2 class="section-title">FAQ</h2>
          <el-collapse>
            <el-collapse-item title="What is this application used for?">
              <p>{{ store.currentApplication.summary || 'No description available.' }}</p>
            </el-collapse-item>
            <el-collapse-item title="What methods belong to this application?">
              <p>{{ store.currentApplication.method_ids?.length || 0 }} method(s) are linked to this application.</p>
            </el-collapse-item>
          </el-collapse>
        </section>
      </div>
    </template>

    <div v-else class="empty-state">
      <el-empty description="Application not found">
        <el-button type="primary" @click="handleBack">Back to Applications</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.application-detail {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.breadcrumb {
  margin-bottom: -8px;
}

.detail-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 24px;
}

.header-left {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.detail-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--color-text);
  margin: 0;
}

.detail-category {
  font-size: 14px;
  color: var(--color-text-secondary);
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.detail-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-card {
  background: var(--color-surface);
}

.card-header-title {
  font-weight: 600;
  color: var(--color-text);
}

.description-text {
  font-size: 14px;
  color: var(--color-text);
  line-height: 1.7;
  margin: 0;
}

.meta-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
}

.meta-card {
  background: var(--color-surface);
}

.meta-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.meta-label {
  font-size: 12px;
  color: var(--color-text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.meta-value {
  font-size: 16px;
  font-weight: 600;
  color: var(--color-text);
}

.reagents-card {
  background: var(--color-surface);
}

.detail-section {
  margin-bottom: 24px;
}

.section-title {
  font-size: 18px;
  font-weight: 600;
  color: var(--color-text);
  margin: 0 0 12px 0;
  border-bottom: 1px solid var(--color-border);
  padding-bottom: 6px;
}

.info-text {
  color: var(--color-text-secondary);
  font-size: 14px;
  margin-bottom: 12px;
}

.loading-state {
  padding: 24px;
}

.empty-state {
  padding: 48px 0;
}
</style>
