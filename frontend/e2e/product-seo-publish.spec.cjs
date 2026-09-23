/**
 * Part 1 · 组 G 「SEO」—— 覆盖矩阵点名的**未覆盖**项
 *
 * 覆盖矩阵（`2026-09-23_P0覆盖矩阵_重算.md`）列出这三条**完全无脚本**：
 *   · **G1** 新建态点 `自动生成` ⇒ `U` 按钮 **disabled**（必须先保存）
 *   · **G2** 编辑态点 `自动生成` ⇒ `A` `POST /products/{id}/generate-seo/` 200；`U` 两字段被填入
 *   · **G3** draft→active 时 SEO 为空 ⇒ **后端自动生成**（`_auto_seo_on_publish`）；`D` 两字段非空
 *
 * 代码事实（**已 Read 核实**，勿凭剧本行号）：
 *   · 按钮：`ProductEditPage.vue:1910` `:disabled="seoGenerating || !isEdit"`；
 *     文案随态变化 —— 新建态 `Save product first to enable SEO auto-gen`、编辑态 `Auto-generate SEO`
 *     （用正则同时匹配两态，**无需为测试改生产代码**）
 *   · 处理器：`ProductEditPage.vue:332 autoGenerateSeo()` → 成功回调 `:339-340` 填
 *     `form.seo_title` / `form.seo_description`
 *   · 后端：`commerce/api/v1/views.py:302` `url_path='generate-seo'`；
 *     `serializers.py:293 _auto_seo_on_publish()` —— **只填空值**，且仅在 `is_becoming_active` 时调用（`:464`）
 *
 * 纪律：只写 `E2E-` 前缀夹具；`afterAll` 用 cleanupByPrefix() 硬删；不改应用代码。
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { catalogNo, slug, cleanupByPrefix } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })

/** SEO 自动生成按钮：**两态文案都匹配**（新建态是 "Save product first to enable SEO auto-gen"） */
const seoBtn = (page) =>
  page.locator('button', { hasText: /Auto-generate SEO|Save product first to enable SEO auto-gen/ })
/** SEO 输入框（`<label>SEO Title <AppInput/></label>`） */
const seoInput = (page, label) => page.locator('label', { hasText: label }).locator('input')

const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))
/** 读某产品的单个字段（现算，禁硬编码） */
const productField = (id, field) =>
  dbQuery(
    `import json\nfrom apps.commerce.models import Product\n` +
      `print('__SNAP__' + json.dumps(getattr(Product.objects.get(id=${id}), '${field}')))`
  )

