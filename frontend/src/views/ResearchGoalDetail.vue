<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useResearchGoalsStore } from '@/stores/researchGoals'
import { formatDate, getStatusType } from '@/utils/helpers'
import { AppButton } from '@/components/common'

const route = useRoute()
const router = useRouter()
const store = useResearchGoalsStore()

/* ★ 2026-10-30（走查发现）：本页两个 el-table 原本无分页，直接 `:data` 绑全量
   —— 生产 RNA Analysis 有 496 条协议，实测本地 778 条时页面被撑到 **33,524px**，
   一次性渲染 778 个 <tr>，滚动和首屏都很糟。
   Method 详情页此前踩过同一个坑（585 条 → 8,325px），用「只渲染前 20 条」修过；
   这里是表格，用分页更合适（能看到总数、可翻页）。 */
const PAGE_SIZE = 20

const appPage = ref(1)
const protoPage = ref(1)

const appList = computed(() => store.currentGoal?.application_collection || [])
const protoList = computed(() => store.currentGoal?.protocols || [])

const pagedApps = computed(() => {
  const start = (appPage.value - 1) * PAGE_SIZE
  return appList.value.slice(start, start + PAGE_SIZE)
})
const pagedProtocols = computed(() => {
  const start = (protoPage.value - 1) * PAGE_SIZE
  return protoList.value.slice(start, start + PAGE_SIZE)
})

// 换目标（路由参数变化）时把页码复位，避免停在越界页显示空白
watch(() => route.params.id, () => {
  appPage.value = 1
  protoPage.value = 1
})

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

      <!-- ★ 2026-10-30 补：AG→AP 这一段此前在页面上**完全缺失**。
           序列化器早就返回 `application_collection`（`serializers.py:57/66`，
           典型一个研究目标挂 3 个技术族），但本页只渲染 Summary 与 Curated Protocols
           ⇒ 用户从知识图谱顶层点进来后**无路可走**，主链 RG→AP 在 UI 上断掉。
           位置按链路顺序放在 Summary 之后、Protocols 之前。 -->
      <section class="detail-section">
        <h2 class="section-title">
          Applications
          <span v-if="store.currentGoal.application_collection?.length" class="count-badge">
            {{ store.currentGoal.application_collection.length }}
          </span>
        </h2>
        <div v-if="store.currentGoal.application_collection?.length">
          <el-table :data="pagedApps" stripe>
            <el-table-column label="Application" min-width="260">
              <template #default="{ row }">
                <router-link :to="`/applications/${row.id}`" class="protocol-link">{{ row.name }}</router-link>
              </template>
            </el-table-column>
            <el-table-column prop="slug" label="Slug" min-width="200" />
          </el-table>
          <el-pagination
            v-if="appList.length > PAGE_SIZE"
            v-model:current-page="appPage"
            :page-size="PAGE_SIZE"
            :total="appList.length"
            layout="total, prev, pager, next"
            background
            class="section-pager"
          />
        </div>
        <el-empty v-else description="No applications linked to this research goal yet" />
      </section>

      <section class="detail-section">
        <h2 class="section-title">Curated Protocols</h2>
        <div v-if="store.currentGoal.protocols?.length">
          <el-table :data="pagedProtocols" stripe>
            <el-table-column label="Protocol" min-width="260">
              <template #default="{ row }">
                <router-link :to="`/protocols/${row.id}`" class="protocol-link">{{ row.name }}</router-link>
              </template>
            </el-table-column>
            <el-table-column prop="slug" label="Slug" min-width="200" />
          </el-table>
          <el-pagination
            v-if="protoList.length > PAGE_SIZE"
            v-model:current-page="protoPage"
            :page-size="PAGE_SIZE"
            :total="protoList.length"
            layout="total, prev, pager, next"
            background
            class="section-pager"
          />
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
.count-badge {
  display: inline-block; margin-left: 8px; padding: 1px 8px;
  font-size: 12px; font-weight: 600; line-height: 18px;
  color: var(--color-text-secondary); background: var(--color-bg-alt);
  border: 1px solid var(--color-border); border-radius: 9999px;
  vertical-align: middle;
}
.section-content { font-size: 15px; line-height: 1.6; color: var(--color-text); }
.info-text { color: var(--color-text-secondary); font-size: 14px; margin-bottom: 12px; }
.protocol-link { color: var(--color-primary); text-decoration: none; font-weight: 500; }
.protocol-link:hover { text-decoration: underline; }
.section-pager { margin-top: 12px; justify-content: flex-end; display: flex; }
.loading-container, .empty-container { padding: 60px 0; text-align: center; }
</style>
