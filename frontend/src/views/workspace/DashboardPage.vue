<script setup>
import { ref, onMounted } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { useRouter } from 'vue-router'
import { http } from '@/api/http'

const auth = useAuthStore()
const router = useRouter()

console.log('DashboardPage mounted, isStaff:', auth.isStaff, 'token:', !!localStorage.getItem('token'))

if (!auth.isStaff) {
  router.replace('/')
}

const stats = ref({
  total_products: 0, active_products: 0, draft_products: 0,
  incomplete_products: 0, products_with_cas: 0,
  products_with_smiles: 0, products_with_knowledge: 0,
  total_goals: 0, total_applications: 0,
  total_methods: 0, total_protocols: 0,
})
const recentProducts = ref([])
const loading = ref(true)
const error = ref('')

function pct(n, total) {
  if (!total) return 0
  return Math.round(n / total * 100)
}

onMounted(async () => {
  try {
    console.log('Fetching dashboard stats...')
    const resp = await http.get('/admin/dashboard-stats/')
    console.log('Dashboard resp:', JSON.stringify(resp).slice(0, 300))
    if (resp.success) {
      stats.value = resp.data
    }
    // Load recent products
    const prodResp = await http.get('/products/', { params: { page_size: 10, ordering: '-updated_at' } })
    console.log('Products resp:', JSON.stringify(prodResp).slice(0, 300))
    if (prodResp.success) {
      recentProducts.value = (prodResp.data.results || prodResp.data).slice(0, 10)
    }
  } catch (e) {
    console.error('Dashboard error:', e)
    error.value = 'Failed to load dashboard data'
  } finally {
    loading.value = false
  }
})
</script>

<template>
  <div class="dashboard">
    <div v-if="loading" class="loading">Loading...</div>
    <div v-else-if="error" class="error">{{ error }}</div>
    <template v-else>
      <!-- Stats cards -->
      <div class="stats-grid">
        <div class="stat-card">
          <div class="stat-value">{{ stats.total_products }}</div>
          <div class="stat-label">Total Products</div>
        </div>
        <div class="stat-card stat-card--success">
          <div class="stat-value">{{ stats.active_products }}</div>
          <div class="stat-label">Active</div>
        </div>
        <div class="stat-card stat-card--warning">
          <div class="stat-value">{{ stats.incomplete_products }}</div>
          <div class="stat-label">Incomplete</div>
        </div>
        <div class="stat-card">
          <div class="stat-value">{{ pct(stats.products_with_cas, stats.total_products) }}%</div>
          <div class="stat-label">CAS Coverage</div>
        </div>
      </div>

      <!-- Quick actions -->
      <div class="actions-bar">
        <router-link to="/workspace/products/new" class="btn btn-primary">+ New Product</router-link>
      </div>

      <!-- Data health -->
      <div class="section">
        <h3 class="section-title">Data Health</h3>
        <div class="health-grid">
          <div class="health-item">
            <span class="health-label">CAS</span>
            <span class="health-value">{{ stats.products_with_cas }} / {{ stats.total_products }}</span>
            <span class="health-pct">{{ pct(stats.products_with_cas, stats.total_products) }}%</span>
          </div>
          <div class="health-item">
            <span class="health-label">SMILES</span>
            <span class="health-value">{{ stats.products_with_smiles }} / {{ stats.total_products }}</span>
            <span class="health-pct">{{ pct(stats.products_with_smiles, stats.total_products) }}%</span>
          </div>
          <div class="health-item">
            <span class="health-label">Knowledge Link</span>
            <span class="health-value">{{ stats.products_with_knowledge }} / {{ stats.total_products }}</span>
            <span class="health-pct">{{ pct(stats.products_with_knowledge, stats.total_products) }}%</span>
          </div>
        </div>
      </div>

      <!-- Knowledge graph -->
      <div class="section">
        <h3 class="section-title">Knowledge Graph</h3>
        <div class="kg-grid">
          <span>Goals: <strong>{{ stats.total_goals }}</strong></span>
          <span>Applications: <strong>{{ stats.total_applications }}</strong></span>
          <span>Methods: <strong>{{ stats.total_methods }}</strong></span>
          <span>Protocols: <strong>{{ stats.total_protocols }}</strong></span>
        </div>
      </div>

      <!-- Recent activity -->
      <div class="section">
        <h3 class="section-title">Recently Updated</h3>
        <table class="recent-table" v-if="recentProducts.length">
          <thead>
            <tr>
              <th>Catalog No</th>
              <th>Name</th>
              <th>Status</th>
              <th>Updated</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="p in recentProducts" :key="p.id">
              <td>{{ p.catalog_no }}</td>
              <td>
                <router-link :to="`/workspace/products/${p.id}/edit`">{{ p.name }}</router-link>
              </td>
              <td><span class="status-tag" :class="`status-${p.status}`">{{ p.status }}</span></td>
              <td>{{ p.updated_at ? new Date(p.updated_at).toLocaleDateString() : '—' }}</td>
            </tr>
          </tbody>
        </table>
        <p v-else class="empty-text">No products yet.</p>
      </div>
    </template>
  </div>
</template>

<style scoped>
.dashboard { max-width: 900px; }
.stats-grid { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
.stat-card { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 20px; text-align: center; }
.stat-value { font-size: 28px; font-weight: 700; color: var(--color-text); }
.stat-label { font-size: 13px; color: var(--color-text-secondary); margin-top: 4px; }
.stat-card--success .stat-value { color: var(--color-success); }
.stat-card--warning .stat-value { color: var(--color-warning); }
.actions-bar { margin-bottom: 24px; }
.section { margin-bottom: 24px; }
.section-title { font-size: 16px; font-weight: 600; margin-bottom: 12px; color: var(--color-text); }
.health-grid { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 16px; display: flex; flex-direction: column; gap: 12px; }
.health-item { display: flex; align-items: center; gap: 12px; }
.health-label { font-weight: 600; min-width: 100px; font-size: 13px; color: var(--color-text-secondary); }
.health-value { font-size: 14px; color: var(--color-text); }
.health-pct { font-weight: 700; font-size: 14px; color: var(--color-primary); margin-left: auto; }
.kg-grid { background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; padding: 16px; display: flex; gap: 24px; font-size: 14px; color: var(--color-text); }
.recent-table { width: 100%; border-collapse: collapse; background: var(--color-surface); border: 1px solid var(--color-border); border-radius: 12px; overflow: hidden; }
.recent-table th, .recent-table td { text-align: left; padding: 10px 16px; font-size: 13px; }
.recent-table th { background: var(--color-bg); font-weight: 600; color: var(--color-text-secondary); border-bottom: 1px solid var(--color-border); }
.recent-table td { border-bottom: 1px solid var(--color-border); color: var(--color-text); }
.recent-table a { color: var(--color-primary); text-decoration: none; }
.status-tag { padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: 500; }
.status-active { background: #dcf7e8; color: #176b3a; }
.status-draft { background: #ffeeba; color: #856404; }
.loading, .error { text-align: center; padding: 40px; color: var(--color-text-secondary); }
.empty-text { color: var(--color-text-secondary); font-size: 14px; }
</style>
