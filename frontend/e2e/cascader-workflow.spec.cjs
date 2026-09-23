/**
 * E2E 测试 — 产品分类 Cascader 全流程验证（7 项）
 *
 * 验证 ProductEditPage 的 el-cascader 在以下场景下的行为：
 *   1. 新建产品 — cascader 选择分类 → 写入 product_class_id → 保存草稿
 *   2. 编辑回填 — 打开已有产品，cascader 从 product_class_id 反显分类路径
 *   3. Completeness — 选择/取消分类对完整性条的影响
 *   4. Publish — 完整产品可发布，status→active
 *   5. 列表页分类列 — ProductsPage 表格显示 product_class_name
 *   6. Jena 回填 — AI AUTO MATCH 命中 jena 后，apply 把 category_l1 映射到 cascader L1
 *   7. 发布不完整警告 — 已发布但缺推荐字段的产品显示 incomplete-banner
 *
 * 运行方式：
 *   cd E:\scireagent-tencent\frontend
 *   npx playwright test e2e/cascader-workflow.spec.cjs
 *
 * 前提：后端 127.0.0.1:8000 + 前端 127.0.0.1:5173 已启动
 *       后端 admin 账号已存在（is_staff=True）
 */

const { test, expect, request } = require('@playwright/test');

const BASE_URL = process.env.BASE_URL || 'http://localhost:5173';
const API_BASE = 'http://localhost:8000/api/v1';
// 单一口径：凭据一律取自 helpers/auth.cjs。
// 2026-09-23 修复：此处曾自行硬编码默认密码 'AdminPass123!'（与 helpers/auth.cjs 的 'admin123' 漂移）
// ⇒ 登录 401 ⇒ 反复跳 /login ⇒ `waitForURL` 超时 ⇒ 本文件 6 条用例长期假红。
const { ADMIN_USER, ADMIN_PASS } = require('./helpers/auth');

// 已知数据基线（2026-09-23 经 GET /api/v1/products/ 实测核对）
// ⚠️ 锚点会随 dev 库数据漂移腐烂：以下每条用例都带**运行期前置校验**（不满足即 fail，不 skip），
//    使下一次腐烂立刻响，而不是变成"假绿/长期假红"。
//
// ⚠️ 用例创建的产品货号/slug 必须**每次运行唯一**（RUN_TAG）：
//    后端 delete = **软归档**（archived=1，行不删除，见 backend/.../views.py perform_destroy），
//    而 catalog_no/slug 的唯一约束把归档行也算 ⇒ 固定货号会让本文件"首跑绿、次跑 409"。
const RUN_TAG = Date.now().toString(36);
const EDIT_PRODUCT_ID = 23;        // SC8003 / '5‑Propargylamino‑CTP-Cy3' / class_id=9 (Nucleotides & Nucleosides, L1 根)
const EDIT_CLASS_NAME = 'Nucleotides & Nucleosides';
const INCOMPLETE_PUBLISHED_ID = 39; // SC8020 / 'Sulfo-Cy5 dUTP' / active / cas='' ⇒ 触发 incomplete-banner
const JENA_L1_NAME = 'Nucleotides & Nucleosides';
const JENA_L1_SLUG = 'nucleotides_nucleosides'; // class 9 的 slug（L1 根，parent_id IS NULL）

// ── 登录 helper：走真实 UI 登录页，确保 store 正确初始化（isStaff 等） ──
async function loginAsStaff(page) {
  await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });

  // 用 placeholder 精确定位登录表单（避免命中导航栏的搜索框）
  await page.locator('input[placeholder="Enter your username"]').fill(ADMIN_USER);
  await page.locator('input[placeholder="Enter your password"]').fill(ADMIN_PASS);

  // 提交登录 — staff 用户会被重定向到 /workspace
  await Promise.all([
    page.waitForURL(/\/workspace/, { timeout: 15000 }),
    page.getByRole('button', { name: 'Sign In' }).click(),
  ]);
}

async function waitForProductSave(page, method, timeout = 30000) {
  // 接受 200/201（创建）—— 等待产品路径（含 /api/v1/products/）并排除空的 create 路径
  return page.waitForResponse(
    r => r.request().method() === method &&
         r.url().match(/\/api\/v1\/products\/$/) &&
         (r.status() === 200 || r.status() === 201),
    { timeout }
  );
}

