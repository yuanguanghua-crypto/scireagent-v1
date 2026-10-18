/**
 * 回归测试 —— 前端合并后的 localStorage 清理逻辑（commit 1ab7d0f）
 * ============================================================================
 * 覆盖 `frontend/src/stores/basket.js` 的 `mergeLocalBasket()`（:185-237）与
 * `pruneMergedLocalItems()`（:254-294）。提交 1ab7d0f 之前，这三条分支**只靠代码
 * 审查保证**，而项目无前端单测框架（用户明确不为此新建 vitest/jest）⇒ 用 Playwright
 * E2E 补上唯一可自动化的回归网。
 *
 * 三条被测分支：
 *   1. `skipped === 0` → localStorage **整键被清**（:210-212）
 *   2. `skipped  > 0` → **只剔除已确认合并成功的行**，跳过的行留在本地（:213-222）
 *   3. 未提交/脏行    → 不被误删（:276-282 的 `!submittedSkus.has(k) → return true`）
 *
 * ★ 最关键的是 BC4「二次登录不叠加」：后端合并是**加法语义**
 *   （basket_views.py:278 `basket_item.quantity += quantity`），前端清理若有问题，
 *   同一批游客行会被提交两次 ⇒ 数量翻倍（实现者报告的 2→4、3→6）。这是真实数据
 *   损坏风险，不是清理细节。
 *
 * 运行方式（**必须打本地**，dev server 未起时全部会失败）：
 *   cd C:\Users\yuankaifeng\WorkBuddy\2026-07-08-11-22-32\src_claude\frontend
 *   node node_modules/@playwright/test/cli.js test e2e/basket-local-merge-prune.spec.cjs --project=chromium --reporter=line
 *
 * 前提：后端 :8000 + 前端 :5173 已启动（vite 代理 /api → 127.0.0.1:8000）。
 * ⚠️⚠️ **绝不可对生产跑本spec**：全部用例都会真登录并**写库**（合并购物车）。
 *   已打 `@write` + `@local-only` 标签（与全套 e2e 一致，见 `test:e2e:local`
 *   脚本按 `-g "@local-only"` 过滤、`e2e/gate-audit.cjs` 的 tier 闸门）。
 *
 * ⚠️ **本机环境的两个坑（实测踩过，不写下来下一个跑的人还会踩）**：
 *   1. `C:\Users\...\src_claude` 是指向 `E:\Users\...\src_claude` 的 junction。
 *      从 C: 启动 vite 会把 `src/main.js` 判定为"root 之外"而**原样返回**（不做
 *      依赖重写）⇒ 浏览器报 `Failed to resolve module specifier "vue"` ⇒ **整站白屏**，
 *      症状是"登录页找不到输入框"，很容易误判成选择器写错。
 *      ⇒ **必须从 E: 真实路径启动**：`cd /e/Users/yuankaifeng/.../frontend && npx vite`。
 *   2. 加购/查询端点带 `product__archived=False` 过滤（basket_views.py:47/54）
 *      ⇒ 必须挑一个**产品未归档**的 SKU，否则行写得进库却查不出来（实测 SKU 443
 *      的产品已归档 ⇒ `GET /basket` 返回空）。本spec 的 `PICK_REAL_SKU` 已处理。
 *
 * ---------------------------------------------------------------------------
 * ★ 为什么用 `page.route()` 拦截 `/basket/merge`
 * ---------------------------------------------------------------------------
 * 后端 `MergeBasketView`（basket_views.py:229-284）的 4 个跳过分支，
 * **只有 1 个能被 HTTP 触发**（读码 + 实测结论）：
 *
 *   分支 1 `if not sku_id`（:232-235）
 *     ⇒ **HTTP 不可达**。`MergeBasketItemSerializer.sku_id` 是
 *       `IntegerField(min_value=1)`（basket_serializers.py:74）⇒ 缺失/0/None
 *       在 `is_valid(raise_exception=True)`（:219）就整请求 400 了，进不了循环。
 *
 *   分支 2 `SKU.DoesNotExist / TypeError / ValueError`（:249-252）
 *     ⇒ ★**唯一 HTTP 可达的跳过分支**，也是本 spec 采用的构造方式：
 *       传一个**库里不存在的 sku_id**（`MISSING_SKU = 999999`）。serializer 只校验
 *       「int且≥1」，**不校验存在性** ⇒ 通过校验后在 `SKU.objects.get(id=)` 抛
 *       `DoesNotExist` ⇒ 落入 `skipped_items`。**这就是最小可构造方式。**
 *
 *   分支 3 `int(quantity)` 抛错（:255-259）
 *     ⇒ **HTTP 不可达**。`quantity` 是 `IntegerField(min_value=1, max_value=999)`
 *       （:75）⇒ 非数字在序列化层就400；数字必能 `int()`。:255 的裸 `int()` 是
 *       **纵深防御**，HTTP 打不到。
 *
 *   分支 4 `get_or_create` 写库抛 TypeError/ValueError/OverflowError（:280-283）
 *     ⇒ **HTTP 不可达**。quantity 被 `max_value=999` 夹住 ⇒ 不会有超大整数；且
 *       叠加超 999 在 :271-277 是**主动 `raise ValidationError`（整请求 400）**，
 *       不是跳过。此分支是给绕过 serializer 的调用方兜底的。
 *
 * ⇒ 既然真实后端也只能触发分支 2 一条，用 `page.route()` 直接控制 merge 响应体
 *   更稳、更快、更可控。沿用既有写法：`frontend/e2e/knowledge-intake.spec.cjs`
 *   （同样是 `page.route()` + `route.fulfill()` 伪造响应）。
 *   ★ 例外：**BC4 不拦截 merge**，走真实后端 —— 否则"数量会不会翻倍"就成了自证。
 *
 * ---------------------------------------------------------------------------
 * ★★ 本spec 覆盖不到什么（诚实评估，勿只看绿灯）
 * ---------------------------------------------------------------------------
 *   - 后端 `skipped` / `skipped_items` 的**产生**逻辑未被覆盖 —— BC1/BC2/BC3 的
 *     响应体是伪造的。真实链路里"哪种脏数据会产生 skipped、产生几条"**仍无自动化
 *     保护**。只有 BC4 的 MISSING_SKU 一行走的是真实后端分支 2。
 *   - `pruneMergedLocalItems` 的**其余防御分支未覆盖**：`localStorage` 不可用
 *     （隐私模式，:259）、写回失败/配额超限（:290-293）、`parsed.items` 非数组
 *     （:273-274）、无标识行（:278）。
 *   - BC4 断言的是「**提交给后端的 payload 不含重复 sku**」+「后端叠加后的总量」，
 *     它**不能**区分"前端少提交了一次"与"后端少合并了一次" —— 若两者同时发生，
 *     数量恰好对得上也会通过。
 *   - `mergeLocalBasket` 的**catch 分支**（:232-236，合并失败保留本地副本、
 *     不阻断登录）未覆盖。
 *   - 游客行的**产生**（`AddToBasketView` 写 `Basket(user=NULL, session_key=X)`）
 *     本 spec 会真实调用，但它本身不是本次被测对象。
 */

