/**
 * @local-only A-258 —— 收藏夹里的「已下架」商品不得冒充在售（2026-11-18 / S4）
 *
 * ## 真实缺陷
 * 收藏夹写入侧只拦「收藏**已归档**的商品」（`Product.objects.filter(archived=False)`），
 * 但拦不住「收藏**之后**才被下架」。而读侧 `WishlistSerializer.products` 内嵌
 * `ProductListSerializer` 时**不过滤 archived**，前端 `WishlistPage` 又直接
 * `<ProductCard :product="p" />` ⇒ 下架商品与在售商品渲染得一模一样。
 * 更糟的是点进去必然 404（`ProductViewSet.retrieve` 对非 staff 的 archived 行抛 404），
 * 用户只会以为站点坏了。
 *
 * ## 本用例要同时钉住三件事
 * 1. **后端确实把 `archived` 暴露在 wishlist 的 products 里**（DS4 里这项标着"需再确认"，
 *    此前没人实测过；若它不暴露，前端判据 `p.archived === true` 恒 false ⇒ 全部失效）。
 * 2. 卡片渲染成 **`div` 而不是 `a`** —— 真正的不可点，不是 `pointer-events:none` 那种
 *    能被 Tab + Enter 绕过的假禁用。
 * 3. 角标 `Unavailable` + 顶部「N 件商品已下架」提示条（不静默隐藏）。
 *
 * ## 数据纪律
 * 只造自己的一条 `__e2e_wishlist_a258__` 夹具产品（名字 `__` 前缀 ⇒ 后端自动
 * `is_test_fixture=True` ⇒ 不进前台列表），**绝不碰真实产品**。
 * 收尾顺序：先把收藏夹恢复成原始 id 集合 → 再还原/删除夹具产品。
 */
const { test, expect } = require('@playwright/test');
const A = require('./helpers/auth.cjs');

const NAME = '__e2e_wishlist_a258__';
/**
 * slug **每次运行唯一**。
 *
 * ★ 踩点：`slug` 是**全表永久唯一**（含回收站行）。最初用固定 slug，首次运行通过后
 *   把夹具降级成 `draft` 留着，第二次运行 `POST` 直接 400「slug 已被另一个产品占用」
 *   ⇒ **第一次绿、第二次红**，而且报错长得像一次普通的创建失败，掩盖了"用例不可重复"。
 *   改成唯一 slug 是根治：不依赖清理是否成功。
 */
const SLUG_PREFIX = 'e2e-wishlist-a258';
const SLUG = `${SLUG_PREFIX}-${Date.now().toString(36)}`;

