<script setup>
import { computed, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isInternal } from '@/utils/internalAccess'

const auth = useAuthStore()
const router = useRouter()
const route = useRoute()

// ── 侧栏分组折叠 ───────────────────────────────────────────────────────
// 22 项平铺太长（要滚动才看全），所以每组标题可点击折叠。
// 三条规则：
//   1. 折叠状态存 localStorage，刷新后保持
//   2. **当前路由所在分组强制展开** —— 否则会出现"当前页被折叠起来看不见"
//      的困惑；这条不写入存储，切走再回来仍按用户自己的偏好
//   3. 默认全部展开（首次访问的人不该看到一堆收起的标题）
const GROUP_STORAGE_KEY = 'workspace.sidebar.collapsed'
const GROUP_NAMES = ['Overview', 'Products', 'Knowledge', 'Operations', 'System']

function readCollapsed() {
  try {
    const raw = JSON.parse(localStorage.getItem(GROUP_STORAGE_KEY) || '[]')
    return Array.isArray(raw) ? raw.filter((n) => GROUP_NAMES.includes(n)) : []
  } catch {
    return []
  }
}

const collapsedGroups = ref(new Set(readCollapsed()))

/** 当前路由属于哪个分组 —— 用于强制展开。 */
const activeGroup = computed(() => {
  const p = route.path
  if (p.startsWith('/ops/')) return 'Operations'
  if (p === '/workspace' || p === '/workspace/') return 'Overview'
  if (p.startsWith('/workspace/products')) return 'Products'
  if (/^\/workspace\/(system|users|email-templates|email-outbox|audit-log)/.test(p)) return 'System'
  return 'Knowledge'
})

function isCollapsed(name) {
  if (name === activeGroup.value) return false   // 当前页所在组永远展开
  return collapsedGroups.value.has(name)
}

function toggleGroup(name) {
  if (name === activeGroup.value) return        // 当前组不允许折叠
  const next = new Set(collapsedGroups.value)
  if (next.has(name)) next.delete(name)
  else next.add(name)
  collapsedGroups.value = next
  try {
    localStorage.setItem(GROUP_STORAGE_KEY, JSON.stringify([...next]))
  } catch { /* 隐私模式下不可写 —— 折叠仍生效，只是不记忆 */ }
}

// ★ 内部人员判定收敛到 utils/internalAccess.js（口径= is_staff || role∈(procurement,admin)）
//   ——与后端 permissions.py IsProcurementOrAdmin 一致；普通注册用户仍被踢回首页。
if (!isInternal(auth)) {
  router.replace('/')
}
</script>

