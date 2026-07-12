/**
 * 运行时配置（部署时由平台注入，无需重新构建）
 * Cloudflare Pages 构建时把 __BACKEND_API_BASE__ 替换为真实后端域名。
 * 例如：window.__RUNTIME_CONFIG__ = { API_BASE_URL: 'https://scireagent-backend.hf.space/api/v1' }
 *
 * 默认（本地开发 / 同源）留空，前端走相对路径 /api/v1（由 dev proxy 或同源后端处理）。
 */
window.__RUNTIME_CONFIG__ = {
  API_BASE_URL: '__BACKEND_API_BASE__',
}
