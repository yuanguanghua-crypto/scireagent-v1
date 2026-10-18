/**
 * 回归测试 —— ★ **真实后端**下 merge「叠加超 999 ⇒ 跳过 + 明细回传」的运行时行为
 * ============================================================================
 * 覆盖 commit `5463633`（`backend/apps/transactions/api/v1/basket_views.py:291-321`）：
 * 叠加后突破 `max_line_quantity`(999) 时，由 `raise ValidationError`（整条 400）
 * 改为 `skipped_count += 1` + `skipped_items.append({sku_id, quantity, reason})`。
 *
 * ---------------------------------------------------------------------------
 * ★★ 为什么这个 spec 必须存在
 * ---------------------------------------------------------------------------
 * `basket-local-merge-prune.spec.cjs`（c03f076）的 BC1/BC2/BC3 用 `page.route()`
 * **伪造** merge 响应体，文件头明确写了「后端 `skipped`/`skipped_items` 的**产生**
 * 逻辑未被覆盖」。本spec 全部走**真实后端**：
 *   - **绝不碰 `/api/v1/basket/merge` 的路由**（不 fulfill / 不 continue）
 *   - 用 `page.on('response')` **旁路观测**真实响应体
 *   - 断言直接读后端 `GET /basket` 的**真实落库结果**，不看响应体的自述
 * ⚠️ 为什么不复制 BC4 的 `route.continue()` / `route.fetch()` 观测法：
 *   两者在本机 vite 代理链路下都会让后端**收不到**请求（BC4 文件头实测记录），
 *   症状是「合并成功但账户查不到」——极具误导性。
 *
 * ---------------------------------------------------------------------------
 * ★★★ 本 spec 揭露的一个**未决缺陷**（RT5，用例故意保持失败）
 * ---------------------------------------------------------------------------
 * **`5463633` 的设计论证前提在真实链路上不成立。**
 *
 * 论证原文（`basket_views.py:307-310`）：「被跳过的行会留在 localStorage
 * （前端 `pruneMergedLocalItems` 只剔除已确认合并成功的行），用户自行调整数量后
 * 可重试」。**实测（RT5）：真实链路下 localStorage 从来就没有副本。**
 *
 * 原因链（每一环都已实测或读码确认）：
 *   1. 匿名加购走 `AddToBasketView` 落**后端** `Basket(user=NULL, session_key=K)`
 *      （`basket_views.py:108-127`）；
 *   2. `loadBasket()` 成功时不调 `saveLocalBasket()` ⇒ **localStorage 无副本**
 *      （实测：登录前后 `scireagent_basket` 均为 `null`）；
 *   3. ⇒ `pruneMergedLocalItems` 的 `if (!stored) return`（`basket.js:278`）
 *      **直接返回** ⇒ 「保留被跳过的行」这段逻辑在真实链路上**从未生效过**。
 *      既有 BC1/BC2 能覆盖它，靠的是 `seedLocalBasket()` **人工种入** —— 那是
 *      `addItem` 兜底分支（API 调用失败时）才走的路径，不是主路径。
 *   4. 被跳过的行只剩后端游客行，而 `mergeLocalBasket` 成功后**无条件**执行
 *      `removeItem(SESSION_KEY_KEY); getSessionKey()`（`basket.js:242-243`）
 *      ⇒ 老 key 失效 ⇒ `GET /basket` 用新 key 查**不到**（实测返回 `[]`）。
 *
 * ⇒ **净效果：被跳过的商品对用户彻底消失** —— 不在账户购物车（被跳过）、
 *   不在 localStorage（从无副本）、游客行也因 key 轮换而不可达（实测「Your cart
 *   is empty」）。用户既无法自动重试，也**无法人工找回**。
 *
 * ⚠️ 与**旧行为（整条 400）**的对比（这是本缺陷的严重性所在）：
 *   `basket.js:246-250` 的 catch 分支 `return false` **在轮换 session key 之前**
 *   ⇒ 400 时老 key 保留 ⇒ 用户登出后匿名访问购物车**仍能看到全部商品**（含被跳
 *   过的那件）⇒ 人工可自救。
 *   ⇒ 即「自动重试会死循环」成立，但「人工可找回」同样成立；
 *      改成跳过后，**两者都不成立了**。
 *
 * ⚠️⚠️ **RT5 是故意保持失败的。** 它断言的是**期望行为**（被跳过的商品应留在
 *   某处、用户可找回），当前实现不满足 ⇒ 红。
 *   **不要通过放宽断言让它变绿** —— 那正是它存在的意义。
 *   修复方向（⚠️ 待产品/技术决策，本次**未改任何生产代码**）：
 *     a) 跳过时**不轮换** session key（把轮换移到 `skipped === 0` 分支）；
 *     b) 或merge 失败/部分跳过时，把 `skipped_items` **写回** localStorage；
 *     c) 或后端在 merge 时**接管**被跳过的行（转存到账户并标记待调整）。
 *
 * ---------------------------------------------------------------------------
 * ★★ 怎么把账户购物车数量顶到接近 999（构造手法，实测可行、且不改库）
 * ---------------------------------------------------------------------------
 * 直接用**已登录 token** 调 `POST /basket/items {sku_id, quantity: 998}`：
 *   - `AddToBasketSerializer.quantity` 是 `max_value=999`（`basket_serializers.py:49`）
 *     ⇒ 998 合法，一次请求即建行；
 *   - `AddToBasketView` 走 `get_or_create` + `quantity += n`
 *     （`basket_views.py:99-106`）⇒ **必须先purge**，否则累加到残留行上。
 * 即「数量接近 999」是**真实业务接口**造出来的，不是绕过校验的假数据。
 *
 * ---------------------------------------------------------------------------
 * ⚠️ 本机环境的坑（沿用既有 spec 的实测结论）
 * ---------------------------------------------------------------------------
 *   1. `C:\...\src_claude` 是指向 `E:\` 的 junction ⇒ **必须从 `E:` 起 vite**，
 *      否则 `main.js` 原样返回（依赖不重写）⇒ 整站白屏，症状伪装成「选择器不对」。
 *   2. **绝不能用 `loginAsStaff`**：它走会话复用直接注入 token，绕过
 *      `authStore.login()` ⇒ merge 唯一触发点（`auth.js:77`）不执行 ⇒ **假绿**。
 *   3. 只往 localStorage 塞数据 merge **不会触发**：guestItems 取自**store 内存**
 *      （`auth.js:58`）且有 `guestItems.length > 0` 守卫（`auth.js:75`）
 *      ⇒ 必须真实匿名加购 + 在 `/cart` 触发 `loadBasket()`。
 *   4. `APIResponse.body` **只能消费一次** ⇒ 读 basket 必须 `.text()` + `JSON.parse`。
 *   5. 长期持有的 `apiContext` 在 purge 后读 basket 会返回空 ⇒ **每次读都新建**。
 *   6. ⚠️ **后端必须 `DB_ENGINE=sqlite`**，不是 `django.db.backends.sqlite3`
 *      （`config/settings/development.py:8` 比较的是**字符串** `'sqlite'`）。
 *      传引擎路径会挂到一个**空的 `scireagent` 库**上，而 `GET /basket` 仍返 200
 *      —— **看起来一切正常，实际连的是空库**（实测踩过）。
 *
 * 运行方式（**必须打本地**）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   node node_modules/@playwright/test/cli.js test \
 *     e2e/basket-merge-over-limit.spec.cjs --project=chromium --reporter=line
 * 前提：后端 :8000 + 前端 :5173 已启动。
 * ⚠️⚠️ **绝不可对生产跑**：全部用例真登录并**写库**。
 *   已打 `@write` + `@local-only`（符合 `e2e/gate-audit.cjs` 的 tier 闸门）。
 *
 * ---------------------------------------------------------------------------
 * ★★ 覆盖不到什么（诚实评估，勿只看绿灯）
 * ---------------------------------------------------------------------------
 *   - **RT5 故意红**，它标记的是未决缺陷而非测试写错。
 *   - `verifyEmail`（`auth.js:106-119`）是第二条触发 merge 的入口，未覆盖。
 *   - 合并后的 **Toast 文案**未断言（`reason.includes('上限')` 只影响提示，不影响数据）。
 *   - 「用户调小数量后重试成功」只在后端单元测试里，本 spec 未覆盖。
 *   - 并发 merge（两次登录同时打）未覆盖。
 */

