/**
 * 研究员工作台 · **知识实体治理 5 页**（Goals / Applications / Methods / Protocols / References）
 *
 * 来源：全工作台动作普查（`2026-09-23_全工作台动作普查.md`）判定这 5 页**同一模板**：
 *   处理器相同（`openNew` / `openEdit(e)` / `save` / `showEditor=false`）· 按钮同构
 *   （`+ New <X>` / `Cancel` / `Save` / 行内 `Edit`）· 写接口同构（`POST` + `PUT /<resource>/`）
 *   ⇒ **表驱动一个 spec 覆盖 5 页**。
 *
 * ★ 选择器**全部已 Read 取证**（GoalsPage 模板，其余 4 页同构；勿再凭猜）：
 *   · 列表：`table.entity-table > tbody tr`；名称单元格 `td.col-name`
 *   · 编辑器：`div.dialog-overlay > div.dialog`（`v-if="showEditor"`）
 *   · 名称输入：`.dialog input.input-full`（v-model 绑定 ⇒ 断言**必须用 `toHaveValue`**，
 *     不能用 `input[value=…]` —— 那是 **HTML 属性**，Vue 绑的是 **DOM property**，属性不会同步）
 *   · 按钮：`Cancel` / `Save`（保存中变 `Saving...`）/ 行内 `Edit`
 *   · 编辑器标题 `{{ editing ? 'Edit' : 'New' }} <X>` ⇒ 可做**模式**的独立佐证
 *   · ⚠️ Goals 的 `el-select` 是 `multiple filterable remote`（需输入才会出选项）⇒ **本 spec 不碰它**，
 *     只填名称字段；若某实体的外键**必填**，第一次跑就会 400 暴露（届时再补，不预先猜）
 *
 * 动作空间（阶段 1 普查结论，**已封闭**）：列表 + 4 个处理器 + 编辑器字段；**UI 层无删除动作**。
 * 环境 tier：**本地真实写**（会建知识实体）⇒ 生产侧维持只读。
 * 夹具自清：接口是 `ModelViewSet` + router（`knowledge/api/v1/urls.py:18`）⇒ `DELETE /<resource>/{id}/` 已核实可用。
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

/** 计数用 **API 现算**（禁硬编码；也不用模型类名，避免猜表名） */
async function countViaApi(api, path) {
  const body = await (await api.get(path, { params: { page_size: 500 } })).json()
  const d = body?.data
  return (Array.isArray(d) ? d : d?.results || []).length
}

const ENTITIES = [
  { noun: 'Goal', page: '/workspace/goals', api: '/research-goals/' },
  { noun: 'Application', page: '/workspace/applications', api: '/applications/' },
  { noun: 'Method', page: '/workspace/methods', api: '/methods/' },
  { noun: 'Protocol', page: '/workspace/protocols', api: '/protocols/' },
  { noun: 'Reference', page: '/workspace/references', api: '/references/' },
]

