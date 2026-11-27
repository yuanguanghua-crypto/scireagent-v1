import axios from 'axios'
import { ElMessage } from 'element-plus'

// 运行时基地址：Cloudflare Pages 部署时通过 public/runtime-config.js 注入。
// 留空或仍为占位符时走同源相对路径（本地 dev proxy / 同域后端）。
const RT = (typeof window !== 'undefined' && window.__RUNTIME_CONFIG__) || {}
const API_BASE_URL = RT.API_BASE_URL && RT.API_BASE_URL !== '__BACKEND_API_BASE__' ? RT.API_BASE_URL : '/api/v1'

const http = axios.create({
  baseURL: API_BASE_URL,
  timeout: 15000,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor
http.interceptors.request.use(
  (config) => {
    // Add auth token if exists.
    // Use X-Auth-Token (not Authorization) so it does NOT clash with the
    // nginx HTTP Basic Auth popup, which also uses the Authorization header.
    const token = localStorage.getItem('token')
    if (token) {
      config.headers['X-Auth-Token'] = token
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
// ★ 2026-10-21 导出（D10）：列表/详情页的**持久错误横幅**也要显示同一句后端文案，
//   否则 toast 与横幅会说两套话。
//   `fallback` 可定制兜底文案（加载失败 vs 动作失败语义不同）。
export function extractErrorMessage(data, fallback = 'Action failed') {
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
  return fallback
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
    // ★ 2026-11-27（A-153）：`config.silent === true` 的请求不弹全局 toast。
    //   用途是"探测型"请求（如边打字边渲染 SMILES 结构）——它们的失败是**预期内**的，
    //   弹给用户的只是噪音；调用方会自己决定怎么提示。
    if (!response.config?.silent) ElMessage.error(extractErrorMessage(data))
    return Promise.reject(data)
  },
  (error) => {
    const status = error.response?.status

    // ★ 2026-11-27（A-169）：**凭据类端点的 401 是业务答案，不是会话过期。**
    //   "用户名或密码错" 也返回 401，原来一律走下面的全局分支：
    //   弹 "Session expired" + `window.location.href='/login'` **整页刷新**，
    //   把页面自己算好的错误提示连同组件状态一起冲掉 ⇒ 用户点登录后页面闪一下、
    //   屏幕上什么都没有，后端明明返回了 401（QA Batch 15 两轮实测均复现，
    //   DOM 里 .auth-error-banner 全程为空）。
    //   这些端点把错误交给调用方自己渲染（LoginPage 已有 401 → "Incorrect
    //   username or password" 的分支）。
    const CREDENTIAL_PATHS = [
      '/auth/login',
      '/auth/register',
      '/auth/reset-password',
      '/auth/request-password-reset',
      '/auth/verify-email',
      '/auth/resend-verification',
    ]
    const url = String(error.config?.url || '')
    const isCredentialCall = CREDENTIAL_PATHS.some((p) => url.includes(p))

    // 401 统一跳转登录（凭据类端点除外）
    if (status === 401 && !isCredentialCall) {
      ElMessage.error('Session expired, please sign in again')
      localStorage.removeItem('token')
      window.location.href = '/login'
      return Promise.reject(error)
    }

    // 其余错误优先透传后端真实错误消息（含 403/404/5xx 等）
    // 凭据类端点不弹全局 toast：页面自己就有持久横幅（toast 会一闪而过，
    // 且与横幅重复说同一句话）。
    if (!error.config?.silent && !isCredentialCall) {
      const message = extractErrorMessage(error.response?.data)
      ElMessage.error(message || 'Action failed')
    }
    return Promise.reject(error)
  }
)

export default http