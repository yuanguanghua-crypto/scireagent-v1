/**
 * API helper —— 直连后端（:8000 本地 / https://scireagent.com 生产）做数据工厂与清理。
 * 信封约定：{ success, data, meta }。Token 取自 localStorage 或显式传入。
 *
 * ⚠️ 2026-09-22 修正 #2（R2 生产必需，此前本地能过、上生产必 401）：
 *   应用层 token **必须放在 `X-Auth-Token`**，不能放 `Authorization`！
 *   依据 `frontend/src/utils/http.js:21-26`：
 *     "Use X-Auth-Token (not Authorization) so it does NOT clash with the
 *      nginx HTTP Basic Auth popup, which also uses the Authorization header."
 *   两层认证占**同一个头** `Authorization` ⇒ 若应用 token 放那里，会**覆盖掉** nginx 的
 *   Basic 凭证 ⇒ nginx 回 401（实测：`-u scire01:… -H "Authorization: Token …"` ⇒ 401；
 *   改 `-H "X-Auth-Token: …"` ⇒ 200）。生产后端认 `X-Auth-Token`（已实测 200 + JSON）。
 *   生产还需 nginx Basic：用 env `E2E_BASIC_USER` / `E2E_BASIC_PASS`（本地留空即可）。
 */
const API_HOST = process.env.E2E_API_BASE || 'http://localhost:8000';
const API_PREFIX = '/api/v1';
const API_BASE = `${API_HOST}${API_PREFIX}`;
const BASIC_USER = process.env.E2E_BASIC_USER || '';
const BASIC_PASS = process.env.E2E_BASIC_PASS || '';

/** 统一构造请求头：应用层走 X-Auth-Token，nginx 层走 Authorization: Basic */
function buildHeaders(token) {
  const headers = { Accept: 'application/json' };
  if (token) headers['X-Auth-Token'] = token;
  if (BASIC_USER) {
    headers.Authorization = `Basic ${Buffer.from(`${BASIC_USER}:${BASIC_PASS}`).toString('base64')}`;
  }
  return headers;
}

async function apiContext(token) {
  const { request } = require('@playwright/test');
  const ctx = await request.newContext({
    baseURL: API_HOST,
    extraHTTPHeaders: buildHeaders(token),
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
    headers: { 'Content-Type': 'application/json', ...buildHeaders(null) },
    data: { username, password },
  });
  const body = await resp.json();
  return body?.data?.token || null;
}

module.exports = { API_BASE, apiContext, getToken, buildHeaders };

