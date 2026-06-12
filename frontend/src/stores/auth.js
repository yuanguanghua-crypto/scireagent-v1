import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, logout as logoutApi, getMe, updateProfile as updateProfileApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')

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

  async function fetchUser() {
    if (!token.value) return
    try {
      const result = await getMe()
      user.value = result.data
    } catch {
      token.value = ''
      user.value = null
      localStorage.removeItem('token')
    }
  }

  async function login(credentials) {
    const result = await loginApi(credentials)
    token.value = result.data.token
    user.value = result.data.user
    localStorage.setItem('token', token.value)
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
    }
    return result
  }

  function updateUser(patch) {
    if (user.value) {
      user.value = { ...user.value, ...patch }
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
    localStorage.removeItem('token')
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
    login,
    register,
    updateProfile,
    updateUser,
    logout,
    fetchUser,
    setToken,
  }
})