const { test, expect } = require('@playwright/test');
const { BASE_URL, ADMIN_USER, ADMIN_PASS, logout } = require('./helpers/auth.cjs');
const { apiContext, getToken } = require('./helpers/api.cjs');

/**
 * 本spec 专用 SKU（实测确认：存在 + 产品未归档 + admin 购物车里无行）。
 * ⚠️ 与 `basket-local-merge-prune.spec.cjs` 的候选集（458/153/154/459/460/155）
 *    **刻意错开** —— 共享 dev 库下两套 spec 抢同一行会污染「增量口径」。
 * ⚠️ `admin_basket_rows=0` 是硬要求：账户里若已有行，`quantity += n` 会累加，
 *    「顶到 998」就变成「顶到 998+残留」。
 */
const SKU_OVER = 461;   // 顶到 998 ⇒ 本次提交必超限
const SKU_OK = 462;     // 与超限行同批提交 ⇒ 必须正常合并成功
const SKU_ONLY = 463;   // 单独构造「只有超限这一件」
const SKU_CLEAN = 464;  // 账户干净 ⇒ 走 created=True 分支
const ALL_SKUS = [SKU_OVER, SKU_OK, SKU_ONLY, SKU_CLEAN];
const FALLBACK_SKUS = [465, 466, 467, 468];

