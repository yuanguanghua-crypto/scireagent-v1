/**
 * 研究员工作台 · **知识实体治理 5 页**（Goals / Applications / Methods / Protocols / References）
 *
 * 来源：全工作台动作普查（`2026-09-23_全工作台动作普查.md`）判定这 5 页**同一模板**。
 *
 * ★ 标记**已逐页取证**（5 页的列表/名称格/名称字段**完全一致**——曾因只验 Goals 就外推而误判"不同构"）：
 *   · 列表：`table.entity-table > tbody tr`，但 **`v-else-if="entities.length"`** ⇒ **数据到达前表格不存在**
 *     ⇒ **必须先轮询等待**，不能在 `goto` 后立刻数行数（这是我第一版的真错因）
 *   · 名称单元格 `td.col-name` · 编辑器 `.dialog`（`v-if="showEditor"`）· 名称输入 `.dialog input.input-full`
 *   · 按钮 `Cancel` / `Save`（保存中 `Saving...`）/ 行内 `Edit` · 编辑器标题 `{{ editing ? 'Edit' : 'New' }} <X>`
 *   · 预填断言**必须用 `toHaveValue`**（读 DOM property）—— `input[value=…]` 是 HTML 属性，Vue 绑定不同步
 *
 * ★★ 实测出的**产品事实**：治理页列表**最多渲染 200 行且无截断提示**（`Goal API=500 DOM=200`）⇒ 与覆盖矩阵 §3.3 G3 同类。
 *   本 spec 用 `== min(API, 200)` **钉住**该行为并打印 `API/DOM` 供核查。
 *
 * 动作空间（阶段 1 结论，**已封闭**）：列表 + 4 个处理器 + 编辑器字段；**UI 层无删除动作**。
 * 环境 tier：本地真实写 ⇒ 生产侧维持只读。夹具自清：`DELETE /<resource>/{id}/`（`ModelViewSet`+router，已核实）。
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { consoleErrors } = require('./helpers/assertions.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))
const rows = (page) => page.locator('table.entity-table tbody tr')
const dlg = (page) => page.locator('.dialog')
const nameInput = (page) => dlg(page).locator('input.input-full').first()

/** 计数用 **API 现算**（禁硬编码；也不猜模型类名/表名）
 *  ★ 2026-11-18：`params` 必须传**页面自己的口径** —— ReferencesPage 的列表带
 *    `include_test_fixtures=1`（它要显示/清理夹具残骸），而本函数不传时拿到的是
 *    排除夹具后的数量。实测差异：reference 表 219 行，排除 32 条夹具后 API=187，
 *    页面 DOM 却渲染 200 ⇒ `dom0 <= n0` 断言假红（与渲染无关，纯口径不一致）。 */
async function countViaApi(api, path, params = {}) {
  const body = await (await api.get(path, { params: { page_size: 500, ...params } })).json()
  const d = body?.data
  return (Array.isArray(d) ? d : d?.results || []).length
}

/** 总数用 **`meta.pagination.count`** 现算 —— 与组件所读的信封字段**同源**（禁硬编码 11028 之类）
 *  `params` 用于复现**页面自己的口径**（★ 2026-11-18：四页默认只看公开态，
 *  见下方 `publicStatus`；不传的话拿到的是 staff 全量，与页面上的数字不是同一个东西）。 */
async function totalViaApi(api, path, params = {}) {
  const body = await (await api.get(path, { params: { page_size: 1, ...params } })).json()
  return body?.meta?.pagination?.count ?? null
}

/**
 * ★ 2026-11-18（S4 / A-066 + A-014）新增三个字段：
 *  · `publicStatus` —— 页面「Show drafts」关着时显式传的 status（四页各自模型的公开态）。
 *    Protocol 用自有 `PublicationStatus`（公开态是 `published`，`active` 恒为 0）；
 *    其余三个用 `StatusMixin`（公开态是 `active`）。
 *  · `paginated` —— 该页是否已改真分页。`Reference` 本轮**未改造**，仍是
 *    「page_size=200 + 静默截断横幅」的旧行为，故保留旧断言分支。
 *  · `apiParams` —— 页面自己额外带的查询参数（目前只有 ReferencesPage 的
 *    `include_test_fixtures=1`），用于让 API 现算与 DOM 口径对齐。
 */
