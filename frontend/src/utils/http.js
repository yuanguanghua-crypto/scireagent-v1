import axios from 'axios'
import { ElMessage } from 'element-plus'

const http = axios.create({
  baseURL: '/api/v1',
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
http.interceptors.request.use(
  (config) => {
    // Add auth token if exists
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Token ${token}`
    }

    // Add session key for guest users (only when no auth token)
    if (!token) {
      const sessionKey = localStorage.getItem('scireagent_session_key')
      if (sessionKey) {
        config.headers['X-Session-Key'] = sessionKey
      }
    }

    return config
  },
  (error) => Promise.reject(error)
)

// Response interceptor
http.interceptors.response.use(
  (response) => {
    const { data } = response
    // Backend returns { success, data, meta }
    if (data.success) {
      return data
    }
    // Handle business errors
    ElMessage.error(data.meta?.error?.message || 'Request failed')
    return Promise.reject(data)
  },
  (error) => {
    const status = error.response?.status
    const message = error.response?.data?.meta?.error?.message || error.message

    if (status === 401) {
      ElMessage.error('Session expired, please sign in again')
      localStorage.removeItem('token')
      window.location.href = '/login'
    } else if (status === 403) {
      ElMessage.error('Access denied')
    } else if (status === 404) {
      ElMessage.error('Resource not found')
    } else if (status >= 500) {
      ElMessage.error('Server error, please try again later')
    } else {
      ElMessage.error(message)
    }

    return Promise.reject(error)
  }
)

export default http