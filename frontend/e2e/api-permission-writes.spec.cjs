/**
 * ★ API 层鉴权写用例（2026-09-24，⑦）—— 真实 HTTP，不经 DRF test client。
 *
 * ## 为什么需要这个 spec
 * `permission-matrix.spec.cjs`（83 例）只覆盖**前端路由守卫**（导航级），对写端点的
 * **API 鉴权 0 覆盖**。而本项目**未设** `REST_FRAMEWORK['DEFAULT_PERMISSION_CLASSES']`
 * ⇒ 任何 ViewSet 只要忘写 `permission_classes`，就**静默变成匿名可读写**，
 * 且当时**没有任何用例会抓到**（这正是 2026-09-24 查出 9 个真·隐式的原因）。
 *
 * 该缺陷已在 `dd252be`（commerce 5）+ `cf5c988`（transactions 4）修复，后端单测见
 * `backend/apps/commerce/tests/test_masterdata_permissions.py` 与
 * `backend/apps/transactions/tests/test_api_permission_hardening.py`。
 * **本 spec 是同一批修复的 HTTP 层闸门**：单测走 DRF test client（不过真实 URL 路由 /
 * 中间件链 / 认证类），本 spec 走**真实 HTTP**，两层互补。
 *
 * ## 判据（关键：不许用"只要不是 2xx 就算拦住了"）
 * 只有 **401 / 403** 才算"鉴权把它拦下了"。
 * **404（URL/对象不存在）、405（方法不允许）、415（解析器先报错）、400（校验不过）
 * 全都意味着「鉴权已被放行」** —— 2026-09-24 改前实测正是这些码（见下表），
 * 其中 `POST /quotes/` 更直接 **201**（匿名建了库）。
 * 故本 spec 一律**精确断言 401/403**，并另设 **staff 正对照**（同样的写请求必须
 * **不**返回 401/403）—— 否则若端点写错，全组会以 404 "假绿"。
 *
 * ## 零写入保证
 * 写探针一律使用 **哨兵 id `999999999`** 的 `DELETE`：该对象必然不存在，
 * 因此**即使在鉴权被放行的情况下，最差也只得到 404/405**，不可能删掉或创建任何数据。
 * `POST` 探针只用于**匿名组**（此时必然 401，请求根本到不了业务层）。
 * ⇒ 本 spec 全程零写入，故 tier 标 `@readonly` + `@local-only`。
 *
 * ## 2026-09-24 改前 / 改后实测对照（dev，`http://127.0.0.1:8000`）
 * | 写探针 | 改前（无权限声明） | 改后 |
 * |---|---|---|
 * | `POST /skus/` | 400（进了校验） | **401** |
 * | `POST /product-classes/` | 405 | **401** |
 * | `POST /catalog-groups/` | 405 | **401** |
 * | `POST /documents/` | 415（解析器先报错） | **401** |
 * | `POST /orders/` | 400 | **401** |
 * | `POST /quotes/` | **201（匿名写入成功）** | **401** |
 * | `POST /wishlist/` | **500**（`user` NOT NULL 而序列化器无 user） | **401** |
 * | `POST /products/999999999/detail/` | 405 | **401** |
 * | 匿名 `GET`（7 个列表端点） | 200 | **200（不变）** |
 */
const { test, expect } = require('@playwright/test')
const { apiContext, getToken } = require('./helpers/api.cjs')
const { ADMIN_USER, ADMIN_PASS, CUST_USER, CUST_PASS } = require('./helpers/auth.cjs')

/** 哨兵 id：必然不存在 ⇒ 写探针在任何权限状态下都不会创建/修改数据。 */
const SENTINEL = 999999999
/** "鉴权拦下"的唯一两个合法码。 */
const DENY = [401, 403]