const ENTITIES = [
  { noun: 'Goal', page: '/workspace/goals', api: '/research-goals/', publicStatus: 'active', paginated: true },
  { noun: 'Application', page: '/workspace/applications', api: '/applications/', publicStatus: 'active', paginated: true },
  { noun: 'Method', page: '/workspace/methods', api: '/methods/', publicStatus: 'active', paginated: true },
  { noun: 'Protocol', page: '/workspace/protocols', api: '/protocols/', publicStatus: 'published', paginated: true },
  {
    noun: 'Reference',
    page: '/workspace/references',
    api: '/references/',
    publicStatus: null,
    paginated: false,
    apiParams: { include_test_fixtures: 1 },
  },
]

/** 治理页一页多少行（`useEntityList` 的 `pageSize` 默认值，改动需同步本常量） */
const PAGE_SIZE = 50

for (const e of ENTITIES) {
  // ★ `Goal` 曾因**真实缺陷 E1**（Detail 序列化器把 slug 视为必填、而表单无此字段 ⇒ 新建必 400）标 fixme；
  //   该缺陷已修（`ResearchGoalDetailSerializer` 补宽容 slug 声明，与 List 版一致 ⇒ 交给模型 `save()` 自动生成）
  //   ⇒ 本用例即该修复的**闸门**，故转正。若将来又红，先查 E1 是否回退。
  const t = test
  t(`${e.noun} 治理页：列表渲染 / +New / Cancel 零写入 / Save 写库 / Edit 预填`, { tag: ['@write', '@local-only'] }, async ({ page, request }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(request)
    const uniq = `E2E-${e.noun}-${Date.now()}`
    let createdId = null
    const newBtn = page.getByRole('button', { name: new RegExp(`\\+ New ${e.noun}`) }).first()
    try {
      await loginAsStaff(page)
      await goto(page, e.page)

      // ① 列表渲染行数 —— **轮询**等待（`v-else-if="entities.length"` ⇒ 数据到达前无表格）
      //   ★ 实测：渲染上限**并非统一 200**（Goals/Apps/Methods=200，Protocol 达 500）⇒ **不假设上限**，
      //     只断"渲染出了行" 且 "不超过 API 总数"，并把 API/DOM 打印出来**记录各页实际上限**（供后续核查）。
      const n0 = await countViaApi(api, e.api, e.apiParams)
      await expect
        .poll(async () => rows(page).count(), { timeout: 25000, intervals: [300, 600, 1000] })
        .toBeGreaterThan(0)
      const dom0 = await rows(page).count()
      expect(dom0, `${e.noun} 渲染行数不应超过 API 总数`).toBeLessThanOrEqual(n0)
      console.log(`__E2E__ ${e.noun} 列表 API=${n0} DOM=${dom0}${dom0 < n0 ? '（有渲染上限，静默截断）' : '（全量渲染）'}`)

      // ①b 分页 / 截断提示
      //    ★ 2026-11-18（S4 / A-014）行为已变更：Goals/Applications/Methods/Protocols
      //      四页从「page_size 硬编码 200/500 + 一句 Showing first N of M records」
      //      改为**真分页**（50/页 + el-pagination）。用户终于能翻到第 N+1 行。
      //      ⇒ 截断横幅必须**消失**：留着等于把「有 28568 条但你只看得到 50 条」说了两遍，
      //        且两处数字来源不同（横幅读 API count、分页器读同一 count 的人工派生）⇒ 必然打架。
      //      ⇒ 总量超过一页时必须渲染分页器（否则等于换了皮、仍然没有翻页能力）。
      //    Reference 页本轮未改造，走下面的旧分支（保留它对「静默截断」的既有闸门）。
      // ★ 口径必须**两个都带**：页面自己的额外参数（Reference 的 include_test_fixtures）
      //   与页面默认的公开态过滤。只带后者会让 Reference 的 total 少 32 条夹具，
      //   于是 `expectTruncated` 判成 false，反过来要求一个明明存在的横幅消失。
      const pageParams = {
        ...(e.apiParams || {}),
        ...(e.publicStatus ? { status: e.publicStatus } : {}),
      }
      const total0 = await totalViaApi(api, e.api, pageParams)
      const hint = page.locator('[data-testid="truncation-hint"]')
      if (e.paginated) {
        await expect(hint, `${e.noun} 已改真分页，不应再有静默截断横幅`).toHaveCount(0)
        if (total0 > PAGE_SIZE) {
          await expect(
            page.locator('.entity-page .el-pagination'),
            `${e.noun} 总数 ${total0} > 一页(${PAGE_SIZE}) 时必须渲染分页器`,
          ).toHaveCount(1, { timeout: 10000 })
        }
        console.log(`__E2E__ ${e.noun} 分页 API=${total0} DOM=${dom0} 每页=${PAGE_SIZE}`)
      } else {
        // ★ 旧行为（Reference）：未截断的页该元素必须不存在；有截断则文案两个数字都用现算。
        const expectTruncated = total0 > dom0
        if (expectTruncated) {
          await expect(hint, `${e.noun} 有静默截断时应显示提示`).toBeVisible({ timeout: 10000 })
          await expect(hint, `${e.noun} 提示文案应为「Showing first <DOM> of <API> records」`)
            .toHaveText(`Showing first ${dom0} of ${total0} records`)
        } else {
          await expect(hint, `${e.noun} 未截断时不应出现提示`).toHaveCount(0)
        }
        console.log(`__E2E__ ${e.noun} 截断提示 API=${total0} DOM=${dom0} 显示=${expectTruncated}`)
      }

      // ② `+ New <X>` ⇒ 编辑器出现，标题为 New 形态
      await newBtn.click()
      await expect(dlg(page), `点 + New ${e.noun} 后应出现编辑器`).toHaveCount(1, { timeout: 10000 })
      await expect(dlg(page).locator('h3'), '新建态标题应含 New').toContainText('New')

      // ④ `Cancel` ⇒ 关闭 **且零写入**
      const nBeforeCancel = await countViaApi(api, e.api, e.apiParams)
      await dlg(page).getByRole('button', { name: 'Cancel' }).click()
      await expect(dlg(page), 'Cancel 后编辑器应关闭').toHaveCount(0, { timeout: 10000 })
      expect(await countViaApi(api, e.api, e.apiParams), 'Cancel 不得产生任何写入').toBe(nBeforeCancel)

      // ⑤ Save（新建）⇒ POST 2xx + API 计数 Δ+1
      //   ⚠️ 不断"列表出现新行"：本页只渲染前 200 行，新行**可能没被渲染** ⇒ 断它会得到与实现无关的假失败。
      //   ⚠️ 若 POST 非 2xx，**把响应体打出来**（自证，不要只说"400"）。
      await newBtn.click()
      await expect(dlg(page)).toHaveCount(1, { timeout: 10000 })
      await nameInput(page).fill(uniq)
      const [resp] = await Promise.all([
        page.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes(e.api)),
        dlg(page).getByRole('button', { name: 'Save' }).click(),
      ])
      if (resp.status() >= 300) {
        console.log(`__E2E__ ${e.noun} POST ${resp.status()} BODY=${String(await resp.text()).slice(0, 400)}`)
      }
      expect(resp.status(), `${e.noun} 新建的 POST 应 2xx`).toBeLessThan(300)
      createdId = (await resp.json())?.data?.id ?? null
      // ★ 写库证据**不用"总计数 Δ+1"**：本数据集已达 500+，而 `page_size` **封顶 500** ⇒ 总数**测不出 Δ**（我的测法有错）。
      //   改用**存在性**：按唯一名检索应恰好 1 条 —— 这是"真写进去了"的可靠证据，且与总量无关。
      //   ★ 2026-11-18（S4）：**必须带 `include_unpublished=1`**。新建实体的 `status` 默认是
      //     `draft`（`core/models.py` StatusMixin / Protocol.PublicationStatus 都是 default=draft），
      //     而 MethodViewSet / ProtocolViewSet 的 list 端点对 staff 也套「方案 B」过滤
      //     ⇒ 不带这个参数时，刚建好的草稿**检索不到**（实测 Method/Protocol 恒 0 条，
      //     Goal/Application 因为后端没做方案 B 才侥幸为 1）。这是**检索口径**问题，
      //     不是「没写进去」—— 本用例要验的是后者。
      const body = await (await api.get(e.api, {
        params: { search: uniq, page_size: 20, include_unpublished: 1 },
      })).json()
      const arr = Array.isArray(body?.data) ? body.data : body?.data?.results || []
      expect(arr.filter((x) => (x.name || x.title) === uniq).length,
        `${e.noun} 新建后应能按唯一名检索到 1 条`).toBe(1)

      // ③⑥ 行内 `Edit` 的**预填**（★只断"编辑器出现"是必要不充分）
      //   取第一条已渲染的行（顺序无关，不依赖我新建那条是否被渲染）⇒ 现算其名称 ⇒ 断预填值 == 该名称
      const firstRow = rows(page).first()
      const firstName = (await firstRow.locator('td.col-name').innerText()).trim()
      await firstRow.getByRole('button', { name: 'Edit' }).click()
      await expect(dlg(page), 'Edit 后应出现编辑器').toHaveCount(1, { timeout: 10000 })
      await expect(dlg(page).locator('h3'), '编辑态标题应含 Edit').toContainText('Edit')
      await expect(nameInput(page), `${e.noun} Edit 应把既有值预填（现算：${firstName}）`).toHaveValue(firstName)
      await dlg(page).getByRole('button', { name: 'Cancel' }).click()
      await expect(dlg(page), '取消编辑后应关闭').toHaveCount(0, { timeout: 10000 })

      expect(errors).toEqual([])
    } finally {
      if (createdId) await api.delete(`${e.api}${createdId}/`).catch(() => {})
      await api.dispose()
    }
  })
}

