/**
 * Part 1（研究员工作台·产品新建页）· **组 B「文档导入」（📄 Word Import）** B1–B6
 *
 * 规格来源：《2026-09-22_动作剧本×期望断言_Part1_研究员工作台产品新建页.md》§组 B（B1–B6）；
 *          覆盖缺口定性见《2026-09-22_P0_动作剧本覆盖矩阵.md》§2/§4（B 组整组 ✗，零覆盖）。
 * 判据层级（e2e/README.md §6）：L0 铁律 > L1 规格 > L2 代码现值；L3 不变量恒成立。
 * **期望值只取自 L1 规格 + 直读代码现值**，与规格不一致处单列于文末「发现」。
 *
 * 本机跑法（**必须**，见 e2e/README.md §1；输出重定向到文件，勿管道给 tail；与同伴共用 dev 库须加锁串行）：
 *   cd /e/Users/yuankaifeng/WorkBuddy/2026-07-08-11-22-32/src_claude/frontend
 *   while [ -f ../../_pw.lock ]; do echo "lock busy, wait..."; sleep 30; done
 *   echo $$ > ../../_pw.lock
 *   node node_modules/@playwright/test/cli.js test e2e/product-new-doc-import.spec.cjs \
 *     --project=chromium --reporter=list --retries=0 --output=test-results-p3b > ../../_p3b.log 2>&1
 *   rm -f ../../_pw.lock
 *
 * 前置：本地 dev 已起（Django :8000 DB_ENGINE=sqlite / Vite :5173，且 Vite 从 **E: 物理路径** 启动）；
 *      docx 语料 `E:\试剂网站的\试剂产品说明文档`（可用 E2E_DOCX_DIR 覆盖）。
 * 纪律：只新增本文件；不改应用代码、不 git commit；写操作只碰 `E2E-` 前缀夹具，afterAll 硬删。
 */
const { test, expect, request } = require('@playwright/test')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { runSync } = require('./helpers/sync-spawn.cjs')
const { BASE_URL, loginAsStaff, ADMIN_USER, ADMIN_PASS } = require('./helpers/auth')
const { getToken, apiContext } = require('./helpers/api')
const { expectApi, snapshotDb, expectDelta, expectNoWrites, consoleErrors } = require('./helpers/assertions.cjs')
const { BACKEND } = require('./helpers/db-snapshot.cjs')
const { findDocx, cleanupByPrefix } = require('./fixtures/index.cjs')

const WL = ['wasm streaming compile failed', 'falling back to ArrayBuffer instantiation']
// 触发 4xx/413 的用例：Chromium 把失败资源记为 console error，按语义白名单放行
const WL2 = [...WL, 'Failed to load resource']

const goto = (page, p) => page.goto(`${BASE_URL}${p}`, { waitUntil: 'domcontentloaded' })
const staffApi = async (req) => apiContext(await getToken(req, ADMIN_USER, ADMIN_PASS))

// ★ 选择器全部来自真实 DOM（ProductEditPage.vue），非猜测。
//   `button.file-upload-btn` 在 AI AUTO MATCH 面板 :1426 **也**出现 ⇒ 一律限定 `.word-import-section`。
const FILE_INPUT = '.word-import-section input[type="file"]'   // :1401（hidden）
const UPLOAD_LABEL = '.word-import-section label.file-upload-btn' // :1399
const OK = '.word-import-section .word-status.word-ok'          // :1405-1407
const ERR = '.word-import-section .word-status.word-err'        // :1411

// 表单字段选择器（AppInput → <input>/<textarea>）
const IN = {
  name: `input[placeholder="e.g. 2'-Amino-ATP"]`,              // :1684
  catalog_no: `input[placeholder="e.g. SC8043"]`,               // :1688
  cas: `input[placeholder="e.g. 1927-31-7"]`,                   // :1692
  synonyms: `input[placeholder="comma separated"]`,             // :1696
  smiles: `textarea[placeholder="e.g. C1=CC=C(C=C1)N"]`,        // :1711
  formula: `input[placeholder="e.g. C10H17N6O13P3"]`,           // :1717
  molecular_weight: `input[placeholder="e.g. 522.2"]`,          // :1721
  overview: `textarea[placeholder^="Describe the product"]`,    // :1842
}

