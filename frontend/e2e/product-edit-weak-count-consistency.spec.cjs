/**
 * N3 · 产品编辑页「弱相关 (N)」计数一致性 —— **只读**（@readonly @local-only）
 *
 * 守护的不变量（ProductEditPage.vue:132 displayProtocolRows）：
 *   展示层只能把「本页载入后新增」的协议 id（locallyAddedProtocolIds，见
 *   ProductEditPage.vue:119-124）并入协议芯片，**不得**把服务端 `protocol_ids`
 *   整体并入。原因：`protocol_ids`（走 MethodProtocol 桥）与 `protocol_links`
 *   （走 ProductProtocol 表）不同源，前者可能多出上百个 id（实测 product 34 多 95 个）；
 *   若并入，会以「待保存」徽标混进「弱相关(N)」，使计数虚高。
 *
 * 判据（恒等式）：UI 的「弱相关 (N)」必须 == 服务端 `protocol_links` 里
 *   `tier === 'weak'` 的条数。
 *
 * 逐产品断言四条（期望值全部**现算**，不硬编码）：
 *   A. 强相关渲染条数（.chip-group:not(.weak-group) .chip-protocol）== min(10, strong)
 *   B. 「显示全部 (N)」里的 N == max(0, strong - 10)（strong-10 === 0 则该按钮不存在）
 *   C. 「弱相关 (N)」里的 N == 服务端 weak（★N3 核心；weak === 0 则该按钮不存在）
 *   D. 每产品一行 console.log 输出实测值，便于失败时定位
 *
 * 只读：不点 Save、不新增/删除任何数据；afterAll 无需清理（未写入）。
 *
 * 运行（照 e2e/README.md §1，务必用 E: 物理路径 / node 直调 cli.js）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do sleep 15; done; echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test \
 *     e2e/product-edit-weak-count-consistency.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-n3 \
 *     > ../../_n3.log 2>&1
 *   rm -f ../../_pw.lock
 */
const { test, expect } = require('@playwright/test')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')

// 8 个已在库产品（dev sqlite）。期望值不硬编码：每条用例一律先调 A-API 现算。
const PRODUCT_IDS = [66, 94, 70, 29, 35, 63, 33, 34]

// 折叠 TopN：与前端 buildFolded(strong, 10, showAll) 对齐（protocolLinks.js:95）。
const TOP_N = 10

const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })

async function staffApi(request) {
  return apiContext(await getToken(request, ADMIN_USER, ADMIN_PASS))
}

/** 从服务端详情取真值：{ strong, weak }（strong = 非 weak 条数，weak = tier==='weak' 条数） */
async function serverLinkTiers(api, id) {
  const r = await api.get(`/products/${id}/`)
  expect(r.status(), `GET /products/${id}/ 状态码`).toBe(200)
  const body = await r.json()
  const links = (body && body.data && body.data.protocol_links) || []
  const weak = links.filter((x) => x && x.tier === 'weak').length
  return { strong: links.length - weak, weak, total: links.length }
}

/** 读按钮内部文案里的 (N)；按钮不存在时返回 null。直接读按钮自身 innerText，
 *  ⚠️ 绝不用 textContent.slice 截断后做包含判断（长芯片名会截掉徽标 → 假阴性）。 */
async function btnCount(locator) {
  if ((await locator.count()) === 0) return null
  const text = await locator.first().innerText()
  const m = text.match(/\((\d+)\)/)
  return m ? Number(m[1]) : NaN
}