/**
 * ★ 修 B 的回归闸门（**已转正**）：`ReferencesPage` 的 **Citation** 输入框必须能读。
 *
 * 背景：页面原先用 `citation` 作表单键，而模型字段与 `ReferenceSerializer.fields` 都是
 * **`citation_text`** ⇒ 该输入框「读恒空、写被 DRF 静默忽略」（死字段）。已一并修为 `citation_text`；
 * 同批还修了 Source Type 下拉：原把后端的 `web` 写成了 **`website`**（选它保存必 400）且缺 `thesis`。
 */
test('References 治理页：Edit 应把 citation_text 预填进 Citation 框',
  { tag: ['@readonly', '@local-only'] }, async ({ page, request }) => {
    const api = await staffApi(request)
    try {
      await loginAsStaff(page)
      await goto(page, '/workspace/references')
      await expect
        .poll(async () => rows(page).count(), { timeout: 25000, intervals: [300, 600, 1000] })
        .toBeGreaterThan(0)
      const row = rows(page).first()
      const rid = Number((await row.locator('td').first().innerText()).trim())
      const detail = await (await api.get(`/references/${rid}/`)).json()
      const expectText = (detail?.data ?? detail)?.citation_text || ''
      await row.getByRole('button', { name: 'Edit' }).click()
      await expect(dlg(page)).toHaveCount(1, { timeout: 10000 })
      // 表单里第 4 个 `.input-full` = Citation（前三为 Title / URL / DOI）
      await expect(dlg(page).locator('.input-full').nth(3), 'Citation 应预填 citation_text')
        .toHaveValue(expectText)
    } finally {
      await api.dispose()
    }
  })