// ══════════════════════════════════════════════════════════════════════════
// helpers
// ══════════════════════════════════════════════════════════════════════════

/** ★★ 必须走 **UI 表单登录**（理由见文件头坑 2）。会话复用会让 merge 压根不触发。 */
async function loginViaForm(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);
  await page.getByRole('button', { name: 'Sign In' }).click();
  await page.waitForFunction(() => !!(localStorage.getItem('token') || '').trim(), null,
    { timeout: 30000 });
}

/** 真实匿名加购 ⇒ 后端写 `Basket(user=NULL, session_key=X)` ⇒ store 能拿到 `_guest` 行 */
async function addGuestRowViaApi(page, skuId, quantity) {
  await page.waitForLoadState('load');
  const res = await page.evaluate(async ({ sku, qty }) => {
    let lastErr = null;
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const r = await fetch('/api/v1/basket/items', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'X-Session-Key': localStorage.getItem('scireagent_session_key') || '',
          },
          body: JSON.stringify({ sku_id: sku, quantity: qty }),
        });
        let body = null;
        try { body = await r.json(); } catch { /* 非 JSON */ }
        return { status: r.status, body };
      } catch (e) {
        lastErr = String(e && e.message ? e.message : e);
        await new Promise((r) => setTimeout(r, 400));
      }
    }
    return { status: 0, body: null, error: lastErr };
  }, { sku: skuId, qty: quantity });
  if (res.status !== 201) {
    throw new Error(
      `匿名加购失败：HTTP ${res.status} ${JSON.stringify(res.body).slice(0, 200)}` +
      (res.error ? `（fetch 错误：${res.error}）` : ''),
    );
  }
  return res.body?.data?.id;
}

/** 进 `/cart` 触发 `loadBasket()`（`CartPage.vue:64`），让 store 真的拿到 `_guest` 行 */
async function loadGuestRowsIntoStore(page) {
  await page.goto(`${BASE_URL}/cart`, { waitUntil: 'domcontentloaded' });
  await page.waitForFunction(
    () => {
      const pinia = document.querySelector('#app')?.__vue_app__
        ?.config?.globalProperties?.$pinia;
      const store = pinia?._s?.get?.('basket');
      return !!store && Array.isArray(store.items) && store.items.length > 0;
    },
    null,
    { timeout: 20000 },
  );
  return page.evaluate(() => {
    const pinia = document.querySelector('#app').__vue_app__.config.globalProperties.$pinia;
    return JSON.parse(JSON.stringify(pinia._s.get('basket').items));
  });
}

/** 在页面**当前**同源 localStorage **人工种入**一份购物车副本。
 *
 * ⚠️ 为什么不用 `addInitScript`：它只对**后续导航**生效（见既有 spec BC1 的用法 ——
 *   那里 seed 之后紧跟一次 `page.goto`）。本 spec 的调用点若不立刻导航，
 *   `addInitScript` 写的东西在当前页还读不到 ⇒ 表现为「seed 没生效」
 *   （实测踩过：RT3 前置护栏直接报 null）。
 *   ⇒ 这里**直接 evaluate 写入**，读-写-读都在同一页，行为确定。
 *   额外仍注册 `addInitScript`，防止后续 `page.goto` 把它冲掉。
 */
async function seedLocalBasket(page, obj) {
  const value = JSON.stringify(obj);
  await page.addInitScript(
    ({ key, v }) => {
      try { localStorage.setItem(key, v); } catch { /* 忽略 */ }
    },
    { key: 'scireagent_basket', v: value },
  );
  await page.evaluate(
    ({ key, v }) => {
      try { localStorage.setItem(key, v); } catch { /* 忽略 */ }
    },
    { key: 'scireagent_basket', v: value },
  );
}

/** 读 localStorage 副本（已解析；无法解析时返回 `{ __unparseable }`） */
function readLocalBasket(page) {
  return page.evaluate(() => {
    const raw = localStorage.getItem('scireagent_basket');
    if (raw === null) return null;
    try { return JSON.parse(raw); } catch { return { __unparseable: raw }; }
  });
}

/**
 * ★★ **旁路观测**真实 merge 响应 —— 只监听，不碰路由。
 * ⚠️ 任何 `route.fulfill/continue/fetch` 都会让合并不落库（见文件头）。
 */
function observeMerge(page) {
  const state = { calls: 0, responses: [] };
  page.on('response', async (res) => {
    let pathname;
    try { pathname = new URL(res.url()).pathname; } catch { return; }
    if (pathname !== '/api/v1/basket/merge') return;
    state.calls += 1;
    let body = null;
    try { body = await res.json(); } catch { /* 非 JSON */ }
    state.responses.push({ status: res.status(), body });
  });
  return state;
}

async function waitForMerge(state, atLeast = 1) {
  await expect
    .poll(() => state.responses.length, { timeout: 20000 })
    .toBeGreaterThanOrEqual(atLeast);
  return state.responses[atLeast - 1];
}

