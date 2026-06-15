import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/views/HomePage.vue'),
    meta: { title: 'Home' },
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
    meta: { title: 'Search' },
  },
  {
    path: '/applications',
    name: 'Applications',
    component: () => import('@/views/ApplicationIndex.vue'),
    meta: { title: 'Applications' },
  },
  {
    path: '/applications/:id',
    name: 'ApplicationDetail',
    component: () => import('@/views/ApplicationDetail.vue'),
    meta: { title: 'Application Detail' },
  },
  {
    path: '/methods',
    name: 'Methods',
    component: () => import('@/views/MethodIndex.vue'),
    meta: { title: 'Methods' },
  },
  {
    path: '/methods/:id',
    name: 'MethodDetail',
    component: () => import('@/views/MethodDetail.vue'),
    meta: { title: 'Method Detail' },
  },
  {
    path: '/protocols',
    name: 'Protocols',
    component: () => import('@/views/ProtocolIndex.vue'),
    meta: { title: 'Protocols' },
  },
  {
    path: '/protocols/:id',
    name: 'ProtocolDetail',
    component: () => import('@/views/ProtocolDetail.vue'),
    meta: { title: 'Protocol Detail' },
  },
  {
    path: '/products',
    name: 'Products',
    component: () => import('@/views/ProductIndex.vue'),
    meta: { title: 'Products' },
  },
  {
    path: '/products/:id',
    name: 'ProductDetail',
    component: () => import('@/views/ProductDetail.vue'),
    meta: { title: 'Product Detail' },
  },
  {
    path: '/research-goals',
    name: 'ResearchGoals',
    component: () => import('@/views/ResearchGoalIndex.vue'),
    meta: { title: 'Research Goals' },
  },
  {
    path: '/research-goals/:id',
    name: 'ResearchGoalDetail',
    component: () => import('@/views/ResearchGoalDetail.vue'),
    meta: { title: 'Research Goal Detail' },
  },
  {
    path: '/quote-request',
    name: 'QuoteRequest',
    component: () => import('@/views/QuoteRequestPage.vue'),
    meta: { title: 'Request Quote' },
  },
  {
    path: '/cart',
    name: 'Cart',
    component: () => import('@/views/CartPage.vue'),
    meta: { title: 'Shopping Cart' },
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
  {
    path: '/admin/products',
    name: 'AdminProducts',
    component: () => import('@/views/admin/AdminProductsPage.vue'),
    meta: { title: 'Product Management', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/products/new',
    name: 'AdminProductNew',
    component: () => import('@/views/admin/AdminProductEdit.vue'),
    meta: { title: 'New Product', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/admin/products/:id/edit',
    name: 'AdminProductEdit',
    component: () => import('@/views/admin/AdminProductEdit.vue'),
    meta: { title: 'Edit Product', requiresAuth: true, requiresAdmin: true },
  },
  {
    path: '/knowledge-intake',
    name: 'KnowledgeIntake',
    component: () => import('@/views/KnowledgeIntake.vue'),
    meta: { title: 'Knowledge Intake' },
  },
  {
    path: '/products/new',
    name: 'ProductNew',
    component: () => import('@/views/products/ProductEditPage.vue'),
    meta: { title: 'New Product' },
  },
  {
    path: '/products/:id/edit',
    name: 'ProductEdit',
    component: () => import('@/views/products/ProductEditPage.vue'),
    meta: { title: 'Edit Product' },
  },
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

  // If route requires admin, check role (deferred check — will re-verify in component)
  if (to.meta.requiresAdmin && !hasToken) {
    next({ path: '/login', query: { redirect: to.fullPath } })
    return
  }

  // If user is authenticated and route is guest-only (login/register), redirect to home
  if (to.meta.guest && hasToken) {
    next({ path: '/' })
    return
  }

  next()
})

export default router
