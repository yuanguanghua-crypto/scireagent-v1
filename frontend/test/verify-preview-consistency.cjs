/**
 * 预览一致性验证 —— 用真实 Chromium 加载 sds-preview.html / coa-preview.html，
 * postMessage 一条 SC8003 的真实数据，断言：
 *   1) 所有关键字段渲染为真实记录值（映射对齐后端 ReportLab 生成器）
 *   2) 无任何 SC8001 样本残留（原串号 Bug 根因）
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
  await page.goto(url)
  await page.evaluate((d) => { window.postMessage(d, '*') }, data)
  // 等 bridge 完成渲染
  await page.waitForTimeout(200)
  const text = await page.evaluate(() => document.body.innerText)
  const html = await page.evaluate(() => document.body.innerHTML)
  await page.close()
  return { text, html }
}

(async () => {
  const browser = await chromium.launch()
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
  } finally {
    await browser.close()
  }

  const failed = results.filter(r => !r.ok)
  results.forEach(r => console.log((r.ok ? 'PASS ' : 'FAIL ') + r.label))
  console.log('\n==== ' + (results.length - failed.length) + '/' + results.length + ' passed ====')
  if (failed.length) { process.exitCode = 1 }
})()
