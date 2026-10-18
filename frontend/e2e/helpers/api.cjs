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

/**
 * 应用层登录，取 token。
 *
 * ★ 2026-10-18 生产实测修正（原实现**静默降级**，导致误判）：
 *   原实现 `return body?.data?.token || null` —— 登录失败（401 账号错 / 429 被限流）时
 *   一律返回 null，调用方 `apiContext(null)` 拿到**无 token 的上下文**，
 *   后续 GET 全部 401 ⇒ `resp.json().data` 为 null ⇒ 断言里"行数==0"，
 *   表现成**业务数据为 0**（实测生产 125 个产品时断言成 "0 products"），
 *   极具误导性（让人以为生产没数据/代码坏了）。
 *   ⇒ 现在**失败即抛错**，并区分 429（限流）与 401（凭据错）。
 *
 * ★ 限流（429）的真实来源：后端 `core/permissions.py` 的 `LoginRateThrottle`
 *   = **5 次/分钟/IP**。生产 E2E 全部流量来自**同一台机器的同一个出口 IP**，
 *   而每个用例要登录 2 次（UI 登录 1 次 + API 取 token 1 次）⇒ 必然撞限流。
 *   ⇒ 用模块级缓存复用**同一个 token**（DRF Token 不过期），把登录次数压到 1 次/轮。
 */
const _sessionCache = new Map(); // username -> {token, isStaff, role, username}

/**
 * 执行一次应用层登录并**缓存**结果（整轮只真正登录 1 次）。
 *
 * 缓存安全性依据：
 *   - DRF `Token` **不过期**（后端 `apps/accounts/api/v1/views.py:94` 用 `get_or_create`
 *     ⇒ 同一用户每次登录拿到的都是**同一个** token）；
 *   - 本套 e2e **没有任何 spec 调用服务端 logout**（服务端 logout 会 `auth_token.delete()`，
 *     见 `views.py:183`）⇒ 整轮复用安全。
 */
async function _login(request, username, password) {
  const resp = await request.post(`${API_BASE}/auth/login`, {
    headers: { 'Content-Type': 'application/json', ...buildHeaders(null) },
    data: { username, password },
  });
  const body = await resp.json().catch(() => null);
  const token = body?.data?.token || null;
  if (!token) {
    // 失败 ⇒ 显式抛错（不再返回 null 让上层"静默降级"成空数据）。
    if (resp.status() === 429) {
      const retryAfter = resp.headers()['retry-after'];
      throw new Error(
        `应用层登录被限流（HTTP 429）——后端 LoginRateThrottle = 5 次/分钟/IP。` +
        `账号=${username}。${retryAfter ? `需等待 ${retryAfter}s 后重试。` : ''}\n` +
        '  ⚠️ 生产 E2E 全部走同一出口 IP ⇒ 短时间内多次登录必被限流。' +
        '  ⇒ 本 helper 已做整轮 token 复用（只登录 1 次）；若仍 429，说明是**别的进程**在并发登录。',
      );
    }
    const msg = body?.meta?.error?.message || body?.detail || resp.statusText() || '无响应体';
    throw new Error(
      `应用层登录失败（HTTP ${resp.status()}）——账号=${username}：${msg}\n` +
      '  ⚠️ 请用环境变量注入**生产真实**账号：E2E_USER / E2E_PASS（不要把密码写进代码）。' +
      '  ⚠️ 若目标在 nginx Basic Auth 之后，还需 E2E_BASIC_USER / E2E_BASIC_PASS（浏览器层）。',
    );
  }
  const user = body?.data?.user || {};
  const session = {
    token,
    isStaff: !!user.is_staff,
    role: user.role || '',
    username: user.username || username,
  };
  _sessionCache.set(username, session);
  return session;
}

/**
 * 应用层登录，取 token。
 *
 * ★ 2026-10-18 生产实测修正（原实现**静默降级**，导致误判）：
 *   原实现 `return body?.data?.token || null` —— 登录失败（401 账号错 / 429 被限流）时
 *   一律返回 null，调用方 `apiContext(null)` 拿到**无 token 的上下文**，
 *   后续 GET 全部 401 ⇒ `resp.json().data` 为 null ⇒ 断言里"行数==0"，
 *   表现成**业务数据为 0**（实测生产 125 个产品时断言成 "0 products"），
 *   极具误导性（让人以为生产没数据 / 代码坏了）。
 *   ⇒ 现在**失败即抛错**，并区分 429（限流）与 401（凭据错）。
 *
 * ★ 限流（429）的真实来源：后端 `core/permissions.py:36` 的 `LoginRateThrottle`
 *   = **5 次/分钟/IP**。生产 E2E 全部流量来自**同一台机器的同一个出口 IP**，
 *   而每个用例要登录 2 次（UI 登录 1 次 + API 取 token 1 次）⇒ 必然撞限流。
 *   ⇒ 整轮复用同一个 token，把登录请求数从「每例 2 次」降到「整轮 1 次」。
 */
async function getToken(request, username, password) {
  const cached = _sessionCache.get(username);
  if (cached) return cached.token;
  return (await _login(request, username, password)).token;
}

/**
 * 取"可直接注入浏览器的会话"（token + 角色标记）——**只登录一次**，供整轮复用。
 *
 * 背景：生产每个用例登录 2 次（UI + API）× 5 次/分钟限流 ⇒ 必然 429 ⇒ 用例随机失败。
 *  DRF 的 Token（`rest_framework.authtoken`）**不过期**（生产实测 40 位 hex，长期有效），
 *  且后端 `Token.objects.get_or_create(user=user)` ⇒ 同一用户反复登录拿到**同一个 token**。
 *  ⇒ 整轮只登录 1 次，把 token 直接写进 localStorage（与前端 `stores/auth.js` 的落盘键一致：
 *     `token` / `is_staff` / `role`）即可跳过 UI 登录，**零额外登录请求**。
 *
 * ⚠️ 不改变被测语义：前端判定登录态只看 localStorage（`stores/auth.js:8,12,15`）与路由守卫
 *   （`router/index.js:295` 读 `localStorage.getItem('token')`）⇒ 注入等价于登录成功。
 * ⚠️ 因此**不适用于**要验证"登录页本身"的用例（那类用例请自己填表单）。
 */
async function getSession(request, username, password) {
  // 与 getToken 共用同一缓存 ⇒ 整轮只登录 1 次（UI 与 API 两侧共用一个 token）。
  const cached = _sessionCache.get(username);
  if (cached) return cached;
  return _login(request, username, password);
}

module.exports = { API_BASE, apiContext, getToken, getSession, buildHeaders };

