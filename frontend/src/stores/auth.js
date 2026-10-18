import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, logout as logoutApi, getMe, updateProfile as updateProfileApi, verifyEmail as verifyEmailApi, resendVerification as resendVerificationApi } from '@/api/auth'
import { useBasketStore } from '@/stores/basket'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  // 同步角色提示：全页刷新后 store 重新初始化时 user 尚未经 fetchUser() 异步加载，
  // 守卫若仅依赖 user.is_staff 会误判为 false，导致已登录 staff 被错误重定向到首页而非 /workspace。
  // 登录成功时把 is_staff 缓存进 localStorage，使路由守卫可同步判定角色（真实访问门禁仍在 AdminLayout 兜底）。
  const cachedIsStaff = ref(localStorage.getItem('is_staff') === 'true')
  // ★ 2026-10-14：同理缓存 role —— 守卫需判定"是否内部人员"（is_staff 或 role∈procurement/admin），
  //   硬刷新时 user 未异步加载完，若无缓存会把 procurement 误判为外部而挡在 /ops/po/* 外。
  const cachedRole = ref(localStorage.getItem('role') || '')

  const isAuthenticated = computed(() => !!token.value)
  const userInitial = computed(() => {
    const name = user.value?.nickname || user.value?.username || user.value?.email || ''
    return name.charAt(0).toUpperCase() || 'U'
  })
  const username = computed(() => user.value?.username || '')
  const email = computed(() => user.value?.email || '')
  const role = computed(() => user.value?.role || cachedRole.value)
  const organization = computed(() => user.value?.organization || null)
  const isOrgAdmin = computed(() => user.value?.is_org_admin || false)
  const isStaff = computed(() => user.value?.is_staff ?? cachedIsStaff.value)

  async function fetchUser() {
    if (!token.value) return
    try {
      const result = await getMe()
      user.value = result.data
      cachedIsStaff.value = !!result.data?.is_staff
      cachedRole.value = result.data?.role || ''
      localStorage.setItem('role', cachedRole.value)
    } catch {
      token.value = ''
      user.value = null
      cachedIsStaff.value = false
      cachedRole.value = ''
      localStorage.removeItem('token')
      localStorage.removeItem('is_staff')
      localStorage.removeItem('role')
    }
  }

  async function login(credentials) {
    // ① Snapshot the guest basket BEFORE the token is written.
    // Once localStorage.token exists the http interceptor stops sending
    // X-Session-Key (utils/http.js:29), so the guest rows become unreachable.
    //
    // ⚠️ Only `_guest` rows may be merged. `logout()` clears the token, so
    // "no token" does NOT imply "these rows belong to a guest" — after a
    // logout the store may still hold the *account's* rows, and the backend
    // merge is additive ⇒ replaying them would double quantities (实测 2 → 4)。
    const basket = useBasketStore()
    const guestItems = basket.items
      .filter((i) => i._guest || i._local)
      .map((i) => ({ sku: i.sku, sku_id: i.sku_id, quantity: i.quantity }))

    const result = await loginApi(credentials)
    token.value = result.data.token
    user.value = result.data.user
    cachedIsStaff.value = !!result.data.user?.is_staff
    cachedRole.value = result.data.user?.role || ''
    localStorage.setItem('token', token.value)
    localStorage.setItem('is_staff', String(cachedIsStaff.value))
    localStorage.setItem('role', cachedRole.value)

    // ② Merge AFTER the token is persisted, so the merge request carries the
    // auth header (the endpoint is IsAuthenticated —实测匿名调用返回 401)。
    // Failure must never block login: mergeLocalBasket swallows its own errors
    // and keeps the local copy, so the user stays logged in either way.
    if (guestItems.length > 0) {
      try {
        await basket.mergeLocalBasket(guestItems)
      } catch (err) {
        console.error('[Auth] basket merge failed after login:', err)
      }
    }

    return result
  }

  async function register(data) {
    const result = await registerApi(data)
    return result
  }

  // Verify email via the link token; on success the backend mints a token and
  // we log the user in directly (the link acts as a one-click sign-in).
  async function verifyEmail(verificationToken) {
    // Same P0-2 defect as `login`: this is a second silent sign-in path, so a
    // guest basket must be merged here too or the items vanish just the same.
    const basket = useBasketStore()
    const guestItems = basket.items
      .filter((i) => i._guest || i._local)
      .map((i) => ({ sku: i.sku, sku_id: i.sku_id, quantity: i.quantity }))

    const result = await verifyEmailApi(verificationToken)
    token.value = result.token
    user.value = result.user
    cachedIsStaff.value = !!result.user?.is_staff
    cachedRole.value = result.user?.role || ''
    localStorage.setItem('token', token.value)
    localStorage.setItem('is_staff', String(cachedIsStaff.value))
    localStorage.setItem('role', cachedRole.value)

    // After the token is persisted so the merge call is authenticated; a failure
    // must not prevent the user from getting into the app.
    if (guestItems.length > 0) {
      try {
        await basket.mergeLocalBasket(guestItems)
      } catch (err) {
        console.error('[Auth] basket merge failed after email verification:', err)
      }
    }

    return result
  }

  async function resendVerification(email) {
    return await resendVerificationApi(email)
  }

  async function updateProfile(data) {
    const result = await updateProfileApi(data)
    // Merge updated fields into local user object
    if (result.data) {
      user.value = { ...user.value, ...result.data }
      if (result.data.is_staff !== undefined) {
        cachedIsStaff.value = !!result.data.is_staff
        localStorage.setItem('is_staff', String(cachedIsStaff.value))
      }
      if (result.data.role !== undefined) {
        cachedRole.value = result.data.role || ''
        localStorage.setItem('role', cachedRole.value)
      }
    }
    return result
  }

  function updateUser(patch) {
    if (user.value) {
      user.value = { ...user.value, ...patch }
      if (patch.is_staff !== undefined) {
        cachedIsStaff.value = !!patch.is_staff
        localStorage.setItem('is_staff', String(cachedIsStaff.value))
      }
      if (patch.role !== undefined) {
        cachedRole.value = patch.role || ''
        localStorage.setItem('role', cachedRole.value)
      }
    }
  }

  async function logout() {
    try {
      await logoutApi()
    } catch {
      /* ignore logout API errors */
    }
    token.value = ''
    user.value = null
    cachedIsStaff.value = false
    localStorage.removeItem('token')
    localStorage.removeItem('is_staff')
  }

  function setToken(newToken) {
    token.value = newToken
    localStorage.setItem('token', newToken)
  }

  // Initialize: fetch user if token exists
  if (token.value) {
    fetchUser()
  }

  return {
    user,
    token,
    isAuthenticated,
    userInitial,
    username,
    email,
    role,
    organization,
    isOrgAdmin,
    isStaff,
    login,
    register,
    verifyEmail,
    resendVerification,
    updateProfile,
    updateUser,
    logout,
    fetchUser,
    setToken,
  }
})
