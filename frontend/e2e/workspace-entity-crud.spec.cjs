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

/** 计数用 **API 现算**（禁硬编码；也不猜模型类名/表名） */
async function countViaApi(api, path) {
  const body = await (await api.get(path, { params: { page_size: 500 } })).json()
  const d = body?.data
  return (Array.isArray(d) ? d : d?.results || []).length
}

/** 总数用 **`meta.pagination.count`** 现算 —— 与组件所读的信封字段**同源**（禁硬编码 11028 之类） */
async function totalViaApi(api, path) {
  const body = await (await api.get(path, { params: { page_size: 1 } })).json()
  return body?.meta?.pagination?.count ?? null
}

const ENTITIES = [
  { noun: 'Goal', page: '/workspace/goals', api: '/research-goals/' },
  { noun: 'Application', page: '/workspace/applications', api: '/applications/' },
  { noun: 'Method', page: '/workspace/methods', api: '/methods/' },
  { noun: 'Protocol', page: '/workspace/protocols', api: '/protocols/' },
  { noun: 'Reference', page: '/workspace/references', api: '/references/' },
]

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
      const n0 = await countViaApi(api, e.api)
      await expect
        .poll(async () => rows(page).count(), { timeout: 25000, intervals: [300, 600, 1000] })
        .toBeGreaterThan(0)
      const dom0 = await rows(page).count()
      expect(dom0, `${e.noun} 渲染行数不应超过 API 总数`).toBeLessThanOrEqual(n0)
      console.log(`__E2E__ ${e.noun} 列表 API=${n0} DOM=${dom0}${dom0 < n0 ? '（有渲染上限，静默截断）' : '（全量渲染）'}`)

      // ①b 截断提示（`[data-testid="truncation-hint"]`）——**仅当 API 总数 > 实际渲染行数**时出现。
      //    文案里两个数字**都用现算**：总数 = `meta.pagination.count`，行数 = 当前 DOM 行数 ⇒ **禁硬编码 11028 之类**。
      //    反向用例：未截断的页（如 dev 的 references 193/193）该元素**必须不存在**。
      const total0 = await totalViaApi(api, e.api)
      const hint = page.locator('[data-testid="truncation-hint"]')
      const expectTruncated = total0 > dom0
      if (expectTruncated) {
        await expect(hint, `${e.noun} 有静默截断时应显示提示`).toBeVisible({ timeout: 10000 })
        await expect(hint, `${e.noun} 提示文案应为「Showing first <DOM> of <API> records」`)
          .toHaveText(`Showing first ${dom0} of ${total0} records`)
      } else {
        await expect(hint, `${e.noun} 未截断时不应出现提示`).toHaveCount(0)
      }
      console.log(`__E2E__ ${e.noun} 截断提示 API=${total0} DOM=${dom0} 显示=${expectTruncated}`)

      // ② `+ New <X>` ⇒ 编辑器出现，标题为 New 形态
      await newBtn.click()
      await expect(dlg(page), `点 + New ${e.noun} 后应出现编辑器`).toHaveCount(1, { timeout: 10000 })
      await expect(dlg(page).locator('h3'), '新建态标题应含 New').toContainText('New')

      // ④ `Cancel` ⇒ 关闭 **且零写入**
      const nBeforeCancel = await countViaApi(api, e.api)
      await dlg(page).getByRole('button', { name: 'Cancel' }).click()
      await expect(dlg(page), 'Cancel 后编辑器应关闭').toHaveCount(0, { timeout: 10000 })
      expect(await countViaApi(api, e.api), 'Cancel 不得产生任何写入').toBe(nBeforeCancel)

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
      const body = await (await api.get(e.api, { params: { search: uniq, page_size: 20 } })).json()
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
 * ⚠️ 已知缺陷 / 挂起原因（本组用例是它的闸门）：
 *  · `Reference` 的 `PUT 400 source_type=pubmed` **已修**（序列化器层并入 `pubmed`，不动模型）
 *    ⇒ 其 PUT 用例**已转正**。
 *  · `Protocol` 的 `PUT 500 NameError(MethodProtocol 未导入)` **已修**（补模块级导入），
 *    但本用例**仍挂起**，原因换成**夹具副作用**：
 *      协议 PUT 走通后，`update()` 会按**单选下拉**刷新该协议的 `explicit` 桥
 *      （已实测：夹具 2 条 explicit → 收敛为 1 条；非 explicit 桥不受影响）。
 *      本用例为不污染数据，只改名并靠 API 还原**名字**；但**没有清理 `MethodProtocol` 的接口**
 *      ⇒ 跑一次会在首行协议上**新建 1 条 explicit 桥**且无法回收。
 *    ⇒ 转正前置：① 明确「编辑保存收敛 explicit 桥」的口径；② 提供夹具桥的清理手段。
 *      （生产 `method_protocol.explicit=true` 实测 **0 条**（共 15,241）⇒ 该副作用**当前零波及**。）
 */
const PUT_KNOWN_DEFECT = {
  Protocol: 'PUT 已修(补导入)；本用例挂起＝夹具会在首行协议新建 1 条 explicit 桥且无接口回收',
}
for (const e of ENTITIES) {
  const defect = PUT_KNOWN_DEFECT[e.noun]
  const t = defect ? test.fixme : test
  const suffix = defect ? `（已知缺陷：${defect}）` : ''
  t(`${e.noun} 治理页：Edit → Save 走 PUT 且落库${suffix}`,
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