/** 用页面已登录的 token 调 API（与前端同款 X-Auth-Token） */
async function apiCall(page, method, path, body) {
  return page.evaluate(
    async ({ method, path, body }) => {
      const headers = { 'X-Auth-Token': localStorage.getItem('token') || '' };
      if (body !== undefined) headers['Content-Type'] = 'application/json';
      const r = await fetch(path, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      let data = null;
      try { data = await r.json(); } catch { data = null; }
      return { status: r.status, data };
    },
    { method, path, body },
  );
}

/** 剥 EnvelopeRenderer 外壳 */
function unwrap(res) {
  const b = res?.data;
  if (b && typeof b === 'object' && 'success' in b && 'data' in b) return b.data;
  return b;
}

/** 取当前用户的收藏夹；没有就建一个（与页面逻辑一致） */
async function ensureWishlist(page) {
  const got = await apiCall(page, 'GET', '/api/v1/wishlist/');
  const list = unwrap(got);
  const arr = Array.isArray(list) ? list : (list?.results || []);
  if (arr.length) return arr[0];
  const created = await apiCall(page, 'POST', '/api/v1/wishlist/', { name: 'My Wishlist' });
  return unwrap(created);
}

/**
 * 清掉历史运行可能残留的同前缀夹具产品（best effort）。
 *
 * ★ 为什么不能靠 `?search=` 找：`ProductViewSet.search_fields` 只有
 *   `name/cas/smiles/inchi/catalog_no/formula` —— **不含 slug**，而这个夹具的名字是
 *   `__e2e_wishlist_a258__`（下划线形态），用连字符 slug 去搜命中不了。
 *
 * ★ 排序只能用 `ordering_fields` 里**真实存在**的字段
 *   （`name/created_at/catalog_no/aggregate_relevance_score`）。
 *   最初写的 `ordering=-id` 会被 DRF 的 `OrderingFilter` **静默忽略**，落回默认排序
 *   ⇒ 夹具掉出前 100 条 ⇒ 清理"看起来跑了但什么也没删"（本 spec 踩过）。
 *   夹具永远是**最新创建**的，所以用 `-created_at` 稳定排在最前。
 *   `page_size=500`（`max_page_size` 上限）确保不会因翻页漏掉。
 *   `archived=1` 是为了把回收站里的也捞出来（默认列表 `exclude(archived=True)`）。
 */
async function purgeFixtures(page) {
  const res = await apiCall(
    page, 'GET', '/api/v1/products/?archived=1&ordering=-created_at&page_size=500');
  const body = unwrap(res);
  const rows = Array.isArray(body) ? body : (body?.results || []);
  const mine = rows.filter((p) => (p.slug || '').startsWith(SLUG_PREFIX));
  for (const p of mine) {
    const del = await apiCall(page, 'POST', `/api/v1/products/${p.id}/hard-delete/`);
    console.log(`[A-258 setup] 清理历史夹具 id=${p.id} slug=${p.slug} → ${del.status}`);
  }
  return mine.length;
}

test.describe('@local-only A-258 收藏夹中的下架商品', () => {
  test('收藏后下架 ⇒ 角标 Unavailable + 卡片不可点 + 提示条（并验证 archived 真的暴露）', async ({ page }) => {
    test.setTimeout(180_000);

    let productId = null;
    let wishlistId = null;
    let originalIds = null;
    let ok = false;

    try {
      // ── 0. staff 登录，先清历史残留，再造一条夹具产品（在售）──
      await A.loginAsStaff(page);
      const purged = await purgeFixtures(page);
      if (purged) console.log(`[A-258 setup] 清掉 ${purged} 条历史夹具`);

      const created = await apiCall(page, 'POST', '/api/v1/products/', {
        name: NAME, slug: SLUG, status: 'active',
      });
      expect(created.status, `夹具产品创建失败：${JSON.stringify(created.data).slice(0, 300)}`)
        .toBe(201);
      productId = unwrap(created).id;
      expect(productId).toBeTruthy();

      // ── 1. 切成客户身份，把它收藏进去 ──
      await A.logout(page);
      await A.loginAsCustomer(page);

      const wl = await ensureWishlist(page);
      wishlistId = wl.id;
      originalIds = (wl.products || []).map((p) => p.id);
      const patched = await apiCall(page, 'PATCH', `/api/v1/wishlist/${wishlistId}/`, {
        product_ids: [...originalIds, productId],
      });
      expect(patched.status, `收藏失败：${JSON.stringify(patched.data).slice(0, 300)}`).toBe(200);

      // 前置自证：此刻它还是「在售」，卡片应当是链接
      await page.goto(`${A.BASE_URL}/wishlist`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2500);
      const liveCard = page.locator(`[data-testid="product-card"]:has-text("${NAME}")`).first();
      await expect(liveCard, '收藏后收藏夹里找不到该产品').toHaveCount(1);
      expect(
        await liveCard.evaluate((el) => el.tagName),
        '★ 前置不成立：在售商品本应是 <a>，否则本用例证明不了"下架后才变成 div"',
      ).toBe('A');

      // ── 2. staff 把它移入回收站（archived=True，status 保持 active —— 正是生产那批矛盾态）──
      await A.logout(page);
      await A.loginAsStaff(page);
      const del = await apiCall(page, 'DELETE', `/api/v1/products/${productId}/`);
      expect(del.status, `软删除失败：${JSON.stringify(del.data).slice(0, 300)}`).toBe(200);

      // ── 3. 切回客户，验收藏夹的展示口径 ──
      await A.logout(page);
      await A.loginAsCustomer(page);

      // 3a. 后端契约：archived 必须出现在 wishlist 的 products 里（DS4 的待确认项）
      const after = await apiCall(page, 'GET', '/api/v1/wishlist/');
      const afterList = unwrap(after);
      const afterArr = Array.isArray(afterList) ? afterList : (afterList?.results || []);
      const row = (afterArr[0]?.products || []).find((p) => p.id === productId);
      expect(row, '收藏夹里丢了该产品（后端把它过滤掉了？本用例前提是"保留 + 标注"）').toBeTruthy();
      expect(
        row.archived,
        '★ 后端没有把 archived 暴露在 wishlist.products 里 —— 前端判据会恒 false',
      ).toBe(true);

      // 3b. 页面：角标 + 不可点 + 提示条
      await page.goto(`${A.BASE_URL}/wishlist`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(2500);

      const card = page.locator(`[data-testid="product-card"]:has-text("${NAME}")`).first();
      await expect(card, '下架后卡片消失了（按设计应保留并标注）').toHaveCount(1);

      expect(
        await card.evaluate((el) => el.tagName),
        '★ 下架商品仍渲染成 <a> —— 用户点进去会拿到 404',
      ).toBe('DIV');
      await expect(card).toHaveAttribute('aria-disabled', 'true');

      const badge = card.locator('[data-testid="product-unavailable-badge"]');
      await expect(badge).toBeVisible();
      await expect(badge).toHaveText(/Unavailable/i);

      // 库存标签必须让位（否则「In Stock」与下架自相矛盾）
      await expect(card).not.toContainText(/In Stock/i);

      // 提示条：不静默隐藏，得让用户知道"不是我删的，是卖不了了"
      const note = page.locator('[data-testid="wishlist-unavailable-note"]');
      await expect(note).toBeVisible();
      await expect(note).toContainText(/已下架/);

      // 3c. 全页不应再有任何指向该产品的链接
      const links = page.locator(`a[href*="${SLUG}"]`);
      expect(await links.count(), '★ 仍存在指向下架产品的 <a href>').toBe(0);

      ok = true;
    } finally {
      // ── 收尾：先恢复收藏夹原状，再收拾夹具产品 ──
      try {
        if (productId) {
          await A.logout(page);
          await A.loginAsStaff(page);
          // 还原（archived=False），否则产品永远卡在回收站
          await apiCall(page, 'POST', `/api/v1/products/${productId}/restore/`);
          // 尽量彻底删除；失败就降级为 draft（带 __ 前缀，前台本就看不见）
          // ⚠️ hard-delete 是 **POST**（`@action(methods=['post'])`），不是 DELETE ——
          //    写成 DELETE 会得到 405 并静默走降级分支（本 spec 初版就踩了这个）。
          const hard = await apiCall(page, 'POST', `/api/v1/products/${productId}/hard-delete/`);
          if (hard.status !== 200) {
            await apiCall(page, 'PATCH', `/api/v1/products/${productId}/`, { status: 'draft' });
            console.warn(`[A-258 cleanup] hard-delete 未成功（${hard.status}），已降级为 draft`);
          }
        }
        if (wishlistId && originalIds) {
          await A.logout(page);
          await A.loginAsCustomer(page);
          await apiCall(page, 'PATCH', `/api/v1/wishlist/${wishlistId}/`, {
            product_ids: originalIds,
          });
        }
      } catch (e) {
        console.warn('[A-258 cleanup] 清理异常（不影响断言结论）：', e.message);
      }
      if (!ok) console.warn('[A-258] 断言未通过，夹具可能残留：', { productId, wishlistId });
    }
  });
});
