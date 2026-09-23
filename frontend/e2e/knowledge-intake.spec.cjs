/**
 * Knowledge Intake（研究员工作台 · 知识录入页）—— 真实 Playwright 覆盖
 *
 * 页面：`frontend/src/views/KnowledgeIntake.vue`，路由 `/workspace/knowledge-intake`（纯手写 `.ki-*` 组件）。
 * 后端：`POST /api/v1/knowledge-intake/`（`apps/knowledge/api/v1/intake_views.py`，`IsAdminUser` + `EnvelopeMixin`）
 *   ⇒ 成功 **200**（非 201），信封 `{success:true,data:{...},meta:{}}`。
 *   ⇒ 一次 POST 的写入（commit `14cbd43` 后）：`research_goal` / `application` / `method` / `protocol` 各 Δ+1，
 *      **四者状态一律 `draft`**（未经策展不得对外可见）；`product_method` Δ+1（`role` 默认 `reagent`，
 *      `bridges/models.py:30-33`）、`method_protocol` Δ+1。
 *   ⇒ 同名多行时（commit `1777fb3`）：`_get_or_create_unique` 抛 **409 conflict**（`AmbiguousKnowledgeName`），
 *      整个 `post()` 包在 `transaction.atomic()` 内 ⇒ **原子回滚，6 表 Δ0**。
 *   ⇒ 对外可见性（commit `14cbd43` 的价值）：公开读（匿名/非 staff）经 `apply_public_visibility` 仅见
 *      `status='active'`（Protocol 为 `published`）⇒ 以 `draft` 入库的新行**匿名不可见**。
 *   ⇒ DELETE（commit `17eeb66`）：`EnvelopeRenderer` 对 204/304 直接返回空字节 ⇒ Playwright `request`
 *      收 **204 且响应体为空**（不再抛 `Parse Error`）。
 * 判据层级（`e2e/README.md §6`）：L0 铁律 > L1 规格 > L2 代码现值；**期望值一律现算（API / DB 只读查询），不硬编码**。
 * 清理：写用例按捕获 id **逆序 DELETE**（protocol→method→application→research_goal），放 `finally`，
 *      **断言失败也必须清**；删 protocol/method 会级联清 `method_protocol` / `product_method`。
 *
 * ⚠️ 关键实测（2026-09-23，dev sqlite，只读核对）——与任务书的「6 表各 Δ+1」一致，但**有前提**：
 *   · GOAL_OPTIONS / APP_OPTIONS / METHOD_OPTIONS 里多数名字**在库中已存在或重名**；
 *   · 后端用 `_get_or_create_unique(name=...)`：**已存在的名字只复用（Δ0）、重名的名字直接 409**。
 *     故写路径用例**现算「库中不存在的候选」再点**（`pickAbsent`），否则断不出 Δ+1；
 *     B 用例则**现算「库中真实重名」**的名字再 POST（不硬编码某条重名，如 34/3443 之类）。
 *
 * 本机跑法（`e2e/README.md §1`）——必须串行、输出重定向到文件、显式 `--project=chromium`：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   test -f e2e/_pw.lock && echo "LOCK BUSY" || \
 *   node node_modules/@playwright/test/cli.js test e2e/knowledge-intake.spec.cjs \
 *     --project=chromium --retries=0 --output=test-results-ki1 > e2e/_ki.log 2>&1
 *   注意：不要在命令里用管道（`| tail` 会挂死）；用裸 `bash`/`npm`/`npx` 会被 WSL 别名劫持，直调 `node …/cli.js`。
 * 前置：本地 dev 已起（Django :8000 DB_ENGINE=sqlite / Vite :5173 **从 E: 物理路径启动**）。
 * 纪律：只新增本文件；不改应用代码、不 git commit；写操作只碰本次新建行（候选名均取自「库中不存在」），finally 硬删。
 */
const { test, expect, request } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS, CUST_USER, CUST_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, expectDelta, zeroSpec, expectNoWrites, consoleErrors } = require('./helpers/assertions.cjs')
const { dbQuery } = require('./helpers/db-snapshot.cjs')
const { RUN_TS } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const WL2 = [...WL, 'Failed to load resource']
const J = JSON.stringify
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

// ── 选择器（真实 DOM，KnowledgeIntake.vue）────────────────────────────
const ITEM = '.ki-product-item'
const SEARCH = 'input.ki-search'
/** 按 `.ki-section-title` 文案圈定区块（Goals / Applications / Methods / Protocol …） */
const section = (page, title) =>
  page.locator('.ki-section').filter({ has: page.locator('.ki-section-title', { hasText: title }) })
