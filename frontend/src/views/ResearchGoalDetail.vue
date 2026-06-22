<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import PageBridge from '@/components/common/PageBridge.vue'
import { useResearchGoalsStore } from '@/stores/researchGoals'
import { formatDate, getStatusType } from '@/utils/helpers'

const route = useRoute()
const router = useRouter()
const store = useResearchGoalsStore()

onMounted(() => {
  store.fetchGoal(route.params.id)
})

onUnmounted(() => {
  store.clearCurrent()
})
</script>

<template>
  <div class="research-goal-detail">
    <PageBridge />
    <div v-if="store.loading" class="loading-container">
      <el-skeleton :rows="6" animated />
    </div>

    <template v-else-if="store.currentGoal">
      <el-breadcrumb separator="/">
        <el-breadcrumb-item :to="{ path: '/research-goals' }">Research Goals</el-breadcrumb-item>
        <el-breadcrumb-item>{{ store.currentGoal.name }}</el-breadcrumb-item>
      </el-breadcrumb>

      <div class="detail-header">
        <h1 class="detail-title">{{ store.currentGoal.name }}</h1>
        <div class="header-tags">
          <el-tag :type="getStatusType(store.currentGoal.status)" size="small">
            {{ store.currentGoal.status }}
          </el-tag>
          <el-tag size="small" type="info">Priority: {{ store.currentGoal.priority }}</el-tag>
        </div>
      </div>

      <section class="detail-section">
        <h2 class="section-title">Summary</h2>
        <p class="section-content">{{ store.currentGoal.summary || 'No summary available.' }}</p>
      </section>

      <section class="detail-section">
        <h2 class="section-title">Applications</h2>
        <div v-if="store.currentGoal.application_ids?.length">
          <p class="info-text">{{ store.currentGoal.application_ids.length }} application(s) under this goal</p>
          <el-table :data="store.currentGoal.application_ids.map(id => ({ id }))" stripe>
            <el-table-column prop="id" label="Application ID" width="120" />
            <el-table-column label="Action" width="120">
              <template #default="{ row }">
                <el-button size="small" text type="primary" @click="router.push(`/applications/${row.id}`)">
                  View →
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
        <el-empty v-else description="No applications linked yet" />
      </section>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="Created">{{ formatDate(store.currentGoal.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="Updated">{{ formatDate(store.currentGoal.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </template>

    <div v-else class="empty-container">
      <el-empty description="Research goal not found">
        <el-button @click="router.push('/research-goals')">Back to Research Goals</el-button>
      </el-empty>
    </div>
  </div>
</template>

<style scoped>
.detail-header { margin: 20px 0 24px 0; }
.detail-title { font-size: 28px; font-weight: 700; color: var(--color-text); margin: 0 0 12px 0; }
.header-tags { display: flex; gap: 8px; }
.detail-section { margin-bottom: 24px; }
.section-title { font-size: 18px; font-weight: 600; color: var(--color-text); margin: 0 0 8px 0; border-bottom: 1px solid var(--color-border); padding-bottom: 6px; }
.section-content { font-size: 15px; line-height: 1.6; color: var(--color-text); }
.info-text { color: var(--color-text-secondary); font-size: 14px; margin-bottom: 12px; }
.loading-container, .empty-container { padding: 60px 0; text-align: center; }
</style>
