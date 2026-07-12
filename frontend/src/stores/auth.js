import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, logout as logoutApi, getMe, updateProfile as updateProfileApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  // 同步角色提示：全页刷新后 store 重新初始化时 user 尚未经 fetchUser() 异步加载，
  // 守卫若仅依赖 user.is_staff 会误判为 false，导致已登录 staff 被错误重定向到首页而非 /workspace。
  // 登录成功时把 is_staff 缓存进 localStorage，使路由守卫可同步判定角色（真实访问门禁仍在 AdminLayout 兜底）。
  const cachedIsStaff = ref(localStorage.getItem('is_staff') === 'true')

  const isAuthenticated = computed(() => !!token.value)
  const userInitial = computed(() => {
    const name = user.value?.nickname || user.value?.username || user.value?.email || ''
    return name.charAt(0).toUpperCase() || 'U'
  })
  const username = computed(() => user.value?.username || '')
  const email = computed(() => user.value?.email || '')
  const role = computed(() => user.value?.role || '')
  const organization = computed(() => user.value?.organization || null)
  const isOrgAdmin = computed(() => user.value?.is_org_admin || false)
  const isStaff = computed(() => user.value?.is_staff ?? cachedIsStaff.value)

  async function fetchUser() {
    if (!token.value) return
    try {
      const result = await getMe()
      user.value = result.data
      cachedIsStaff.value = !!result.data?.is_staff
    } catch {
      token.value = ''
      user.value = null
      cachedIsStaff.value = false
      localStorage.removeItem('token')
      localStorage.removeItem('is_staff')
    }
  }

  async function login(credentials) {
    const result = await loginApi(credentials)
    token.value = result.data.token
    user.value = result.data.user
    cachedIsStaff.value = !!result.data.user?.is_staff
    localStorage.setItem('token', token.value)
    localStorage.setItem('is_staff', String(cachedIsStaff.value))
    return result
  }

  async function register(data) {
    const result = await registerApi(data)
    return result
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
    updateProfile,
    updateUser,
    logout,
    fetchUser,
    setToken,
  }
})