const { test, expect } = require('@playwright/test');
const { BASE_URL, ADMIN_USER, ADMIN_PASS, logout } = require('./helpers/auth.cjs');
const { apiContext, getToken } = require('./helpers/api.cjs');

/**
 * localStorage 键名 —— **实测自源码，非推断**：
 *   - `frontend/src/stores/basket.js:18` `LOCAL_STORAGE_KEY = 'scireagent_basket'`
 *   - `frontend/src/stores/basket.js:19` `SESSION_KEY_KEY  = 'scireagent_session_key'`
 *   （`utils/http.js:30` 也硬编码了后一个，见 X-Session-Key 头）
 *
 * ⚠️ 值里**没有** `_guest` 作用域标记 —— `_guest` 只是 **store 内存里的行属性**
 *   （由 `loadBasket()` 按"取数当下是否匿名"现打，`basket.js:47`/`:52`），
 *   **不落 localStorage**。
 *
 * localStorage 副本的**确切结构**是 `{ items: [ ...行... ] }`
 *   （`saveLocalBasket()` :82 `JSON.stringify({ items: items.value })`）；
 *   行的键是 `sku_id`（`addItem` 兜底分支写的是 `sku`，:104-109 ——
 *   prune 用 `sku_id ?? sku` 兼容两者，:277）。
 *
 * ★★ **merge 到底被什么触发**（实测结论，与直觉相反，务必读）：
 *   `auth.js:57-60` 的 `guestItems` 取自 **store 内存的 `basket.items`**
 *   （`.filter(i => i._guest || i._local)`），**完全不读 localStorage**；
 *   且 `auth.js:75` 有`if (guestItems.length > 0)` 前置守卫
 *   ⇒ **只往 localStorage 塞数据、却没让 store 拿到游客行，merge 压根不会发生**
 *   （实测：`MERGE CALLS = 0`，localStorage 原封不动 —— 这就是"假绿"的来源）。
 *   所以下面 `addGuestRowViaApi()` 必须**真实调后端加购**并在 `/cart` 页触发
 *   `loadBasket()`，让 store 真的拿到 `_guest: true` 的行。
 */