/**
 * 读账户购物车。⚠️ 必须 `.text()` + `JSON.parse`（坑 4）。
 * ⚠️ 路径不能带尾斜杠（`urls.py:29` 注册的是 `basket`）⇒ 带斜杠返 404 HTML。
 * ⚠️ 行里 sku 字段名是 `sku` 不是 `sku_id`（`basket_serializers.py:34`）。
 */
async function fetchAccountBasket(api) {
  const resp = await api.get('/basket');
  const raw = await resp.text();
  let body = null;
  try { body = JSON.parse(raw); } catch {
    throw new Error(
      `GET /basket 返回非 JSON（HTTP ${resp.status()}）：${raw.slice(0, 200)}`);
  }
  return (body?.data?.items || []).map((r) => ({ id: r.id, sku: r.sku, quantity: r.quantity }));
}

/** ★ 每次读都**新建** context（坑 5） */
async function qtyOf(request, skuId) {
  const fresh = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
  try {
    return (await fetchAccountBasket(fresh)).find((r) => r.sku === skuId)?.quantity;
  } finally { await fresh.dispose().catch(() => {}); }
}

/** 把某 sku 在**账户**购物车里的所有行删干净并校验（只删该 sku） */
async function purgeAccountRowsForSku(request, skuId) {
  for (let i = 0; i < 5; i++) {
    const fresh = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
    let mine = [];
    try { mine = (await fetchAccountBasket(fresh)).filter((r) => r.sku === skuId); }
    finally { await fresh.dispose().catch(() => {}); }
    if (!mine.length) return true;
    const del = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
    try { for (const r of mine) await del.delete(`/basket/items/${r.id}/delete`); }
    finally { await del.dispose().catch(() => {}); }
  }
  throw new Error(`前置清理失败：sku ${skuId} 仍残留行`);
}

/**
 * ★★ 用**真实业务接口**把账户购物车某 sku 的数量顶到 `target`（见文件头「构造手法」）。
 * @returns {Promise<number>} 落库后的实际数量（**读回确认**，不信响应体自述）
 */
async function seedAccountQuantity(request, skuId, target) {
  await purgeAccountRowsForSku(request, skuId);
  const api = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
  try {
    const resp = await api.post('/basket/items', { data: { sku_id: skuId, quantity: target } });
    if (resp.status() !== 201) {
      throw new Error(`预置数量失败：HTTP ${resp.status()} ${(await resp.text()).slice(0, 200)}`);
    }
  } finally { await api.dispose().catch(() => {}); }
  const actual = await qtyOf(request, skuId);
  if (actual !== target) throw new Error(`预置数量未生效：期望 ${target}，实际 ${actual}`);
  return actual;
}

/** 探测候选 SKU 是否「存在 + 产品未归档」（匿名加 1 件 → GET /basket 看在不在 → 立刻删） */
async function probeGuestVisibility(page, skuId) {
  const probe = await page.evaluate(async (sku) => {
    try {
      const sk = localStorage.getItem('scireagent_session_key');
      if (!sk) return null;
      const r = await fetch('/api/v1/basket/items', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Session-Key': sk },
        body: JSON.stringify({ sku_id: sku, quantity: 1 }),
      });
      if (r.status !== 201) return null;
      const b = await r.json();
      return { rowId: b?.data?.id, sk };
    } catch { return null; }
  }, skuId);
  if (!probe?.rowId) return false;

  const seen = await page.evaluate(async (sk) => {
    const r = await fetch('/api/v1/basket', { headers: { 'X-Session-Key': sk } });
    if (!r.ok) return false;
    const b = await r.json();
    return (b?.data?.items || []).length > 0;
  }, probe.sk);

  await page.evaluate(async ({ rowId, sk }) => {
    try {
      await fetch(`/api/v1/basket/items/${rowId}/delete`, {
        method: 'DELETE', headers: { 'X-Session-Key': sk },
      });
    } catch { /* 清理失败不影响探测结论 */ }
  }, { rowId: probe.rowId, sk: probe.sk });

  return seen;
}

/** 校验本 spec 的 SKU 全部「存在 + 产品未归档」，否则全部断言会落空 */
async function assertSkusUsable(page) {
  await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
  await page.waitForLoadState('load');
  for (const sku of [...ALL_SKUS, ...FALLBACK_SKUS]) {
    if (await probeGuestVisibility(page, sku)) return;
  }
  throw new Error(
    '★ 全部候选 SKU 都不可用（不存在或产品已归档）—— 本 spec 全部断言会落空。' +
    '请在 backend 换一批未归档的 SKU 后再跑，勿把断言改松来「修复」。',
  );
}

/** 收尾：清掉本 spec 用过的全部 SKU 的**账户**行 */
async function cleanupAll(request) {
  for (const sku of ALL_SKUS) {
    await purgeAccountRowsForSku(request, sku).catch((e) => {
      console.warn(`[cleanup] sku ${sku} 清理失败：${String(e.message).split('\n')[0]}`);
    });
  }
}

