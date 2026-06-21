import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomePage.vue'),
    meta: { title: 'Home', noSidebar: true },
  },
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/LoginPage.vue'),
    meta: { title: 'Sign In', guest: true },
  },
  {
    path: '/register',
    name: 'Register',
    component: () => import('@/views/RegisterPage.vue'),
    meta: { title: 'Register', guest: true },
  },
  {
    path: '/search',
    name: 'Search',
    component: () => import('@/views/SearchPage.vue'),
    meta: { title: 'Search', noSidebar: true },
  },
  {
    path: '/applications',
    name: 'Applications',
    component: () => import('@/views/ApplicationIndex.vue'),
    meta: { title: 'Applications', noSidebar: true },
  },
  {
    path: '/applications/:id',
    name: 'ApplicationDetail',
    component: () => import('@/views/ApplicationDetail.vue'),
    meta: { title: 'Application Detail', noSidebar: true },
  },
  {
    path: '/methods',
    name: 'Methods',
    component: () => import('@/views/MethodIndex.vue'),
    meta: { title: 'Methods', noSidebar: true },
  },
  {
    path: '/methods/:id',
    name: 'MethodDetail',
    component: () => import('@/views/MethodDetail.vue'),
    meta: { title: 'Method Detail', noSidebar: true },
  },
  {
    path: '/protocols',
    name: 'Protocols',
    component: () => import('@/views/ProtocolIndex.vue'),
    meta: { title: 'Protocols', noSidebar: true },
  },
  {
    path: '/protocols/:id',
    name: 'ProtocolDetail',
    component: () => import('@/views/ProtocolDetail.vue'),
    meta: { title: 'Protocol Detail', noSidebar: true },
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/views/ProductIndex.vue'),
    meta: { title: 'Products', noSidebar: true },
  },
  {
    path: '/products/:id',
    name: 'ProductDetail',
    component: () => import('@/views/ProductDetail.vue'),
    meta: { title: 'Product Detail', noSidebar: true },
  },
  {
    path: '/research-goals',
    name: 'ResearchGoals',
    component: () => import('@/views/ResearchGoalIndex.vue'),
    meta: { title: 'Research Goals', noSidebar: true },
  },
  {
    path: '/research-goals/:id',
    name: 'ResearchGoalDetail',
    component: () => import('@/views/ResearchGoalDetail.vue'),
    meta: { title: 'Research Goal Detail', noSidebar: true },
  },
  {
    path: '/quote-request',
    name: 'QuoteRequest',
    component: () => import('@/views/QuoteRequestPage.vue'),
    meta: { title: 'Request Quote', noSidebar: true },
  },
  {
    path: '/cart',
    name: 'Cart',
    component: () => import('@/views/CartPage.vue'),
    meta: { title: 'Shopping Cart', noSidebar: true },
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/views/SettingsPage.vue'),
    meta: { title: 'Settings' },
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
    meta: { title: 'Order Management', requiresAuth: true },
  },
  {
    path: '/admin/orders/:id',
    name: 'AdminOrderDetail',
    component: () => import('@/views/admin/AdminOrderDetail.vue'),
    meta: { title: 'Order Processing', requiresAuth: true },
  },
  // ── Workspace routes ──────────────────────────────
  {
    path: '/workspace',
    name: 'Workspace',
    component: () => import('@/views/workspace/AdminLayout.vue'),
    meta: { title: 'Workspace', requiresAuth: true, requiresAdmin: true },
    children: [
      { path: '', name: 'Dashboard', component: () => import('@/views/workspace/DashboardPage.vue'), meta: { title: 'Dashboard' } },
      { path: 'products', name: 'WorkspaceProducts', component: () => import('@/views/workspace/ProductsPage.vue'), meta: { title: 'Products' } },
      { path: 'products/new', name: 'WorkspaceProductNew', component: () => import('@/views/workspace/ProductEditPage.vue'), meta: { title: 'New Product' } },
      { path: 'products/:id/edit', name: 'WorkspaceProductEdit', component: () => import('@/views/workspace/ProductEditPage.vue'), meta: { title: 'Edit Product' } },
      { path: 'goals', name: 'WorkspaceGoals', component: () => import('@/views/workspace/GoalsPage.vue'), meta: { title: 'Research Goals' } },
      { path: 'applications', name: 'WorkspaceApps', component: () => import('@/views/workspace/AppsPage.vue'), meta: { title: 'Applications' } },
      { path: 'methods', name: 'WorkspaceMethods', component: () => import('@/views/workspace/MethodsPage.vue'), meta: { title: 'Methods' } },
      { path: 'protocols', name: 'WorkspaceProtocols', component: () => import('@/views/workspace/ProtocolsPage.vue'), meta: { title: 'Protocols' } },
    ],
  },
  // ── Old admin product routes removed — use /workspace/products instead
  {
    path: '/:pathMatch(.*)*',
    name: 'NotFound',
    component: () => import('@/views/NotFound.vue'),
    meta: { title: '404' },
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

  // Read token directly from localStorage to avoid circular store imports
  const hasToken = !!localStorage.getItem('token')

  // If route requires auth and user is not authenticated, redirect to login
  if (to.meta.requiresAuth && !hasToken) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // If route requires admin, verify is_staff via the auth store
  if (to.meta.requiresAdmin) {
    if (!hasToken) {
      next({ path: '/login', query: { redirect: to.fullPath } })
      return
    }
    // Deferred check — component will redirect if user is not staff
  }

  // If user is authenticated and route is guest-only (login/register), redirect to home
  if (to.meta.guest && hasToken) {
    next({ path: '/' })
    return
  }

  next()
})

export default router
