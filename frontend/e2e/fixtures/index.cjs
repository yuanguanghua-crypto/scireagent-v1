/**
 * P1 基建 · 夹具（命名规范 / docx 定位）与清理
 *
 * 三条纪律（对应「写操作全部可自愈」）：
 *   1. 造数一律带 `E2E-` 前缀 + 时间戳 ⇒ 可识别、可批量回收
 *   2. 清理一律**硬删**（超管）⇒ 不在回收站留垃圾；已删再删不报错（幂等）
 *   3. 真实 docx 语料**不进 repo**（体积/版权/污染）⇒ 由 env 指向外部目录
 */
const path = require('node:path')
const fs = require('node:fs')

/** 本次运行的时间戳（同一 spec 文件内全部夹具共享，便于一次清理） */
const RUN_TS = Date.now()

function tag(prefix = 'X', ts = RUN_TS) {
  return `E2E-${prefix}-${ts}`
}
const catalogNo = (prefix, ts) => tag(prefix, ts)
const slug = (prefix, ts) => tag(prefix, ts).toLowerCase()
const skuCode = (prefix, ts) => `${tag(prefix, ts)}-SKU`

/** 所有夹具的统一前缀（清理时的扫描键） */
const PREFIX = 'E2E-'

/**
 * 按货号前缀批量硬删夹具。
 * @param {{get:Function, post:Function, dispose:Function}} api  helpers/api.cjs 的 apiContext()
 * @param {{prefix?:string, label?:string}} opts
 * @returns {Promise<{found:number, deleted:number, failed:any[]}>}
 */
async function cleanupByPrefix(api, { prefix = PREFIX, label = '' } = {}) {
  const tagL = label ? `[${label}] ` : ''
  const result = { found: 0, deleted: 0, failed: [] }
  let targets = []
  try {
    const resp = await api.get('/products/', { params: { archived: 1, page_size: 500 } })
    const body = await resp.json()
    targets = (body?.data || []).filter((p) => String(p.catalog_no || '').startsWith(prefix))
  } catch (e) {
    result.failed.push(`列表拉取失败：${String(e.message).slice(0, 120)}`)
    return result
  }
  result.found = targets.length
  for (const t of targets) {
    try {
      const r = await api.post(`/products/${t.id}/hard-delete/`)
      if (r.ok()) result.deleted += 1
      else result.failed.push(`${t.catalog_no}(id=${t.id}) HTTP ${r.status()}`)
    } catch (e) {
      result.failed.push(`${t.catalog_no}(id=${t.id}) ${String(e.message).slice(0, 80)}`)
    }
  }
  if (result.failed.length) {
    // 只告警不抛错：清理失败不应掩盖业务断言结果（但必须在报告里可见）
    console.warn(`${tagL}清理未全成功：found=${result.found} deleted=${result.deleted} failed=${JSON.stringify(result.failed)}`)
  }
  return result
}

/** docx 语料目录（默认指向本机真实语料；可用 E2E_DOCX_DIR 覆盖） */
const DOCX_DIR = process.env.E2E_DOCX_DIR || 'E:\\试剂网站的\\试剂产品说明文档'

function findDocx(namePrefix) {
  if (!fs.existsSync(DOCX_DIR)) {
    throw new Error(`docx 目录不存在：${DOCX_DIR}（用 E2E_DOCX_DIR 指定）`)
  }
  const hit = fs.readdirSync(DOCX_DIR).find((f) => f.startsWith(namePrefix) && f.toLowerCase().endsWith('.docx'))
  if (!hit) throw new Error(`未找到以 ${namePrefix} 开头的 docx（目录：${DOCX_DIR}）`)
  return path.join(DOCX_DIR, hit)
}

module.exports = { RUN_TS, PREFIX, tag, catalogNo, slug, skuCode, cleanupByPrefix, DOCX_DIR, findDocx }
