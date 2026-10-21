/**
 * 阶段 7 · 维度 S（状态分支）—— 商业域 **按页面** 的状态穷举
 *
 * ## 为什么有这个文件（与 state-matrix.spec.cjs 的分工）
 * `state-matrix.spec.cjs` 是**按 PO 的 8/9 个状态**组织的（一态一条，全部落在
 * `/ops/orders/:id` 一个页面上），审计脚本 `scripts/audit_7d_auto.py` 判 S 维的依据是
 * 「该页出现在某个状态矩阵 spec 里」⇒ 其余页面一律判 ✗。
 * 本文件把「**一个页面**上真实存在的状态分支」逐页走一遍（同页多态对比、含反向断言），
 * 断言点落在**状态导致的可见差异**上，而不是"页面能打开"。
 *
 * ## 覆盖的页面（与审计口径一致，`path:` 字面量同时是 goto 依据）
 *   /products                      ProductIndex        空态 / 有数据 / 分页边界
 *   /products/:id                  ProductDetail       有SKU·无SKU / draft·active·deprecated / 回收站兜底
 *   /orders                        OrderListPage       空态 / 有数据（状态徽章）
 *   /orders/:id                    OrderDetailPage     quoted 才有报价动作条（含 accept→confirmed 迁移）
 *   /workspace/products/new        ProductEditPage     新建态（无步进器）/ 首存后进 edit 态 / 必填标红作用域
 *   /workspace/products/:id/edit   ProductEditPage     draft vs active 步进器（双向真迁移）
 *
 * ## 纪律（本项目硬性）
 *  - 拟人化：状态一律从 UI 造/改（工作台新建、状态下拉、行操作菜单），不用 page.evaluate 塞值。
 *    **API 只用于两类事**：① 只读取真实数据（取一个带 SKU 的产品 id）；② `afterAll` 清理。
 *    唯一例外是 `/orders` 的空态：该页无筛选且共享库中 e2e_customer 有 900+ 单，
 *    无法在共享库上确定性地得到 0 条 ⇒ 用**响应拦截**构造空响应（不写库、不改组件状态），
 *    并在该用例注释里显式标注。
 *  - 禁止断言绝对数量：只断言「我自己造的那一条」及其状态（`E2E-ST-<ts>` 唯一标记）。
 *  - 禁止 snapshotDb() 的 Δ 断言（并发会假失败）。
 *  - 选择器均来自源码，注释里给 `文件:行号`。
 *
 * ## 数据与清理
 *  产品：一律 UI 新建，catalog_no = `E2E-ST-<RUN_TS>-<k>`；afterAll 用
 *        `cleanupByPrefix(prefix=MARK)` **硬删**（只匹配本轮时间戳 ⇒ 不动别人的 E2E- 数据）。
 *  订单：`/orders*` 的夹具是 checkout(quote) 单；**quoted 是粘性态**（`quoted → cancelled`
 *        状态机不允许，实测 400 INVALID_TRANSITION）⇒ 用例内用 UI 点 Accept Quote
 *        （quoted → quote_accepted → confirmed），afterAll 再对 confirmed 取消 ⇒ 零残留。
 *        兜底：仍未取消成功的**我自己创建的 id** 才会被 dbExec 删除（只按 id，不做通配）。
 *
 * ## 运行（必须带 --output，避开共享 test-results）
 *   cd frontend
 *   npx playwright test e2e/state-branches-commerce.spec.cjs --project=chromium \
 *     --reporter=line --output=/tmp/pw-stA > /tmp/pw-stA.log 2>&1; echo "EXIT=$?"
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, ADMIN_USER, ADMIN_PASS, CUST_USER, CUST_PASS } = require('./helpers/auth.cjs')
const { apiContext, getToken, getSession } = require('./helpers/api.cjs')
const { cleanupByPrefix } = require('./fixtures/index.cjs')
const { dbExec } = require('./helpers/db-write.cjs')
const h = require('./helpers/poHelpers.cjs')

const RUN_TS = Date.now()
const MARK = `E2E-ST-${RUN_TS}` // 本轮唯一标记（产品货号前缀 / 订单 PO 号前缀）
const catOf = (k) => `${MARK}-${k}`

/**
 * 页面清单 —— `path` 字面量既是 goto 依据，也是 `scripts/audit_7d_auto.py` 判 S 维的数据源
 * （它用 `re.findall(r"path:\s*'([^']+)'")` 扫描）。**不要把 path 改成模板字符串**，
 * 否则审计读不到（这正是这 14 页判 ✗ 的历史原因）。
 */
const PAGES = {
  productIndex: { name: 'ProductIndex', path: '/products' },
  productDetail: { name: 'ProductDetail', path: '/products/:id', base: '/products' },
  orders: { name: 'OrderListPage', path: '/orders' },
  orderDetail: { name: 'OrderDetailPage', path: '/orders/:id', base: '/orders' },
  productNew: { name: 'ProductEditPage', path: '/workspace/products/new' },
  productEdit: { name: 'ProductEditPage', path: '/workspace/products/:id/edit', base: '/workspace/products' },
}