/** Confidence 区块用的不是标题而是裸 `<label>Confidence Level</label>`（:314） */
const confSection = (page) =>
  page.locator('.ki-section').filter({ has: page.locator('label', { hasText: 'Confidence Level' }) })

// ── D-DB 只读现算（禁止硬编码期望值）─────────────────────────────────
/** Knowledge Intake 的 6 张表计数快照（本地 dev sqlite；只读） */
const kiSnapshot = () =>
  dbQuery(
    `import json\n` +
      `from apps.knowledge.models import ResearchGoal, Application, Method, Protocol\n` +
      `from apps.bridges.models import ProductMethod, MethodProtocol\n` +
      `print('__SNAP__' + json.dumps({` +
      `'research_goal': ResearchGoal.objects.count(),` +
      `'application': Application.objects.count(),` +
      `'method': Method.objects.count(),` +
      `'protocol': Protocol.objects.count(),` +
      `'product_method': ProductMethod.objects.count(),` +
      `'method_protocol': MethodProtocol.objects.count(),` +
      `}))`
  )
/** 现算若干候选名在指定知识表中的行数（0=不存在，可安全新建；>1=重复，get_or_create 会 500） */
const nameCounts = (model, names) =>
  dbQuery(
    `import json\nfrom apps.knowledge.models import ${model} as M\n` +
      `names = ${J(names)}\n` +
      `print('__SNAP__' + json.dumps({n: M.objects.filter(name=n).count() for n in names}))`
  )
/** 按名取唯一 id（清理用）；返回 {count, id} */
const idByName = (model, name) =>
  dbQuery(
    `import json\nfrom apps.knowledge.models import ${model} as M\n` +
      `qs = M.objects.filter(name=${J(name)}).order_by('id')\n` +
      `print('__SNAP__' + json.dumps({'count': qs.count(), 'id': qs.values_list('id', flat=True).first()}))`
  )
/** 现算新建行的状态指纹 + product_method.role（不硬编码任何「新建即 active」的假设之外的值） */
const rowFingerprint = (gid, aid, mid, pid) =>
  dbQuery(
    `import json\nfrom apps.knowledge.models import ResearchGoal, Application, Method, Protocol\n` +
      `from apps.bridges.models import ProductMethod\n` +
      `print('__SNAP__' + json.dumps({` +
      `'goal': ResearchGoal.objects.get(id=${gid}).status,` +
      `'app': Application.objects.get(id=${aid}).status,` +
      `'method': Method.objects.get(id=${mid}).status,` +
      `'protocol': Protocol.objects.get(id=${pid}).status,` +
      `'pm_role': ProductMethod.objects.filter(method_id=${mid}).values_list('role', flat=True).first(),` +
      `}))`
  )
/** 从一组 chip 中现算「库中不存在」的第一个可点选项（保证 get_or_create 真新建 ⇒ Δ+1） */
async function pickAbsent(model, chipLoc) {
  const labels = (await chipLoc.allInnerTexts()).map((s) => s.trim())
  const counts = nameCounts(model, labels)
  const hit = labels.find((l) => counts[l] === 0)
  expect(hit, `${model} 需存至少一个「库中不存在」的候选（否则 get_or_create 复用，断不出 Δ+1）`).toBeTruthy()
  return hit
}
/** 现算某知识表中**真实重名**（count>1）的名字与重名数（B 用例用；不硬编码 34 之类）。
 *  返回 {name, c}；若无重名返回 null（B 用例将如实失败，而不是被放宽）。 */
function pickDuplicate(model) {
  return dbQuery(
    `import json\nfrom django.db.models import Count\nfrom apps.knowledge.models import ${model}\n` +
      `r = (${model}.objects.values('name').annotate(c=Count('id'))` +
      `.filter(c__gt=1).order_by('-c', 'name').first())\n` +
      `print('__SNAP__' + json.dumps(r))`
  )
}