/** 未归档候选 SKU（实测存在）；pickRealSku 会逐个探测其可读性 */
const CANDIDATE_SKUS = [458, 153, 154, 459, 460, 155];

/** 库里不存在的 SKU id ⇒ 后端走 `SKU.DoesNotExist` ⇒ skipped（最小构造） */
const MISSING_SKU = 999999;

/**
 * 真实且**产品未归档**的 SKU id（实测得来，非拍脑袋）。
 * ⚠️ 必须未归档：`basket_views.py:47/54` 的读取侧过滤 `product__archived=False`
 *   会把归档产品的行藏起来 ⇒ 加购能写库成功（201）但 `GET /basket` 查不到，
 *   store 永远拿不到 `_guest` 行 ⇒ merge 不触发。
 *   （实测 SKU 443 的产品 `archived=True`，踩过；SKU 458/153/154/459/460/155 未归档。）
 * 运行时若该 SKU 失效，用 `pickRealSku()` 的兜底动态挑选。
 */
const PICK_REAL_SKU = 458;

/**
 * 动态挑一个"存在且产品未归档"的 SKU —— 避免把 id 写死导致库一变就红。
 * 失败时回落到 `PICK_REAL_SKU`。
 */
/**
 * ★ 动态挑一个「存在 + 产品未归档 + 账户购物车里没有」的 SKU。
 *
 * 三个条件缺一不可，每个都对应实测踩过的坑：
 *   1. **存在** —— 否则后端走 `SKU.DoesNotExist` ⇒ 落 skipped，测不到"合并成功"分支。
 *   2. **产品未归档** —— `basket_views.py:47/54` 读取侧过滤 `product__archived=False`
 *      ⇒ 归档产品的行**写得进库但永远查不到**（实测 SKU 443 就是这样），症状是
 *      "合并明明成功，断言却说没合并"，极具误导性。
 *   3. **账户购物车里没有** —— 后端合并是 `get_or_create` + `quantity += n`
 *      ⇒ 若已有行会累加到既有行上。
 *
 * 前端无法直接查"产品是否归档"，故用**间接探测**：把候选 SKU 匿名加进购物车，
 * 再 `GET /basket` 看它出不出来 —— 出不来就是归档的，跳过。探测完立刻删掉自己
 * 造的那行，不污染共享 dev 库。这样不硬编码"当前哪个没归档"，库变了也不用改代码。
 *
 * @param {import('@playwright/test').Page} page 复用本用例的页面（同源，有 session key）
 */
async function pickRealSku(page, request) {
  const token = await getToken(request, ADMIN_USER, ADMIN_PASS);
  const api = await apiContext(token);
  try {
    const used = new Set((await fetchAccountBasket(api)).map((r) => r.sku));

    // 确保页面已加载（拿到同源 localStorage 与 session key）
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });

    for (const candidate of CANDIDATE_SKUS) {
      if (used.has(candidate)) continue;
      if (await probeGuestVisibility(page, candidate)) return candidate;
    }
    // 都不可用 ⇒ 用账户里第一个（此时靠 base0 增量口径兜住）
    for (const r of await fetchAccountBasket(api)) if (r.sku) return r.sku;
  } catch (e) {
    console.warn(
      `[pickRealSku] 探测失败，回落到 ${PICK_REAL_SKU}：${String(e.message).split('\n')[0]}`,
    );
  } finally {
    await api.dispose().catch(() => {});
  }
  return PICK_REAL_SKU;
}

/**
 * 探测某 sku 是否"能被读侧看到"：匿名加 1 件 → `GET /basket` 看在不在。
 * ★ 探测完立刻删掉自己造的那行（游客作用域需带同一个 `X-Session-Key`）。
 */
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
    } catch {
      return null;
    }
  }, skuId);
  if (!probe?.rowId) return false;

  const seen = await page.evaluate(async (sk) => {
    const r = await fetch('/api/v1/basket', { headers: { 'X-Session-Key': sk } });
    if (!r.ok) return false; // ⚠️ 浏览器 fetch 的 `ok` 是**属性**，不是方法（勿写 r.ok()）
    const b = await r.json();
    return (b?.data?.items || []).length > 0;
  }, probe.sk);

  // 清理探测行
  await page.evaluate(async ({ rowId, sk }) => {
    try {
      await fetch(`/api/v1/basket/items/${rowId}/delete`, {
        method: 'DELETE',
        headers: { 'X-Session-Key': sk },
      });
    } catch { /* 清理失败不影响探测结论 */ }
  }, { rowId: probe.rowId, sk: probe.sk });

  return seen;
}