/* ── 本轮造的数据（只用于 afterAll 精确清理） ───────────────────────────── */
const createdOrderIds = [] // 我创建的订单 id（清理只认这些 id，不做任何通配）
let adminToken = null
let custToken = null
let liveProd = null // 共享库里一个 **status=active 且带 SKU** 的产品（只读，用于「有 SKU」分支）
let reqCtx = null

test.beforeAll(async () => {
  reqCtx = await request.newContext()
  // getToken 内部按 username 缓存（DRF token 不过期）⇒ 整轮只真正登录 1 次/账号，
  // 避免撞后端 LoginRateThrottle = 5 次/分钟/IP（helpers/api.cjs:66-133）。
  adminToken = await getToken(reqCtx, ADMIN_USER, ADMIN_PASS)
  custToken = await getToken(reqCtx, CUST_USER, CUST_PASS)
  liveProd = await findActiveProductWithSkus()
  expect(liveProd?.id, '共享库里应存在 status=active 且带 SKU 的产品（公开详情页可见的前提，views.py:394-396）').toBeTruthy()
})

/**
 * 只读挑一个「public 详情页真的能打开」的产品：`status=active` **且** 有 SKU。
 * 依据 `views.py:394-396`：`/products/<pk>/detail/` 只放行 active + deprecated 且非软删，
 * **draft 一律 404**（所以 draft 产品不能拿来验「有 SKU」分支）。
 */
async function findActiveProductWithSkus() {
  const api = await apiContext(custToken)
  try {
    const body = await (await api.get('/skus/', { params: { page_size: 100 } })).json()
    const list = body?.data?.results || body?.data || body?.results || []
    const tried = new Set()
    for (const s of list) {
      const pid = s.product_id
      if (!pid || tried.has(pid)) continue
      tried.add(pid)
      if (tried.size > 40) break // 有界，避免慢查询拖垮 beforeAll
      const pb = await (await api.get(`/products/${pid}/`)).json()
      const p = pb?.data
      if (p && p.status === 'active' && (p.skus?.length || 0) > 0) return p
    }
    return null
  } finally {
    await api.dispose().catch(() => {})
  }
}

test.afterAll(async () => {
  // 1) 产品：按**本轮时间戳前缀**硬删（cleanupByPrefix 内部走 /products/?archived=1 + hard-delete）
  const api = await apiContext(adminToken)
  const prodClean = await cleanupByPrefix(api, { prefix: MARK, label: 'state-branches-commerce' })
  console.log('__E2E__ CLEANUP_PRODUCTS ' + JSON.stringify(prodClean))
  await api.dispose()

  // 2) 订单：先走产品自己的清理路径（cancel），再**按 id + 本轮标记硬删**
  //    为什么还要删：cancel 只把 status 改成 cancelled，**行仍留在库里**（dev 库已有 659 条
  //    历史 cancelled），达不到"零残留"。这里只删我自己造出来的行：
  //      · 按 id（创建时记录的）—— 精确，不含通配；
  //      · 按本轮唯一标记（po_number / shipping_name 以 `E2E-ST-<ts>` 开头）——
  //        兜住"用例中途失败、没走到 push(id)"的那几条。
  let cancelled = 0
  for (const id of createdOrderIds) {
    if (await h.cancelOrder(custToken, adminToken, id)) cancelled += 1
  }
  if (createdOrderIds.length) {
    const py =
      "import json\nfrom django.db import models\nfrom apps.transactions.models import Order\n" +
      `ids = ${JSON.stringify(createdOrderIds)}\nm = ${JSON.stringify(MARK)}\n` +
      "q1 = Order.objects.filter(id__in=ids)\nn1 = q1.count(); q1.delete()\n" +
      "q2 = Order.objects.filter(models.Q(po_number__startswith=m) | models.Q(shipping_name__startswith=m))\n" +
      "n2 = q2.count(); q2.delete()\n" +
      "print('__SNAP__' + json.dumps({'deletedById': n1, 'deletedByMarker': n2}))"
    console.log('__E2E__ CLEANUP_ORDERS ' + JSON.stringify({ created: createdOrderIds.length, cancelled, ...dbExec(py, 'cleanup-orders') }))
  }

  if (reqCtx) await reqCtx.dispose().catch(() => {})
})

/* ── 通用小工具 ──────────────────────────────────────────────────────── */

const go = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })

/**
 * 注入会话（不发起 UI 登录）。与 `helpers/auth.cjs:73-108` 的 loginViaSession 完全同法：
 * 前端判定登录态只读 localStorage 的 token / is_staff / role 三键（stores/auth.js:67-69；
 * router/index.js:295），DRF token 不过期 ⇒ 注入 ≡ 登录成功，且省掉 5 次/分钟限流的登录请求。
 */