/** 需 **staff** 才能写（`IsAdminOrReadOnly`）。 */
const ADMIN_ONLY = [
  { name: 'SKUViewSet', path: '/skus', list: '/skus/' },
  { name: 'ProductClassViewSet', path: '/product-classes', list: '/product-classes/' },
  { name: 'CatalogGroupViewSet', path: '/catalog-groups', list: '/catalog-groups/' },
  { name: 'ProductDocumentViewSet', path: '/documents', list: '/documents/' },
  // ⚠️ 本端点是 `<pk>/detail/` 形态，路径**自带 id** ⇒ 探针 URL 必须单独给，
  //    不能再机械地拼 `${path}/${SENTINEL}/`（那会得到 `/detail/999999999/` ⇒ 对所有人 404，
  //    表现为"匿名 404 而非 401"的**假失败** —— 2026-09-24 第一版就踩了，
  //    正是靠 staff 正对照（期望非 401/403）把 URL 写错的痕迹暴露出来才定位到）。
  {
    name: 'ProductDetailAPIView',
    path: `/products/${SENTINEL}/detail`,
    probe: `/products/${SENTINEL}/detail/`,
    postPath: `/products/${SENTINEL}/detail/`,
    list: null,
  },
]
/** 仅要求**登录**即可写（与真实下单路径 CheckoutView / POSubmitView 的 IsAuthenticated 一致）。 */
const AUTH_ONLY = [
  { name: 'OrderViewSet', path: '/orders', list: '/orders/' },
  { name: 'QuoteViewSet', path: '/quotes', list: '/quotes/' },
  { name: 'WishlistViewSet', path: '/wishlist', list: '/wishlist/' },
]
/** 补齐默认探针 URL：集合型端点 = `<path>/<SENTINEL>/`；detail 型已在上面显式给出。 */
for (const e of [...ADMIN_ONLY, ...AUTH_ONLY]) {
  if (!e.probe) e.probe = e.path + '/' + SENTINEL + '/'
  if (!e.postPath) e.postPath = e.path + '/'
  // 自检：探针 URL 绝不能含 undefined/NaN —— 否则请求会打到假 URL 得到 404，
  // 而 `not.toContain([401,403])` 这类断言**会被 404 蒙混过关**（2026-09-24 真踩过）。
  if (!e.probe || !e.postPath || /undefined|NaN/.test(e.probe + e.postPath)) {
    throw new Error('端点 ' + e.name + ' 的探针 URL 未正确补齐：' + e.probe + ' / ' + e.postPath)
  }
}
const ALL = [...ADMIN_ONLY, ...AUTH_ONLY]
const LISTED = ALL.filter((e) => e.list)

// ─────────────────────────── 匿名：写必须 401 ───────────────────────────
test.describe('匿名（无 token）· 写必须被鉴权拦下', { tag: ['@readonly', '@local-only'] }, () => {
  let api
  test.beforeEach(async () => { api = await apiContext(null) })
  test.afterEach(async () => { await api.dispose() })

  for (const e of ALL) {
    test(`DELETE ${e.probe} → 401（${e.name}）`, async () => {
      const r = await api.delete(`${e.probe}`)
      expect(
        DENY,
        `${e.name} 匿名 DELETE 必须 401/403；拿到 404/405/415 说明**鉴权被放行**了`,
      ).toContain(r.status())
    })
  }

  for (const e of ALL) {
    test(`POST ${e.postPath} → 401（${e.name}）`, async () => {
      const r = await api.post(`${e.postPath}`, { data: {} })
      expect(
        DENY,
        `${e.name} 匿名 POST 必须 401/403；拿到 400/405/415/201 说明**鉴权被放行**了`,
      ).toContain(r.status())
    })
  }
})

// ─────────────── staff 正对照：写必须过鉴权（否则本 spec 假绿） ───────────────
test.describe('staff（is_staff）· 正对照：写必须过鉴权层', { tag: ['@readonly', '@local-only'] }, () => {
  let api
  test.beforeEach(async ({ request }) => {
    api = await apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))
  })
  test.afterEach(async () => { await api.dispose() })

  // ★ 断言用**精确集合 {404,405}**，不是 `not.toContain([401,403])`。
  //   理由（2026-09-24 实测踩到）：哨兵 URL 若被拼错（第一版拼成 `/undefined/`），
  //   请求会打到不存在的路径得到 **404** —— 而 `not.toContain([401,403])` **会放它过关**，
  //   正对照就此变成"什么都拦不住"的空壳。钉死 {404,405} 才能同时验到"鉴权放行"与"URL 正确"。
  //   实测：SKU / ProductDocument / Order / Quote / Wishlist / ProductDetail 的 DELETE 哨兵 = 404，
  //        只读类 ProductClass / CatalogGroup = 405（DRF 先过权限再查方法）。
  for (const e of ALL) {
    test(`DELETE ${e.probe} → 404/405（staff 正对照，${e.name}）`, async () => {
      const r = await api.delete(`${e.probe}`)
      console.log(`__E2E__ ${e.name} staff DELETE 哨兵 → ${r.status()}`)
      expect(
        [404, 405],
        `${e.name} staff 应越过鉴权后得到 404/405。401/403 ⇒ 收紧过头或 token 失效；` +
        `其他值 ⇒ 探针 URL 或端点行为与预期不符`,
      ).toContain(r.status())
    })
  }
})