// L1 §B1 列出的期望预填值（来源：规格文档，非代码；仅作「现状 vs 规格」对照记录）
const L1_B1 = {
  name: '5-Propargylamino-CTP',
  catalog_no: 'SC8001',
  cas: '150718-26-6',
  formula: 'C12H19N4O14P3 (free acid)',
  molecular_weight: '536.01',        // L1 写 536.01；docx 原文为 '536.01 g/mol (free acid)'（parseFloat 后取 536.01）
  purity: '≥ 95% (HPLC)',
  concentration: '100 mM',
  storage: 'stored at -20°C',        // ⚠ L1 写的是 **docx 原文**；表单实际值经 normalizeStorage 归一为 '-20°C'
  shipping: 'Shipped with Blue Ice', // ⚠ 同上，经 normalizeShipping 归一为 'Blue Ice'
  smiles: '',
}
const l1Diff = (form) => Object.entries(L1_B1)
  .map(([k, v]) => [k, v, String(form[k] ?? '')])
  .filter(([, l1, got]) => got.trim() !== l1).map(([k, l1, got]) => ({ field: k, l1, got }))

// ── 夹具：临时目录 + 伪造/最简 docx（不进 repo；afterAll 删目录）──────
const TMP = fs.mkdtempSync(path.join(os.tmpdir(), 'e2e-docimport-'))
const PY = path.join(BACKEND, 'venv', 'Scripts', 'python.exe')   // backend venv 内有 python-docx
const fakeTxt = (name) => { const p = path.join(TMP, name); fs.writeFileSync(p, 'this is not a docx'); return p }
const fakeDocx = (name, mb) => { const p = path.join(TMP, name); fs.writeFileSync(p, Buffer.alloc(mb * 1024 * 1024)); return p }
function makeDocx(name, paras) {
  const py = ['from docx import Document', 'd = Document()',
    ...paras.map((t) => `d.add_paragraph(${JSON.stringify(t)})`),
    `d.save(${JSON.stringify(path.join(TMP, name))})`].join('\n')
  runSync(PY, ['-B', '-c', py], { cwd: BACKEND, env: { ...process.env, DB_ENGINE: 'sqlite' }, label: 'build docx' })
  return path.join(TMP, name)
}

/** 上传文件并等 `POST /products/parse-word/` 的响应（前端 ProductEditPage.vue:280） */
async function upload(page, file) {
  const [resp] = await Promise.all([
    page.waitForResponse((r) => r.url().includes('/products/parse-word/')),
    page.locator(FILE_INPUT).setInputFiles(file),
  ])
  return resp
}
/** 逐字段读回「表单实际被填了什么」，用于取证记录 */
async function readForm(page) {
  const out = {}
  for (const [k, sel] of Object.entries(IN)) {
    const loc = page.locator(sel)
    out[k] = (await loc.count()) ? await loc.first().inputValue() : null
  }
  out.selects = (await page.locator('.form-section .app-select').allInnerTexts()).map((s) => s.trim())
  out.structure_img = await page.locator('.chem-preview img').count()
  return out
}
const brief = (o) => JSON.stringify(o, (k, v) => (typeof v === 'string' && v.length > 160 ? v.slice(0, 160) + '…' : v))
const say = (label, obj) => console.log(`__E2E__ ${label} ${brief(obj)}`)   // 落进 *_p3b.log，供报告取证
// 空白归一：docx 正文含 **U+2009 THIN SPACE**（如 formula 的 `...P3 <TS>(free acid)`），
// 与 L1 规格写作普通空格 ⇒ 语义等价、按归一比较；原文差异由 l1_diff（精确比较）逐条留证。
const norm = (s) => String(s ?? '').replace(/\s+/g, ' ').trim()