/**
 * ★★ 清掉本用例造的**游客作用域**行（`Basket(user=NULL, session_key=K)`）。
 *
 * ⚠️⚠️ 两个实测踩出来的约束，缺一个都会出问题：
 *
 * **约束①：必须显式传 `sessionKey`，不能用「当前 localStorage 里的 key」。**
 *   `mergeLocalBasket` 成功后 `basket.js:242-243` 会轮换 session key ⇒ 登录后
 *   「当前 key」已是新值，用它 `GET /basket` 返回 `[]`（实测），那些行
 *   **再也删不掉** ⇒ 每跑一轮就在共享 dev 库里**永久累积**孤儿游客行
 *   （实测首版跑 5 轮积了 24 行）。账户 API（带 token）也查不到它们 ——
 *   `_get_basket_queryset` 按作用域分流（`basket_views.py:44-54`）。
 *   ⇒ 调用方必须在**登录前**把 key 存下来、登录后显式传进来。
 *   （`DeleteBasketItemView` 只比对 `item.session_key != session_key`，
 *     后端**不**校验 key 是否已轮换 ⇒ 用老 key 删自己的行是合法的。）
 *
 * **约束②：必须在 `loginViaForm` 之后调用，绝不能在它之前。**
 *   ⚠️ 首版把清理放在登录前，结果 5 个用例**全红**——`waitForMerge` 超时，
 *   即 merge 压根没触发。原因是清理动作会让 store 失去那批 `_guest` 行，
 *   而 merge 的触发源正是 **store 内存**（`auth.js:58-60`）+ 守卫
 *   `guestItems.length > 0`（`auth.js:75`）⇒ store 空 ⇒ 不触发。
 *   登录后调用则只碰后端，不影响 store 快照，被测行为完全不变。
 *
 * @param {string} sessionKey 登录**前**的 session key
 * @returns {Promise<number>} 实际删除的行数
 */
async function cleanupGuestRows(page, sessionKey) {
  return page.evaluate(async (sk) => {
    if (!sk) return 0;
    try {
      const r = await fetch('/api/v1/basket', { headers: { 'X-Session-Key': sk } });
      if (!r.ok) return 0; // ⚠️ 浏览器 fetch 的 `ok` 是**属性**，不是方法（勿写 r.ok()）
      const b = await r.json();
      const rows = b?.data?.items || [];
      let n = 0;
      for (const it of rows) {
        const d = await fetch(`/api/v1/basket/items/${it.id}/delete`, {
          method: 'DELETE', headers: { 'X-Session-Key': sk },
        });
        if (d.ok) n += 1;
      }
      return n;
    } catch {
      return 0;
    }
  }, sessionKey);
}

/** 读当前 session key（登录**前**调用并存下来，供登录后清理游客行用） */
function readSessionKey(page) {
  return page.evaluate(() => localStorage.getItem('scireagent_session_key'));
}

