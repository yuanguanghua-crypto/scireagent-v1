/**
 * 跨浏览器冒烟 —— 全站 44 个页面（维度 B）
 *
 * 覆盖范围：docs/e2e/COVERAGE_AUDIT.md「逐页审计」表的全部 44 条路由（1 行 1 页）。
 * 页面清单与根 class 直接复用 `e2e/responsive.spec.cjs` 的 PUBLIC / STAFF 两个数组
 * （来源：responsive.spec.cjs:27-70；本文件复制粘贴而非 require，因为该文件在模块加载时
 *  就执行了 test.describe，require 会把整套响应式用例再注册一遍）。
 * 缺失的 9 条路由（5 个公开详情/兜底 + 4 个后台详情）由本文件补齐 →
 *   PUBLIC 17 + STAFF 27 = 44。
 *
 * 每个页面的断言（刻意保持"轻但真"，只读、零写入）：
 *   1) 页面根元素 `sel` 可见（toBeVisible）
 *   2) 零 pageerror（监听 page.on('pageerror')）
 *   3) 无 4xx/5xx 的 `/api/` 响应（监听 page.on('response')，只过滤 url 含 '/api/'）
 *
 * 反假绿：
 *   - 循环生成用例前先断言 ALL.length === 44（数组漏项会让"全绿"变得毫无意义）；
 *   - 断言不允许 `>=0` 这类永真条件；
 *   - 每条断言的 message 都带「页面 name + path」，失败可直接定位。
 *
 * :id 不写死：首次需要时调用 getIds()（模块级 memo），经 helpers/api.cjs 的 getSession
 *   拿 staff token，读各实体列表的第一条 id。
 *   ★ 2026-10-21 改造：解析**尽力而为** —— 某个实体在本库没有数据时，
 *   只 `test.skip` **依赖它的那几页**（并写明原因），其余页面照跑。
 *   原实现是任一缺失就 throw，而每个用例都会调 getIds() ⇒ 空库/缺数据时**44 页全红**
 *   （连 Home/Login 都红）。在 CI（空库 + 最小种子）里会把「缺 4 类实体」放大成「整站不可用」，
 *   属假失败。**注意：skip 一律带原因，不静默跳过。**
 *
 * ⚠️ 环境说明：本机系统代理（FlClash）会把 http://localhost:5173/@vite/client 接走返回 404，
 *   导致 Firefox 下 SPA 挂不上。config 的 firefox project 已加
 *   `network.proxy.type: 0`（关代理）⇒ FF 可正常跑。WebKit 在 Windows 上无法绕开系统代理，
 *   本 spec 不在 WebKit 上运行。
 */
