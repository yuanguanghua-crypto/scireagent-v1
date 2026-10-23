import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { isInternal } from '@/utils/internalAccess'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomePage.vue'),
    meta: { title: 'Home', nav: 'public' },
  },
  {
    path: '/privacy',
    name: 'PrivacyPolicy',
    component: () => import('@/views/PrivacyPolicyPage.vue'),
    meta: { title: 'Privacy Policy', nav: 'public' },
  },
  {
    path: '/terms',
    name: 'TermsOfService',
    component: () => import('@/views/TermsPage.vue'),
    meta: { title: 'Terms of Service', nav: 'public' },
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
    // 密码重置第一步：输入邮箱，后端发一封带 token 的链接
    path: '/forgot-password',
    name: 'ForgotPassword',
    component: () => import('@/views/ForgotPasswordPage.vue'),
    meta: { title: 'Forgot Password', guest: true, nav: 'public' },
  },
  {
    // 密码重置第二步：邮件链接指向这里，query 里带 ?token=xxx
    path: '/reset-password',
    name: 'ResetPassword',
    component: () => import('@/views/ResetPasswordPage.vue'),
    // 不加 guest:true —— 已登录用户也可能点邮件里的链接来改密码
    meta: { title: 'Reset Password', nav: 'public' },
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
    path: '/applications/classes/:class_id',
    name: 'ConvergenceClassDetailAp',
    component: () => import('@/views/ConvergenceClassDetail.vue'),
    // group 固定为 ap；class_id 含下划线，用 props 透传保证原始值不被解码丢失
    props: (route) => ({ group: 'ap', class_id: route.params.class_id }),
    meta: { title: 'Convergence Class Detail', nav: 'public' },
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
    path: '/research-goals/classes/:class_id',
    name: 'ConvergenceClassDetailRg',
    component: () => import('@/views/ConvergenceClassDetail.vue'),
    // group 固定为 rg；class_id 含下划线，用 props 透传保证原始值不被解码丢失
    props: (route) => ({ group: 'rg', class_id: route.params.class_id }),
    meta: { title: 'Convergence Class Detail', nav: 'public' },
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
    // 匿名也可进入：后端 GET 返回 200 + 空列表，页面负责给出登录提示（不设 requiresAuth）
    path: '/wishlist',
    name: 'Wishlist',
    component: () => import('@/views/WishlistPage.vue'),
    meta: { title: 'My Wishlist', nav: 'public' },
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
    path: '/ops/orders',
    name: 'AdminOrders',
    component: () => import('@/views/admin/AdminOrdersPage.vue'),
    meta: { title: 'Order Management', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/ops/orders/:id',
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
    path: '/ops/po/review',
    name: 'PoReviewDesk',
    component: () => import('@/views/admin/PoReviewDesk.vue'),
    meta: { title: 'Order Review Desk', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/ops/po/shipments',
    name: 'PoShipmentDesk',
    component: () => import('@/views/admin/PoShipmentDesk.vue'),
    meta: { title: 'Shipment Desk', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/ops/po/invoicing',
    name: 'PoInvoicingDesk',
    component: () => import('@/views/admin/PoInvoicingDesk.vue'),
    meta: { title: 'Invoicing Desk', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/ops/po/ar',
    name: 'PoArReport',
    component: () => import('@/views/admin/PoArReport.vue'),
    meta: { title: 'AR Aging Report', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/ops/po/organizations',
    name: 'PoOrgManagement',
    component: () => import('@/views/admin/PoOrgManagement.vue'),
    meta: { title: 'Organization Management', requiresAuth: true, requiresAdmin: true },
  },
  {
    // ★ v4.1 DEV-1：库存管理台（入库/盘点调整/变动流水）—— F3 缺口
    path: '/ops/inventory',
    name: 'InventoryDesk',
    component: () => import('@/views/admin/InventoryDesk.vue'),
    meta: { title: 'Inventory Desk', requiresAuth: true, requiresAdmin: true },
  },
  {
    // ★ 2026-10-22：RFQ 收件箱 —— 此前客户提交的询价单**只有创建入口、无任何查询入口**
    //   （详情按 contact_email 过滤，连 staff 也 404，运营只能进 Django admin）。
    //   后端新增 GET /quote-requests/manage/（IsProcurementOrAdmin），本页为列表 + 详情。
    //   2026-10-23 起详情可填写报价（POST /quote-requests/:id/quote/），不再只读。
    //   ⚠️ requiresAdmin 用 utils/internalAccess.js 的 isInternal，与后端口径对齐。
    path: '/ops/rfq',
    name: 'RfqDesk',
    component: () => import('@/views/admin/RfqDesk.vue'),
    meta: { title: 'RFQ Inbox', requiresAuth: true, requiresAdmin: true },
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
      // 系统状态：邮件通道 / 投递队列 / 调度心跳 / DB（内部人员可读）
      { path: 'system', name: 'WorkspaceSystem', component: () => import('@/views/workspace/SystemStatusPage.vue'), meta: { title: 'System Status' } },
      // 用户与角色：改 role / 启停 / 验证邮箱 / 触发重置（IsAdmin）
      { path: 'users', name: 'WorkspaceUsers', component: () => import('@/views/workspace/UserManagementPage.vue'), meta: { title: 'Users & Roles' } },
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
    next(isInternal(auth) ? '/workspace' : '/')
    return
  }

  if (to.meta.requiresAuth && !hasToken) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // requiresAdmin：在守卫层统一做角色判定（不再 defer 给 AdminLayout）。
  // ★ 2026-10-14：内部人员 = is_staff 或 role∈(procurement, admin) —— 与后端权限类口径对齐
  //   （后端已允许 procurement 跨机构看所有订单；此前守卫仅认 isStaff ⇒ 非 staff 的 procurement 够不着内部台）。
  // ★ 2026-10-17：口径改为调用 utils/internalAccess.js 单一真相源（此前此处内联、9 个页面各一份，
  //   导致"路由放行 → 页面踢回"的分裂）。
  // 覆盖：5 个 PO 内部台 + /workspace + /ops/orders(+:id)。
  if (to.meta.requiresAdmin) {
    if (!hasToken) {
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
    if (!isInternal(auth)) {
      next('/') // 已登录但非内部人员：静默跳首页
      return
    }
  }

  next()
})

// ★ v4.1 DEV-7 SEO Phase B：每路由动态 title + meta description
const SITE_NAME = 'SciReagent'
router.afterEach((to) => {
  const title = to.meta?.title
  document.title = title ? `${title} | ${SITE_NAME}` : `${SITE_NAME} — AI-Native Scientific Reagent Platform`
  const desc = document.querySelector('meta[name="description"]')
  if (desc) {
    desc.setAttribute('content', to.meta?.description
      || 'Search reagents by CAS number, explore research applications, methods and protocols. B2B sales with COA/SDS compliance.')
  }
})

export default router