for (const e of ENTITIES) {
  // ★ 只 `Reference` 已跑通并转正；其余 4 项**如实标 fixme**（不留红测试），原因如下（均为实测）：
  //   · Goal：保存 **POST 400** —— 夹具 payload 不足（存在必填字段），**未逐页取证字段必填性**
  //   · Application / Method / Protocol：列表选择器**不匹配** —— 实测 `DOM=0`（API 有数据）
  //     ⇒ 它们的列表/编辑器标记与 Goals **不同构**；我此前**只在 Goals 取证就泛化**（教训：同构必须逐页取证）
  //   转正条件：逐页 Read 列表/编辑器标记 + 必填字段 ⇒ 补进 ENTITIES 的 per-entity 配置（结构不用改，仍是表驱动）。
  const t = e.noun === 'Reference' ? test : test.fixme
  t(`${e.noun} 治理页：列表==min(API,200) / +New / Cancel 零写入 / Save Δ+1 / Edit 预填`, async ({ page, request }) => {
    const errors = consoleErrors(page, WL)
    const api = await staffApi(request)
    const uniq = `E2E-${e.noun}-${Date.now()}`
    let createdId = null
    const newBtn = page.getByRole('button', { name: new RegExp(`\\+ New ${e.noun}`) }).first()
    try {
      await loginAsStaff(page)
      await goto(page, e.page)

      // ① 列表渲染行数 vs API 现算数
      //   ★ 实测发现（2026-09-23）：这些治理页**最多只渲染 200 行**，而 API `page_size=500` 能返回 500
      //     ⇒ **静默截断、界面无任何提示** ⇒ 与 `2026-09-23_P0覆盖矩阵_重算.md §3.3 G3`（">500 截断告警"）同类，
      //     属**报告级发现**。⇒ 本用例**不断绝对相等**，改断"== min(API, 200)"把该行为**钉住**（防回退或静默变化）。
      const n0 = await countViaApi(api, e.api)
      const dom0 = await rows(page).count()
      expect(dom0, `${e.noun} 列表应渲染出至少一行`).toBeGreaterThan(0)
      expect(dom0, `${e.noun} 列表渲染行数应 == min(API 现算, 200)（200 为本页渲染上限）`).toBe(Math.min(n0, 200))
      console.log(`__E2E__ ${e.noun} 列表 API=${n0} DOM=${dom0}（上限 200，静默截断）`)

      // ② `+ New <X>` ⇒ 编辑器出现，且标题是 "New" 形态
      await newBtn.click()
      await expect(dlg(page), `点 + New ${e.noun} 后应出现编辑器`).toHaveCount(1, { timeout: 10000 })
      await expect(dlg(page).locator('h3'), '新建态标题应含 New').toContainText('New')

      // ④ `Cancel` ⇒ 关闭 **且零写入**
      const nBeforeCancel = await countViaApi(api, e.api)
      await dlg(page).getByRole('button', { name: 'Cancel' }).click()
      await expect(dlg(page), 'Cancel 后编辑器应关闭').toHaveCount(0, { timeout: 10000 })
      expect(await countViaApi(api, e.api), 'Cancel 不得产生任何写入').toBe(nBeforeCancel)

      // ⑤ Save（新建）⇒ POST 2xx + **API 计数 Δ+1**（写库证据）
      //   ⚠️ **不断"列表出现新行"**：本页只渲染前 200 行，新建行**可能压根没被渲染**（已实测 200 上限）
      //      ⇒ 若断它会得到与实现无关的假失败。这里只把"是否渲染出来"当**观察**打印，不作判定。
      await newBtn.click()
      await expect(dlg(page)).toHaveCount(1, { timeout: 10000 })
      await nameInput(page).fill(uniq)
      const [resp] = await Promise.all([
        page.waitForResponse((r) => r.request().method() === 'POST' && r.url().includes(e.api)),
        dlg(page).getByRole('button', { name: 'Save' }).click(),
      ])
      expect(resp.status(), `${e.noun} 新建的 POST 应 2xx`).toBeLessThan(300)
      createdId = (await resp.json())?.data?.id ?? null
      expect(await countViaApi(api, e.api), `${e.noun} 新建后 API 计数应 Δ+1`).toBe(n0 + 1)
      console.log(`__E2E__ ${e.noun} 新建后 列表是否渲染该新行 = ${await rows(page).filter({ hasText: uniq }).count()}`)

      // ③⑥ 行内 `Edit` 的**预填**（★只断"编辑器出现"是必要不充分）
      //   取**第一条已渲染的行**（顺序无关，不依赖我新建的那条是否被渲染）⇒ 现算其名称 ⇒ 断预填值 == 该名称。
      const firstRow = rows(page).first()
      const firstName = (await firstRow.locator('td.col-name').innerText()).trim()
      await firstRow.getByRole('button', { name: 'Edit' }).click()
      await expect(dlg(page), 'Edit 后应出现编辑器').toHaveCount(1, { timeout: 10000 })
      await expect(dlg(page).locator('h3'), '编辑态标题应含 Edit').toContainText('Edit')
      //   预填断言必须用 `toHaveValue`（读 DOM property）；用 `input[value=…]` 是 HTML 属性、Vue 绑定不会同步
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
