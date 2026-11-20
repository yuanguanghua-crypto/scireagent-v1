/**
 * 预览一致性验证 —— 用真实 Chromium 加载 sds-preview.html / coa-preview.html，断言：
 *   1) 投递一条真实数据后，所有关键字段渲染为真实记录值（映射对齐后端 ReportLab 生成器）
 *   2) 无任何样本残留
 *   3) ★ 2026-11-20（A-052 / A-150）**未投递数据时也不得出现任何产品样本**
 *      —— 这是原用例漏掉的失效形态：旧模板内置 SC8001 硬编码文档，
 *      一旦 postMessage 没送达（QA 实际遇到的情况），预览就整份显示别人的 COA/SDS。
 *      现在模板只保留中性占位，投递失败必须是空白 + 提示，而不是串号。
 *   4) 模板会主动发 `__ready`，渲染完成后回 `__ack`（父侧握手协议的另一半）
 * 运行：node test/verify-preview-consistency.cjs
 */
const path = require('path')
const { chromium } = require('playwright')

const SDS = 'file://' + path.resolve(__dirname, '../public/sds-preview.html').replace(/\\/g, '/')
const COA = 'file://' + path.resolve(__dirname, '../public/coa-preview.html').replace(/\\/g, '/')

const sdsData = {
  __type: 'sds',
  product_name: '3-Methylcytidine',
  catalog_no: 'SC8003',
  cas: '2140-64-9',
  revision_no: 2,
  revised_at: '2026-07-10',
  signal_word: 'Danger',
  pictograms: JSON.stringify(['GHS06', 'GHS08']),
  hazard_codes: JSON.stringify(['H301', 'H331']),
  precaution_codes: JSON.stringify(['P261', 'P280', 'P301+P310']),
  section_data: JSON.stringify({
    section_1: { synonyms: '3-MeC', recommended_use: 'Research reagent', restrictions: 'Not for human use',
      supplier: { company: 'SciReagent', address: '123 Science Blvd', telephone: '+1-858', email: 'safety@x.com', emergency_phone: 'CHEMTREC' } },
    section_2: { other_hazards: 'None known' },
    section_3: { composition: [{ name: '3-Methylcytidine', concentration: '>=98%', classification: 'Acute Tox. 3' }], note: 'Impurities not hazardous' },
    section_4: { inhalation: 'Fresh air', skin_contact: 'Wash', eye_contact: 'Rinse', ingestion: 'Rinse mouth', symptoms: 'Nausea', physician_notes: 'Symptomatic' },
    section_5: { suitable_media: 'CO2', unsuitable_media: 'Water jet', hazards: 'Toxic fumes', firefighter_equipment: 'SCBA' },
    section_6: { personal: 'PPE', environmental: 'No drains', cleanup: 'Collect' },
    section_7: { handling: 'Fume hood', storage: '-20C', specific_use: 'Lab only' },
    section_8: { exposure_limits: 'None', engineering_controls: 'LEV', hygiene: 'Wash hands', ppe: { eye: 'Goggles', hands: 'Nitrile' } },
    section_9: { appearance: 'White powder', melting_point: '210C', solubility_water: 'Slight' },
    section_10: { reactivity: 'Stable', incompatible_materials: 'Oxidizers' },
    section_11: { acute_toxicity: { oral_ld50: '300 mg/kg' }, carcinogenicity: 'Not listed' },
    section_12: { ecotoxicity: 'No data' },
    section_13: { waste: 'Licensed contractor', packaging: 'As product', rcra: 'Not listed' },
    section_14: { un_number: 'None' },
    section_15: { tsca: 'Not listed', reach: 'Not registered' },
    section_16: { supersedes: 'v1', prepared_by: 'Safety Dept', references: ['OSHA', 'GHS Rev 9'], abbreviations: { GHS: 'Globally Harmonized System' }, disclaimer: 'Info based on current knowledge.' }
  })
}