// 安装网络监听器：打印即将发出的所有 /products/ 请求与响应状态，便于调试
function traceApi(page) {
  page.on('request', r => {
    if (r.url().match(/\/api\/v1\/products/) && (r.method() === 'POST' || r.method() === 'PUT')) {
      console.log(`[REQ] ${r.method()} ${r.url()}`);
      console.log(`[BODY] ${r.postData()}`);
    }
  });
  page.on('response', r => {
    if (r.url().match(/\/api\/v1\/products/)) {
      console.log(`[API] ${r.request().method()} ${r.url()} → ${r.status()}`);
    }
  });
}

// ── 运行期前置校验 helper ──
// 用登录后的 localStorage token 直连 8000 读实体；锚点腐烂时由调用方 fail（不 skip）。
// 注意：这里的 apiRequest 是 Playwright 的 `request` **夹具实例**（APIRequestContext），
//       不是 `require('@playwright/test').request` 模块——夹具没有 .newContext()，直接用 .get()。
async function apiGet(apiRequest, page, path) {
  const token = await page.evaluate(() => localStorage.getItem('token'));
  const r = await apiRequest.get(`${API_BASE}${path}`, { headers: { Authorization: `Token ${token}` } });
  const status = r.status();
  let body = null;
  if (status === 200) { try { body = (await r.json()).data; } catch { body = null; } }
  return { status, body };
}

// ── el-cascader 交互 helper ──
// Element Plus cascader：点击 .el-cascader 触发面板，菜单项为 .el-cascader-node
async function openCascader(page) {
  const cascader = page.locator('.el-cascader').first();
  await cascader.scrollIntoViewIfNeeded();
  await cascader.click();
  await page.waitForSelector('.el-cascader__dropdown .el-cascader-panel', { timeout: 5000 });
}

// 选择指定层级的菜单项（按可见文本匹配）。pathLabels = ['L1名', 'L2名']
async function selectCascaderPath(page, pathLabels) {
  await openCascader(page);
  for (let i = 0; i < pathLabels.length; i++) {
    const label = pathLabels[i];
    // 当前最后一列（最新展开的 menu）中的节点
    const menus = page.locator('.el-cascader__dropdown .el-cascader-menu');
    const menuCount = await menus.count();
    const currentMenu = menus.nth(menuCount - 1);
    const node = currentMenu.locator('.el-cascader-node', { hasText: label }).first();
    await node.waitFor({ state: 'visible', timeout: 5000 });
    // 非最后一级需要 hover 触发下一级展开（expandTrigger: hover）
    if (i < pathLabels.length - 1) {
      await node.hover();
      await page.waitForTimeout(300);
    } else {
      await node.click();
    }
  }
  // 选中后面板关闭
  await page.waitForTimeout(300);
}