async function asUser(page, username, password) {
  const session = await getSession(page.request, username, password)
  await page.addInitScript((s) => {
    try {
      localStorage.setItem('token', s.token)
      localStorage.setItem('is_staff', String(s.isStaff))
      localStorage.setItem('role', s.role || '')
    } catch {
      /* about:blank 无 localStorage ⇒ 忽略 */
    }
  }, session)
  await go(page, '/')
  await page.waitForFunction(() => !!(localStorage.getItem('token') || '').trim(), null, { timeout: 30000 })
  return session
}
const asStaff = (page) => asUser(page, ADMIN_USER, ADMIN_PASS)
const asCustomer = (page) => asUser(page, CUST_USER, CUST_PASS)

/** 产品编辑页选择器（ProductEditPage.vue，真实 DOM） */
const SEL = {
  name: `input[placeholder="e.g. 2'-Amino-ATP"]`, // :2014
  catalog: 'input[placeholder="e.g. SC8043"]', // :2018
  save: '.form-actions button', // :2431-2435
  identity: '.page-identity-status', // :1697
  stepper: '.lifecycle-stepper', // :1667（v-if="isEdit"）
  fieldError: '.field-error',
}
const saveBtn = (page) => page.locator(SEL.save, { hasText: 'Save Draft' })

/** 点 Save Draft 并等**对应写请求的真实响应**（POST=新建 / PUT=更新） */
async function saveDraft(page, method = 'POST') {
  const respP = page.waitForResponse(
    (r) => r.request().method() === method && r.url().includes('/api/v1/products/'),
    { timeout: 60000 },
  )
  await saveBtn(page).click()
  return respP
}

/** 选 Status 下拉（AppSelect → Element Plus el-select，:2034-2036） */
async function selectStatus(page, label) {
  const sel = page.locator('label', { hasText: 'Status' }).locator('.el-select').first()
  await sel.scrollIntoViewIfNeeded()
  await sel.click()
  const items = page.locator('.el-select-dropdown:visible .el-select-dropdown__item')
  await items.filter({ hasText: label }).first().click()
  await expect(page.locator('.el-select-dropdown:visible')).toHaveCount(0)
}

/** 工作台新建一个产品（UI 全流程）；返回 { id, catalog } */
async function createProductViaUi(page, { key, status } = {}) {
  const catalog = catOf(key)
  await go(page, PAGES.productNew.path)
  await expect(page.locator('form.edit-form')).toBeVisible({ timeout: 30000 })
  await page.locator(SEL.name).fill(`${MARK} ${key}`)
  await page.locator(SEL.catalog).first().fill(catalog)
  if (status) await selectStatus(page, status)
  const resp = await saveDraft(page, 'POST')
  expect(resp.status(), `新建产品 ${catalog} 应 201`).toBeLessThan(300)
  const body = await resp.json()
  const id = body?.data?.id
  expect(id, '新建响应应含 data.id').toBeTruthy()
  // 首存后页面 router.replace 到 /workspace/products/<id>/edit 并重载（:1619-1623）
  await expect(page).toHaveURL(new RegExp(`/workspace/products/${id}/edit`), { timeout: 15000 })
  return { id, catalog }
}