const coaData = {
  __type: 'coa',
  doc_id: 'COA-SC8003-2026-007',
  product_name: '3-Methylcytidine',
  catalog_number: 'SC8003',
  cas_number: '2140-64-9',
  lot_number: 'SC8003-L2026007',
  molecular_formula: 'C10H15N3O5',
  molecular_weight: '257.24',
  storage_condition: '-20C, desiccated',
  produced_at: '2026-06-01',
  retest_at: '2028-06-01',
  appearance_spec: 'White powder', appearance_result: 'White to off-white powder',
  purity_spec: '>=98.0%', purity_result: '99.1%', purity_method: 'HPLC',
  water_content_spec: '<=1.0%', water_content_result: '0.4%',
  melting_point: '208-210C', specific_rotation: '-55 deg',
  residual_solvents: '<0.1%', heavy_metals: '<10 ppm',
  nmr_result: 'Conforms to structure', lcms_result: '257.1 [M+H]+',
  hplc_conditions: 'C18 column, UV 260nm', lcms_conditions: 'ESI(+) mode',
  qc_analyst: 'Alice Wong', qa_approval: 'Dr. Bob Kim', approved_at: '2026-06-05T09:30:00Z'
}

const results = []
function check(label, cond) {
  results.push({ label, ok: !!cond })
}

async function renderAndGetText(browser, url, data) {
  const page = await browser.newPage()
  // 记录模板主动发给父窗口的握手消息。
  // 必须用 addInitScript：`__ready` 在文档脚本执行时就会发出，晚于 goto 注入就抓不到。
  // （本文件为 file:// 顶层页，parent === window，且 targetOrigin 为 "null" 会导致
  //   真实投递抛错并被模板自己的 try/catch 吞掉 ⇒ 这里在调用**之前**记录。）
  await page.addInitScript(() => {
    window.__bridgeMsgs = []
    const orig = window.postMessage.bind(window)
    window.postMessage = (m, o) => {
      if (m && typeof m === 'object') {
        if (m.__ready) window.__bridgeMsgs.push('ready')
        else if ('__ack' in m) window.__bridgeMsgs.push('ack:' + m.__ack)
      }
      try { return orig(m, o) } catch (e) { return undefined }
    }
  })
  await page.goto(url)
  await page.evaluate((d) => { window.postMessage(d, '*') }, data)
  // 等 bridge 完成渲染
  await page.waitForTimeout(200)
  const text = await page.evaluate(() => document.body.innerText)
  const html = await page.evaluate(() => document.body.innerHTML)
  const msgs = await page.evaluate(() => window.__bridgeMsgs || [])
  await page.close()
  return { text, html, msgs }
}

/** 只加载、不投递任何数据 —— 模拟"消息没送达"的失效形态。 */
async function loadOnly(browser, url) {
  const page = await browser.newPage()
  await page.goto(url)
  await page.waitForTimeout(200)
  const text = await page.evaluate(() => document.body.innerText)
  await page.close()
  return { text }
}

