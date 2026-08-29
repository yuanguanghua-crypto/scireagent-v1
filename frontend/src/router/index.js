import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomePage.vue'),
    meta: { title: 'Home', nav: 'public' },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginPage.vue'),
    meta: { title: 'Sign In', guest: true, nav: 'public' },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterPage.vue'),
    meta: { title: 'Register', guest: true, nav: 'public' },
  },
  {
    path: '/verify-email',
    name: 'VerifyEmail',
    component: () => import('@/views/VerifyEmailPage.vue'),
    meta: { title: 'Verify Email', nav: 'public' },
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('@/views/SearchPage.vue'),
    meta: { title: 'Search', nav: 'public' },
  },
  {
    path: '/applications',
    name: 'Applications',
    component: () => import('@/views/ApplicationIndex.vue'),
    meta: { title: 'Applications', nav: 'public' },
  },
  {
    path: '/applications/:id',
    name: 'ApplicationDetail',
    component: () => import('@/views/ApplicationDetail.vue'),
    meta: { title: 'Application Detail', nav: 'public' },
  },
  {
    path: '/methods',
    name: 'Methods',
    component: () => import('@/views/MethodIndex.vue'),
    meta: { title: 'Methods', nav: 'public' },
  },
  {
    path: '/methods/:id',
    name: 'MethodDetail',
    component: () => import('@/views/MethodDetail.vue'),
    meta: { title: 'Method Detail', nav: 'public' },
  },
  {
    path: '/protocols',
    name: 'Protocols',
    component: () => import('@/views/ProtocolIndex.vue'),
    meta: { title: 'Protocols', nav: 'public' },
  },
  {
    path: '/protocols/:id',
    name: 'ProtocolDetail',
    component: () => import('@/views/ProtocolDetail.vue'),
    meta: { title: 'Protocol Detail', nav: 'public' },
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/views/ProductIndex.vue'),
    meta: { title: 'Products', nav: 'public' },
  },
  {
    path: '/products/:id',
    name: 'ProductDetail',
    component: () => import('@/views/ProductDetail.vue'),
    meta: { title: 'Product Detail', nav: 'public' },
  },
  {
    path: '/about',
    name: 'About',
    component: () => import('@/views/AboutPage.vue'),
    meta: { title: 'About', nav: 'public' },
  },
  {
    path: '/research-goals',
    name: 'ResearchGoals',
    component: () => import('@/views/ResearchGoalIndex.vue'),
    meta: { title: 'Research Goals', nav: 'public' },
  },
  {
    path: '/research-goals/:id',
    name: 'ResearchGoalDetail',
    component: () => import('@/views/ResearchGoalDetail.vue'),
    meta: { title: 'Research Goal Detail', nav: 'public' },
  },
  {
    path: '/quote-request',
    name: 'QuoteRequest',
    component: () => import('@/views/QuoteRequestPage.vue'),
    meta: { title: 'Request Quote', nav: 'public' },
  },
  {
    path: '/cart',
    name: 'Cart',
    component: () => import('@/views/CartPage.vue'),
    meta: { title: 'Shopping Cart', nav: 'public' },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsPage.vue'),
    meta: { title: 'Settings', requiresAuth: true },
  },
  {
    path: '/checkout',
    name: 'Checkout',
    component: () => import('@/views/CheckoutPage.vue'),
    meta: { title: 'Checkout', requiresAuth: true },
  },
  {
    path: '/orders',
    name: 'Orders',
    component: () => import('@/views/OrderListPage.vue'),
    meta: { title: 'My Orders', requiresAuth: true },
  },
  {
    path: '/orders/:id',
    name: 'OrderDetail',
    component: () => import('@/views/OrderDetailPage.vue'),
    meta: { title: 'Order Detail', requiresAuth: true },
  },
  {
    path: '/admin/orders',
    name: 'AdminOrders',
    component: () => import('@/views/admin/AdminOrdersPage.vue'),
    meta: { title: 'Order Management', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/orders/:id',
    name: 'AdminOrderDetail',
    component: () => import('@/views/admin/AdminOrderDetail.vue'),
    meta: { title: 'Order Processing', requiresAuth: true, requiresAdmin: true },
  },

  // ── PO 采购门户 — 客户侧（节点 1~6） ──
  {
    path: '/po/submit',
    name: 'PoSubmit',
    component: () => import('@/views/po/PoSubmit.vue'),
    meta: { title: 'Submit Purchase Order', requiresAuth: true },
  },
  {
    path: '/po/orders',
    name: 'PoOrders',
    component: () => import('@/views/po/PoOrderList.vue'),
    meta: { title: 'My Purchase Orders', requiresAuth: true },
  },
  {
    path: '/po/orders/:id',
    name: 'PoOrderDetail',
    component: () => import('@/views/po/PoOrderDetail.vue'),
    meta: { title: 'Purchase Order Detail', requiresAuth: true },
  },
  {
    path: '/po/addresses',
    name: 'PoAddresses',
    component: () => import('@/views/po/PoAddressList.vue'),
    meta: { title: 'Address Book', requiresAuth: true },
  },
  {
    path: '/po/reorder',
    name: 'PoReorder',
    component: () => import('@/views/po/PoReorder.vue'),
    meta: { title: 'Re-order', requiresAuth: true },
  },
  {
    path: '/po/downloads',
    name: 'PoDownloads',
    component: () => import('@/views/po/PoDownloadCenter.vue'),
    meta: { title: 'Download Center', requiresAuth: true },
  },

  // ── PO 采购门户 — 内部台（节点 A~E） ──
  {
    path: '/admin/po/review',
    name: 'PoReviewDesk',
    component: () => import('@/views/admin/PoReviewDesk.vue'),
    meta: { title: 'Order Review Desk', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/po/shipments',
    name: 'PoShipmentDesk',
    component: () => import('@/views/admin/PoShipmentDesk.vue'),
    meta: { title: 'Shipment Desk', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/po/invoicing',
    name: 'PoInvoicingDesk',
    component: () => import('@/views/admin/PoInvoicingDesk.vue'),
    meta: { title: 'Invoicing Desk', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/po/ar',
    name: 'PoArReport',
    component: () => import('@/views/admin/PoArReport.vue'),
    meta: { title: 'AR Aging Report', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/po/organizations',
    name: 'PoOrgManagement',
    component: () => import('@/views/admin/PoOrgManagement.vue'),
    meta: { title: 'Organization Management', requiresAuth: true, requiresAdmin: true },
  },
  // ── Workspace routes ──────────────────────────────
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('@/views/workspace/AdminLayout.vue'),
    meta: { title: 'Dashboard', requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('@/views/workspace/DashboardPage.vue'), meta: { title: 'Dashboard' } },
      { path: 'products', name: 'WorkspaceProducts', component: () => import('@/views/workspace/ProductsPage.vue'), meta: { title: 'Products' } },
      { path: 'products/new', name: 'WorkspaceProductNew', component: () => import('@/views/workspace/ProductEditPage.vue'), meta: { title: 'New Product' } },
      { path: 'products/:id/edit', name: 'WorkspaceProductEdit', component: () => import('@/views/workspace/ProductEditPage.vue'), meta: { title: 'Edit Product' } },
      { path: 'goals', name: 'WorkspaceGoals', component: () => import('@/views/workspace/GoalsPage.vue'), meta: { title: 'Research Goals' } },
      { path: 'applications', name: 'WorkspaceApps', component: () => import('@/views/workspace/AppsPage.vue'), meta: { title: 'Applications' } },
      { path: 'methods', name: 'WorkspaceMethods', component: () => import('@/views/workspace/MethodsPage.vue'), meta: { title: 'Methods' } },
      { path: 'protocols', name: 'WorkspaceProtocols', component: () => import('@/views/workspace/ProtocolsPage.vue'), meta: { title: 'Protocols' } },
      { path: 'references', name: 'WorkspaceRefs', component: () => import('@/views/workspace/ReferencesPage.vue'), meta: { title: 'References' } },
      { path: 'verified', name: 'WorkspaceVerified', component: () => import('@/views/workspace/VerifiedPage.vue'), meta: { title: 'Verified Applicability' } },
      { path: 'knowledge-intake', name: 'WorkspaceKnowledgeIntake', component: () => import('@/views/KnowledgeIntake.vue'), meta: { title: 'Knowledge Intake' } },
    ],
  },
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404', nav: 'public' },
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior(to, from, savedPosition) {
    if (savedPosition) return savedPosition
    return { top: 0 }
  },
})

router.beforeEach((to, from, next) => {
  document.title = `${to.meta.title || 'SciReagent'} - LabPro Global`

  const hasToken = !!localStorage.getItem('token')
  const auth = useAuthStore()

  // 已登录用户不应停留在登录/注册页（guest 路由），按角色跳离
  if (to.meta.guest && hasToken) {
    next(auth.isStaff ? '/workspace' : '/')
    return
  }

  if (to.meta.requiresAuth && !hasToken) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // requiresAdmin：在守卫层统一做角色判定（不再 defer 给 AdminLayout）。
  // auth.isStaff 同步自 localStorage 缓存（auth.js:11,23），刷新页面也能即时判定，无需异步等待 profile。
  // 覆盖：5 个 PO 内部台 + /workspace + /admin/orders(+:id)。
  if (to.meta.requiresAdmin) {
    if (!hasToken) {
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
    if (!auth.isStaff) {
      next('/') // 已登录但非 staff：静默跳首页（与 AdminLayout 现状一致）
      return
    }
  }

  next()
})

export default router