/* ══════════════════════════════════════════════════════════════════════
 * 1) /products —— 空态 / 有数据 / 分页边界
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@products 产品列表页的状态分支', { tag: ['@local-only'] }, () => {
  test('搜索无结果 ⇒ 空态「No products found」；清空搜索 ⇒ 回到有数据网格（反向）', { tag: ['@readonly'] }, async ({ page }) => {
    await asStaff(page)
    await go(page, PAGES.productIndex.path)

    // 有数据：商品网格渲染（ProductIndex.vue:131-138 → ProductCard 根节点 .product-card，ProductCard.vue:56-57）
    await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 30000 })

    // 空态：ProductIndex.vue:123-127（EmptyState title="No products found"）
    const search = page.locator('input.product-search-input') // ProductLayout.vue:210-214
    await search.fill(`E2E-NOPE-${RUN_TS}`)
    await search.press('Enter')
    const empty = page.locator('.empty-state') // EmptyState.vue:19
    await expect(empty.locator('.empty-title')).toHaveText('No products found')
    await expect(empty.locator('.empty-description')).toContainText('Try adjusting')
    await expect(page.locator('.product-card')).toHaveCount(0)

    // 反向：清空搜索再回车 ⇒ 网格回来、空态消失（:130 的 v-else 分支）
    await search.fill('')
    await search.press('Enter')
    await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.empty-state')).toHaveCount(0)
  })

  test('分页边界：首页 Prev 禁用 ⇒ 点第 2 页 ⇒ 第 2 页高亮、Prev 可用', { tag: ['@readonly'] }, async ({ page }) => {
    await asStaff(page)
    await go(page, PAGES.productIndex.path)
    await expect(page.locator('.product-card').first()).toBeVisible({ timeout: 30000 })

    // 分页条仅在 totalPages > 1 时渲染（ProductIndex.vue:141）。dev 库在售产品 > 20 条，
    // 故此处断言的是「分页分支存在」，不是某个绝对条数。
    const prev = page.locator('.page-btn', { hasText: '← Prev' }) // :142
    const next = page.locator('.page-btn', { hasText: 'Next →' }) // :160
    await expect(next).toBeVisible()
    await expect(prev, '首页 Prev 应 disabled（:142 :disabled="currentPage <= 1"）').toBeDisabled()

    await page.locator('.page-btn-num', { hasText: /^2$/ }).first().click() // :148-154
    await expect(page.locator('.page-btn--active')).toHaveText('2') // :152
    await expect(prev, '翻页后 Prev 应可用').toBeEnabled()
    await expect(page.locator('.product-card').first()).toBeVisible()

    // 末页边界：连续点 Next 到禁用（**有界循环**，不断言总页数 —— 共享库数据量会变）
    const activeNum = page.locator('.page-btn--active')
    for (let i = 0; i < 50; i++) {
      if (await next.isDisabled()) break
      const before = (await activeNum.innerText()).trim()
      await next.click()
      // 以「当前页号变化」作为翻页落定信号（auto-retry，不裸 waitForTimeout）
      await expect(activeNum, '点 Next 后当前页号应前进').not.toHaveText(before)
      await expect(page.locator('.product-card').first()).toBeVisible()
    }
    await expect(next, '末页 Next 应 disabled（:160 :disabled="currentPage >= totalPages"）').toBeDisabled()
    await expect(prev, '末页 Prev 应可用').toBeEnabled()
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 2) /products/:id —— 有SKU·无SKU / draft·deprecated / 回收站兜底
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@product-detail 产品详情页的状态分支', { tag: ['@local-only'] }, () => {
  test('有 SKU（active）⇒ 渲染「Available SKUs」；无 SKU 的 active 产品 ⇒ 该区块不存在（反向）；draft 产品 ⇒ 公开放行被拒（404 兜底）', { tag: ['@write'] }, async ({ page }) => {
    await asStaff(page)

    // ① 共享库真实 active 产品（带 SKU，只读取 id）⇒ SKU 表存在
    //    ProductDetail.vue:673 `<section class="pd-section" v-if="product.skus?.length">`
    await go(page, `${PAGES.productDetail.base}/${liveProd.id}`)
    await expect(page.locator('.pd-section-title', { hasText: 'Available SKUs' })).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.pd-sku-row').first()).toBeVisible()
    await expect(page.locator('.pd-meta-row .pd-badge').first()).toHaveText('active') // :557

    // ② UI 新建一个**没有任何 SKU 的 active 产品** ⇒ 同一区块不渲染（反向断言）
    const p = await createProductViaUi(page, { key: 'NOSKU', status: 'Active' })
    await go(page, `${PAGES.productDetail.base}/${p.id}`)
    await expect(page.locator('.pd-name')).toHaveText(`${MARK} NOSKU`, { timeout: 30000 })
    await expect(page.locator('.pd-section-title', { hasText: 'Available SKUs' })).toHaveCount(0)
    await expect(page.locator('.pd-sku-row')).toHaveCount(0)
    await expect(page.locator('.pd-meta-row .pd-badge').first()).toHaveText('active')

    // ③ 状态可见性差异：**draft 产品公开详情 404**
    //    依据 views.py:394-396 —— `/products/<pk>/detail/` 只放行 status in ('active','deprecated')
    //    且 archived=False；draft 即使 staff 也 404 ⇒ 前端走 unavailable 兜底（ProductDetail.vue:42/:958-962）
    const d = await createProductViaUi(page, { key: 'DRAFT' }) // 默认状态即 draft
    await go(page, `${PAGES.productDetail.base}/${d.id}`)
    await expect(page.locator('.pd-empty .pd-error-title')).toHaveText('Product not found or unavailable', { timeout: 30000 })
    await expect(page.locator('.pd-name')).toHaveCount(0) // 反向：draft 内容不外泄
  })

  test('deprecated（退出目录）⇒ 停产横幅出现；非 deprecated 产品 ⇒ 无横幅（反向）', { tag: ['@write'] }, async ({ page }) => {
    await asStaff(page)

    // UI 新建时直接把 Status 选成 Deprecated（状态下拉在新建页即存在，ProductEditPage.vue:2034）
    const p = await createProductViaUi(page, { key: 'DEPR', status: 'Deprecated' })

    await go(page, `${PAGES.productDetail.base}/${p.id}`)
    // ProductDetail.vue:487-490 `v-if="isDiscontinued"`（status === 'deprecated'，:46）
    const banner = page.locator('.pd-discontinued')
    await expect(banner).toBeVisible({ timeout: 30000 })
    await expect(banner).toContainText('discontinued and is no longer available for purchase')
    await expect(banner).toHaveAttribute('role', 'status')
    // 页面本身保留（真实网站语义：停产 ≠ 404，货号不释放）
    await expect(page.locator('.pd-name')).toHaveText(`${MARK} DEPR`)
    await expect(page.locator('.pd-meta-row .pd-badge').first()).toHaveText('deprecated')

    // 反向：同一个 active 产品不显示横幅
    await go(page, `${PAGES.productDetail.base}/${liveProd.id}`)
    await expect(page.locator('.pd-name')).toBeVisible({ timeout: 30000 })
    await expect(page.locator('.pd-discontinued')).toHaveCount(0)
  })

  test('回收站（软删 archived）产品 ⇒ 兜底错误态「Product not found or unavailable」，不渲染内容', { tag: ['@write'] }, async ({ page }) => {
    await asStaff(page)
    const p = await createProductViaUi(page, { key: 'RECYCLE' })

    // 从工作台列表把这条**唯一标记**的产品移入回收站（UI：行操作菜单 → 确认框）
    // ProductsPage.vue:740 菜单项 / :900-916 确认框
    await go(page, '/workspace/products')
    const row = page.locator('.products-table tbody tr', { hasText: p.catalog })
    await expect(row).toHaveCount(1, { timeout: 30000 })
    await row.locator('.menu-trigger').click()
    await row.locator('.menu-item', { hasText: 'Move to Recycle Bin' }).click()
    const dlg = page.locator('.dialog-overlay .dialog')
    await expect(dlg).toBeVisible()
    await dlg.locator('.confirm-check input').check()
    await dlg.locator('button', { hasText: 'Move to recycle bin' }).click()
    await expect(row, '移入回收站后应从在售列表消失（:654 默认视图排除 archived）').toHaveCount(0, { timeout: 30000 })

    // 详情页兜底：staff 仍能 200 取到 archived 行（views.py:76-79），前端据此走 unavailable 分支
    // ProductDetail.vue:42 `unavailable = store.productError || product.archived === true`；:958-962 错误态
    await go(page, `${PAGES.productDetail.base}/${p.id}`)
    const errTitle = page.locator('.pd-empty .pd-error-title')
    await expect(errTitle).toHaveText('Product not found or unavailable', { timeout: 30000 })
    await expect(page.locator('.pd-empty .pd-error-sub')).toContainText('removed, archived')
    // 反向：软删产品的内容不得渲染
    await expect(page.locator('.pd-name')).toHaveCount(0)
    await expect(page.locator('.pd-meta-row')).toHaveCount(0)
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 3) /workspace/products/new 与 /workspace/products/:id/edit
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@product-edit 工作台产品编辑页的状态分支', { tag: ['@local-only'] }, () => {
  test('新建页：无生命周期步进器（反向）⇒ 首存后进入 edit 态并出现步进器；必填缺失标红含 Default SKU、不含已填的 Name/Catalog', { tag: ['@write'] }, async ({ page }) => {
    await asStaff(page)
    await go(page, PAGES.productNew.path)
    await expect(page.locator('form.edit-form')).toBeVisible({ timeout: 30000 })

    // 反向：步进器 `v-if="isEdit"`（ProductEditPage.vue:1667）⇒ 新建态不渲染
    await expect(page.locator(SEL.stepper)).toHaveCount(0)

    const catalog = catOf('NEW')
    await page.locator(SEL.name).fill(`${MARK} NEW`)
    await page.locator(SEL.catalog).first().fill(catalog)
    const resp = await saveDraft(page, 'POST')
    expect(resp.status(), `新建 ${catalog} 应 2xx`).toBeLessThan(300)
    const id = (await resp.json())?.data?.id
    expect(id).toBeTruthy()

    // 首存后：same page 进 edit 态（:1619-1623 router.replace + loadProduct）
    await expect(page.locator(SEL.stepper)).toBeVisible({ timeout: 20000 })
    // 身份行状态徽章：`{{ form.status || 'draft' }}`（:1697）
    await expect(page.locator(SEL.identity)).toHaveText('draft')
    await expect(page.locator(SEL.identity)).toHaveClass(/status-draft/)

    // 必填缺失标红的作用域：collectMissing（:48-57 / 保存时写 missingFields :1540）
    //  · Name/Catalog 已填 ⇒ **不**标红（:2020/:2024 的 v-if 为假）
    //  · 仍缺的 CAS/SMILES/Category/SKU 各自标红；其中只有 SMILES 复用同一文案
    //    「⚠ Required field unfilled」（:2047），CAS 无此标记（只有格式校验 :2022），
    //    Category 与 Default SKU 各用专属文案（:2109 / :2287）。
    await expect(page.locator(SEL.fieldError, { hasText: 'Add at least one SKU' })).toHaveCount(1)
    const reqUnfilled = page.locator(SEL.fieldError, { hasText: 'Required field unfilled' })
    await expect(reqUnfilled, '只剩 SMILES 一项复用该文案').toHaveCount(1)
    expect(
      await reqUnfilled.evaluate((el) => (el.closest('label')?.textContent || '').trim()),
      '剩下的「Required field unfilled」必须属于 SMILES，而非 Name/Catalog',
    ).toContain('SMILES')
    await expect(page.locator('label', { hasText: 'Name *' }).locator(SEL.fieldError)).toHaveCount(0)
    await expect(page.locator('label', { hasText: 'Catalog No *' }).locator(SEL.fieldError)).toHaveCount(0)
    await expect(page.locator(SEL.fieldError, { hasText: '请选择 Category' })).toHaveCount(1)
  })

  test('编辑页：draft ⇒ 步进器 Draft=当前、Published=待办；改为 Active 保存 ⇒ 两步全完成；再改回 Draft ⇒ 复原（双向迁移）', { tag: ['@write'] }, async ({ page }) => {
    await asStaff(page)
    const p = await createProductViaUi(page, { key: 'STEP' })

    // ── 态 A：draft ──
    // 步进器两段：Draft / Published（ProductEditPage.vue:1667-1675）
    await expect(page.locator(SEL.stepper)).toBeVisible({ timeout: 20000 })
    const steps = page.locator(`${SEL.stepper} .step`)
    await expect(steps.nth(0)).toHaveText('Draft')
    await expect(steps.nth(1)).toHaveText('Published')
    await expect(steps.nth(0), 'draft 态：Draft 应为当前步（:1674 step-current）').toHaveClass(/step-current/)
    await expect(steps.nth(1), 'draft 态：Published 应为待办（:1676 step-todo）').toHaveClass(/step-todo/)
    await expect(page.locator(SEL.identity)).toHaveText('draft')

    // ── 迁移 draft → active（UI：状态下拉 + Save Draft）──
    await selectStatus(page, 'Active')
    const put1 = await saveDraft(page, 'PUT')
    expect(put1.status(), '切 Active 的 PUT 应 2xx').toBeLessThan(300)

    // ── 态 B：active（同页断言，反向：无 step-current / step-todo）──
    const stepsB = page.locator(`${SEL.stepper} .step`)
    await expect(stepsB.nth(0), 'active 态：Draft 应 step-done（:1674）').toHaveClass(/step-done/)
    await expect(stepsB.nth(1), 'active 态：Published 应 step-done（:1676）').toHaveClass(/step-done/)
    await expect(stepsB.nth(1)).not.toHaveClass(/step-todo/)
    await expect(page.locator(SEL.identity)).toHaveText('active')
    await expect(page.locator(SEL.identity)).toHaveClass(/status-active/)

    // ── 迁移回 active → draft（双向，确认不是单向写死）──
    await selectStatus(page, 'Draft')
    const put2 = await saveDraft(page, 'PUT')
    expect(put2.status(), '切回 Draft 的 PUT 应 2xx').toBeLessThan(300)
    const stepsC = page.locator(`${SEL.stepper} .step`)
    await expect(stepsC.nth(0)).toHaveClass(/step-current/)
    await expect(stepsC.nth(1)).toHaveClass(/step-todo/)
    await expect(page.locator(SEL.identity)).toHaveText('draft')
    // 落到编辑页 URL（productEdit 这条路由的实体页；:270-272）
    await expect(page).toHaveURL(new RegExp(`/workspace/products/${p.id}/edit`))
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 4) /orders —— 空态 / 有数据（状态徽章）
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@orders 客户订单列表页的状态分支', { tag: ['@local-only'] }, () => {
  test('0 条 ⇒ 空态「No orders yet」+ Browse Products 出口（响应拦截构造空态，不写库）', { tag: ['@readonly'] }, async ({ page }) => {
    await asCustomer(page)
    // ★ 该页无任何筛选（OrderListPage.vue 全文），共享库中 e2e_customer 有 900+ 单
    //   ⇒ 无法在共享库上确定性地得到「0 条」。这里用**响应拦截**构造 200 + 空列表
    //   （不写库、不改组件状态，只喂一次响应），仅用于走 `v-else-if="store.orders.length === 0"`
    //   的空态分支（OrderListPage.vue:45-54）。
    await page.route(
      (url) => /\/api\/v1\/orders\/?(\?.*)?$/.test(url.href),
      (route) =>
        route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify({ success: true, data: [], meta: { pagination: { page: 1, pageSize: 20, count: 0 } } }),
        }),
    )
    await go(page, PAGES.orders.path)
    await expect(page.locator('.empty-state .empty-title')).toHaveText('No orders yet', { timeout: 30000 })
    await expect(page.locator('.empty-state .empty-description')).toContainText('no orders yet')
    await expect(page.locator('.empty-state').getByRole('link', { name: 'Browse Products' })).toBeVisible()
    await expect(page.locator('.order-table')).toHaveCount(0)
  })

  test('有数据 ⇒ 我造的那一单出现在列表，且状态徽章 = Quoted（状态文案来自 getStatusLabel）', { tag: ['@write'] }, async ({ page }) => {
    // ── 夹具前置（非被测路径）：customer checkout(payment_method=quote) → admin 报价 ──
    //    quote_pending 由 legacy checkout 产生（poHelpers.cjs:183-208），随后
    //    POST /admin/orders/{id}/quote/ 把它推进到 quoted（admin_order_views.py:146-156）。
    const po = await seedQuoteOrder('Q-LIST')
    expect(po?.id, 'quote 夹具应返回订单 id').toBeTruthy()
    createdOrderIds.push(po.id)
    await quoteOrder(po.id)
    const detail = await h.getOrder(adminToken, po.id)
    expect(detail.status, '夹具应处于 quoted').toBe('quoted')

    await asCustomer(page)
    await go(page, PAGES.orders.path)

    // OrderListPage.vue:70-80 —— 行 + `.status-badge`，文案 = getStatusLabel(status)（:28-30）
    const row = page.locator('.order-table tbody tr', { hasText: detail.order_no })
    await expect(row).toHaveCount(1, { timeout: 30000 })
    await expect(row.locator('.status-badge')).toHaveText('Quoted')
    await expect(row.locator('.order-no')).toHaveText(detail.order_no)
    // 反向：同一行不显示别的状态文案（防止徽章取值写错）
    await expect(row.locator('.status-badge')).not.toHaveText('Quote Pending')

    // 清场：quoted 粘性、不可取消 ⇒ 用例内先落到 confirmed，afterAll 再取消
    expect(await acceptQuoteViaApi(po.id)).toBeTruthy()
  })
})

/* ══════════════════════════════════════════════════════════════════════
 * 5) /orders/:id —— quoted 才有报价动作条（含真实迁移）
 * ══════════════════════════════════════════════════════════════════════ */