(async () => {
  let browser
  for (const ch of ['chrome', 'msedge']) {
    try { browser = await chromium.launch({ channel: ch }); break } catch (e) { /* 下一种 */ }
  }
  if (!browser) browser = await chromium.launch()
  try {
    // ===== SDS =====
    const sds = await renderAndGetText(browser, SDS, sdsData)
    const st = sds.text
    check('SDS: 产品名 3-Methylcytidine', st.includes('3-Methylcytidine'))
    check('SDS: Catalog SC8003', st.includes('SC8003'))
    check('SDS: CAS 2140-64-9', st.includes('2140-64-9'))
    check('SDS: Doc ID SD-SC8003-v2', st.includes('SD-SC8003-v2'))
    check('SDS: 信号词 DANGER', st.includes('DANGER'))
    check('SDS: 象形图 GHS06', st.includes('GHS06'))
    check('SDS: 象形图 GHS08', st.includes('GHS08'))
    check('SDS: H-code H301', st.includes('H301'))
    check('SDS: H-code H331', st.includes('H331'))
    check('SDS: P-code P301+P310', st.includes('P301+P310'))
    check('SDS: §9 缺失属性回退 Not available', st.includes('Not available'))
    check('SDS: §14 DOT 缺省 Not regulated', st.includes('Not regulated'))
    check('SDS: §16 Revision Number 2.0', st.includes('2.0'))
    check('SDS: §16 References OSHA', st.includes('OSHA'))
    check('SDS: §16 disclaimer', st.includes('Info based on current knowledge'))
    // 无 SC8001 样本残留
    check('SDS: 无残留 SC8001', !st.includes('SC8001'))
    check('SDS: 无残留旧CAS 2140-79-6', !st.includes('2140-79-6'))
    check('SDS: 无残留 2\'-O-Methyladenosine', !st.includes('Methyladenosine'))
    check('SDS: 无残留 7 pages 提示', !sds.html.includes('all 16 sections covered, 7 pages'))

    // ===== COA =====
    const coa = await renderAndGetText(browser, COA, coaData)
    const ct = coa.text
    check('COA: Doc ID COA-SC8003-2026-007', ct.includes('COA-SC8003-2026-007'))
    check('COA: 产品名 3-Methylcytidine', ct.includes('3-Methylcytidine'))
    check('COA: Catalog SC8003', ct.includes('SC8003'))
    check('COA: Lot SC8003-L2026007', ct.includes('SC8003-L2026007'))
    check('COA: 分子量追加 g/mol', ct.includes('257.24 g/mol'))
    check('COA: 生产日期 2026-06-01', ct.includes('2026-06-01'))
    check('COA: 复检日期 2028-06-01', ct.includes('2028-06-01'))
    check('COA: QC 纯度实测 99.1%', ct.includes('99.1%'))
    check('COA: QC LC-MS spec MW: 257.24', ct.includes('MW: 257.24'))
    check('COA: Specific Rotation 方法 USP <781>', ct.includes('USP <781>'))
    check('COA: 分析方法 C18 column', ct.includes('C18 column'))
    check('COA: 分析方法 ESI(+)', ct.includes('ESI(+)'))
    check('COA: 签名 QC Alice Wong', ct.includes('Alice Wong'))
    check('COA: 签名 QA Dr. Bob Kim', ct.includes('Dr. Bob Kim'))
    check('COA: 签名日期 2026-06-05', ct.includes('2026-06-05'))
    // 无 SC8001 样本残留
    check('COA: 无残留 SC8001', !ct.includes('SC8001'))
    check('COA: 无残留 Sarah Chen', !ct.includes('Sarah Chen'))
    check('COA: 无残留 Dr. Michael Lee', !ct.includes('Michael Lee'))
    check('COA: 无残留 COA-SC8001', !ct.includes('COA-SC8001'))
    check('COA: 无残留笔误 USP <771>', !ct.includes('USP <771>'))

    // ===== 握手协议：模板必须先发 __ready，渲染后回 __ack =====
    check('SDS: 发出 __ready', (sds.msgs || []).includes('ready'))
    check('SDS: 渲染后回 __ack:true', (sds.msgs || []).includes('ack:true'))
    check('COA: 发出 __ready', (coa.msgs || []).includes('ready'))
    check('COA: 渲染后回 __ack:true', (coa.msgs || []).includes('ack:true'))

    // ===== ★ 回归（A-052 / A-150）：不投递数据时也不得显示任何产品样本 =====
    const sdsEmpty = await loadOnly(browser, SDS)
    check('SDS 空载: 无样本 SC8001', !sdsEmpty.text.includes('SC8001'))
    check('SDS 空载: 无样本产品名 Methyladenosine', !sdsEmpty.text.includes('Methyladenosine'))
    check('SDS 空载: 无样本 CAS 2140-79-6', !sdsEmpty.text.includes('2140-79-6'))
    check('SDS 空载: 无样本 CID 102211', !sdsEmpty.text.includes('102211'))
    check('SDS 空载: 显示中性占位', sdsEmpty.text.includes('Waiting for document data'))

    const coaEmpty = await loadOnly(browser, COA)
    check('COA 空载: 无样本 SC8001', !coaEmpty.text.includes('SC8001'))
    check('COA 空载: 无样本产品名 Methyladenosine', !coaEmpty.text.includes('Methyladenosine'))
    check('COA 空载: 无样本纯度 99.52', !coaEmpty.text.includes('99.52'))
    check('COA 空载: 无样本签名 Sarah Chen', !coaEmpty.text.includes('Sarah Chen'))
    check('COA 空载: 无样本 Doc ID COA-SC8001', !coaEmpty.text.includes('COA-SC8001'))
  } finally {
    await browser.close()
  }

  const failed = results.filter(r => !r.ok)
  results.forEach(r => console.log((r.ok ? 'PASS ' : 'FAIL ') + r.label))
  console.log('\n==== ' + (results.length - failed.length) + '/' + results.length + ' passed ====')
  if (failed.length) { process.exitCode = 1 }
})()
