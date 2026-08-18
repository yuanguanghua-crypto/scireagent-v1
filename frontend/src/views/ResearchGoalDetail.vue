<script setup>
import { onMounted, onUnmounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResearchGoalsStore } from '@/stores/researchGoals'
import { formatDate, getStatusType } from '@/utils/helpers'
import { AppButton } from '@/components/common'

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
        <h2 class="section-title">Curated Protocols</h2>
        <div v-if="store.currentGoal.protocols?.length">
          <el-table :data="store.currentGoal.protocols" stripe>
            <el-table-column label="Protocol" min-width="260">
              <template #default="{ row }">
                <router-link :to="`/protocols/${row.id}`" class="protocol-link">{{ row.name }}</router-link>
              </template>
            </el-table-column>
            <el-table-column prop="slug" label="Slug" min-width="200" />
          </el-table>
        </div>
        <el-empty v-else description="No curated protocols yet" />
      </section>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="Created">{{ formatDate(store.currentGoal.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="Updated">{{ formatDate(store.currentGoal.updated_at) }}</el-descriptions-item>
      </el-descriptions>
    </template>

    <div v-else class="empty-container">
      <el-empty description="Research goal not found">
        <AppButton variant="ghost" @click="router.push('/research-goals')">Back to Research Goals</AppButton>
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
.protocol-link { color: var(--color-primary); text-decoration: none; font-weight: 500; }
.protocol-link:hover { text-decoration: underline; }
.loading-container, .empty-container { padding: 60px 0; text-align: center; }
</style>