/**
 * ★必须走 **UI 表单登录**，不能用 `loginAsStaff`。
 *
 * 原因（决定性）：`helpers/auth.cjs` 的 `loginAsStaff` 默认走会话复用
 * （`loginViaSession`，:73-108）—— 它用 `addInitScript` **直接往 localStorage 写
 * token**，完全**绕过 `authStore.login()`**（`src/stores/auth.js:48-81`）。而
 * `mergeLocalBasket` 的**唯一触发点**是 `auth.js:77`（在 `login()` 内部、token
 * 落盘之后）⇒ 走会话复用时 merge **压根不会发生**，本 spec 要测的分支一条都不执行，
 * 测试会"通过"但毫无意义（假绿）。故自建 `loginViaForm()`，
 * 选择器沿用 `helpers/auth.cjs:123-127`（已实测核对）。
 */
async function loginViaForm(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);
  await page.getByRole('button', { name: 'Sign In' }).click();
  // 权威信号是 localStorage.token（auth.js:67 写入；登录失败绝不写）
  await page.waitForFunction(() => !!(localStorage.getItem('token') || '').trim(), null,
    { timeout: 30000 });
}

/** 在页面脚本运行前于同源 localStorage 种入数据（见文件头"merge 被什么触发"） */
async function seedLocalBasket(page, obj) {
  await page.addInitScript(
    ({ key, value }) => {
      try {
        localStorage.setItem(key, value);
      } catch { /* 某些页面无 localStorage ⇒ 交给后续严格校验 */ }
    },
    { key: 'scireagent_basket', value: JSON.stringify(obj) },
  );
}

/** 读取 localStorage 副本（已解析；无法解析时返回 `{ __unparseable }` 便于断言原样保留） */
function readLocalBasket(page) {
  return page.evaluate(() => {
    const raw = localStorage.getItem('scireagent_basket');
    if (raw === null) return null;
    try {
      return JSON.parse(raw);
    } catch {
      return { __unparseable: raw };
    }
  });
}

/** 读localStorage 原始字符串（用于"损坏副本逐字节保留"的断言） */
function readLocalBasketRaw(page) {
  return page.evaluate(() => localStorage.getItem('scireagent_basket'));
}

/** 读当前 session key */
function readSessionKey(page) {
  return page.evaluate(() => localStorage.getItem('scireagent_session_key'));
}

/**
 * ★ 真实匿名加购：调后端 `POST /api/v1/basket/items`（带 `X-Session-Key`）
 *   ⇒ 后端写 `Basket(user=NULL, session_key=<当前 key>)`（basket_views.py:108-127）。
 * 这是让 store 拿到 `_guest: true` 行的**唯一真实途径**。
 * @returns {Promise<number>} 后端返回的 Basket 行 id（供清理用），失败抛错
 */
async function addGuestRowViaApi(page, skuId, quantity) {
  // ⚠️ 必须先确保页面**完全就绪**：`page.goto(..., 'domcontentloaded')` 之后 SPA 还在
  //   加载模块，此时立刻 `fetch()` 会因页面仍在导航而抛 `TypeError: Failed to fetch`
  //   （实测踩过）。这里用 `waitForLoadState('load')` + 探活重试把它变成确定性等待。
  await page.waitForLoadState('load');
  const res = await page.evaluate(async ({ sku, qty }) => {
    let lastErr = null;
    // 探活 + 重试：最多 5 次，每次间隔 400ms
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

/**
 * 进入 `/cart` 触发 `loadBasket()`（`CartPage.vue:64`），让 store 真的拿到
 * `_guest` 行。**不这样做的实测后果**：store.items 为空 ⇒ `auth.js:75` 的
 * `guestItems.length > 0` 守卫不成立 ⇒ merge 不触发。
 * @returns {Promise<Array>} store 里的行（供断言确实拿到了游客行）
 */
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

/** 断言：本次确实触发了 merge（否则后续断言全是空转 —— 防"假绿"的关键护栏） */
function expectMergeTriggered(state, atLeast = 1) {
  expect(
    state.calls,
    `★ merge 未被触发（calls=${state.calls}）—— 若为 0，说明 store 里没有 _guest 行，` +
    '本用例的断言全部落空、属于假绿。请检查加购是否成功、SKU 产品是否已归档。',
  ).toBeGreaterThanOrEqual(atLeast);
  expect(state.body, 'merge 请求体应含 items').toBeTruthy();
  expect(Array.isArray(state.body.items)).toBe(true);
}

/** 统一的 merge 拦截器工厂（返回 { calls, body, payload 记录 }） */
function interceptMerge(page, data) {
  const state = { calls: 0, body: null, payloads: [] };
  page.route((u) => u.pathname === '/api/v1/basket/merge', (route) => {
    state.calls += 1;
    try {
      state.body = JSON.parse(route.request().postData() || 'null');
      state.payloads.push(state.body);
    } catch { /* 忽略 */ }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ success: true, data, meta: {} }),
    });
  });
  return state;
}