test.describe('Part 1 · 组 B 文档导入（WORD IMPORT）', () => {
  test.afterAll(async () => {
    const ctx = await request.newContext()
    const api = await apiContext(await getToken(ctx, ADMIN_USER, ADMIN_PASS))
    await cleanupByPrefix(api, { label: 'B-group' })   // 安全网：本组不落库，预期 found=0
    await ctx.dispose(); await api.dispose()
    fs.rmSync(TMP, { recursive: true, force: true })
  })

  // ── B1：正常 docx 导入 ⇒ 表单被预填（L1 §B1；逐字段记录实测值）──
  test('B1 @readonly @local-only 正常 docx 导入 ⇒ 表单被预填（逐字段记录实测）', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    const before = snapshotDb()
    const resp = await upload(page, findDocx('SC8001'))
    await expectApi(resp, { status: 200, label: 'B1 parse-word' })
    const data = (await resp.json()).data
    await expect(page.locator(OK)).toContainText('fields extracted')
    const form = await readForm(page)
    say('B1_PREFILL', { fields_found: data.fields_found, api: data, form, l1_diff: l1Diff(form) })
    for (const k of ['name', 'catalog_no', 'cas', 'formula']) expect(norm(form[k]), `B1 应预填 ${k}（L1 §B1；空白归一）`).toBe(norm(L1_B1[k]))
    expect(form.smiles, 'B1 docx 无 SMILES ⇒ 该字段必须留空').toBe('')
    expectDelta(before, snapshotDb(), { product: 0 }, 'B1 只解析不落库')
    expect(errors).toEqual([])
  })

  // ── B2：重复导入同一 docx（L1 §B2 标 🔶 未定义 ⇒ 只断言不变量 + 记录行为）──
  test('B2 @readonly @local-only 重复导入同一 docx ⇒ 不落库；覆盖/幂等按 🔶 记录', async ({ page }) => {
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    const before = snapshotDb()
    await expectApi(await upload(page, findDocx('SC8001')), { status: 200, label: 'B2 首次' })
    const first = await readForm(page)
    // 同值再选不会触发 change ⇒ 先清空输入再放同一文件（见文末发现 #6）
    await page.locator(FILE_INPUT).setInputFiles([])
    await expectApi(await upload(page, findDocx('SC8001')), { status: 200, label: 'B2 再次' })
    const second = await readForm(page)
    expect(second.name, 'B2 二次导入后表单仍应有 name').toBeTruthy()
    say('B2_REIMPORT', { overwritten: JSON.stringify(first) !== JSON.stringify(second), first, second })
    expectDelta(before, snapshotDb(), { product: 0 }, 'B2 重复导入仍不落库')
  })

  // ── B3：非 docx ⇒ 400 被拒 + 可读提示 + Δ0（L1 §B3 文案待认定 ⇒ 取代码现值）──
  test('B3 @readonly @local-only 上传非 docx(.txt) ⇒ 400 被拒 + 提示 + product Δ0', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    const before = snapshotDb()
    const resp = await upload(page, fakeTxt('B3-not-a-docx.txt'))
    await expectApi(resp, { status: 400, json: { 'meta.error.code': 'UNSUPPORTED_FORMAT' }, label: 'B3' })
    await expect(page.locator(ERR)).toContainText('仅支持 .docx')
    expectDelta(before, snapshotDb(), { product: 0 }, 'B3 非 docx 不得产生产品行')
    expect(errors).toEqual([])
  })

  // ── B4：超大 docx ⇒ 413 被拒 + 提示 + Δ0（上限取自 word_parser.py:21 = 10MB）──
  test('B4 @readonly @local-only 超大伪 docx(11MB > 10MB 上限) ⇒ 413 被拒 + 提示 + Δ0', async ({ page }) => {
    const errors = consoleErrors(page, WL2)
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    const before = snapshotDb()
    const resp = await upload(page, fakeDocx('B4-huge.docx', 11))   // 上限 = MAX_UPLOAD_SIZE_MB=10（word_parser.py:21）
    await expectApi(resp, { status: 413, json: { 'meta.error.code': 'FILE_TOO_LARGE' }, label: 'B4' })
    await expect(page.locator(ERR)).toContainText('10MB')
    expectDelta(before, snapshotDb(), { product: 0 }, 'B4 超大文件不得产生产品行')
    expect(errors).toEqual([])
  })

  // ── B5：缺字段 docx ⇒ 成功、不崩、缺失字段留空、N 变小（L1 §B5；word_parser.py:117-120 按锚点取）──
  test('B5 @readonly @local-only 缺字段 docx ⇒ 不崩 + 缺失字段留空 + 字段数 N 变小', async ({ page }) => {
    const errors = consoleErrors(page, WL)
    const paras = ['E2E-B5 Minimal Product', 'Catalog Number: E2E-B5-MIN']   // 故意**无** 'CAS Number:' 行
    const want = 1 + paras.filter((p) => /^[A-Za-z ]+:\s*\S/.test(p)).length // 首段→产品名；其余按 'Label: value' 计
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    const before = snapshotDb()
    const resp = await upload(page, makeDocx('B5-min.docx', paras))
    await expectApi(resp, { status: 200, json: { 'data.fields_found': want }, label: 'B5' })
    const form = await readForm(page)
    say('B5_MISSING_FIELDS', { want, form })
    expect(form.name, 'B5 有产品名 ⇒ 该填').toContain('E2E-B5')
    expect(form.cas, 'B5 文档无 CAS ⇒ 字段必须留空，不得凭猜填').toBe('')
    expectDelta(before, snapshotDb(), { product: 0 }, 'B5 不落库')
    expect(errors).toEqual([])
  })

  // ── B6：导完不保存就离开 ⇒ 全部表 Δ0（L1 §B6 不变量）──
  test('B6 @readonly @local-only 导完不保存就离开 ⇒ product/audit_log 及各表 Δ0', async ({ page }) => {
    await loginAsStaff(page); await goto(page, '/workspace/products/new')
    await expectNoWrites(async () => {
      await upload(page, findDocx('SC8001'))
      await expect(page.locator(OK)).toContainText('fields extracted')
      await goto(page, '/workspace/products')
    }, 'B6 导入后未保存即离开')
  })
})

