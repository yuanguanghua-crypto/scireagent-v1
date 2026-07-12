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

// 从后端返回体（envelope 或原始 DRF 形状）中提取可读错误消息
function extractErrorMessage(data) {
  const metaError = data?.meta?.error
  // 1) 后端错误可能被包成 meta.error（字符串直接可用）
  if (typeof metaError === 'string') {
    return metaError
  }
  // 2) 对象时优先取 message / detail（DRF 默认异常为 {detail: '...'}）
  if (metaError && typeof metaError === 'object') {
    if (metaError.message) return metaError.message
    if (metaError.detail) return metaError.detail
    // 兜底：取对象中任意字符串值
    for (const value of Object.values(metaError)) {
      if (typeof value === 'string') return value
    }
  }
  // 3) 未包 envelope 的原始 DRF 形状（response.data.detail / message）
  if (data?.detail) return data.detail
  if (data?.message) return data.message
  // 4) 通用兜底文案
  return '操作失败'
}

// Response interceptor
http.interceptors.response.use(
  (response) => {
    const { data, status } = response
    // 204 No Content（如 DELETE）直接返回成功
    if (status === 204) {
      return { success: true }
    }
    // Backend returns { success, data, meta }
    if (data && data.success) {
      return data
    }
    // 裸 DRF 成功响应（无信封但 HTTP 状态码 2xx）— 直接通过
    if (status >= 200 && status < 300) {
      return data
    }
    // 业务错误：透传后端真实错误消息
    ElMessage.error(extractErrorMessage(data))
    return Promise.reject(data)
  },
  (error) => {
    const status = error.response?.status

    // 401 统一跳转登录（保留原有行为，不改变）
    if (status === 401) {
      ElMessage.error('Session expired, please sign in again')
      localStorage.removeItem('token')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // 其余错误优先透传后端真实错误消息（含 403/404/5xx 等）
    const message = extractErrorMessage(error.response?.data)
    ElMessage.error(message || '操作失败')
    return Promise.reject(error)
  }
)

export default http