/**
 * ★ 修 ① 的闸门（**已转正**）：`MethodsPage` 的 **Purpose** 必须能读。
 *
 * 根因（已修）：`MethodViewSet.get_serializer_class()` 此前**只在 `retrieve` 走 Detail**，
 * create/update 走 `MethodListSerializer`（其 `Meta.fields` **不含 `purpose`**）
 * ⇒ 列表行读不到（输入框恒空）、PUT 里带的 `purpose` 被 DRF 静默忽略。
 * 修法（对齐 `ResearchGoalViewSet` 的既有正确模式）：**写路径改走 Detail** + Detail 补**宽容 slug**
 * （否则 400 `slug is required`，与 E1 同型）+ 本页 `openEdit` **拉详情预填**。
 * 写侧契约由后端 `test_protocol_reference_write_gates.py::MethodPurposeWriteTest` 钉住；本用例只验**读/预填**。
 */
test('Method 治理页：Edit 应把 purpose 预填进 Purpose 框',
  { tag: ['@readonly', '@local-only'] }, async ({ page, request }) => {
    const api = await staffApi(request)
    try {
      await loginAsStaff(page)
      await goto(page, '/workspace/methods')
      await expect
        .poll(async () => rows(page).count(), { timeout: 25000, intervals: [300, 600, 1000] })
        .toBeGreaterThan(0)
      const row = rows(page).first()
      const mid = Number((await row.locator('td').first().innerText()).trim())
      const detail = await (await api.get(`/methods/${mid}/`)).json()
      const expectPurpose = (detail?.data ?? detail)?.purpose || ''
      await row.getByRole('button', { name: 'Edit' }).click()
      await expect(dlg(page)).toHaveCount(1, { timeout: 10000 })
      // 对话框里唯一的 textarea = Purpose（Name 是 input.input-full）
      await expect(dlg(page).locator('textarea.input-full').first(), 'Purpose 应预填后端 purpose')
        .toHaveValue(expectPurpose)
    } finally {
      await api.dispose()
    }
  })