test.describe('@order-detail 客户订单详情页的状态分支', { tag: ['@local-only'] }, () => {
  test('quoted ⇒ 报价动作条可见（Accept/Reject）；点 Accept 后 status=Confirmed 且动作条消失（反向）', { tag: ['@write'] }, async ({ page }) => {
    const po = await seedQuoteOrder('Q-DETAIL')
    createdOrderIds.push(po.id)
    await quoteOrder(po.id)
    const quoted = await h.getOrder(adminToken, po.id)

    await asCustomer(page)
    await go(page, `${PAGES.orderDetail.base}/${po.id}`)

    // 态 A：quoted —— OrderDetailPage.vue:52 `v-if="order.status === 'quoted'"`
    await expect(page.locator('.status-badge')).toHaveText('Quoted', { timeout: 30000 })
    const bar = page.locator('.action-bar') // :52-58
    await expect(bar).toBeVisible()
    await expect(bar).toContainText('A quote has been provided')
    await expect(bar.getByRole('button', { name: 'Accept Quote' })).toBeVisible()
    await expect(bar.getByRole('button', { name: 'Reject Quote' })).toBeVisible()

    // 态 A → B：UI 点 Accept Quote（POST /orders/{id}/confirm-quote/，OrderDetailPage.vue:28-31）
    //   后端：quoted → quote_accepted → confirmed（po_views.py:172-178）
    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && r.url().includes('/confirm-quote/'),
        { timeout: 30000 },
      ),
      bar.getByRole('button', { name: 'Accept Quote' }).click(),
    ])
    expect(resp.status(), 'confirm-quote 应 2xx').toBeLessThan(300)

    // 态 B：confirmed —— 动作条**必须消失**（同一页反向断言），徽章改为 Confirmed
    await expect(page.locator('.status-badge')).toHaveText('Confirmed', { timeout: 20000 })
    await expect(page.locator('.action-bar')).toHaveCount(0)
    expect(quoted.grand_total).toBeTruthy()
  })

  test('非 quoted（po_received）⇒ 无报价动作条（反向）；且有发票的订单才渲染 Invoice 区块', { tag: ['@write'] }, async ({ page }) => {
    // 夹具 A：po_received（无动作条、无发票）
    const prod = liveProd
    const poReceived = await h.submitPoApi(custToken, {
      poNumber: `${MARK}-OR`,
      productId: prod.id,
      skuId: prod.skus[0].id,
      qty: 1,
      price: '10.00',
    })
    expect(poReceived?.id).toBeTruthy()
    createdOrderIds.push(poReceived.id)

    // 夹具 B：delivered + 已开票（走 approve → shipment → shipped → delivered → invoice）
    const poInvoiced = await h.seedInvoiced(custToken, adminToken)
    expect(poInvoiced?.id).toBeTruthy()
    createdOrderIds.push(poInvoiced.id)

    await asCustomer(page)

    // ① 非 quoted 订单：OrderDetailPage.vue:52 的 v-if 为假 ⇒ 动作条不存在
    await go(page, `${PAGES.orderDetail.base}/${poReceived.id}`)
    await expect(page.locator('.status-badge')).toHaveText('Po Received', { timeout: 30000 })
    await expect(page.locator('.action-bar')).toHaveCount(0)

    // ② 有发票的订单：Invoice 区块（OrderDetailPage.vue:124-144）
    const inv = await h.getOrder(adminToken, poInvoiced.id)
    expect(inv.invoice, '夹具应已开票').toBeTruthy()
    await go(page, `${PAGES.orderDetail.base}/${poInvoiced.id}`)
    const invoiceSection = page.locator('.detail-section', { has: page.locator('h2', { hasText: 'Invoice' }) })
    await expect(invoiceSection).toBeVisible({ timeout: 30000 })
    await expect(invoiceSection.locator('.info-value.mono').first()).toHaveText(inv.invoice.invoice_no)

    // ③ 反向：无发票的 po_received 订单不渲染 Invoice 区块
    await go(page, `${PAGES.orderDetail.base}/${poReceived.id}`)
    await expect(page.locator('.status-badge')).toHaveText('Po Received', { timeout: 30000 })
    await expect(page.locator('.detail-section', { has: page.locator('h2', { hasText: 'Invoice' }) })).toHaveCount(0)
  })
})