/* ────────────────────────────────────────────────────────────────────────────
 * 发现（纠错 / 纠偏 / 记录） —— 与 L1 规格或真实网站不一致处，带 文件:行号
 *
 * #1【记录】L1 §B2「重复导入」标 🔶（Q4）；**实测净效果 = 幂等**（两次表单态逐字段相同）
 *    · 实测：`B2_REIMPORT {"overwritten":false, ...}` —— first == second（同一 docx ⇒ 同值）。
 *    · 但**代码路径是无条件覆盖**：`prefillFromWord`（`ProductEditPage.vue:294-328`）逐字段
 *      `if (data.x) form.x = data.x`，且 `skus.value = data.skus.map(...)`（`:312`）**重建 SKU 列表**
 *      ⇒ 若研究员**先手改再重导**，手改值会被静默覆盖（本次未构造该场景，属代码推断，非实测）。
 *    · 是否应改为「只填空字段」需用户拍板（Q4）。
 *
 * #2【纠偏/记录】L1 §B1 的 `storage`/`shipping` 期望值是 **docx 原文**，非表单值
 *    · 表单路径经 `normalizeStorage`/`normalizeShipping`（`ProductEditPage.vue:1170-1197`）归一化：
 *      `'stored at -20°C'` → `'-20°C'`；`'Shipped with Blue Ice'` → `'Blue Ice'`（实测见日志 `B1_PREFILL`）。
 *    · ⇒ L1 §B1 行的期望值层级与「表单被回填什么」不同，断言以**表单实测值**为准并记录差异。
 *
 * #2b【纠偏】L1 §B1 的 `formula` 期望值用的是**普通空格**，docx 原文实为 **U+2009 THIN SPACE**
 *    · 实测：docx → `C12H19N4O14P3\u2009(free acid)`；L1 写作 `C12H19N4O14P3 (free acid)`。
 *    · 解析链路（`word_parser.py:83-95` 原样返回 + `ProductEditPage.vue:298` 原样赋值）**无加工**
 *      ⇒ 应用行为正确，是 **L1 规格的字符级失真**。断言按空白归一比较，原文差异留在 `l1_diff`。
 *    · 同类：文件名 `SC8001_5‑Propargylamino‑CTP.docx` 用的是 **U+2011 不换行连字符**（`fixtures/index.cjs:67`
 *      只用 `startsWith('SC8001')` ⇒ 不受影响）。
 *
 * #3【记录】L1 §B4 只写「4xx」，代码实际 = **413 / code=FILE_TOO_LARGE**
 *    · `word_views.py:43-46`；守卫 `word_parser.py:65`；上限常量 `word_parser.py:21 MAX_UPLOAD_SIZE_MB=10`
 *      （另在 `views.py:37` 重复定义一份，两处无单一出处）。
 *
 * #4【记录】同一个导入错误会**两处提示**
 *    · `handleWordFile` catch（`ProductEditPage.vue:288`）写 `wordResult.error` → 模板 `.word-status.word-err`（`:1411`）；
 *    · 同时 http 响应拦截器（`src/utils/http.js:96-97`）再弹一枚 `ElMessage.error`。非缺陷，但文案重复。
 *
 * #5【记录】file input 是 `hidden`（`ProductEditPage.vue:1401`），E2E 用 `setInputFiles` 直驱；
 *    选择器必须限定 `.word-import-section`（`button.file-upload-btn` 在 AI 面板 `:1426` 同名）。
 *
 * #6【记录/测试坑】连选**同一文件**不会触发 `change` ⇒ 第二次导入无请求
 *    · 实测：B2 第二次 `setInputFiles(同一路径)` 后 `waitForResponse(parse-word)` 45s 超时（无请求）。
 *    · 修法：先 `setInputFiles([])` 清空，再放同一文件（`handleWordFile` 对空 files 早返回，无副作用）。
 *    · 应用侧无缺陷 —— 这是浏览器/测试驱动语义，非 `word_import` 行为。
 * ──────────────────────────────────────────────────────────────────────── */