test.describe('产品分类 Cascader 全流程', () => {

  test.beforeEach(async ({ page }) => {
    await loginAsStaff(page);
  });

  // ═══════════════════════════════════════════
  // 1. 新建产品 — cascader 选择分类 → 保存草稿
  // ═══════════════════════════════════════════
  test('1. 新建产品：cascader 选分类后保存草稿，product_class_id 持久化', async ({ page }) => {
    const newUrl = `${BASE_URL}/workspace/products/new`;
    await page.goto(newUrl, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 填最小必填字段（含 slug — 后端 slug blank=False，前端无自动生成，这里显式填以隔离 cascader 验证）
    // 货号/slug/sku 带 RUN_TAG：避免软归档残留撞唯一约束（见文件头注释）
    await page.locator('input[placeholder*="Amino-ATP"]').fill('E2E Test Product');
    await page.locator('input[placeholder*="SC8043"]').first().fill(`E2E-TEST-${RUN_TAG}`);
    await page.locator('input[placeholder*="auto-generated-if-empty"]').fill(`e2e-test-${RUN_TAG}`);

    // 选择分类：L1 = Nucleotides & Nucleosides, L2 = Fluorescent Nucleotides
    await selectCascaderPath(page, ['Nucleotides & Nucleosides', 'Fluorescent Nucleotides']);

    // 验证 cascader 输入框显示选中路径
    const cascaderInput = page.locator('.el-cascader input').first();
    await expect(cascaderInput).toHaveValue(/Nucleotides/);
    await expect(cascaderInput).toHaveValue(/Fluorescent/);

    // 添加默认 SKU（completeness 需要）
    await page.locator('button', { hasText: '+ Add SKU' }).click();
    await page.locator('.sku-table input').first().fill(`E2E-TEST-${RUN_TAG}-1`); // sku_code

    // 保存草稿（POST 创建，返回 201）
    traceApi(page);
    const [saveResp] = await Promise.all([
      waitForProductSave(page, 'POST'),
      page.locator('.form-actions button', { hasText: 'Save Draft' }).click(),
    ]);
    expect([200, 201]).toContain(saveResp.status());

    // 新建后应跳转到 edit 页
    await expect(page).toHaveURL(/\/workspace\/products\/\d+\/edit/, { timeout: 10000 });
    const createdId = new URL(page.url()).pathname.match(/\/products\/(\d+)\/edit/)[1];

    // 从 API 拉取该产品，确认 product_class_id 已落库
    const token = await page.evaluate(() => localStorage.getItem('token'));
    const ctx = await request.newContext();
    const getResp = await ctx.get(`${API_BASE}/products/${createdId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const pData = (await getResp.json()).data;
    expect(pData.product_class_id).not.toBeNull();
    expect(pData.name).toBe('E2E Test Product');
    await ctx.dispose();

    // 清理：删除测试产品（DELETE 走 8000 直连，Playwright http 解析对 204 偶发 Parse Error，容错）
    const delCtx = await request.newContext();
    try {
      await delCtx.delete(`${API_BASE}/products/${createdId}/`, {
        headers: { Authorization: `Token ${token}` },
      });
    } catch { /* 清理失败不影响测试结论 */ }
    await delCtx.dispose();
  });

  // ═══════════════════════════════════════════
  // 2. 编辑回填 — 已有产品 cascader 反显分类路径
  //    用 L2 叶子分类产品验证回填逻辑（cascader checkStrictly:false 只支持叶子）
  //    ⚠ 附带发现：历史数据 product_class_id 全落在 L1 根，回填为空（记录为 bug）
  // ═══════════════════════════════════════════
  test('2. 编辑回填：L2 叶子分类产品，cascader 反显分类路径', async ({ page }) => {
    // 通过 API 创建一个 L2 叶子分类产品（product_class_id=84 Fluorescent Nucleotides）
    // 货号/slug/sku 带 RUN_TAG：避免软归档残留撞唯一约束（见文件头注释）
    const token = await page.evaluate(() => localStorage.getItem('token'));
    const ctx = await request.newContext();
    const createResp = await ctx.post(`${API_BASE}/products/`, {
      headers: { Authorization: `Token ${token}`, 'Content-Type': 'application/json' },
      data: {
        name: 'E2E Edit Backfill', slug: `e2e-edit-${RUN_TAG}`, catalog_no: `E2E-EDIT-${RUN_TAG}`,
        status: 'draft', product_class_id: 84,
        skus: [{ sku_code: `E2E-EDIT-${RUN_TAG}-1`, pack_size: '1', currency: 'USD', price: '10', is_default: true }],
        method_ids: [], protocol_ids: [],
      },
    });
    expect([200, 201]).toContain(createResp.status());
    const createdId = (await createResp.json()).data.id;

    try {
      const editUrl = `${BASE_URL}/workspace/products/${createdId}/edit`;
      await page.goto(editUrl, { waitUntil: 'domcontentloaded' });
      await page.waitForSelector('.edit-form', { timeout: 10000 });

      // 等待分类 options 加载 + cascader 回填（异步 loadCategoryOptions）
      const cascaderInput = page.locator('.el-cascader input').first();
      await expect(cascaderInput).toHaveValue(/Nucleotides/, { timeout: 15000 });
      await expect(cascaderInput).toHaveValue(/Fluorescent/);

      // 验证 Name 字段也回填了
      const nameInput = page.locator('input[placeholder*="Amino-ATP"]').first();
      await expect(nameInput).toHaveValue(/Edit Backfill/);
    } finally {
      // 清理：DELETE 走 8000 直连，Playwright http 解析对 204 偶发 Parse Error，容错
      try {
        await ctx.delete(`${API_BASE}/products/${createdId}/`, {
          headers: { Authorization: `Token ${token}` },
        });
      } catch { /* 清理失败不影响测试结论 */ }
      await ctx.dispose();
    }
  });

  // ═══════════════════════════════════════════
  // 2b. L1 根分类产品编辑页 cascader 正常回填 L1
  //     历史（checkStrictly:false 时代）：L1 根 product_class_id 经 _findIdPath 返回单节点
  //       [id]，el-cascader 认为非完整分支 ⇒ 回填为空（曾记为 bug）。
  //     现状：el-cascader 已改为 checkStrictly:true（commit aa57ef0, 2026-07-13），
  //       允许选中任意层级 ⇒ L1 根单层路径可回显，输入框显示 L1 名。
  //     ⚠ 本用例自带运行期前置校验：product 必须存在、非 archived、且其分类为 L1 根；
  //       不满足即 fail（不 skip）——锚点腐烂立刻响。
  // ═══════════════════════════════════════════
  test('2b. L1 根分类产品编辑页 cascader 回填 L1（checkStrictly:true 修复原"回填为空"）', async ({ page, request }) => {
    // 运行期前置校验（fail 不 skip）
    const { status, body: p } = await apiGet(request, page, `/products/${EDIT_PRODUCT_ID}/`);
    expect(status, `前置：product ${EDIT_PRODUCT_ID} 应存在（GET 200），实得 ${status}`).toBe(200);
    expect(p && p.status, `前置：product ${EDIT_PRODUCT_ID} 不应为 archived`).not.toBe('archived');
    const cls = await apiGet(request, page, `/product-classes/${p.product_class_id}/`);
    expect(cls.status, `前置：class ${p.product_class_id} 应存在`).toBe(200);
    expect(cls.body && cls.body.parent_id,
      `前置：product ${EDIT_PRODUCT_ID} 的分类 (id=${p.product_class_id}) 必须是 L1 根（parent_id IS NULL）`,
    ).toBeNull();

    const editUrl = `${BASE_URL}/workspace/products/${EDIT_PRODUCT_ID}/edit`;
    await page.goto(editUrl, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 等待 options 加载（等 Name 回填确认数据已就绪）
    const nameInput = page.locator('input[placeholder*="Amino-ATP"]').first();
    await expect(nameInput).toHaveValue(/Propargylamino/, { timeout: 10000 });

    // 现状：checkStrictly:true 下 L1 根单层路径可回显 ⇒ 输入框显示 L1 名（不再为空）
    const cascaderInput = page.locator('.el-cascader input').first();
    await expect(cascaderInput).toHaveValue(/Nucleotides/, { timeout: 10000 });
  });

  // ═══════════════════════════════════════════
  // 3. Completeness — 分类对完整性条的影响
  // ═══════════════════════════════════════════
  test('3. Completeness：未选分类时警告条含 Category，选后该项消除', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 初始：未选分类，警告条应含 Category
    const bar = page.locator('.completeness-bar');
    await expect(bar).toContainText('Incomplete');
    await expect(bar).toContainText('Category');

    // 选分类
    await selectCascaderPath(page, ['Nucleotides & Nucleosides', 'Fluorescent Nucleotides']);

    // 警告条不再含 Category（但仍 Incomplete，因还缺 name/catalog/sku）
    await expect(bar).not.toContainText('Category');
  });

  // ═══════════════════════════════════════════
  // 4. Publish — 完整产品发布，status→active
  // ═══════════════════════════════════════════
  test('4. Publish：填满必填项后发布，status 变 active', async ({ page }) => {
    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // 填齐完整条件：name, catalog_no, cas, smiles, product_class_id, default sku
    // 货号/slug/sku 带 RUN_TAG：避免软归档残留撞唯一约束（见文件头注释）
    await page.locator('input[placeholder*="Amino-ATP"]').fill('E2E Publish Test');
    await page.locator('input[placeholder*="SC8043"]').first().fill(`E2E-PUB-${RUN_TAG}`);
    await page.locator('input[placeholder*="1927-31-7"]').first().fill('150718-26-6');
    await page.locator('textarea[placeholder*="C1=CC"]').fill('C1=CC=C(C=C1)N');
    await page.locator('input[placeholder*="auto-generated-if-empty"]').fill(`e2e-pub-${RUN_TAG}`);
    await selectCascaderPath(page, ['Nucleotides & Nucleosides', 'Fluorescent Nucleotides']);
    await page.locator('button', { hasText: '+ Add SKU' }).click();
    await page.locator('.sku-table input').first().fill(`E2E-PUB-${RUN_TAG}-1`);

    // 等待完整性条变绿
    await expect(page.locator('.completeness-bar')).toHaveClass(/completeness-ok/, { timeout: 5000 });
    await expect(page.locator('.completeness-bar')).toContainText('Complete');

    // Publish 按钮可点且文本为 Publish
    // ⚠ 按可访问名精确匹配：该按钮 textContent 为 "\n          Publish\n        "（含首尾空白），
    //   hasText 正则 /^Publish$/ 会因空白匹配不到（ProductEditPage.vue:2058-2060）。
    const publishBtn = page.locator('.form-actions').getByRole('button', { name: 'Publish', exact: true });
    await expect(publishBtn).toBeEnabled();

    // 点 Publish → 弹确认框 → 确认（创建 POST 201）
    await publishBtn.click();
    await page.waitForSelector('.dialog', { timeout: 5000 });
    const [pubResp] = await Promise.all([
      waitForProductSave(page, 'POST'),
      // 发布确认框内按钮文案经核对确为 "Confirm Publish"（ProductEditPage.vue:2085），无需改
      page.locator('.dialog button', { hasText: 'Confirm Publish' }).click(),
    ]);
    expect([200, 201]).toContain(pubResp.status());

    // 验证落库 status=active
    await expect(page).toHaveURL(/\/workspace\/products\/\d+\/edit/, { timeout: 10000 });
    const createdId = new URL(page.url()).pathname.match(/\/products\/(\d+)\/edit/)[1];
    const token = await page.evaluate(() => localStorage.getItem('token'));
    const ctx = await request.newContext();
    const getResp = await ctx.get(`${API_BASE}/products/${createdId}/`, {
      headers: { Authorization: `Token ${token}` },
    });
    const pData = (await getResp.json()).data;
    expect(pData.status).toBe('active');
    await ctx.dispose();

    // 清理：DELETE 走 8000 直连，Playwright http 解析对 204 偶发 Parse Error，容错
    const delCtx = await request.newContext();
    try {
      await delCtx.delete(`${API_BASE}/products/${createdId}/`, {
        headers: { Authorization: `Token ${token}` },
      });
    } catch { /* 清理失败不影响测试结论 */ }
    await delCtx.dispose();
  });

  // ═══════════════════════════════════════════
  // 5. 列表页分类列 — ProductsPage 显示 product_class_name
  // ═══════════════════════════════════════════
  test('5. 列表页：分类列显示 product_class_name', async ({ page, request }) => {
    // 前置（fail 不 skip）：SC8003 对应 product 23 必须存在且 non-archived，否则列表页不渲染该行
    const { status, body: p } = await apiGet(request, page, `/products/${EDIT_PRODUCT_ID}/`);
    expect(status, `前置：product ${EDIT_PRODUCT_ID} 应存在（GET 200），实得 ${status}`).toBe(200);
    expect(p && p.status,
      `前置：SC8003 (product ${EDIT_PRODUCT_ID}) 必须 non-archived，实得 status=${p && p.status}`,
    ).not.toBe('archived');

    await page.goto(`${BASE_URL}/workspace/products`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.products-table', { timeout: 10000 });

    // 找到 SC8003 的行，验证 Category 列显示分类名
    const row = page.locator('.products-table tbody tr', { hasText: 'SC8003' }).first();
    await expect(row).toBeVisible({ timeout: 10000 });

    // Category 是第 7 列（checkbox / catalog / name / cas / complete / status / category）——
    // 表头顺序见 ProductsPage.vue:578-584（<th>Category</th> 为下标 6），渲染 product_class_name
    const cells = row.locator('td');
    const categoryCell = cells.nth(6);
    await expect(categoryCell).toContainText(EDIT_CLASS_NAME);
  });

  // ═══════════════════════════════════════════
  // 6. Jena 回填 — AI AUTO MATCH 命中后 apply 把 category_l1 映射到 cascader L1
  //     依赖 **stub**（page.route 注入合成信封），不再依赖"活 jena 命中"：
  //       dev 库 jena 索引已不命中原锚点名（数据漂移），且原命中文案组件已换。
  //     ⚠ 实际渲染组件是 MultiSourceMatchSection（.ms-section / "Matched by …" / .ms-apply-btn）；
  //       JenaMatchSection.vue（.jena-section / "Matched (...)" / .jena-apply-btn）已**无任何引用**
  //       （死代码），据其断言的旧写法必然 404。
  //     现状：enrich 返回 jena.matched + normalized.category_l1(L1 根 slug) 时，
  //       ProductEditPage.vue:584-586 自动调 applyJenaCategoryL1 ⇒ cascader 选 L1 根；
  //       el-cascader 已 checkStrictly:true（aa57ef0）⇒ L1 根单层路径可回显。
  // ═══════════════════════════════════════════
  test('6. Jena 回填：apply L1 根分类后 cascader 选中 L1（checkStrictly:true）', async ({ page }) => {
    // 可控 stub：让依赖数据的路径确定（参考 product-new-ai-automatch.spec.cjs 的 D13 回放式 stub）
    await page.route(/\/products\/enrich\//, route => route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        success: true, meta: {}, data: {
          jena: {
            matched: true, match_key: 'catalog', catalog_no: 'NU-833',
            product_name: 'ATP-ATTO-540Q', cas_number: '1234-56-7',
            normalized: {
              purity: '>=95%', storage_condition: 'store at -20C',
              shipping_condition: 'shipped at ambient', category_l1: JENA_L1_SLUG,
            },
          },
        },
      }),
    }));

    await page.goto(`${BASE_URL}/workspace/products/new`, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    await page.locator('input[placeholder*="Amino-ATP"]').fill('ATP-ATTO-540Q');
    await page.locator('input[placeholder*="SC8043"]').first().fill('E2E-JENA-001');

    // 确保 cascader 初始为空
    const cascaderInput = page.locator('.el-cascader input').first();
    await expect(cascaderInput).toHaveValue('');

    // 触发 AI AUTO MATCH（按钮文本含产品名，用 role+name 正则）
    await page.getByRole('button', { name: /AI AUTO MATCH/ }).click();

    // stub 命中 ⇒ 渲染 Supplier Spec Match 分组（真实组件文案为 "Matched by <key>"）
    const msSection = page.locator('.ms-section');
    await expect(msSection).toBeVisible({ timeout: 20000 });
    await expect(msSection).toContainText('Matched by');
    await expect(msSection).toContainText('NU-833');

    // 现状：category_l1= L1 根 slug 时自动 applyJenaCategoryL1 ⇒ checkStrictly:true 下 cascader 回显 L1 名
    await expect(cascaderInput).toHaveValue(/Nucleotides/, { timeout: 10000 });

    // 点击 "Apply from jena"（多源分组组件实际文案；子串 "Apply" 亦可命中）
    const applyBtn = msSection.locator('button', { hasText: 'Apply' });
    await expect(applyBtn).toBeVisible();
    await applyBtn.click();

    // apply 后仍为 L1 根选中（无回归）。注：不再断言"输入框为空"——那是 checkStrictly:false 时代的旧行为。
    await expect(cascaderInput).toHaveValue(/Nucleotides/);
  });

  // ═══════════════════════════════════════════
  // 7. 发布不完整警告 — 已发布但缺推荐字段
  // ═══════════════════════════════════════════
  test('7. 发布不完整警告：已发布缺字段产品显示 incomplete-banner', async ({ page, request }) => {
    // 前置（fail 不 skip）：product 必须 active + non-archived + 确实缺 ≥1 个受检字段
    //（受检字段判定见 ProductEditPage.vue:944-956；缺字段清单见 :225-234 suggestionsMissing）
    const { status, body: p } = await apiGet(request, page, `/products/${INCOMPLETE_PUBLISHED_ID}/`);
    expect(status, `前置：product ${INCOMPLETE_PUBLISHED_ID} 应存在（GET 200），实得 ${status}`).toBe(200);
    expect(p && p.status, `前置：product ${INCOMPLETE_PUBLISHED_ID} 必须 active`).toBe('active');
    const missingCore = ['cas', 'smiles', 'formula', 'molecular_weight'].filter(k => !p[k]);
    const noLinks = !(p.method_ids || []).length && !(p.protocol_ids || []).length;
    const noSeo = !p.seo_title && !p.seo_description;
    expect(missingCore.length > 0 || noLinks || noSeo,
      `前置：product ${INCOMPLETE_PUBLISHED_ID} 必须缺 ≥1 个受检字段（cas/smiles/formula/mw/知识链接/SEO），否则 banner 不渲染`,
    ).toBe(true);

    const editUrl = `${BASE_URL}/workspace/products/${INCOMPLETE_PUBLISHED_ID}/edit`;
    await page.goto(editUrl, { waitUntil: 'domcontentloaded' });
    await page.waitForSelector('.edit-form', { timeout: 10000 });

    // product 39 是 active 但缺 cas，应显示 incomplete-banner
    const banner = page.locator('.incomplete-banner');
    await expect(banner).toBeVisible({ timeout: 10000 });
    await expect(banner).toContainText('published but is missing');
    await expect(banner).toContainText('CAS');
  });
});