/* ── API 小工具（夹具专用，不属于被测路径） ───────────────────────────── */

/**
 * 夹具：造一张 quote_pending 订单（legacy checkout，payment_method=quote）。
 *
 * 与 `helpers/poHelpers.cjs:183-208` 的 seedQuotePending 同一套调用，但**收货人写成本轮唯一标记**
 * `${MARK}-<key>` —— 这样即使某个用例中途失败丢了 id 记录，afterAll 也能按标记回收，
 * 不给共享库留"看不出是谁造的"报价单（该态**不可取消**：quoted→cancelled 状态机不允许）。
 */
async function seedQuoteOrder(key) {
  const api = await apiContext(custToken)
  try {
    await api.post('/basket/items', {
      headers: { 'Content-Type': 'application/json' },
      data: { product_id: liveProd.id, sku_id: liveProd.skus[0].id, quantity: 1 },
    })
    const res = await api.post('/checkout/', {
      headers: { 'Content-Type': 'application/json' },
      data: {
        payment_method: 'quote',
        shipping_name: `${MARK}-${key}`, // ← 唯一标记（清理键）
        shipping_address: '1 E2E Way, Test City',
        shipping_email: 'e2e@lab.edu',
      },
    })
    const body = await res.json().catch(() => ({}))
    expect(res.status(), `quote 夹具 ${key} 的 checkout 应 2xx`).toBeLessThan(300)
    return body?.data || body || {}
  } finally {
    await api.dispose().catch(() => {})
  }
}