const { test, expect, request: apiRequest } = require('@playwright/test')
const { loginAsStaff, BASE_URL, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth.cjs')
const { getSession, apiContext, API_BASE } = require('./helpers/api.cjs')

// ── 公开页（匿名访问）────────────────────────────────────────────────────────
// 前 12 条原样来自 responsive.spec.cjs:27-42（/products/66 改为动态解析真实 id）
const PUBLIC = [
  { name: 'Home', path: '/', sel: '.home' },
  { name: 'Products', path: '/products', sel: '.product-grid' },
  { name: 'ProductDetail', path: (ids) => `/products/${ids.product}`, sel: 'main', needs: 'product' },
  { name: 'Search', path: '/search', sel: '.search-page' },
  { name: 'Login', path: '/login', sel: '.auth-page' },
  { name: 'Register', path: '/register', sel: '.auth-page' },
  { name: 'QuoteRequest', path: '/quote-request', sel: '.rfq-page' },
  { name: 'AppIndex', path: '/applications', sel: '.application-index' },
  { name: 'MethodIndex', path: '/methods', sel: '.method-index' },
  { name: 'ProtocolIndex', path: '/protocols', sel: '.protocol-index' },
  { name: 'RGIndex', path: '/research-goals', sel: '.research-goal-index' },
  { name: 'CartPage', path: '/cart', sel: '.cart-page' },
  // ★ 本文件补齐（audit 第 6/8/10/14/17 行）
  { name: 'AppDetail', path: (ids) => `/applications/${ids.application}`, sel: '.detail-page', needs: 'application' },
  { name: 'MethodDetail', path: (ids) => `/methods/${ids.method}`, sel: '.detail-page', needs: 'method' },
  { name: 'ProtocolDetail', path: (ids) => `/protocols/${ids.protocol}`, sel: '.protocol-detail', needs: 'protocol' },
  { name: 'RGDetail', path: (ids) => `/research-goals/${ids.researchGoal}`, sel: '.research-goal-detail', needs: 'researchGoal' },
  { name: 'NotFound', path: '/__xbr_no_such_route__', sel: '.not-found' },
]

// ── 后台页（staff 登录）──────────────────────────────────────────────────────
// 前 23 条原样来自 responsive.spec.cjs:43-70
const STAFF = [
  { name: 'AdminOrders', path: '/ops/orders', sel: '.order-table' },
  { name: 'Workspace', path: '/workspace', sel: '.workspace-layout' },
  { name: 'WorkspaceProducts', path: '/workspace/products', sel: '.products-page' },
  { name: 'ProductNew', path: '/workspace/products/new', sel: '.product-edit' },
  { name: 'SettingsPage', path: '/settings', sel: '.settings-page' },
  { name: 'CheckoutPage', path: '/checkout', sel: '.checkout-page' },
  { name: 'OrderList', path: '/orders', sel: '.order-list-page' },
  { name: 'PoSubmit', path: '/po/submit', sel: '.po-page' },
  { name: 'PoOrderList', path: '/po/orders', sel: '.po-page' },
  { name: 'PoAddressList', path: '/po/addresses', sel: '.po-page' },
  { name: 'PoReorder', path: '/po/reorder', sel: '.po-page' },
  { name: 'PoDownloadCenter', path: '/po/downloads', sel: '.po-page' },
  { name: 'PoReviewDesk', path: '/ops/po/review', sel: '.po-page' },
  { name: 'PoShipmentDesk', path: '/ops/po/shipments', sel: '.po-page' },
  { name: 'PoInvoicingDesk', path: '/ops/po/invoicing', sel: '.po-page' },
  { name: 'PoArReport', path: '/ops/po/ar', sel: '.po-page' },
  { name: 'PoOrgManagement', path: '/ops/po/organizations', sel: '.po-page' },
  { name: 'WsGoals', path: '/workspace/goals', sel: '.entity-page' },
  { name: 'WsApplications', path: '/workspace/applications', sel: '.entity-page' },
  { name: 'WsMethods', path: '/workspace/methods', sel: '.entity-page' },
  { name: 'WsProtocols', path: '/workspace/protocols', sel: '.entity-page' },
  { name: 'WsReferences', path: '/workspace/references', sel: '.entity-page' },
  { name: 'WsKnowledgeIntake', path: '/workspace/knowledge-intake', sel: '.ki-page' },
  // ★ 本文件补齐（audit 第 21/24/31/39 行）
  // 真实路由是 `products/:id/edit`（router/index.js:272），不是 products/new/:id/edit
  { name: 'OrderDetail', path: (ids) => `/orders/${ids.order}`, sel: '.order-detail-page', needs: 'order' },
  { name: 'PoOrderDetail', path: (ids) => `/po/orders/${ids.poOrder}`, sel: '.po-page', needs: 'poOrder' },
  { name: 'ProductEdit', path: (ids) => `/workspace/products/${ids.product}/edit`, sel: '.product-edit', needs: 'product' },
  { name: 'AdminOrderDetail', path: (ids) => `/ops/orders/${ids.adminOrder}`, sel: '.admin-order-detail', needs: 'adminOrder' },
]

const ALL = [...PUBLIC, ...STAFF]
const ROUTE_COUNT = 44

const pathOf = (p, ids) => (typeof p.path === 'function' ? p.path(ids) : p.path)

// ── :id 解析（模块级 memo：整轮只解析一次，失败也缓存 ⇒ 不重复打登录接口）──
let _idsPromise = null

async function _rows(client, path, label) {
  const resp = await client.get(path)
  if (resp.status() !== 200) {
    throw new Error(`解析 ${label} 的 :id 失败：GET ${path} 返回 HTTP ${resp.status()}`)
  }
  let body
  try {
    body = await resp.json()
  } catch (e) {
    throw new Error(`解析 ${label} 的 :id 失败：GET ${path} 响应不是 JSON（${e.message}）`)
  }
  const rows = Array.isArray(body.data) ? body.data : (body.data && body.data.results) || []
  if (!rows.length) {
    throw new Error(`解析 ${label} 的 :id 失败：GET ${path} 返回空列表（本地库没有可用于冒烟的数据）`)
  }
  return rows
}

function _pickId(row, label, path) {
  const id = row && row.id
  if (id === undefined || id === null || id === '') {
    throw new Error(`解析 ${label} 的 :id 失败：GET ${path} 首条记录没有 id 字段`)
  }
  return id
}

async function _resolveIds() {
  const staffReq = await apiRequest.newContext()
  const anonReq = await apiRequest.newContext()
  let api = null
  const ids = {}
  // ★ 2026-10-21 改造：解析**尽力而为**，缺哪个只影响依赖它的那几页，不再连坐全部 44 页。
  //   原实现是"任一缺失就 throw"，而 throw 发生在每个用例里（都调 getIds()）
  //   ⇒ 空库/缺数据时 44 页**全部**失败，连 Home/Login 这种静态页也红。
  //   在 CI（全新空库 + 最小种子）里这会把"缺 4 类实体"放大成"整站不可用"，属于假失败。
  //   ⇒ 现在：缺失记进 `ids._issues`，用例侧只 `test.skip` 依赖它的页，其余照跑。
  ids._issues = {}

  const take = async (key, label, fn) => {
    try {
      const v = await fn()
      if (v === undefined || v === null || v === '') throw new Error('解析结果为空')
      if (!Number.isFinite(Number(v)) || Number(v) <= 0) {
        throw new Error('期望正整数，实际 ' + JSON.stringify(v))
      }
      ids[key] = v
    } catch (e) {
      ids._issues[key] = label + '：' + String((e && e.message) || e).split('\n')[0]
    }
  }

  try {
    // staff token：与 loginAsStaff 共用 helpers/api.cjs 的模块级缓存 ⇒ 整轮只登录 1 次
    const session = await getSession(staffReq, ADMIN_USER, ADMIN_PASS)
    api = await apiContext(session.token)

    // ⚠️ 5 个**公开**实体（applications/methods/protocols/research-goals/products）的 :id
    //   必须从**匿名**列表里取：staff 列表含未发布/内部状态的实体，
    //   拿它去打开公开详情页会得到 404（实测：/api/v1/methods/54/ 匿名 404）。
    // ⚠️ anonReq 是裸 request context（没有 baseURL）⇒ 必须用绝对 URL。
    const anonList = (path, label) => _rows(anonReq, `${API_BASE}${path}`, label)

    await take('application', 'applications（匿名）', async () =>
      _pickId((await anonList('/applications/?page_size=5', 'applications（匿名）'))[0], 'applications', '/applications/'))
    await take('method', 'methods（匿名）', async () =>
      _pickId((await anonList('/methods/?page_size=5', 'methods（匿名）'))[0], 'methods', '/methods/'))
    await take('protocol', 'protocols（匿名）', async () =>
      _pickId((await anonList('/protocols/?page_size=5', 'protocols（匿名）'))[0], 'protocols', '/protocols/'))
    await take('researchGoal', 'research-goals（匿名）', async () =>
      _pickId((await anonList('/research-goals/?page_size=5', 'research-goals（匿名）'))[0], 'research-goals', '/research-goals/'))
    await take('product', 'products（匿名）', async () =>
      _pickId((await anonList('/products/?page_size=5', 'products（匿名）'))[0], 'products', '/products/'))

    // 订单类：一次取 200 条，同时挑出普通单 / PO 单
    let orderRows = []
    try {
      orderRows = await _rows(api, '/orders/?page_size=200', 'orders')
      const first = orderRows[0]
      if (first) {
        ids.order = _pickId(first, 'orders', '/orders/')
      } else {
        ids._issues.order = 'orders：列表为空（本库没有订单）'
      }
      const poRow = orderRows.find(
        (o) => o.payment_method === 'purchase_order' || /^po_/.test(String(o.status || '')),
      )
      if (poRow) ids.poOrder = _pickId(poRow, 'po orders', '/orders/')
      else ids._issues.poOrder = 'poOrder：本库没有 PO 单（/po/orders/:id 只对 PO 单有意义）'
    } catch (e) {
      ids._issues.order = 'orders：' + String((e && e.message) || e).split('\n')[0]
      ids._issues.poOrder = ids._issues.order
    }

    await take('adminOrder', 'admin/orders', async () =>
      _pickId((await _rows(api, '/admin/orders/?page_size=5', 'admin/orders'))[0], 'admin/orders', '/admin/orders/'))

    return ids
  } finally {
    if (api) await api.dispose().catch(() => {})
    await staffReq.dispose().catch(() => {})
    await anonReq.dispose().catch(() => {})
  }
}

function getIds() {
  if (!_idsPromise) _idsPromise = _resolveIds()
  return _idsPromise
}

// ── 守卫：pageerror + /api/ 4xx/5xx ─────────────────────────────────────────
function attachGuards(page) {
  const pageErrors = []
  const badApi = []
  page.on('pageerror', (e) => pageErrors.push(String((e && e.message) || e)))
  page.on('response', (r) => {
    try {
      const url = r.url()
      if (!url.includes('/api/')) return
      const status = r.status()
      if (status >= 400) badApi.push(`HTTP ${status} ${url}`)
    } catch {
      /* response 对象可能已失效 ⇒ 忽略 */
    }
  })
  return { pageErrors, badApi }
}

async function checkPage(page, p, ids) {
  const path = pathOf(p, ids)
  const label = `[${p.name}] ${path}`

  const guards = attachGuards(page)
  await page.goto(BASE_URL + path, { waitUntil: 'domcontentloaded' })

  // 1) 根元素可见
  await expect(
    page.locator(p.sel).first(),
    `${label} 根元素 ${p.sel} 未渲染/不可见（页面没挂上或数据请求失败）`,
  ).toBeVisible({ timeout: 20000 })

  // 给异步请求/渲染留出窗口，避免"检查太早"造成的假绿
  await page.waitForLoadState('load').catch(() => {})
  await page.waitForTimeout(500)

  // 2) 零 pageerror
  expect(
    guards.pageErrors,
    `${label} 出现 pageerror（共 ${guards.pageErrors.length} 条）：\n${guards.pageErrors.join('\n---\n')}`,
  ).toHaveLength(0)

  // 3) 无 4xx/5xx 的 /api/ 响应
  expect(
    guards.badApi,
    `${label} 出现 ${guards.badApi.length} 条 4xx/5xx /api/ 响应：\n${guards.badApi.join('\n')}`,
  ).toHaveLength(0)
}

test.describe('跨浏览器冒烟：全站 44 页', { tag: ['@readonly', '@local-only', '@cross-browser'] }, () => {
  // 防假绿：数组漏项时下面这条会先失败
  test('页面清单完整性（44 条，无重复）', () => {
    expect(ALL.length, `页面清单应为 ${ROUTE_COUNT} 条，实际 ${ALL.length} 条（PUBLIC=${PUBLIC.length}, STAFF=${STAFF.length}）`).toBe(ROUTE_COUNT)
    expect(ALL.length, 'PUBLIC + STAFF 拼接后条数不一致').toBe(PUBLIC.length + STAFF.length)
    const names = ALL.map((p) => p.name)
    expect(new Set(names).size, `页面 name 有重复：${names.join(', ')}`).toBe(names.length)
    const literalPaths = ALL.filter((p) => typeof p.path === 'string').map((p) => p.path)
    expect(new Set(literalPaths).size, `固定路径有重复：${literalPaths.join(', ')}`).toBe(literalPaths.length)
  })

  test.describe('公开页（匿名）', () => {
    for (const p of PUBLIC) {
      test(`${p.name} — 匿名渲染正常`, async ({ page }) => {
        const ids = await getIds()
        // 该页需要某个 :id 但本库没有 ⇒ 只跳过这一页，并写明原因（不静默、不连坐）
        if (p.needs && ids[p.needs] === undefined) {
          test.skip(true, `本库无可用 ${p.needs}：${(ids._issues || {})[p.needs] || '解析失败'}`)
        }
        await checkPage(page, p, ids)
      })
    }
  })

  test.describe('后台页（staff）', () => {
    test.beforeEach(async ({ page }) => {
      await loginAsStaff(page)
    })
    for (const p of STAFF) {
      test(`${p.name} — staff 渲染正常`, async ({ page }) => {
        const ids = await getIds()
        if (p.needs && ids[p.needs] === undefined) {
          test.skip(true, `本库无可用 ${p.needs}：${(ids._issues || {})[p.needs] || '解析失败'}`)
        }
        await checkPage(page, p, ids)
      })
    }
  })
})