// ══════════════════════════════════════════════════════════════════════════
// ★★ RT1 —— 核心：超 999 跳过 + 其余正常合并 + 重试不死循环（★ 真实后端）
// ══════════════════════════════════════════════════════════════════════════
test.describe('RT1 — 叠加超999：跳过 + 明细回传 + 重试不死循环（★ 真实后端）', () => {
  test('RT1 — 1件超限 ⇒ 200/skipped=1/其余合并成功/重试仍200', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    await assertSkusUsable(page);

    // ── 前置：把 SKU_OVER 的账户数量**真实**顶到 998 ────────────────────
    expect(await seedAccountQuantity(request, SKU_OVER, 998),
      '账户购物车该 sku 应已被真实顶到 998').toBe(998);
    console.log(`[RT1] 合并前 Basket(sku=${SKU_OVER}) = ${await qtyOf(request, SKU_OVER)}`);

    // ── 匿名加购：超限 sku 2 件（998+2=1000>999）+ 另一 sku 3 件 ─────────
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await addGuestRowViaApi(page, SKU_OVER, 2);   // 这行会被跳过
    await addGuestRowViaApi(page, SKU_OK, 3);     // 这行必须合并成功

    const merge = observeMerge(page);
    const rows = await loadGuestRowsIntoStore(page);
    expect(
      rows.map((r) => r.sku),
      '★ store 里必须真的拿到 _guest 行，否则 merge 不会触发（防假绿）',
    ).toEqual(expect.arrayContaining([SKU_OVER, SKU_OK]));

    // ★ 登录前记下 session key —— 登录后用它清理本用例造的游客行
    const sk1 = await readSessionKey(page);

    // ★ 真实 UI 表单登录 ⇒ `auth.js:77` 触发真实 merge
    await loginViaForm(page);
    await cleanupGuestRows(page, sk1);
    const first = await waitForMerge(merge, 1);

    // ── 断言组 A：响应契约 ──────────────────────────────────────────────
    expect(
      first.status,
      '★ 超限不得让整条请求 400（那正是「死循环」根因）。真实响应体='
      + JSON.stringify(first.body).slice(0, 500),
    ).toBe(200);

    const data = first.body?.data || {};
    expect(data.skipped, '★ 必须恰好跳过 1 条').toBe(1);
    expect(Array.isArray(data.skipped_items), 'skipped_items 必须是数组').toBe(true);
    expect(data.skipped_items).toHaveLength(data.skipped);

    const skippedRow = data.skipped_items.find((r) => r.sku_id === SKU_OVER);
    expect(skippedRow, '★ skipped_items 必须精确含被跳过的那个 sku').toBeTruthy();
    expect(skippedRow.quantity, '明细必须回传数量').toBe(2);
    expect(String(skippedRow.reason),
      '★ reason 必须可区分「超上限」，否则前端给不出「调小即可重试」的提示')
      .toContain('上限');
    expect(String(skippedRow.reason), 'reason 应带上限值，便于诊断').toContain('999');
    expect(data.merged, '★ 另一件必须被算作合并成功').toBe(1);

    // ── 断言组 B：★ 落库结果（直读后端，**不看**响应体的自述）────────────
    await expect.poll(async () => qtyOf(request, SKU_OVER), { timeout: 20000 }).toBe(998);
    expect(await qtyOf(request, SKU_OVER),
      '★ 超限行既不得静默截断（变999），也不得叠加（变1000）').toBe(998);
    await expect.poll(async () => qtyOf(request, SKU_OK), { timeout: 20000 }).toBe(3);
    expect(await qtyOf(request, SKU_OVER), '★ 超限不得影响同批次其他行').toBe(998);

    // ── 断言组 D：★★ 重试不死循环（5463633 变更的核心论据）─────────────
    console.log('[RT1] ── 登出 → 重新匿名加购 → 再登录，验证重试仍 200 ──');
    await logout(page);
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await addGuestRowViaApi(page, SKU_OVER, 2);   // 同样的 payload 重放
    await loadGuestRowsIntoStore(page);
    const sk2 = await readSessionKey(page);

    const retry = observeMerge(page);   // ★ 新一轮观测
    await loginViaForm(page);
    await cleanupGuestRows(page, sk2);
    const second = await waitForMerge(retry, 1);

    expect(
      second.status,
      '★★ 重试不得变成 400 —— 那正是「死循环」的根因。真实响应体='
      + JSON.stringify(second.body).slice(0, 500),
    ).toBe(200);

    const d2 = second.body?.data || {};
    expect(d2.skipped, '★★ 未调小数量前，重试仍应被跳过（而非静默合并或 400）').toBe(1);
    expect(String((d2.skipped_items || [])[0]?.reason || ''),
      '重试时 reason 仍应说明超上限').toContain('上限');
    expect(await qtyOf(request, SKU_OVER),
      '★★ 重试后数量必须仍是 998（不得叠加、不得截断）').toBe(998);

  });
});

// ══════════════════════════════════════════════════════════════════════════
// RT2 —— 整批只有超限这一件时 ⇒ 被跳过且不留半成品（★ 真实后端）
// ══════════════════════════════════════════════════════════════════════════
test.describe('RT2 — 整批只有超限这一件（★ 真实后端）', () => {
  test('RT2 — merged=0/skipped=1，且账户里不出现新行或半成品', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    await assertSkusUsable(page);
    expect(await seedAccountQuantity(request, SKU_ONLY, 998)).toBe(998);
    expect(await qtyOf(request, SKU_ONLY)).toBe(998);

    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await addGuestRowViaApi(page, SKU_ONLY, 2);   // 998 + 2 = 1000 > 999
    const merge = observeMerge(page);
    await loadGuestRowsIntoStore(page);
    const sk1 = await readSessionKey(page);
    await loginViaForm(page);
    await cleanupGuestRows(page, sk1);

    const r = await waitForMerge(merge, 1);
    expect(r.status, '★ 整批只有超限这一件时也必须 200').toBe(200);

    const data = r.body?.data || {};
    expect(data.merged, '★ 一件都不该合并成功').toBe(0);
    expect(data.skipped).toBe(1);
    expect(String(data.skipped_items?.[0]?.reason || '')).toContain('上限');

    // ★ 不留半成品：既没有数量变化，也没有新增行
    expect(await qtyOf(request, SKU_ONLY), '★ 数量必须原样 998').toBe(998);
    const fresh = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
    let rowCount;
    try {
      rowCount = (await fetchAccountBasket(fresh)).filter((x) => x.sku === SKU_ONLY).length;
    } finally { await fresh.dispose().catch(() => {}); }
    expect(rowCount, '★ 不得出现半成品行（应仍只有预置的那1 行）').toBe(1);

  });
});