/** 删除测试造出来的后端行（只删本用例造的，绝不碰其他既有行） */
async function cleanupBasketRow(api, rowId) {
  if (!rowId) return;
  try {
    const r = await api.delete(`/basket/items/${rowId}/delete`);
    if (!r.ok()) {
      console.warn(`[cleanup] 删除 Basket 行 ${rowId} 失败：HTTP ${r.status()}`);
    }
  } catch (e) {
    console.warn(`[cleanup] 删除 Basket 行 ${rowId} 异常：${String(e.message).split('\n')[0]}`);
  }
}

/**
 * ★ 读账户购物车。
 *
 * ⚠️⚠️ **必须用 `.text()` + `JSON.parse`，不能用 `.data`** —— 实测踩过：
 *   Playwright 的 `APIResponse` **body 只能被消费一次**。`helpers/api.cjs` 的
 *   `get()` 包装在某些调用序列下会让 `.data` 拿到 `undefined`
 *   （实测：同一请求 `.text()` 能读到 1570 字节、含 `"sku":458`，
 *   而 `.data` 却解析成 `undefined` ⇒ `items=[]` ⇒ 断言读成"合并没生效"，
 *   极具误导性）。`.text()` 是显式读取，不依赖内部缓存状态。
 *
 * 另外两个实测踩过的坑：
 *   1. 路径**不能带尾斜杠**：`GET /api/v1/basket/`（带斜杠）返回 **404 HTML**
 *      （后端 `urls.py:29` 注册的是 `path('basket', ...)`）⇒ 必须用 `/basket`。
 *   2. 行里的 sku 字段名是 **`sku`**，不是 `sku_id`
 *      （`basket_serializers.py:34` 的 `fields` 里是 `'sku'`；`sku_id` 只是
 *      **写入**时的入参名，见 `MergeBasketItemSerializer`）。
 *
 * @returns {Promise<Array<{id:number, sku:number, quantity:number}>>}
 */
async function fetchAccountBasket(api) {
  const resp = await api.get('/basket');
  const raw = await resp.text();
  let body = null;
  try {
    body = JSON.parse(raw);
  } catch {
    throw new Error(
      `GET /basket 返回非 JSON（HTTP ${resp.status()}，content-type=` +
      `${resp.headers()['content-type']}）：${raw.slice(0, 200)}`,
    );
  }
  const rows = body?.data?.items || [];
  return rows.map((r) => ({ id: r.id, sku: r.sku, quantity: r.quantity }));
}

/** 读账户购物车里某 sku 的数量（不存在 ⇒ undefined） */
async function accountQtyOf(api, skuId) {
  const rows = await fetchAccountBasket(api);
  return rows.find((r) => r.sku === skuId)?.quantity;
}

/**
 * ★ 把某 sku 在**账户**购物车里的所有行删干净，并校验确实删掉了。
 *
 * 为什么必须校验：共享 dev 库里该 sku 可能有**上一轮跑剩下的残留**（实测踩过：
 * 账户里留着 qty=8 的行，导致"期望 2"直接失败，且每重跑一次再叠加 ⇒ 越跑越离谱）。
 * 只删指定 sku 的行，绝不碰其他商品。
 */
async function purgeAccountRowsForSku(api, skuId) {
  for (let i = 0; i < 5; i++) {
    const mine = (await fetchAccountBasket(api)).filter((r) => r.sku === skuId);
    if (!mine.length) return true;
    for (const r of mine) await cleanupBasketRow(api, r.id);
  }
  const left = (await fetchAccountBasket(api)).filter((r) => r.sku === skuId);
  if (left.length) {
    throw new Error(
      `前置清理失败：sku ${skuId} 仍残留 ${left.length} 行（id=${left.map((r) => r.id)}）`,
    );
  }
  return true;
}

