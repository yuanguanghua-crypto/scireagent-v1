/**
 * API helper —— 直连后端（:8000）做数据工厂与清理。
 * 信封约定：{ success, data, meta }。Token 取自 localStorage 或显式传入。
 */
const API_BASE = 'http://localhost:8000/api/v1';

async function apiContext(token) {
  const { request } = require('@playwright/test');
  return request.newContext({
    baseURL: API_BASE,
    extraHTTPHeaders: {
      Accept: 'application/json',  // 强制 JSON，避免 DRF 可浏览 API 返回 HTML
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
  });
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
