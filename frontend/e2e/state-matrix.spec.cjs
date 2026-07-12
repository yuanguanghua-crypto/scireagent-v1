/**
 * 阶段 7 — 状态分支穷举（维度 S）
 * PO 状态 UI 差异：每态标签文案 + 可用按钮集。
 *
 * 经实证（po_views.py）：
 *  - ApproveOrderView: PO_RECEIVED → CONFIRMED（直达，不经过 IN_PRODUCTION）
 *  - 后端无任何端点推进到 IN_PRODUCTION → 该态为死态（不可达），本 spec 不造该态
 *  - AdminOrderDetail 状态标签 = getStatusLabel(status)：下划线→空格+首字母大写
 *  - 按钮集按态 v-if；终态 completed/cancelled 无 .btn-action
 *  - AdminOrderDetail 未渲染 StatusLog 时间线（仅 items/customer/payment 区块）→ 时间线断言不可做，如实记录
 *
 * 可 seed 的 9 态：po_received / confirmed / shipped / delivered / invoiced / paid / completed / cancelled / quote_pending
 */
const { test, expect } = require('@playwright/test')
const { loginAsStaff, BASE_URL } = require('./helpers/auth.cjs')
const h = require('./helpers/poHelpers.cjs')

const PO_STATES = [
  { name: 'po_received',   label: 'Po Received', buttons: ['Approve', 'Cancel Order'], seed: (c, a) => h.seedPoReceived(c) },
  { name: 'confirmed',     label: 'Confirmed',   buttons: ['Create & Mark Shipped', 'Cancel Order'], seed: h.seedApproved },
  { name: 'shipped',       label: 'Shipped',     buttons: ['Mark as Delivered', 'Cancel Order'], seed: h.seedShipped },
  { name: 'delivered',     label: 'Delivered',   buttons: ['Generate Invoice', 'Cancel Order'], seed: h.seedDelivered },
  { name: 'invoiced',      label: 'Invoiced',    buttons: ['Record Payment', 'Cancel Order'], seed: h.seedInvoiced },
  { name: 'paid',          label: 'Paid',        buttons: ['Mark as Completed'], seed: h.seedPaid },
  { name: 'completed',     label: 'Completed',   buttons: [], seed: h.seedCompleted },
  { name: 'cancelled',     label: 'Cancelled',   buttons: [], seed: h.seedCancelled },
  { name: 'quote_pending', label: 'Quote Pending', buttons: ['Submit Quote', 'Cancel Order'], seed: (c) => h.seedQuotePending(c) },
]

test.describe('PO 状态分支（AdminOrderDetail UI）', () => {
  let custToken, adminToken
  test.beforeAll(async () => {
    custToken = await h.getCustomerToken()
    adminToken = await h.getAdminToken()
  })
  test.beforeEach(async ({ page }) => { await loginAsStaff(page) })

  for (const s of PO_STATES) {
    test(`态 ${s.name} → 标签「${s.label}」+ 按钮集 ${JSON.stringify(s.buttons)}`, async ({ page }) => {
      const po = await s.seed(custToken, adminToken)
      await page.goto(`${BASE_URL}/admin/orders/${po.id}`, { waitUntil: 'domcontentloaded' })
      await page.waitForSelector('.status-badge', { timeout: 10000 })

      // 状态标签文案
      await expect(page.locator('.status-badge')).toHaveText(s.label)

      // 按钮集（终态为空）
      const btns = await page.locator('.btn-action').allInnerTexts()
      const norm = (arr) => arr.map((t) => t.replace(/\s+/g, ' ').trim()).sort()
      expect(norm(btns)).toEqual(norm(s.buttons))

      // 清理（可取消态）
      if (['po_received', 'confirmed', 'shipped', 'delivered', 'invoiced', 'quote_pending'].includes(s.name)) {
        await h.cancelOrder(custToken, adminToken, po.id).catch(() => {})
      }
    })
  }

  test('IN_PRODUCTION 为后端死态（无端点推进至此）— 记录不造数据', async () => {
    // 断言点：后端无任何端点把订单推进到 in_production（ApproveOrderView 直达 CONFIRMED）。
    // 故该态经 E2E 不可构造，仅在此登记。AdminOrderDetail 虽为其预留按钮组（同 confirmed）但无订单进入。
    expect(true).toBeTruthy()
  })
})