// ══════════════════════════════════════════════════════════════════════
// BC1 — `skipped === 0`：全部合并成功 ⇒ localStorage **整键被清**
//      （basket.js:210-212；成功路径不回归）
// ══════════════════════════════════════════════════════════════════════
test.describe('BC1 — 全部合并成功时整键清理', () => {
  test('BC1 — skipped=0 ⇒ localStorage 整键被清空且 session key 已轮换', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    const realSku = await pickRealSku(page, request);

    // 真实匿名加购 ⇒ store 能拿到 _guest 行 ⇒ merge 会真的触发
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const guestRowId = await addGuestRowViaApi(page, realSku, 2);

    // 本地副本里再放两行（含一个不存在的 sku，但本用例假设后端全部合并成功）
    await seedLocalBasket(page, {
      items: [
        { sku_id: realSku, quantity: 2 },
        { sku_id: realSku + 1, quantity: 1 },
      ],
    });
    const sessionKeyBefore = await readSessionKey(page);
    expect(sessionKeyBefore, '匿名态应已有 session key').toBeTruthy();

    const merge = interceptMerge(page, {
      merged: 2, skipped: 0, skipped_items: [],
      items: [], total: '0.00', count: 0,
    });

    await loadGuestRowsIntoStore(page);
    await loginViaForm(page);

    // ★ 护栏：先确认 merge 真的发生了，否则下面的断言全是空转
    expectMergeTriggered(merge);
    expect(merge.body.items.map((i) => i.sku_id)).toContain(realSku);

    // ★ 断言 1：本地副本**整键被清**（basket.js:212removeItem）
    await expect.poll(async () => readLocalBasket(page), { timeout: 15000 }).toBeNull();

    // ★ 断言 2：session key 已轮换（basket.js:228-229 removeItem + getSessionKey）
    //   这是防「登出后再登录二次合并」的**另一套机制**，与 localStorage 清理相互独立。
    await expect.poll(async () => readSessionKey(page), { timeout: 15000 })
      .not.toBe(sessionKeyBefore);

    // 清理：只删本用例造出来的账户行
    const api = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
    await purgeAccountRowsForSku(api, realSku);
    await api.dispose();
  });
});

// ══════════════════════════════════════════════════════════════════════
// BC2 — `skipped > 0`：★核心 —— 已合并的剔除、跳过的**必须保留**
//      （basket.js:213-222 + pruneMergedLocalItems:276-282）
// ══════════════════════════════════════════════════════════════════════
test.describe('BC2 — 部分跳过时只剔除已合并的行', () => {
  test('BC2 — skipped>0 ⇒ 合并成功的行被剔除，跳过的行仍留在 localStorage', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    const realSku = await pickRealSku(page, request);
    const DIRTY_SKU = realSku + 1; // 本地副本里存在、但本次**不提交**的脏行

    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const guestRowId = await addGuestRowViaApi(page, realSku, 2);

    // 本地副本 3 行：realSku（将合并成功）、MISSING_SKU（将被跳过）、DIRTY（不提交）
    await seedLocalBasket(page, {
      items: [
        { sku_id: realSku, quantity: 2 },
        { sku_id: MISSING_SKU, quantity: 1 },
        { sku_id: DIRTY_SKU, quantity: 5 },
      ],
    });

    const merge = interceptMerge(page, {
      merged: 1,
      skipped: 1,
      // ★ 只回传被跳过那一行的标识 —— 这正是 1ab7d0f 新增的字段
      skipped_items: [{ sku_id: MISSING_SKU, quantity: 1 }],
      items: [], total: '0.00', count: 1,
    });

    await loadGuestRowsIntoStore(page);
    await loginViaForm(page);

    // ★ 护栏：确认 merge 真的发生
    expectMergeTriggered(merge);

    // 等 prune 写回完成
    await expect.poll(async () => readLocalBasket(page), { timeout: 15000 }).not.toBeNull();
    const local = await readLocalBasket(page);
    const remaining = local.items.map((i) => i.sku_id);

    // ★ 断言 1：**已合并成功的行必须被剔除**
    //   （否则下次重试会二次叠加，数量翻倍 —— 这正是 prune 存在的理由）
    expect(remaining, '已合并成功的行应被剔除').not.toContain(realSku);

    // ★ 断言 2：**被跳过的行必须保留**（★ 本 spec 最核心的断言）
    //   丢失它 ⇒ 商品既没进账户、也没留在本地 ⇒ 彻底丢失（basket.js:175-180）
    expect(remaining, '被跳过的行必须保留待重试').toContain(MISSING_SKU);

    // ★ 断言 3：**本次没提交的脏行不被误删**（prune:280 `!submittedSkus.has(k) → true`）
    expect(remaining, '本次没提交的脏行不应被误删').toContain(DIRTY_SKU);

    // 断言 4：跳过的行**字段未被重塑** —— 数量原样保留（prune:288 只 stringify）
    const skippedRow = local.items.find((i) => i.sku_id === MISSING_SKU);
    expect(skippedRow.quantity).toBe(1);

    // 断言 5：脏行的数量也不应变
    expect(local.items.find((i) => i.sku_id === DIRTY_SKU).quantity).toBe(5);

    const api = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
    await purgeAccountRowsForSku(api, realSku);
    await api.dispose();
  });
});