<template>
  <div class="workspace-layout">
    <aside class="workspace-sidebar">
      <div class="sidebar-header">
        <router-link to="/workspace" class="sidebar-brand">
          <span class="brand-icon">🧪</span>
          <span class="brand-text">SciReAgent</span>
        </router-link>
      </div>

      <nav class="sidebar-nav">
        <div class="nav-group" :class="{ 'is-collapsed': isCollapsed('Overview') }">
          <div
            class="nav-group-title"
            :class="{ 'is-locked': 'Overview' === activeGroup }"
            :title="'Overview' === activeGroup ? '当前所在分组（不可折叠）' : '点击折叠 / 展开'"
            @click="toggleGroup('Overview')"
          >
            <span>Overview</span>
            <svg
              class="nav-chev"
              :class="{ 'is-open': !isCollapsed('Overview') }"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            ><polyline points="9 6 15 12 9 18" /></svg>
          </div>
          <router-link to="/workspace" class="nav-item" exact-active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" />
              <rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
            </svg>
            Dashboard
          </router-link>
        </div>

        <div class="nav-group" :class="{ 'is-collapsed': isCollapsed('Products') }">
          <div
            class="nav-group-title"
            :class="{ 'is-locked': 'Products' === activeGroup }"
            :title="'Products' === activeGroup ? '当前所在分组（不可折叠）' : '点击折叠 / 展开'"
            @click="toggleGroup('Products')"
          >
            <span>Products</span>
            <svg
              class="nav-chev"
              :class="{ 'is-open': !isCollapsed('Products') }"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            ><polyline points="9 6 15 12 9 18" /></svg>
          </div>
          <router-link to="/workspace/products" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M20 7l-8-4-8 4m16 0l-8 4m8-4v10l-8 4m0-10L4 7m8 4v10M4 7v10l8 4" />
            </svg>
            Products
          </router-link>
        </div>

        <div class="nav-group" :class="{ 'is-collapsed': isCollapsed('Knowledge') }">
          <div
            class="nav-group-title"
            :class="{ 'is-locked': 'Knowledge' === activeGroup }"
            :title="'Knowledge' === activeGroup ? '当前所在分组（不可折叠）' : '点击折叠 / 展开'"
            @click="toggleGroup('Knowledge')"
          >
            <span>Knowledge</span>
            <svg
              class="nav-chev"
              :class="{ 'is-open': !isCollapsed('Knowledge') }"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            ><polyline points="9 6 15 12 9 18" /></svg>
          </div>
          <router-link to="/workspace/goals" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="16" /><line x1="8" y1="12" x2="16" y2="12" />
            </svg>
            Research Goals
          </router-link>
          <router-link to="/workspace/applications" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" /><polyline points="14 2 14 8 20 8" />
            </svg>
            Applications
          </router-link>
          <router-link to="/workspace/methods" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <polyline points="16 18 22 12 16 6" /><polyline points="8 6 2 12 8 18" />
            </svg>
            Methods
          </router-link>
          <router-link to="/workspace/protocols" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2" />
              <rect x="9" y="3" width="6" height="4" rx="1" />
            </svg>
            Protocols
          </router-link>
          <router-link to="/workspace/references" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M4 6h16M4 10h16M4 14h16M4 18h12" />
            </svg>
            References
          </router-link>
          <router-link to="/workspace/verified" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M20 6L9 17l-5-5" />
            </svg>
            Verified Applicability
          </router-link>
          <router-link to="/workspace/knowledge-intake" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M12 5v14M5 12h14" />
            </svg>
            Knowledge Intake
          </router-link>
        </div>

        <!-- 运营：交易履约。8 个台统一挂在 AdminLayout 下（见 router 里 /ops 父路由），
             点进来仍在本侧栏内，不会再"跳出导航"。 -->
        <div class="nav-group" :class="{ 'is-collapsed': isCollapsed('Operations') }">
          <div
            class="nav-group-title"
            :class="{ 'is-locked': 'Operations' === activeGroup }"
            :title="'Operations' === activeGroup ? '当前所在分组（不可折叠）' : '点击折叠 / 展开'"
            @click="toggleGroup('Operations')"
          >
            <span>Operations</span>
            <svg
              class="nav-chev"
              :class="{ 'is-open': !isCollapsed('Operations') }"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            ><polyline points="9 6 15 12 9 18" /></svg>
          </div>
          <router-link to="/ops/orders" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M6 2h12l2 4v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6z" /><path d="M4 6h16M9 12h6M9 16h6" />
            </svg>
            Orders
          </router-link>
          <router-link to="/ops/rfq" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z" />
            </svg>
            RFQ Inbox
          </router-link>
          <router-link to="/ops/po/review" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M9 11l3 3L22 4" /><path d="M21 12v7a2 2 0 01-2 2H5a2 2 0 01-2-2V5a2 2 0 012-2h11" />
            </svg>
            Order Review
          </router-link>
          <router-link to="/ops/po/shipments" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M1 3h15v13H1z" /><path d="M16 8h4l3 3v5h-7z" />
              <circle cx="5.5" cy="18.5" r="2.5" /><circle cx="18.5" cy="18.5" r="2.5" />
            </svg>
            Shipments
          </router-link>
          <router-link to="/ops/po/invoicing" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" /><path d="M8 13h8M8 17h5" />
            </svg>
            Invoicing
          </router-link>
          <router-link to="/ops/po/ar" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M3 3v18h18" /><path d="M7 15l4-5 3 3 5-7" />
            </svg>
            AR Aging
          </router-link>
          <router-link to="/ops/po/organizations" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M3 21h18M5 21V7l7-4 7 4v14M9 21v-6h6v6" />
            </svg>
            Organizations
          </router-link>
          <router-link to="/ops/inventory" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z" />
              <polyline points="3.27 6.96 12 12.01 20.73 6.96" /><line x1="12" y1="22.08" x2="12" y2="12" />
            </svg>
            Inventory
          </router-link>
        </div>

        <!-- 系统：排障与配置。组内条目按"是否需要脱离 Django admin"逐步搬过来。 -->
        <div class="nav-group" :class="{ 'is-collapsed': isCollapsed('System') }">
          <div
            class="nav-group-title"
            :class="{ 'is-locked': 'System' === activeGroup }"
            :title="'System' === activeGroup ? '当前所在分组（不可折叠）' : '点击折叠 / 展开'"
            @click="toggleGroup('System')"
          >
            <span>System</span>
            <svg
              class="nav-chev"
              :class="{ 'is-open': !isCollapsed('System') }"
              viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"
            ><polyline points="9 6 15 12 9 18" /></svg>
          </div>
          <router-link to="/workspace/system" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 11-2.83 2.83l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 11-4 0v-.09A1.65 1.65 0 008.6 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 11-2.83-2.83l.06-.06a1.65 1.65 0 00.33-1.82 1.65 1.65 0 00-1.51-1H3a2 2 0 110-4h.09A1.65 1.65 0 004.6 8.6a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 112.83-2.83l.06.06a1.65 1.65 0 001.82.33H9a1.65 1.65 0 001-1.51V3a2 2 0 114 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 112.83 2.83l-.06.06a1.65 1.65 0 00-.33 1.82V9a1.65 1.65 0 001.51 1H21a2 2 0 110 4h-.09a1.65 1.65 0 00-1.51 1z" />
            </svg>
            System Status
          </router-link>
          <router-link to="/workspace/users" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" />
              <circle cx="9" cy="7" r="4" />
              <path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" />
            </svg>
            Users &amp; Roles
          </router-link>
          <router-link to="/workspace/email-templates" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M4 4h16v16H4z" /><path d="M4 8h16" />
            </svg>
            Email Templates
          </router-link>
          <router-link to="/workspace/email-outbox" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M22 12h-6l-2 3h-4l-2-3H2" />
              <path d="M5.45 5.11L2 12v6a2 2 0 002 2h16a2 2 0 002-2v-6l-3.45-6.89A2 2 0 0016.76 4H7.24a2 2 0 00-1.79 1.11z" />
            </svg>
            Delivery Queue
          </router-link>
          <router-link to="/workspace/audit-log" class="nav-item" active-class="active">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z" />
              <polyline points="14 2 14 8 20 8" />
              <path d="M8 13h8M8 17h5" />
            </svg>
            Audit Log
          </router-link>
        </div>
      </nav>

      <div class="sidebar-footer">
        <router-link to="/" class="nav-item">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" class="nav-icon">
            <path d="M3 9l9-7 9 7v11a2 2 0 01-2 2H5a2 2 0 01-2-2z" /><polyline points="9 22 9 12 15 12 15 22" />
          </svg>
          Back to Site
        </router-link>
      </div>
    </aside>

    <main class="workspace-main">
      <!-- meta.bareHeader：/ops/* 那 8 个运营台各自带 po-page-header（h1 + 操作按钮），
           不关掉这里会产生双层标题。 -->
      <header v-if="!$route.meta.bareHeader" class="workspace-header">
        <h1 class="workspace-title">{{ $route.meta.title || 'Workspace' }}</h1>
      </header>
      <div class="workspace-content">
        <router-view />
      </div>
    </main>
  </div>
</template>

<style scoped>
.workspace-layout {
  display: flex; height: 100vh; background: var(--color-bg);
}
.workspace-sidebar {
  width: 240px; background: var(--color-surface); border-right: 1px solid var(--color-border);
  display: flex; flex-direction: column; flex-shrink: 0; overflow-y: auto;
}
.sidebar-header { padding: 20px; border-bottom: 1px solid var(--color-border); }
.sidebar-brand { display: flex; align-items: center; gap: 10px; text-decoration: none; }
.brand-icon { font-size: 24px; }
.brand-text { font-size: 18px; font-weight: 700; color: var(--color-text); }
.sidebar-nav { flex: 1; padding: 12px 8px; }
.nav-group { margin-bottom: 8px; }
/* 分组标题：可点击折叠。当前所在分组 is-locked —— 不允许收起 */
.nav-group-title {
  display: flex; align-items: center; justify-content: space-between; gap: 6px;
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--color-text-secondary); padding: 8px 12px 4px;
  cursor: pointer; user-select: none;
}
.nav-group-title:hover { color: var(--color-text); }
.nav-group-title.is-locked { cursor: default; }
.nav-group-title.is-locked:hover { color: var(--color-text-secondary); }
.nav-chev {
  width: 12px; height: 12px; flex: 0 0 auto;
  transition: transform .15s ease; opacity: .6;
}
.nav-chev.is-open { transform: rotate(90deg); }
/* 折叠：整组隐藏。用 class 控制而不改 DOM 结构，22 个链接的模板一行都不动。 */
.nav-group.is-collapsed .nav-item { display: none; }
.nav-item { display: flex; align-items: center; gap: 10px; padding: 8px 12px; border-radius: 8px; text-decoration: none; font-size: 14px; color: var(--color-text-secondary); transition: background 0.15s, color 0.15s; }
.nav-item:hover { background: var(--color-bg); color: var(--color-text); }
.nav-item.active { background: var(--color-primary-light); color: var(--color-primary-active); font-weight: 600; }
.nav-item--disabled { pointer-events: none; opacity: 0.4; }
.nav-icon { width: 18px; height: 18px; flex-shrink: 0; }
.sidebar-footer { padding: 12px 8px; border-top: 1px solid var(--color-border); }
.workspace-main { flex: 1; display: flex; flex-direction: column; overflow-y: auto; }
.workspace-header { padding: 16px 24px; border-bottom: 1px solid var(--color-border); background: var(--color-surface); display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.workspace-title { font-size: 20px; font-weight: 600; color: var(--color-text); margin: 0; }
.workspace-content { flex: 1; padding: 24px; max-width: var(--content-max-width); width: 100%; }

/* Wide screen: expand workspace content */
@media (min-width: 1400px) {
  .workspace-content { max-width: 1440px; }
}
@media (min-width: 1800px) {
  .workspace-content { max-width: 1600px; }
}
@media (min-width: 2560px) {
  .workspace-content { max-width: 1920px; }
}
</style>