test.describe('N3 · 产品编辑页「弱相关 (N)」与服务端 protocol_links 一致（只读）', () => {
  // 重型产品（200+ 链接）在本机 dev 上偶发慢加载（实测 #70 达 32s）；放宽用例超时，
  // 但**不放宽任何断言**。串行由 playwright.config.cjs 的 workers:1 保证。
  test.describe.configure({ timeout: 120000 })

  for (const id of PRODUCT_IDS) {
    test(`N3 @readonly @local-only product #${id}：UI「弱相关 (N)」== 服务端 protocol_links weak 条数`, async ({ page, request }) => {
      await loginAsStaff(page)

      // ── 1) A-API 现算真值（判据来源：服务端 ProductProtocol 表）──
      const api = await staffApi(request)
      const { strong, weak, total } = await serverLinkTiers(api, id)
      await api.dispose()

      // ── 2) 打开编辑页并等载入完成（.edit-form 可见）──
      // 不用 page.waitForResponse 等详情接口：实测该等待会因响应已被浏览器/代理
      // 缓存或环境卡顿而永不触发（假失败）。改为依赖下方 DOM 断言自带的 auto-retry
      // 等数据落定（强相关芯片可见 == 详情已渲染）。
      await goto(page, `/workspace/products/${id}/edit`)
      await expect(page.locator('.edit-form')).toBeVisible({ timeout: 30000 })

      // ── 3) 从 DOM 读 §5（默认折叠态；不展开弱相关区，保持只读基线）──
      // 强相关可见芯片：父 .chip-group 非 .weak-group（弱相关区默认收起 ⇒ 未渲染）。
      const strongChips = page.locator('.chip-group:not(.weak-group) .chip-protocol')
      const expectVisibleStrong = Math.min(TOP_N, strong)
      const expectFold = Math.max(0, strong - TOP_N)

      // 等 DOM 落定：强相关 >0 时等首片可见；否则等空态 "None"。
      if (expectVisibleStrong > 0) {
        await expect(strongChips.first()).toBeVisible({ timeout: 30000 })
      } else {
        await expect(page.locator('.chip-group:not(.weak-group) .chip-none')).toBeVisible({ timeout: 30000 })
      }
      const uiStrong = await strongChips.count()

      const foldBtn = page.getByRole('button', { name: /显示全部/ })
      const weakBtn = page.locator('button.weak-toggle')

      // ── 4) 四条断言 ──
      // A. 强相关渲染条数 == min(10, strong)
      expect(uiStrong, `#${id} 强相关可见芯片数应 == min(10, ${strong})`).toBe(expectVisibleStrong)

      // B. 「显示全部 (N)」N == max(0, strong-10)；strong-10===0 时该按钮不存在
      if (expectFold > 0) {
        await expect(foldBtn, `#${id} strong-10=${expectFold}>0 应有「显示全部」按钮`).toBeVisible({ timeout: 10000 })
        const foldN = await btnCount(foldBtn)
        expect(foldN, `#${id}「显示全部 (N)」N 应 == max(0, strong-10)=${expectFold}`).toBe(expectFold)
      } else {
        await expect(foldBtn, `#${id} strong-10=0 不应有「显示全部」按钮`).toHaveCount(0)
      }

      // C. ★N3 核心：「弱相关 (N)」N == 服务端 weak；weak===0 时该按钮不存在
      let uiWeak = null
      if (weak > 0) {
        await expect(weakBtn, `#${id} weak=${weak}>0 应有「弱相关」按钮`).toBeVisible({ timeout: 10000 })
        uiWeak = await btnCount(weakBtn)
        expect(uiWeak, `#${id} ★N3：UI「弱相关 (N)」N 应 == 服务端 weak=${weak}`).toBe(weak)
      } else {
        await expect(weakBtn, `#${id} weak=0 不应有「弱相关」按钮`).toHaveCount(0)
      }

      // D. 每产品一行实测值
      const foldN = expectFold > 0 ? await btnCount(foldBtn) : null
      console.log(
        `[N3] product #${id}: strong=${strong} weak(server)=${weak} links=${total} ` +
        `| UI strong=${uiStrong}(期望 ${expectVisibleStrong}) ` +
        `显示全部=${foldN}(期望 ${expectFold || '无'}) ` +
        `UI weak=${uiWeak}(期望 ${weak || '无'})`
      )
    })
  }
})