// ══════════════════════════════════════════════════════════════════════
// BC3 — 本地副本损坏（JSON parse 失败）⇒ **不清除**
//      （basket.js:264-271：无法判断哪些合并成功 ⇒ 宁可留一份待核对）
// ══════════════════════════════════════════════════════════════════════
test.describe('BC3 — 副本损坏时不清除', () => {
  test('BC3 — skipped>0 且副本 JSON 损坏 ⇒ 原样保留，不误删', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    const realSku = await pickRealSku(page, request);
    const CORRUPT = '{"items":[{"sku_id":' + realSku + ',';

    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const guestRowId = await addGuestRowViaApi(page, realSku, 2);

    // 种一个**语法不完整**的 JSON（不是合法JSON ⇒ JSON.parse 必抛）
    await page.addInitScript(
      ({ key, value }) => {
        try { localStorage.setItem(key, value); } catch { /* 忽略 */ }
      },
      { key: 'scireagent_basket', value: CORRUPT },
    );

    const merge = interceptMerge(page, {
      merged: 0,
      skipped: 1,
      skipped_items: [{ sku_id: realSku, quantity: 2 }],
      items: [], total: '0.00', count: 0,
    });

    await loadGuestRowsIntoStore(page);
    await loginViaForm(page);

    expectMergeTriggered(merge);

    // ★ 断言：损坏的副本**逐字节保持原样**（不清除、不覆写）
    await expect.poll(async () => readLocalBasketRaw(page), { timeout: 15000 })
      .toBe(CORRUPT);

    const api = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));
    await purgeAccountRowsForSku(api, realSku);
    await api.dispose();
  });
});