/**
 * ★ 5 个治理页的 **PUT（编辑保存）** 覆盖 —— 此前 P1 缺口：
 *   全 e2e 对这 5 个端点 **零 PUT 覆盖**（所有 PUT 都打在 `/products/`）。
 *
 * 数据安全设计（三条，均踩过坑）：
 *  1) **目标行 = 首行**：列表按排序键升序（priority/sort_order/id/-version/-year）且 UI 有渲染上限
 *     （Goals/Apps/Methods=200、Protocol=500）⇒ 自建夹具 id 最大 ⇒ **不保证被渲染** ⇒ 只能编辑既有首行。
 *  2) **只改 Name**，finally 用**页面自己发出的 PUT 载荷**（`page.on('request')` 捕获 `postDataJSON()`）
 *     把原名写回 ⇒ 不手拼 per-entity 载荷（避免漏字段）。
 *  3) 还原必须写成 `api.put(url, { data: {...} })` —— Playwright 的选项对象在**第二参**；
 *     把 body 直接当第二参会**静默不发 body**（本用例第一版即踩此坑 ⇒ 首行被留成改名值）。
 *
 * ⚠️ 已知缺陷 / 挂起原因（**历史**，两条均已处置）：
 *  · `Reference` 的 `PUT 400 source_type=pubmed` **已修**（序列化器层并入 `pubmed`，不动模型）⇒ 已转正。
 *  · `Protocol` 的 `PUT 500 NameError(MethodProtocol 未导入)` **已修**（补模块级导入）；
 *    但随后暴露**夹具副作用**：协议 PUT 会按单选下拉刷新该协议的 `explicit` 桥，而旧写法只还原
 *    **名字**、桥**无回收接口** ⇒ 跑一次就在首行协议上留一条 explicit 桥。
 *    **2026-09-24 已转正** —— 改为**自建夹具**（`version='9999'` 抢首行，`DELETE` 靠 CASCADE 连桥一起回收），
 *    见本文件末尾 `Protocol 治理页：自建夹具 …（零残留）`。⇒ **本组已无 fixme**。
 */