// ══════════════════════════════════════════════════════════════════════════
// RT3 —— `skipped === 0` 时整键清理不回归（★ 真实后端）
//⚠️⚠️ 注意：**必须先人工 seed 一份 localStorage 副本**，否则断言空转。
//    真实链路下匿名加购落的是后端，`loadBasket()` 成功时**不调**
//    `saveLocalBasket()` ⇒ localStorage 恒为 null ⇒ `toBeNull()` 恒真=
//    **假绿**。（实测踩过：首版没 seed，RT3 "通过"了但什么都没验证。）
//    种子对应 `addItem` 的**兜底分支**（`basket.js:97-112`，API 失败时才走）。
// ══════════════════════════════════════════════════════════════════════════
test.describe('RT3 — 全部成功时整键清理不回归（★ 真实后端）', () => {
  test('RT3 — skipped=0 ⇒ localStorage 整键被清 + session key 已轮换', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    await assertSkusUsable(page);
    await purgeAccountRowsForSku(request, SKU_CLEAN);

    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await addGuestRowViaApi(page, SKU_CLEAN, 4);

    // ★ 先种入本地副本，否则「整键被清」这条断言是空转的（见 describe 注释）
    await seedLocalBasket(page, {
      items: [{ sku_id: SKU_CLEAN, quantity: 4 }],
    });

    const sessionKeyBefore = await page.evaluate(
      () => localStorage.getItem('scireagent_session_key'));
    expect(sessionKeyBefore, '匿名态应已有 session key').toBeTruthy();
    expect(
      await readLocalBasket(page),
      '★ 前置护栏：localStorage 必须真的有副本，否则本用例的清理断言是空转',
    ).not.toBeNull();

    const merge = observeMerge(page);
    await loadGuestRowsIntoStore(page);
    const sk1 = await readSessionKey(page);
    await loginViaForm(page);
    await cleanupGuestRows(page, sk1);

    const r = await waitForMerge(merge, 1);
    expect(r.status, '全部合法时必须是 200').toBe(200);
    const data = r.body?.data || {};
    expect(data.skipped, '★ 全部合法时不得产生任何 skipped').toBe(0);
    expect(data.merged).toBe(1);

    // ★ 落库确认（真实后端确实合并了）
    await expect.poll(async () => qtyOf(request, SKU_CLEAN), { timeout: 20000 }).toBe(4);

    // ★ 前端整键清理（`basket.js:210-212`）不回归 —— 这次种子存在，断言有效
    await expect.poll(async () => readLocalBasket(page), { timeout: 15000 }).toBeNull();

    // ★ session key 已轮换（`basket.js:242-243`）—— 防登出后再登录二次合并
    await expect.poll(
      async () => page.evaluate(() => localStorage.getItem('scireagent_session_key')),
      { timeout: 15000 },
    ).not.toBe(sessionKeyBefore);

  });
});

// ══════════════════════════════════════════════════════════════════════════
// RT4 —— 整数边界：999 成功 / 1000 跳过（★ 真实后端）
// ══════════════════════════════════════════════════════════════════════════
test.describe('RT4 — 整数边界：999 成功 / 1000 跳过（★ 真实后端）', () => {
  test('RT4 — 997+2=999 成功合并；999+1=1000 被跳过', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    await assertSkusUsable(page);

    // ── 边界①：997 + 2 = 999 ⇒ **正好等于上限** ⇒ 必须成功（不误杀）─────
    await seedAccountQuantity(request, SKU_ONLY, 997);
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await addGuestRowViaApi(page, SKU_ONLY, 2);
    const m1 = observeMerge(page);
    await loadGuestRowsIntoStore(page);
    const sk1 = await readSessionKey(page);
    await loginViaForm(page);
    await cleanupGuestRows(page, sk1);
    const r1 = await waitForMerge(m1, 1);

    expect(r1.status).toBe(200);
    const d1 = r1.body?.data || {};
    expect(d1.merged, '★ 正好 999 必须合并成功（边界不得误杀）').toBe(1);
    expect(d1.skipped, '★ 正好 999 不得被跳过').toBe(0);
    await expect.poll(async () => qtyOf(request, SKU_ONLY), { timeout: 20000 }).toBe(999);
    console.log('[RT4] 边界① 997+2=999 ⇒ merged=1, 落库 999 ✅');

    // ── 边界②：999 + 1 = 1000 ⇒ **超一个也要跳过**（`>` 不是 `>=`）───────
    await logout(page);
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await addGuestRowViaApi(page, SKU_ONLY, 1);
    const m2 = observeMerge(page);
    await loadGuestRowsIntoStore(page);
    const sk2 = await readSessionKey(page);
    await loginViaForm(page);
    await cleanupGuestRows(page, sk2);
    const r2 = await waitForMerge(m2, 1);

    expect(r2.status, '★ 超 1 个也必须是 200+跳过，不是 400').toBe(200);
    const d2 = r2.body?.data || {};
    expect(d2.merged, '★ 1000 应被跳过，merged 应为 0').toBe(0);
    expect(d2.skipped).toBe(1);
    expect(String(d2.skipped_items?.[0]?.reason || '')).toContain('上限');
    expect(await qtyOf(request, SKU_ONLY), '★ 数量必须仍 999（不得叠加/截断）').toBe(999);
    console.log('[RT4] 边界② 999+1=1000 ⇒ merged=0, skipped=1, 落库仍 999 ✅');

  });
});