// ─────────────────────── 非 staff 已登录（customer） ───────────────────────
test.describe('customer（已登录非 staff）', { tag: ['@readonly', '@local-only'] }, () => {
  let api
  test.beforeEach(async ({ request }) => {
    api = await apiContext(await getToken(request, CUST_USER, CUST_PASS))
  })
  test.afterEach(async () => { await api.dispose() })

  for (const e of ADMIN_ONLY) {
    test(`DELETE ${e.probe} → 403（${e.name}）`, async () => {
      const r = await api.delete(`${e.probe}`)
      expect(
        r.status(),
        `${e.name} 是主数据端点（IsAdminOrReadOnly）⇒ 非 staff 虽已登录也必须 403；` +
        `拿到 404/405 说明**权限声明被移除**了`,
      ).toBe(403)
    })
  }

  // ★ 口径差异**必须显式写在用例里**，不能靠"没测"来掩盖：
  //   transactions 三端点的写面口径是 IsAuthenticated（不是 IsAdminOrReadOnly）
  //   ⇒ customer 在**鉴权层是被放行的**（哨兵 id ⇒ 得 404，不产生任何写入）。
  //   这是**有意设计**（匿名加购/询价/报价的电商流），与 commerce 主数据不同。
  // ★ 断言同样钉 **404**（而不是 `not.toContain([401,403])`）—— 理由同 staff 组：
  //   松断言会被"URL 拼错 ⇒ 404"蒙混过关，那样这两条用例就完全没在验证东西。
  //   实测：customer 对 orders / quotes / wishlist 的 DELETE 哨兵均为 **404**（鉴权放行、对象不存在）。
  for (const e of AUTH_ONLY) {
    test(`DELETE ${e.probe} → 404（customer 放行，按设计，${e.name}）`, async () => {
      const r = await api.delete(`${e.probe}`)
      console.log(`__E2E__ ${e.name} customer DELETE 哨兵 → ${r.status()}`)
      expect(
        r.status(),
        `${e.name} 的写口径是 IsAuthenticated ⇒ customer 应过鉴权并得到 404；` +
        `401/403 ⇒ 口径被改成仅 staff；其他值 ⇒ 探针 URL 或端点行为与预期不符`,
      ).toBe(404)
    })
  }
})

// ───────────────────── 公开读不得被收紧误伤 ─────────────────────
test.describe('公开读对照：收紧不得误伤匿名读', { tag: ['@readonly', '@local-only'] }, () => {
  let api
  test.beforeEach(async () => { api = await apiContext(null) })
  test.afterEach(async () => { await api.dispose() })

  for (const e of LISTED) {
    test(`匿名 GET ${e.list} → 200（${e.name}）`, async () => {
      const r = await api.get(e.list)
      expect(r.status(), `${e.name} 的读取必须保持匿名可用（SAFE_METHODS 全放开）`).toBe(200)
    })
  }
})

// ───────────────────── 死代码登记 + 真实购物车端点 ─────────────────────
test.describe('BasketViewSet 死代码登记 + 真实购物车端点', { tag: ['@readonly', '@local-only'] }, () => {
  let api
  test.beforeEach(async () => { api = await apiContext(null) })
  test.afterEach(async () => { await api.dispose() })

  test(`BasketViewSet 未被任何 urls 路由：POST /baskets/ → 404`, async () => {
    // `apps/transactions/api/v1/views.py` 的 `BasketViewSet` **没有**被 router.register
    // （transactions 只注册了 orders / quotes / wishlist）⇒ 它是死代码，
    // 仅显式声明了 `AllowAny` 以消除"隐式即公开"这一族隐患。
    // 本用例把这个事实钉住：一旦有人给它加了路由，这里会红，提醒补权限用例。
    const r = await api.post('/baskets/', { data: {} })
    expect(
      r.status(),
      'BasketViewSet 目前**未被路由**（应为 404）。若变成 401/403 ⇒ 已有人接入路由，请同步补鉴权断言',
    ).toBe(404)
  })

  test('真实购物车端点 /basket 匿名可读 → 200（匿名购物车是有意设计）', async () => {
    // 真正生效的购物车端点在 `basket_views.py`（`/basket`、`/basket/items` …），
    // 且已**显式**声明 `AllowAny` —— 与上面 BasketViewSet 死代码是两码事，勿混。
    const r = await api.get('/basket')
    expect(r.status(), '/basket 是匿名购物车入口，应匿名可用').toBe(200)
  })
})