for (const e of ENTITIES.filter((x) => x.noun !== 'Protocol')) {
  test(`${e.noun} 治理页：Edit → Save 走 PUT 且落库`,
    { tag: ['@write', '@local-only'] }, async ({ page, request }) => {
      const errors = consoleErrors(page, WL)
      const api = await staffApi(request)
      let targetId = null
      let targetName = null
      let capturedPutBody = null
      const capPut = (r) => {
        if (r.method() === 'PUT' && r.url().includes(e.api)) {
          try { capturedPutBody = r.postDataJSON() } catch { /* 非 JSON 体忽略 */ }
        }
      }
      page.on('request', capPut)
      try {
        await loginAsStaff(page)
        await goto(page, e.page)
        await expect
          .poll(async () => rows(page).count(), { timeout: 25000, intervals: [300, 600, 1000] })
          .toBeGreaterThan(0)

        const targetRow = rows(page).first()
        targetId = Number((await targetRow.locator('td').first().innerText()).trim())
        targetName = (await targetRow.locator('td.col-name').innerText()).trim()
        const editedName = `${targetName} [E2E-PUT]`

        await targetRow.getByRole('button', { name: 'Edit' }).click()
        await expect(dlg(page), 'Edit 后应出现编辑器').toHaveCount(1, { timeout: 10000 })
        await expect(nameInput(page), `${e.noun} Edit 应把既有值预填（现算：${targetName}）`).toHaveValue(targetName)

        await nameInput(page).fill(editedName)
        const [putResp] = await Promise.all([
          page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes(e.api)),
          dlg(page).getByRole('button', { name: 'Save' }).click(),
        ])
        if (putResp.status() >= 300) {
          console.log(`__E2E__ ${e.noun} PUT ${putResp.status()} BODY=${String(await putResp.text()).slice(0, 400)}`)
        }
        expect(putResp.status(), `${e.noun} 编辑保存的 PUT 应 2xx`).toBeLessThan(300)
        await expect(dlg(page), '保存后编辑器应关闭').toHaveCount(0, { timeout: 10000 })
        const detail = await (await api.get(`${e.api}${targetId}/`)).json()
        const got = detail?.data ?? detail
        expect(got.name ?? got.title, `${e.noun} 编辑后新名应落库`).toBe(editedName)
        expect(errors).toEqual([])
      } finally {
        page.off('request', capPut)
        try {
          if (targetId != null && capturedPutBody) {
            await api.put(`${e.api}${targetId}/`, {
              data: { ...capturedPutBody, name: targetName, title: targetName },
            })
          }
          if (targetId != null) {
            const back = await (await api.get(`${e.api}${targetId}/`)).json()
            const b = back?.data ?? back
            const nowName = b?.name ?? b?.title
            console.log(`__E2E__ ${e.noun} PUT 首行还原 targetId=${targetId} name=${nowName}`)
            if (nowName !== targetName) {
              console.log(`__E2E__ ⚠️ ${e.noun} PUT 首行还原失败：期望 ${targetName} / 实际 ${nowName}`)
            }
          }
        } catch (err) {
          console.log(`__E2E__ ⚠️ ${e.noun} PUT 首行还原异常：${err.message}`)
        }
        await api.dispose()
      }
    })
}

/**
 * ★ Protocol 的 PUT 覆盖（**自建夹具版**，2026-09-24 由 fixme 转正）
 *
 * 为什么它不能沿用上面那条"编辑既有首行"的通用写法：
 *   `ProtocolListSerializer.update()`（`backend/apps/knowledge/api/v1/serializers.py:282-305`）
 *   在收到 `methods` 时会**刷新该协议的 explicit 桥**（删掉不再勾选的、补建新增的）。
 *   而 `ProtocolsPage.save()` 固定发送 `{ name, methods: form.method_id ? [id] : [] }`
 *   （`frontend/src/views/workspace/ProtocolsPage.vue:79-82`）
 *   ⇒ 只要编辑一条**已挂方法**的既有协议，PUT 就会在该协议上增删 explicit 桥；
 *   旧写法只还原**名字**，而桥**没有回收接口** ⇒ 每跑一次留一条。**这就是它被挂起的原因。**
 *
 * 夹具版把副作用关进自建夹具、再靠外键级联回收：
 *   1) **抢首行**：`Protocol.Meta.ordering = ['-version']`（`models.py:319`），
 *      而 `ProtocolsPage.loadList()` **不带 ordering**（`ProtocolsPage.vue:35`）
 *      ⇒ 夹具用 `version='9999'` 必排第一。
 *      已实证（2026-09-24，dev 库）：14,079 条 protocol 的 `version` **全部是 `'1.0'`**，
 *      `Protocol.objects.filter(version__gt='9999').exists()` = **False** ⇒ 无字符串能排到它前面。
 *      注：这里仍**用唯一名定位行**而不是 `rows().first()`，免得将来版本号变了就悄悄改错对象。
 *   2) **走到收敛分支**：夹具创建时带 `methods=[<真实 method id>]` ⇒ 自带 1 条 explicit 桥，
 *      于是 PUT 真的经过"刷新 explicit 桥"的代码路径（而不是空过）。
 *   3) **零残留**：`MethodProtocol.protocol` 是 `on_delete=CASCADE`
 *      （`backend/apps/bridges/models.py:59-62`）⇒ `DELETE /protocols/{id}/` 会把夹具桥一起带走；
 *      收尾再按唯一名检索断言残留 = 0。
 */
