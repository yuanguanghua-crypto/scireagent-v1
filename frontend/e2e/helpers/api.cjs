/**
 * API helper —— 直连后端（:8000）做数据工厂与清理。
 * 信封约定：{ success, data, meta }。Token 取自 localStorage 或显式传入。
 */
// ⚠️ 2026-09-22 修正（真实 bug，此前一直静默失效）：
//   原实现 baseURL = 'http://host/api/v1'，而调用方传**以 '/' 开头**的路径。
//   按 URL 解析规则，前导斜杠会把 baseURL 的路径段**整段丢弃** ⇒ 实际请求
//   'http://host/products/'（丢了 /api/v1）⇒ 404 + text/html ⇒ `res.json()` 抛
//   `Unexpected token '<'` ⇒ 所有 API 断言与「按唯一名清理」静默失效。
//   现改为：baseURL 只取**根**，由 wrapper 统一补 '/api/v1' 前缀 ⇒ 既有调用方
//   （仍写 '/products/'）**无需改动**即恢复正常；host 支持 env 覆盖。
const API_HOST = process.env.E2E_API_BASE || 'http://localhost:8000';
const API_PREFIX = '/api/v1';
const API_BASE = `${API_HOST}${API_PREFIX}`;

async function apiContext(token) {
  const { request } = require('@playwright/test');
  const ctx = await request.newContext({
    baseURL: API_HOST,
    extraHTTPHeaders: {
      Accept: 'application/json',  // 强制 JSON，避免 DRF 可浏览 API 返回 HTML
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
  });
  const withPrefix = (path) =>
    path.startsWith(API_PREFIX) ? path
      : `${API_PREFIX}${path.startsWith('/') ? '' : '/'}${path}`;
  return {
    get: (path, opts) => ctx.get(withPrefix(path), opts),
    post: (path, opts) => ctx.post(withPrefix(path), opts),
    put: (path, opts) => ctx.put(withPrefix(path), opts),
    patch: (path, opts) => ctx.patch(withPrefix(path), opts),
    delete: (path, opts) => ctx.delete(withPrefix(path), opts),
    dispose: () => ctx.dispose(),
  };
}

async function getToken(request, username, password) {
  const resp = await request.post(`${API_BASE}/auth/login`, {
    headers: { 'Content-Type': 'application/json' },
    data: { username, password },
  });
  const body = await resp.json();
  return body?.data?.token || null;
}

module.exports = { API_BASE, apiContext, getToken };