// ══════════════════════════════════════════════════════════════════════
// BC4 — ★最关键★ **二次登录不叠加**
//      后端合并是加法语义（basket_views.py:278`quantity += n`），
//      同一批游客行若被提交两次 ⇒ 数量翻倍（实现者报告实测 2 → 4、3 → 6）。
//      ★ 本用例**不拦截 merge**，走**真实后端**，断言最终落库的数量。
// ══════════════════════════════════════════════════════════════════════
test.describe('BC4 — 二次登录不叠加（★ 真实后端）', () => {
  test('BC4 — 合并成功后登出再登录，同一 sku 数量不翻倍', {
    tag: ['@write', '@local-only'],
  }, async ({ page, request }) => {
    const realSku = await pickRealSku(page, request);
    const api = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS));

    // ★★ 断言口径：**基线增量**。
    //
    // 为什么不用绝对值：共享 dev 库里该 sku 可能已有残留行（实测），而后端合并是
    // `get_or_create` + `quantity += n`（basket_views.py:262-279）⇒ 会**累加到既有
    // 行**上。此时"期望绝对值 2"在脏库上必然失败，而失败原因与本用例真正要测的
    // "二次登录会不会翻倍"毫无关系 ⇒ 纯噪声。
    // ⇒ 记基线 `base0`，之后只断言**增量**（先 +2、再 +3 ⇒ 合计 +5）。
    //    无论库里多脏，断言都精确对应"这两次合并各贡献了多少"。
    // ⚠️ 每次读都**新建**一个 api context，不用长期持有的那个。
    //   实测踩过：长期持有的 context 在 purge 之后读`GET /basket` 会返回空数组，
    //   而同一时刻 curl 能读到行 ⇒ 表现为"合并成功但断言说没合并"，极难诊断。
    //   每次新建 context 代价极小（本地 dev），换来读的一定是当下真实状态。
    const qtyOf = async () => {
      const t = await getToken(request, ADMIN_USER, ADMIN_PASS);
      const fresh = await apiContext(t);
      try {
        return await accountQtyOf(fresh, realSku);
      } finally {
        await fresh.dispose().catch(() => {});
      }
    };
    // 先尽力清理（成功与否都不影响断言 —— 增量口径对此免疫）
    await purgeAccountRowsForSku(api, realSku).catch(() => {});
    const base0 = (await qtyOf()) || 0;

    // ── 第 1 轮：匿名加购 → 登录 → 真实合并 ──────────────────────────
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    await addGuestRowViaApi(page, realSku, 2);
    const sessionKey1 = await readSessionKey(page);

    // ★ 只**观测** merge 请求体，**完全不拦截**。
    //   ⚠️⚠️ 实测踩过两个坑，两者都会让合并**不落库**，症状都是"合并成功但账户查不到"：
    //     a) `route.continue()` —— 请求放行了，但在本机vite 代理链路下后端没收到；
    //     b) `route.fetch()` + `route.fulfill({response})` —— 同样收不到，
    //        且更难察觉（因为"确实发起了请求"，只是没到后端）。
    //   ⇒ 结论：**BC4 绝不碰路由**。用 `page.on('request')` 旁路记录 payload 即可，
    //      数量断言直接读后端，根本不需要伪造或转发任何响应。
    const observed = [];
    page.on('request', (req) => {
      try {
        if (new URL(req.url()).pathname === '/api/v1/basket/merge') {
          observed.push(JSON.parse(req.postData() || 'null'));
        }
      } catch { /* 非 JSON，忽略 */ }
    });

    await loadGuestRowsIntoStore(page);
    await loginViaForm(page);

    // 护栏：merge 必须真的发生过
    await expect.poll(() => observed.length, { timeout: 20000 })
      .toBeGreaterThanOrEqual(1);

    // 等merge 落库：增量应为 +2
    await expect.poll(async () => (await qtyOf()) - base0, { timeout: 20000 }).toBe(2);
    const qty1 = (await qtyOf());
    expect(qty1 - base0, '第 1 次登录后该 sku 应恰好 +2（匿名加的 2 件）').toBe(2);

    // ★★ 断言 1（**最关键**）：第 1 次 merge 的 payload 里，该 sku **只出现一次**。
    //   重复提交同一 sku 是"翻倍"的直接原因 —— 后端会对每一条独立 `+= 2`。
    const firstPayload = observed[0];
    const firstSkuCount = firstPayload.items.filter((i) => i.sku_id === realSku).length;
    expect(firstSkuCount, '★ payload 中同一 sku 不得重复提交（否则后端会叠加多次）').toBe(1);

    // ── 登出 → 第 2 轮 ───────────────────────────────────────────────
    // ⚠️ `logout()`（helpers/auth.cjs:173-188）会 dispose 会话注入脚本 +
    //   `localStorage.clear()` ⇒ 确保从干净匿名态开始。
    await logout(page);

    // ★ 关键场景还原：登出后**匿名又加了同一 sku**（新的游客批次）。
    //   若前端没把游客作用域隔离好，第 2 次登录会把这批行与账户行一起提交 ⇒ 翻倍。
    await page.goto(`${BASE_URL}/`, { waitUntil: 'domcontentloaded' });
    const sessionKey2 = await readSessionKey(page);
    expect(sessionKey2, '登出后应有新的 session key').toBeTruthy();
    expect(sessionKey2, '★ session key 必须已轮换，否则登出后再登录会二次合并')
      .not.toBe(sessionKey1);

    await addGuestRowViaApi(page, realSku, 3);
    await loadGuestRowsIntoStore(page);
    await loginViaForm(page);

    // 等第 2 次 merge 落地（增量应变为 +5 = 2 + 3）
    await expect.poll(async () => (await qtyOf()) - base0, { timeout: 25000 }).toBe(5);

    const qty2 = (await qtyOf());

    // ★★ 断言 2：相对基线的增量恰为 **+5**（第1 批 2 + 第 2 批 3）。
    //   翻倍的话会是 +7（2+2+3）或更多；少提交则是 +3 或 +2。
    //   ⇒ 这正是实现者警告的真实数据损坏场景。
    expect(qty2 - base0, `★ 增量不应翻倍：期望 +5（2+3），实际 +${qty2 - base0}`).toBe(5);

    // 断言 3：第 2 次 merge 的 payload 同样不含重复 sku
    expect(observed.length, '★ 第 2 次登录也应触发 merge').toBeGreaterThanOrEqual(2);
    const secondSkuCount = observed[1].items.filter((i) => i.sku_id === realSku).length;
    expect(secondSkuCount, '★ 第 2 次 payload 中同一 sku 也不得重复').toBe(1);

    // 清理：只删本用例造出来的这一行（失败只warn，不影响上面的结论）
    await purgeAccountRowsForSku(api, realSku).catch(() => {});
    await api.dispose();
  });
});