/** admin 录入报价：quoted（admin_order_views.py:132-158） */
async function quoteOrder(id) {
  const api = await apiContext(adminToken)
  try {
    const r = await api.post(`/admin/orders/${id}/quote/`, {
      headers: { 'Content-Type': 'application/json' },
      data: { grand_total: '99.00' },
    })
    expect(r.status(), `admin 报价应 2xx（order ${id}）`).toBeLessThan(300)
  } finally {
    await api.dispose().catch(() => {})
  }
}

/** customer 接受报价（quoted → confirmed），用于把粘性态带出 quoted 以便清理 */
async function acceptQuoteViaApi(id) {
  const api = await apiContext(custToken)
  try {
    const r = await api.post(`/orders/${id}/confirm-quote/`, {
      headers: { 'Content-Type': 'application/json' },
      data: { action: 'accept' },
    })
    return r.ok()
  } finally {
    await api.dispose().catch(() => {})
  }
}

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（本文件在走状态分支时发现的**真缺陷** / 记录项） —— 均带 文件:行号 + 实测证据
 *
 * #1【缺陷·高价值】`/orders` 客户订单历史不可达，且 store 的 total 被算成 20（真值 976）
 *    · 前端：`OrderListPage.vue` 全文**没有分页、没有筛选、没有「加载更多」**；
 *      `stores/orders.js:14-22` 的 `fetchOrders()` 从不传 page/page_size。
 *    · 后端：`config/settings/base.py:174` `PAGE_SIZE=20`。
 *    · 实测响应形状（e2e_customer）：`data` 是**纯数组 20 条**，
 *      `meta.pagination = {count: 976, next: 'http://localhost:8000/api/v1/orders/?page=2'}`。
 *    · 于是 `stores/orders.js:19-20`：
 *        `orders.value = data.results || data.data || data` ⇒ 命中第三分支（数组 20 条）
 *        `total.value  = data.count || data.meta?.pagination?.count || orders.value.length`
 *                      ⇒ 数组没有 `.count`、也没有 `.meta` ⇒ **落到 length = 20**（真值 976）
 *    · 后果：客户只能看到**最近 20 单**，第 21 单及以前**永久无法到达**；页面也没有任何提示。
 *    （本文件的 `/orders` 用例只断言"我造的那一单"在首页可见，不受该缺陷影响。）
 *
 * #2【记录·设计取舍】草稿（draft）产品即使 staff 也拿不到公开详情（404）
 *    · `apps/commerce/api/v1/views.py:394-396`：`/products/<pk>/detail/` 只放行
 *      `status in ('active','deprecated')` 且 `archived=False`，注释明写「draft 仍不放行」。
 *    · 后果：工作台没有"预览草稿详情页"的出口（只能在编辑页看）。
 *      本文件把这条**规则本身**断言下来了（draft ⇒ unavailable 兜底 + 内容不外泄）。
 *
 * #3【记录】三种"打不开"共用同一句文案，无法区分原因
 *    · `ProductDetail.vue:42` 把 `store.productError`(404/网络/草稿) 与 `product.archived===true`
 *      （回收站）合并成 `unavailable`，`:958-962` 统一显示
 *      "Product not found or unavailable / removed, archived, or is no longer available"。
 *    · ⇒ 用户/运营无法从页面区分「不存在」「草稿未发布」「在回收站」。
 *      本文件分别用 draft 与 archived 两种**真实**数据触发同一分支，正是为了证明这一点。
 * ──────────────────────────────────────────────────────────────────────── */