test.describe('Part 1 · 组 G SEO 自动生成与发布兜底（G1 / G2 / G3）', () => {
  test.afterAll(async ({ request }) => {
    const api = await staffApi(request)
    await cleanupByPrefix(api, { label: 'seo-publish' })
    await api.dispose()
  })

  // ── G1：新建态按钮必须 disabled（可发现性：按钮在、但明确不可用） ──────────
  test('G1 @readonly @local-only 新建态：SEO 自动生成按钮 disabled 且提示先保存', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page)
    await goto(page, '/workspace/products/new')

    const btn = seoBtn(page)
    await expect(btn, '新建态应能**看到**该按钮（可发现性）').toBeVisible({ timeout: 15000 })
    await expect(btn, '新建态 `!isEdit` ⇒ 必须 disabled').toBeDisabled()
    await expect(btn, 'disabled 原因应写进按钮文案').toContainText('Save product first')
    expect(errors).toEqual([])
  })

  // ── G2：编辑态点按钮 ⇒ POST generate-seo 200 + 两个字段被填入 ──────────
  test('G2 @write @local-only 编辑态点自动生成 ⇒ POST generate-seo 200 且两字段被填入', async ({ page, request }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(request)
    const code = catalogNo('G2')
    const created = await api.post('/products/', {
      data: { name: `E2E G2 SEO ${code}`, catalog_no: code, slug: slug('G2'), cas: '150718-26-6' },
    })
    await expectApi(created, { status: 201, label: 'G2 夹具创建' })
    const id = (await created.json()).data.id

    await loginAsStaff(page)
    await goto(page, `/workspace/products/${id}/edit`)
    const btn = seoBtn(page)
    await expect(btn, '编辑态应变为可点（文案 Auto-generate SEO）').toBeEnabled({ timeout: 20000 })
    await expect(btn).toContainText('Auto-generate SEO')

    const [resp] = await Promise.all([
      page.waitForResponse(
        (r) => r.request().method() === 'POST' && /\/products\/\d+\/generate-seo\/$/.test(r.url())
      ),
      btn.click(),
    ])
    expect(resp.status(), 'G2 generate-seo 应 200').toBe(200)

    await expect(seoInput(page, 'SEO Title'), 'G2 `U` 两个字段应被填入').not.toHaveValue('')
    await expect(seoInput(page, 'SEO Description')).not.toHaveValue('')
    expect(errors).toEqual([])
    await api.dispose()
  })

  // ── G3：draft→active 时后端兜底生成（即使 SEO 为空、前端从未点过按钮） ────
  //   ⚠️ 设计要点（第一版写错过）：`create()` 里 `_auto_seo_on_publish` 是**无条件调用**
  //   （`serializers.py:392`）⇒ 新建出来的产品 SEO **已被填充**，直接拿新夹具断不到"发布时兜底"。
  //   所以必须**先把两个 SEO 字段清空**，再做 draft→active 转换（`update()` 里该函数只在
  //   `is_becoming_active` 时触发，见 `:464`）。
  test('G3 @write @local-only draft→active 且 SEO 为空 ⇒ 后端自动生成两字段（断 DB）', async ({ request }) => {
    const api = await staffApi(request)
    const code = catalogNo('G3')
    const name = `E2E G3 SEO ${code}`
    const created = await api.post('/products/', {
      data: { name, catalog_no: code, slug: slug('G3'), cas: '50-78-2', status: 'draft' },
    })
    await expectApi(created, { status: 201, label: 'G3 夹具创建（draft）' })
    const id = (await created.json()).data.id

    // ① 先清空 SEO（`create()` 已自动填过）；此步**不是** draft→active，不应触发兜底
    const cleared = await api.patch(`/products/${id}/`, { data: { seo_title: '', seo_description: '' } })
    await expectApi(cleared, { status: 200, label: 'G3 清空 SEO' })
    expect(await productField(id, 'seo_title'), 'G3 前置：应已清空 seo_title').toBe('')
    expect(await productField(id, 'seo_description'), 'G3 前置：应已清空 seo_description').toBe('')

    // ② draft→active：后端 `_auto_seo_on_publish` 的唯一触发条件
    const published = await api.patch(`/products/${id}/`, { data: { status: 'active' } })
    await expectApi(published, { status: 200, label: 'G3 draft→active' })

    const title = await productField(id, 'seo_title')
    const desc = await productField(id, 'seo_description')
    expect(title, 'G3 `D seo_title` 应被兜底生成（非空）').toBeTruthy()
    expect(desc, 'G3 `D seo_description` 应被兜底生成（非空）').toBeTruthy()
    // 加强（已 Read 核实契约）：自动值由产品名派生 —— 断"含产品名"而非仅"非空"
    expect(title, 'G3 自动 seo_title 应由产品名派生').toContain(name)
    expect(desc, 'G3 自动 seo_description 应含产品名').toContain(name)
    await api.dispose()
  })

  // ── G3 反向护栏：**不覆盖已有 SEO**（`_auto_seo_on_publish` 只填空值） ──────
  test('G3b @write @local-only 非 draft→active 的保存**不得覆盖**已有 SEO（只填空值）', async ({ request }) => {
    const api = await staffApi(request)
    const code = catalogNo('G3B')
    const created = await api.post('/products/', {
      data: {
        name: `E2E G3b SEO ${code}`,
        catalog_no: code,
        slug: slug('G3B'),
        status: 'active',
        seo_title: 'CURATED TITLE',
        seo_description: 'CURATED DESC',
      },
    })
    await expectApi(created, { status: 201, label: 'G3b 夹具创建（active + 既有 SEO）' })
    const id = (await created.json()).data.id

    // 只改 name（**不是** draft→active 转换）⇒ 不应触发自动生成，更不得覆盖既有值
    await expectApi(await api.patch(`/products/${id}/`, { data: { name: `E2E G3b renamed ${code}` } }), {
      status: 200,
      label: 'G3b 只改 name',
    })
    expect(await productField(id, 'seo_title'), 'G3b 策展过的 seo_title 不得被覆盖').toBe('CURATED TITLE')
    expect(await productField(id, 'seo_description'), 'G3b 策展过的 seo_description 不得被覆盖').toBe('CURATED DESC')
    await api.dispose()
  })
})