/**
 * ★★ 收尾清理钩子 —— **必须放`afterEach`，不能放在用例体内**。
 *
 * ⚠️ 实测踩过：清理写在用例体最后一行时，**RT5 是故意失败的** ⇒ 抛异常 ⇒
 *   `cleanupAll` 根本执行不到 ⇒ 每次跑都往共享 dev 库里留一行孤儿账户行
 *   （实测残留 `(613, 461, 998)`）。游客行已在用例内（登录后）清掉，
 *   但账户行必须靠 `afterEach` 兜底。
 */
test.afterEach(async ({ request }) => {
  await cleanupAll(request);
});

// ══════════════════════════════════════════════════════════════════════════
// ★★★ RT5 —— ★ **已知未决缺陷**：被跳过的商品用户**无法找回**
//
// ⚠️⚠️ **本用例故意保持失败。** 它断言的是**期望行为**，当前实现不满足。
//    ⚠️ 不要通过放宽断言让它变绿 —— 那正是它存在的意义。
//    缺陷分析与修复方向见**文件头「本 spec 揭露的一个未决缺陷」**。
//    判定为缺陷而非测试写错的依据：`5463633` 的 commit message 与
//    `basket_views.py:307-310` 的注释都明确承诺「被跳过的行会留在 localStorage，
//    用户自行调整数量后可重试」，而实测证明真实链路上 localStorage 从无副本。
// ══════════════════════════════════════════════════════════════════════════
test.describe('RT5 — ★ 已知缺陷：被跳过的商品应仍可被用户找回', () => {
  test('RT5 — 被跳过的行必须留在用户可达之处（当前不可达 ⇒ 本用例红）', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    await assertSkusUsable(page);
    await seedAccountQuantity(request, SKU_OVER, 998);

    // 记录匿名态的 session key —— 被跳过的行只存在于这个作用域下
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await page.waitForLoadState('load');
    await addGuestRowViaApi(page, SKU_OVER, 2);
    const oldSessionKey = await page.evaluate(
      () => localStorage.getItem('scireagent_session_key'));
    expect(oldSessionKey, '匿名态应已有 session key').toBeTruthy();

    const merge = observeMerge(page);
    await loadGuestRowsIntoStore(page);
    const sk1 = await readSessionKey(page);
    await loginViaForm(page);
    await cleanupGuestRows(page, sk1);
    const r = await waitForMerge(merge, 1);
    expect(r.status).toBe(200);
    expect(r.body?.data?.skipped, '前置：本用例针对「被跳过」这一支').toBe(1);

    // ── 检查点①：localStorage 应留有被跳过的行（用户可在购物车页看到并调小）
    //    实测：真实链路上 `loadBasket()` 成功时不调 `saveLocalBasket()`
    //    ⇒ localStorage 恒 null ⇒ `pruneMergedLocalItems` 的
    //    `if (!stored) return` 直接返回 ⇒ 这条断言失败。
    const local = await readLocalBasket(page);
    expect(
      local && Array.isArray(local.items) && local.items.some((i) => i.sku_id === SKU_OVER),
      '★ 被跳过的行必须留在 localStorage（用户可调小后重试）。'
      + ' 实测为 null —— 真实链路下 localStorage 从无副本，'
      + '`basket.js:278` 的 `if (!stored) return` 使 prune 逻辑从未生效。'
      + ' ⚠️ 这是 5463633 设计前提的缺口，勿放宽断言。',
    ).toBe(true);

    // ── 检查点②：游客作用域应仍可达（老 session key 未失效）─────────────
    //    实测：`basket.js:242-243` 在 merge 成功后**无条件**轮换 session key
    //    ⇒ 老 key 失效 ⇒ 登出后匿名访问购物车为空 ⇒ 用户也**无法人工找回**。
    await logout(page);
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const newSessionKey = await page.evaluate(
      () => localStorage.getItem('scireagent_session_key'));
    expect(
      newSessionKey,
      '★ 部分跳过时应保留原 session key，使被跳过的游客行仍可达。'
      + ` 实测已从 ${oldSessionKey} 轮换为 ${newSessionKey} ⇒ `
      + '被跳过的商品既没合并、也不可见（`basket.js:242-243` 无条件轮换）。'
      + ' ⚠️ 勿放宽断言。',
    ).toBe(oldSessionKey);

  });
});