test('Protocol 治理页：自建夹具 Edit → Save 走 PUT 且落库（零残留）',
  { tag: ['@write', '@local-only'] }, async ({ page, request }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(request)
    const uniq = `E2E-Protocol-${Date.now()}`
    let fixtureId = null
    try {
      // ── Arrange：取一条真实 Method 建桥；自建 version='9999' 的夹具协议 ──
      const mBody = await (await api.get('/methods/', { params: { page_size: 1 } })).json()
      const mArr = Array.isArray(mBody?.data) ? mBody.data : mBody?.data?.results || []
      expect(mArr.length, '需要有可用的 Method 供夹具建桥').toBeGreaterThan(0)
      const methodId = mArr[0].id

      const cResp = await api.post('/protocols/', {
        // ★ 2026-11-18（S4 / A-066）：**必须显式给 `status: 'published'`**。
        //   Protocol 的 `status` 默认是 `draft`（`models.py:522`），而本用例靠
        //   「按唯一名定位列表行 → 点 Edit」来跑，行必须真的渲染出来。
        //   页面「Show drafts」默认关（与后端 list 端点的方案 B 过滤同口径）
        //   ⇒ draft 夹具不可见 ⇒ 定位恒 0 条。这是**夹具设定问题**，不是页面缺陷。
        data: { name: uniq, version: '9999', status: 'published', methods: [methodId] },
      })
      if (cResp.status() >= 300) {
        console.log(`__E2E__ Protocol 夹具创建 ${cResp.status()} BODY=${String(await cResp.text()).slice(0, 400)}`)
      }
      expect(cResp.status(), '夹具协议应创建成功').toBeLessThan(300)
      fixtureId = (await cResp.json())?.data?.id ?? null
      expect(fixtureId, '夹具协议应返回 id').not.toBeNull()

      // ── Act：走 UI 编辑夹具（按唯一名定位行，不依赖"首行"） ──
      await loginAsStaff(page)
      await goto(page, '/workspace/protocols')
      const fixtureRow = page.locator('table.entity-table tbody tr', { hasText: uniq })
      await expect
        .poll(async () => fixtureRow.count(), { timeout: 25000, intervals: [300, 600, 1000] })
        .toBe(1)
      console.log(`__E2E__ Protocol 夹具已渲染（version=9999 ⇒ 首行）id=${fixtureId}`)

      const editedName = `${uniq} [E2E-PUT]`
      await fixtureRow.first().getByRole('button', { name: 'Edit' }).click()
      await expect(dlg(page), 'Edit 后应出现编辑器').toHaveCount(1, { timeout: 10000 })
      await expect(nameInput(page), 'Edit 应把夹具名预填').toHaveValue(uniq)

      await nameInput(page).fill(editedName)
      const [putResp] = await Promise.all([
        page.waitForResponse((r) => r.request().method() === 'PUT' && r.url().includes('/protocols/')),
        dlg(page).getByRole('button', { name: 'Save' }).click(),
      ])
      if (putResp.status() >= 300) {
        console.log(`__E2E__ Protocol PUT ${putResp.status()} BODY=${String(await putResp.text()).slice(0, 400)}`)
      }
      expect(putResp.status(), 'Protocol 编辑保存的 PUT 应 2xx').toBeLessThan(300)
      await expect(dlg(page), '保存后编辑器应关闭').toHaveCount(0, { timeout: 10000 })

      const detail = await (await api.get(`/protocols/${fixtureId}/`)).json()
      expect((detail?.data ?? detail)?.name, 'Protocol 编辑后新名应落库').toBe(editedName)
      expect(errors).toEqual([])
    } finally {
      // ── Cleanup：删夹具 ⇒ MethodProtocol 级联删除 ⇒ 桥零残留 ──
      if (fixtureId != null) {
        const dResp = await api.delete(`/protocols/${fixtureId}/`).catch(() => null)
        // ★ 2026-11-18：带 `include_unpublished=1`，否则**永远查不到 draft 夹具** ⇒
        //   "残留 = 0" 会无条件成立，是个假绿闸门（这条断言的全部意义就是查残留）。
        const after = await (await api.get('/protocols/', {
          params: { search: uniq, page_size: 20, include_unpublished: 1 },
        })).json()
        const arr = Array.isArray(after?.data) ? after.data : after?.data?.results || []
        const left = arr.filter((x) => String(x.name || '').startsWith(uniq)).length
        console.log(`__E2E__ Protocol 夹具回收 id=${fixtureId} delete=${dResp ? dResp.status() : 'ERR'} 残留=${left}`)
        expect(left, 'Protocol PUT 夹具应零残留').toBe(0)
      }
      await api.dispose()
    }
  })