test.describe('Knowledge Intake（/workspace/knowledge-intake）', () => {
  // 写路径用例含多次 spawn Python 取数（现算候选 + 快照 + 指纹），默认 45s 偏紧。
  test.describe.configure({ timeout: 120_000 })

  // ── K1 页面装载 ─────────────────────────────────────────────────────
  test('K1 @readonly @local-only 页面装载：列表非空、未选显空态、选中显表单头', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page)
    await goto(page, '/workspace/knowledge-intake')

    const items = page.locator(ITEM)
    await expect(items.first(), 'K1 产品列表应非空').toBeVisible({ timeout: 15000 })
    expect(await items.count(), 'K1 产品项 > 0').toBeGreaterThan(0)
    await expect(page.locator('.ki-empty'), 'K1 未选产品显示空态').toBeVisible()
    await expect(page.locator('.ki-form-area'), 'K1 未选产品不应有表单').toHaveCount(0)

    const first = items.first()
    const cat = (await first.locator('.ki-product-cat').innerText()).trim()
    const name = (await first.locator('.ki-product-name').innerText()).trim()
    await expectNoWrites(async () => { await first.click() }, 'K1 选中产品')
    console.log(`__E2E__ K1_SELECT ${J({ cat, name })}`)

    await expect(page.locator('.ki-form-area'), 'K1 选中后出现表单区').toBeVisible()
    await expect(page.locator('.ki-empty'), 'K1 选中后空态消失').toHaveCount(0)
    await expect(page.locator('.ki-product-header h2'), 'K1 头部 name 应等于所选项').toHaveText(name)
    await expect(page.locator('.ki-product-header .ki-catalog'), 'K1 头部 catalog 应等于所选项').toHaveText(cat)
    expect(errors).toEqual([])
  })

  // ── K2 过滤 ────────────────────────────────────────────────────────
  test('K2 @readonly @local-only 过滤：命中 catalog 前缀 ⇒ 可见非空子集；清空后恢复原数', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(req)
    const all = (await (await api.get('/products/', { params: { page_size: 200 } })).json()).data || []
    expect(all.length, 'K2 API 产品应非空').toBeGreaterThan(0)
    const prefix = String(all[0].catalog_no || '').slice(0, 4)
    expect(prefix.length, 'K2 首个产品应有 catalog_no 前缀').toBeGreaterThan(0)
    // 期望集合现场从 API 现算（与页面同一端点 / 同一 page_size，口径一致）
    const wantCats = new Set(
      all
        .filter((p) =>
          [p.category_l1, p.name, p.catalog_no].some((v) =>
            String(v || '').toLowerCase().includes(prefix.toLowerCase())
          )
        )
        .map((p) => p.catalog_no)
    )
    expect(wantCats.size, `K2 前缀 ${prefix} 应命中 >=1（现算）`).toBeGreaterThan(0)

    await loginAsStaff(page)
    await goto(page, '/workspace/knowledge-intake')
    const items = page.locator(ITEM)
    await expect(items.first(), 'K2 产品列表就绪').toBeVisible({ timeout: 15000 })
    const total = await items.count()

    await expectNoWrites(async () => { await page.locator(SEARCH).fill(prefix) }, 'K2 输入过滤')
    const vis = page.locator(ITEM)
    const visN = await vis.count()
    const visCats = (await vis.locator('.ki-product-cat').allInnerTexts()).map((s) => s.trim())
    console.log(`__E2E__ K2_FILTER ${J({ prefix, total, visN, expectSetSize: wantCats.size })}`)
    expect(visN, 'K2 过滤后可见项应非空').toBeGreaterThan(0)
    expect(visN, 'K2 过滤后应是子集（<= 原数）').toBeLessThanOrEqual(total)
    for (const c of visCats) {
      expect(wantCats.has(c), `K2 可见项 ${c} 应命中前缀 ${prefix}`).toBe(true)
    }

    await expectNoWrites(async () => { await page.locator(SEARCH).fill('') }, 'K2 清空过滤')
    await expect(vis, 'K2 清空后恢复原数').toHaveCount(total)
    await api.dispose()
    expect(errors).toEqual([])
  })

  // ── K3 chips 多选 / 单选语义 ────────────────────────────────────────
  test('K3 @readonly @local-only chips：Goals/Apps/Methods 各选区 active +1 且可取消；Confidence 恒 1', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page)
    await goto(page, '/workspace/knowledge-intake')
    const items = page.locator(ITEM)
    await expect(items.first(), 'K3 产品列表就绪').toBeVisible({ timeout: 15000 })
    await items.first().click()
    await expect(page.locator('.ki-form-area')).toBeVisible()

    const goals = section(page, 'Research Goals')
    const apps = section(page, 'Applications')
    const methods = section(page, 'Methods')
    const conf = confSection(page)

    await expectNoWrites(async () => {
      for (const [sec, label] of [[goals, 'Goals'], [apps, 'Apps'], [methods, 'Methods']]) {
        const before = await sec.locator('.ki-chip-active').count()
        const chip = sec.locator('.ki-chip').first()
        await chip.click()
        await expect(chip, `K3 ${label} 选中后应带 ki-chip-active`).toHaveClass(/ki-chip-active/)
        await expect(sec.locator('.ki-chip-active'), `K3 ${label} 选中后该区 active 应 +1`).toHaveCount(before + 1)
        await chip.click()
        await expect(sec.locator('.ki-chip-active'), `K3 ${label} 取消后应回到 ${before}`).toHaveCount(before)
        console.log(`__E2E__ K3_${label.toUpperCase()} ${J({ before })}`)
      }
    }, 'K3 chips 交互')

    // Confidence 单选：默认 high ⇒ 恰好 1 个 active；点 medium 仍恰好 1（不叠加）
    await expect(conf.locator('.ki-chip-active'), 'K3 Confidence 恰好 1 个 active').toHaveCount(1)
    await expect(conf.locator('.ki-chip-active'), 'K3 默认 Confidence=high').toHaveText('high')
    await conf.getByRole('button', { name: 'medium', exact: true }).click()
    await expect(conf.locator('.ki-chip-active'), 'K3 切 medium 后仍恰好 1').toHaveCount(1)
    await expect(conf.locator('.ki-chip-active'), 'K3 active=medium').toHaveText('medium')
    expect(errors).toEqual([])
  })

  // ── K4 核心写路径（含 A/D 断言 + 逆序清理）──────────────────────────
  test('K4 @write @local-only Save ⇒ 6 表各 Δ+1、状态 draft/draft/draft/draft、pm.role=reagent、匿名不可见；逆序清理 ⇒ Δ0', async ({ page, request: req }) => {
    const errors = consoleErrors(page, WL2)
    const api = await staffApi(req)
    const protoName = `E2E-KI-${RUN_TS}`
    let goalName = null
    let appName = null
    let methodName = null
    const before = kiSnapshot()
    let bodyErr = null
    let cleanup = null
    try {
      await loginAsStaff(page)
      await goto(page, '/workspace/knowledge-intake')
      const items = page.locator(ITEM)
      await expect(items.first(), 'K4 产品列表就绪').toBeVisible({ timeout: 15000 })
      const cat = (await items.first().locator('.ki-product-cat').innerText()).trim()
      await items.first().click()
      await expect(page.locator('.ki-form-area')).toBeVisible()

      const goals = section(page, 'Research Goals')
      const apps = section(page, 'Applications')
      const methods = section(page, 'Methods')
      const conf = confSection(page)

      // ★ 现算「库中不存在」的候选 ⇒ get_or_create 才会真新建
      goalName = await pickAbsent('ResearchGoal', goals.locator('.ki-chip'))
      appName = await pickAbsent('Application', apps.locator('.ki-chip'))
      methodName = await pickAbsent('Method', methods.locator('.ki-chip'))
      await goals.getByRole('button', { name: goalName, exact: true }).click()
      await apps.getByRole('button', { name: appName, exact: true }).click()
      await methods.getByRole('button', { name: methodName, exact: true }).click()
      await expect(goals.locator('.ki-chip-active')).toHaveCount(1)
      await expect(apps.locator('.ki-chip-active')).toHaveCount(1)
      await expect(methods.locator('.ki-chip-active')).toHaveCount(1)
      console.log(`__E2E__ K4_PICK ${J({ cat, goalName, appName, methodName, protoName })}`)

      await page.getByPlaceholder('e.g. CuAAC RNA Labeling Protocol').fill(protoName)
      await page.getByPlaceholder('1. Prepare RNA 2. Add reagents 3. Incubate 4. Purify').fill('E2E step 1; E2E step 2')
      await page.getByPlaceholder('CuSO4, THPTA, ascorbate, dye').fill('E2E materials')
      await page.getByPlaceholder('2 hours').fill('2 hours')
      await page.locator('select.ki-input').selectOption({ label: 'Advanced' })
      await page.getByPlaceholder('24151973, 25959142').fill('24151973')
      await page.getByPlaceholder('10.1038/nprot.2014.001').fill('10.1038/e2e.ki')
      await page.getByPlaceholder('High specificity; Bioorthogonal').fill('E2E advantage')
      await page.getByPlaceholder('Copper toxicity; Needs modified substrates').fill('E2E limitation')
      await conf.getByRole('button', { name: 'high', exact: true }).click()

      const [resp] = await Promise.all([
        page.waitForResponse(
          (r) => r.request().method() === 'POST' && r.url().includes('/api/v1/knowledge-intake/')
        ),
        page.locator('button.ki-btn-primary').click(),
      ])
      console.log(`__E2E__ K4_POST ${J({ status: resp.status(), url: resp.url() })}`)
      // A 断言：APIView + EnvelopeMixin ⇒ 成功 200（非 201）
      await expectApi(resp, { status: 200, label: 'K4 intake POST' })
      // U 断言：成功 toast 含所选集货号
      await expect(page.locator('.ki-toast.ok'), 'K4 toast 应含 catalog_no').toContainText(cat)

      // D 断言：6 表各 Δ+1
      const after = kiSnapshot()
      expectDelta(
        before,
        after,
        {
          research_goal: +1,
          application: +1,
          method: +1,
          protocol: +1,
          product_method: +1,
          method_protocol: +1,
        },
        'K4 六表 Δ+1'
      )

      // D 断言：新建行状态恰好 draft/draft/draft/draft（未经策展不得对外可见）+ bridge role=reagent
      const g = idByName('ResearchGoal', goalName)
      const a = idByName('Application', appName)
      const m = idByName('Method', methodName)
      const p = idByName('Protocol', protoName)
      expect([g.count, a.count, m.count, p.count], 'K4 新建行应各唯一').toEqual([1, 1, 1, 1])
      const fp = rowFingerprint(g.id, a.id, m.id, p.id)
      console.log(`__E2E__ K4_FINGERPRINT ${J(fp)} ids=${J({ g: g.id, a: a.id, m: m.id, p: p.id })}`)
      expect(fp, 'K4 新建行状态 / bridge role').toEqual({
        goal: 'draft',
        app: 'draft',
        method: 'draft',
        protocol: 'draft',
        pm_role: 'reagent',
      })

      // D 断言：**匿名**（无 token）按名检索，新建的 draft 行必须命中 0。
      //   正对照：同一检索用 staff 会话必须命中 1 ⇒ 证明「0」是**可见性过滤**而非「检索没匹配上」。
      //   口径：列表端点 `data` 是数组、总数在 `meta.pagination.count`（见契约）。
      const anon = await apiContext(null)
      const named = (arr, name) => (Array.isArray(arr) ? arr : []).filter((r) => (r.name || '') === name).length
      const anonGoalBody = await (await anon.get('/research-goals/', { params: { search: goalName, page_size: 50 } })).json()
      const anonProtoBody = await (await anon.get('/protocols/', { params: { search: protoName, page_size: 50 } })).json()
      const staffGoalBody = await (await api.get('/research-goals/', { params: { search: goalName, page_size: 50 } })).json()
      const staffProtoBody = await (await api.get('/protocols/', { params: { search: protoName, page_size: 50 } })).json()
      const vis = {
        anonGoal: named(anonGoalBody.data, goalName),
        anonProtocol: named(anonProtoBody.data, protoName),
        staffGoal: named(staffGoalBody.data, goalName),
        staffProtocol: named(staffProtoBody.data, protoName),
      }
      console.log(`__E2E__ K4_VISIBILITY ${J(vis)}`)
      await anon.dispose()
      expect(vis.anonGoal, `K4 匿名检索新 draft Goal(${goalName}) 应命中 0`).toBe(0)
      expect(vis.anonProtocol, `K4 匿名检索新 draft Protocol(${protoName}) 应命中 0`).toBe(0)
      expect(vis.staffGoal, 'K4 正对照：staff 检索同一 Goal 应命中 1').toBe(1)
      expect(vis.staffProtocol, 'K4 正对照：staff 检索同一 Protocol 应命中 1').toBe(1)
    } catch (e) {
      bodyErr = e
      throw e
    } finally {
      // ── 逆序硬删：protocol → method → application → research_goal ──
      //   删 protocol / method 级联清 method_protocol / product_method；
      //   按名现算 id ⇒ 即使 POST 后的断言先挂，也能把本次新建的行收回（候选名均取自「库中不存在」）。
      // ★ C 修复后改硬断言（commit 17eeb66）：DELETE 必须回 **204 且响应体为空**。
      //   这里**不再吞解析异常**——吞掉就等于把「204 带 body」这道闸门关掉。若该修复回退，
      //   Playwright 解析报 `Parse Error` / 状态码非 204 / body 非空，本处都会当场红（不再掩盖）。
      const del = async (resource, model, name) => {
        if (!name) return [`${model}=${name}`, 'skip-null']
        const { count, id } = idByName(model, name)
        if (!count || !id) return [`${model}=${name}`, 'absent']
        const r = await api.delete(`/${resource}/${id}/`)
        const bodyText = await r.text()
        expect(r.status(), `C: DELETE /${resource}/${id}/ 应回 204`).toBe(204)
        expect(bodyText, `C: DELETE /${resource}/${id}/ 的 204 响应体必须为空`).toBe('')
        return [`${model}=${name}`, id, r.status(), bodyText.length]
      }
      cleanup = []
      cleanup.push(await del('protocols', 'Protocol', protoName))
      cleanup.push(await del('methods', 'Method', methodName))
      cleanup.push(await del('applications', 'Application', appName))
      cleanup.push(await del('research-goals', 'ResearchGoal', goalName))

      const final = kiSnapshot()
      const deltas = Object.fromEntries(Object.keys(before).map((k) => [k, final[k] - before[k]]))
      console.log(`__E2E__ K4_CLEANUP ${J(cleanup)} deltas=${J(deltas)}`)
      // 断言失败也不掩盖根因：仅在主流程已通过时才断「清理后 Δ0」（deltas 始终打印）
      if (!bodyErr) expectDelta(before, final, zeroSpec(before), 'K4 清理后六表 Δ0')
      await api.dispose()
    }
    expect(errors).toEqual([])
  })

  // ── KB（commit 1777fb3）同名多行 ⇒ 409 拒收 + 原子回滚（6 表 Δ0）──────
  test('KB @readonly @local-only B：同名多行 ⇒ POST 409(meta.error.message 含 Ambiguous 与实际重名数) 且 6 表 Δ0', async ({ request: req }) => {
    const api = await staffApi(req)
    const before = kiSnapshot()
    // 现算「真实重名」的 Method 名（count>1）——不硬编码 34 之类，也不硬编码某个具体名字
    const dup = pickDuplicate('Method')
    expect(dup && dup.c > 1, `KB 需库中存在 count>1 的 Method 名（现算），实际 ${J(dup)}`).toBeTruthy()
    // 目标产品：现算一个真实存在的产品 id（不硬编码 66）
    const prodBody = await (await api.get('/products/', { params: { page_size: 1 } })).json()
    const pid = (prodBody?.data || [])[0]?.id
    expect(pid, 'KB 需库中至少一个产品').toBeTruthy()

    const resp = await api.post('/knowledge-intake/', { data: { product_id: pid, methods: [dup.name] } })
    const body = await resp.json()
    const msg = String(body?.meta?.error?.message || '')
    console.log(`__E2E__ KB_409 ${J({ pid, dupName: dup.name, dupCount: dup.c, status: resp.status(), code: body?.meta?.error?.code, msg })}`)
    await expectApi(resp, { status: 409, json: { 'meta.error.code': 'conflict' }, label: 'KB 同名多行' })
    expect(msg, 'KB 409 消息应含 Ambiguous').toContain('Ambiguous')
    expect(msg, `KB 409 消息应含与库中一致的重名数 ${dup.c}`).toContain(String(dup.c))

    // 原子回滚：请求前后 6 表 Δ0（不得因 409 之前的部分写入而留下半成品）
    expectDelta(before, kiSnapshot(), zeroSpec(before), 'KB 409 原子回滚 Δ0')
    await api.dispose()
  })

  // ── KC（commit 17eeb66）DELETE ⇒ 204 且响应体为空（RFC 9110）────────────
  test('KC @write @local-only C：DELETE E2E- 夹具 ⇒ 204 且响应体为空；前后 6 表 Δ0', async ({ request: req }) => {
    const api = await staffApi(req)
    const name = `E2E-C-${RUN_TS}`
    const before = kiSnapshot()
    let id = null
    try {
      const cr = await api.post('/protocols/', { data: { name } })
      await expectApi(cr, { status: 201, label: 'KC 建协议夹具' })
      id = (await cr.json())?.data?.id ?? null
      expect(id, 'KC 夹具协议应返回 id').toBeTruthy()

      // ★ 严格断言：这是"204 不得带 body"这条闸门本身（不再吞任何解析异常）
      const dr = await api.delete(`/protocols/${id}/`)
      const body = await dr.text()
      console.log(`__E2E__ KC_DELETE ${J({ id, status: dr.status(), contentLength: dr.headers()['content-length'], bodyLen: body.length, body })}`)
      expect(dr.status(), 'KC DELETE 应回 204').toBe(204)
      expect(body, 'KC 204 响应体必须为空字节（RFC 9110）').toBe('')
      id = null // 已确认删除 ⇒ 无需再收尾
    } finally {
      if (id) {
        try { await api.delete(`/protocols/${id}/`) } catch (e) { console.warn(`__E2E__ KC_CLEANUP_FAIL ${String(e.message).slice(0, 120)}`) }
      }
      expectDelta(before, kiSnapshot(), zeroSpec(before), 'KC 前后 6 表 Δ0')
      await api.dispose()
    }
  })

  // ── KE（commit 28446c8 / 0f0640e）Copy to Similar：上限内逐条、超限先拒──────
  //   ★ 用 `page.route()` 伪造 `/api/v1/products/` 列表来构造「同类产品数」⇒ **不依赖 dev 库**；
  //     同时拦截 `POST /api/v1/knowledge-intake/` ⇒ **绝不真写库**（只数请求数），跑完 6 表 Δ0。
  //   同类数定义（`KnowledgeIntake.vue:135-138`）：同 `product_class_id` 且 `id !== 选中项`。
  const fakeProducts = (n, cls) =>
    Array.from({ length: n }, (_, i) => ({
      id: 900000 + cls + i, catalog_no: `E2E-FAKE-${cls}-${i}`, name: `E2E Fake Product ${cls}-${i}`,
      product_class_id: cls, category_l1: 'E2E',
    }))

  test('KE1 @readonly @local-only E-上限内：同类=1 ⇒ 弹 1 次确认 + POST 恰好 1 次 + 文案 Copied to 1 of 1 (0 failed)', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    const before = kiSnapshot()
    let posts = 0
    let dialogs = 0
    await loginAsStaff(page)
    // 路由在 login 之后注册、goto 之前生效 ⇒ 只影响本页拉取
    await page.route((u) => u.pathname === '/api/v1/products/', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json',
        body: J({ success: true, data: fakeProducts(2, 71001), meta: {} }) }))
    await page.route((u) => u.pathname === '/api/v1/knowledge-intake/', (route) => {
      if (route.request().method() === 'POST') posts++
      route.fulfill({ status: 200, contentType: 'application/json',
        body: J({ success: true, data: {}, meta: {} }) })
    })
    page.on('dialog', (d) => { dialogs++; d.accept() })

    await goto(page, '/workspace/knowledge-intake')
    const items = page.locator(ITEM)
    await expect(items.first(), 'KE1 伪造列表应渲染').toBeVisible({ timeout: 15000 })
    expect(await items.count(), 'KE1 恰好 2 个产品').toBe(2)
    await items.first().click()
    await expect(page.locator('.ki-form-area')).toBeVisible()

    await page.locator('button.ki-btn-outline').click()
    await expect(page.locator('.ki-toast.ok'), 'KE1 结果文案').toHaveText('Copied to 1 of 1 (0 failed)', { timeout: 10000 })
    console.log(`__E2E__ KE1 ${J({ posts, dialogs })}`)
    expect(posts, 'KE1 POST /knowledge-intake 应恰好 1 次').toBe(1)
    expect(dialogs, 'KE1 应弹 1 次 confirm').toBe(1)
    expectDelta(before, kiSnapshot(), zeroSpec(before), 'KE1 未真写库 Δ0')
    expect(errors).toEqual([])
  })

  test('KE2 @readonly @local-only E-超上限：同类=51 ⇒ 不弹 confirm + POST 0 次 + 错误提示含 51/50', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    const before = kiSnapshot()
    let posts = 0
    let dialogs = 0
    await loginAsStaff(page)
    // 52 个同 `product_class_id` 产品、选 1 个 ⇒ 同类 = 51（> 上限 50）⇒ 走「先判上限」分支
    await page.route((u) => u.pathname === '/api/v1/products/', (route) =>
      route.fulfill({ status: 200, contentType: 'application/json',
        body: J({ success: true, data: fakeProducts(52, 71002), meta: {} }) }))
    await page.route((u) => u.pathname === '/api/v1/knowledge-intake/', (route) => {
      if (route.request().method() === 'POST') posts++
      route.fulfill({ status: 200, contentType: 'application/json',
        body: J({ success: true, data: {}, meta: {} }) })
    })
    page.on('dialog', (d) => { dialogs++; d.accept() })

    await goto(page, '/workspace/knowledge-intake')
    const items = page.locator(ITEM)
    await expect(items.first(), 'KE2 伪造列表应渲染').toBeVisible({ timeout: 15000 })
    expect(await items.count(), 'KE2 恰好 52 个产品').toBe(52)
    await items.first().click()
    await expect(page.locator('.ki-form-area')).toBeVisible()

    await page.locator('button.ki-btn-outline').click()
    const toast = page.locator('.ki-toast.err')
    await expect(toast, 'KE2 应出错误提示').toBeVisible({ timeout: 10000 })
    await expect(toast, 'KE2 提示应含实际同类数 51').toContainText('51')
    await expect(toast, 'KE2 提示应含硬上限 50').toContainText('50')
    console.log(`__E2E__ KE2 ${J({ posts, dialogs, text: (await toast.innerText()).trim() })}`)
    expect(posts, 'KE2 超限不得发起任何 POST').toBe(0)
    expect(dialogs, 'KE2 超限不得弹 confirm（实现是「先判上限再弹确认」）').toBe(0)
    expectDelta(before, kiSnapshot(), zeroSpec(before), 'KE2 未真写库 Δ0')
    expect(errors).toEqual([])
  })

  // ── K5 负向权限（A 断言 + D 零写入）────────────────────────────────
  test('K5 @readonly @local-only 负向权限：匿名 POST ⇒ 401 unauthorized；普通用户 POST ⇒ 403 forbidden', async ({ request: req }) => {
    const before = kiSnapshot()
    const anon = await apiContext(null)
    await expectApi(await anon.post('/knowledge-intake/', { data: {} }), {
      status: 401,
      json: { 'meta.error.code': 'unauthorized' },
      label: 'K5 匿名',
    })

    const token = await getToken(req, CUST_USER, CUST_PASS)
    expect(token, 'K5 e2e_customer 应能登录拿到 token').toBeTruthy()
    const cust = await apiContext(token)
    await expectApi(await cust.post('/knowledge-intake/', { data: {} }), {
      status: 403,
      json: { 'meta.error.code': 'forbidden' },
      label: 'K5 普通用户',
    })

    expectDelta(before, kiSnapshot(), zeroSpec(before), 'K5 负向零写入')
    console.log('__E2E__ K5_NEG_DONE anon=401 customer=403')
    await anon.dispose()
    await cust.dispose()
  })

  // ── K6 负向入参（A 断言 + D 零写入）────────────────────────────────
  test('K6 @readonly @local-only 负向入参：缺 product_id ⇒ 400(含 product_id)；product_id=99999999 ⇒ 404', async ({ request: req }) => {
    const api = await staffApi(req)
    const before = kiSnapshot()

    const r1 = await api.post('/knowledge-intake/', { data: {} })
    await expectApi(r1, { status: 400, json: { 'meta.error.code': 'error' }, label: 'K6 缺 product_id' })
    const msg1 = String((await r1.json())?.meta?.error?.message || '')
    expect(msg1, 'K6 400 消息应含 product_id').toContain('product_id')

    const r2 = await api.post('/knowledge-intake/', { data: { product_id: 99999999 } })
    await expectApi(r2, { status: 404, json: { 'meta.error.code': 'error' }, label: 'K6 不存在产品' })
    const msg2 = String((await r2.json())?.meta?.error?.message || '')
    expect(msg2, 'K6 404 消息应含 Product not found').toContain('Product not found')

    expectDelta(before, kiSnapshot(), zeroSpec(before), 'K6 负向零写入')
    console.log(`__E2E__ K6_NEG_DONE ${J({ m400: msg1, m404: msg2 })}`)
    await api.dispose()
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（纠错 / 纠偏 / 记录）
 *
 * #1【记录】「一次 POST ⇒ 6 表各 Δ+1」**有前提**：`intake_views.py` 用
 *     `_get_or_create_unique(name=...)`（commit 1777fb3）⇒ **已存在的名字只复用（Δ0）、重名的名字 409**
 *     （旧版 `get_or_create` 遇重名会 `MultipleObjectsReturned`(500)，现被显式拒收）。
 *     ⇒ 本 spec 的写路径**现算「库中不存在」的候选再点**（`pickAbsent`）；
 *     B 用例**现算「库中真实重名」的名字**再 POST（`pickDuplicate`），重名数亦现算比对其消息。
 *     这是断言口径（逐条现算），不是放宽。
 *
 * #2【记录】该页 `selectProduct()`（`KnowledgeIntake.vue:87-105`）行内注释写「Load existing knowledge
 *     data if any」，实际**把表单清空、从不加载既有知识** ⇒ 本页无法查看/编辑既有知识；
 *     重存走 `_get_or_create_unique` **静默复用**既有行（不报错、不更新）。**仅记录，不作为缺陷断言**。
 *
 * #3【已覆盖】`copyToSimilar()`（`KnowledgeIntake.vue:133-177`）本轮补上可复现断言 KE1/KE2：
 *     用 `page.route()` 伪造 `/api/v1/products/` 构造同类数、并拦截 `POST /knowledge-intake/` 使其
 *     **绝不真写库** ⇒ 断「上限内逐条 POST + 计数文案」「超限先拒、不弹确认、POST=0」。
 *     （此前只有一次性 ad-hoc 探针，不算资产。）
 *
 * #4【记录】写用例创建的是**固定名 chip 对应的知识实体**（如 `RNA Modification`），非 `E2E-` 前缀；
 *     这是被测功能的既有语义（chip 文案是应用常量）。清理按**现算 id** 逆序硬删，故不触碰任何既有真实行
 *     （候选名均现算自「库中不存在」）。`E2E-KI-<ts>` / `E2E-C-<ts>` 仅用于 Protocol 名。
 * ──────────────────────────────────────────────────────────────────────── */
