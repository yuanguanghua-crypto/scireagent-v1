/**
 * P1 基建 · 四类断言的统一封装
 *
 * 判据来源见《动作剧本 × 期望断言》§2：
 *   A-API ：expectApi(resp, { status, json })            —— 状态码 + 字段值精确相等
 *   D-DB  ：dbSnapshot() + expectDelta(before, after, spec) —— 表计数差 / 字段值
 *   U-UI  ：expect* （Playwright 原生）+ attachConsoleErrorCollector（零 console 错误）
 *   N-负向：expectDelta(before, after, zeroSpec(before))  —— 「不该写的必须零变化」
 *
 * 设计目标：让每条剧本**短且机器可判**，失败信息自带**差异定位**（期望值 + 实际值 + before/after）。
 */
const { expect } = require('@playwright/test')
const { dbSnapshot } = require('./db-snapshot.cjs')
const { attachConsoleErrorCollector } = require('./console.cjs')

/** 点号路径取值：getPath({data:{chemical:{cid:1}}}, 'data.chemical.cid') → 1 */
function getPath(obj, path) {
  return String(path).split('.').reduce((acc, k) => (acc == null ? acc : acc[k]), obj)
}

/**
 * A-API 断言。
 * @param {import('@playwright/test').APIResponse} resp
 * @param {{status?:number, json?:Record<string,unknown>, label?:string}} spec
 *   json 的 key 支持点号路径（如 'data.chemical.cas_resolved'）
 */
async function expectApi(resp, { status, json = {}, label = '' } = {}) {
  const tag = label ? `[${label}] ` : ''
  if (status !== undefined) {
    expect(resp.status(), `${tag}HTTP 状态码`).toBe(status)
  }
  const keys = Object.keys(json)
  if (keys.length) {
    let body
    try {
      body = await resp.json()
    } catch (e) {
      throw new Error(`${tag}响应不是 JSON（可能是 HTML 错误页）：${String(e.message).slice(0, 120)}`)
    }
    for (const p of keys) {
      expect(getPath(body, p), `${tag}${p}`).toEqual(json[p])
    }
  }
  return resp
}

/** D-DB 快照（默认 6 张关键表；见 db-snapshot.cjs） */
function snapshotDb(tables) {
  return dbSnapshot(tables)
}

/**
 * D-DB / N-负向 断言：逐表比对计数差。
 * @param {Record<string,number>} before
 * @param {Record<string,number>} after
 * @param {Record<string,number>} spec  { product: +1, audit_log: +1, ... }
 * 失败信息含「期望 Δ / 实际 Δ / before / after」⇒ 直接可定位。
 */
function expectDelta(before, after, spec, label = '') {
  const tag = label ? `[${label}] ` : ''
  for (const [table, want] of Object.entries(spec)) {
    const b = before[table]
    const a = after[table]
    const d = (a ?? 0) - (b ?? 0)
    expect(d, `${tag}${table} 计数差应为 ${want}，实际 ${d}（before=${b} after=${a}）`).toBe(want)
  }
}

/** 由 before 生成「全 0」期望，用于 N-负向断言（只读动作后不得有任何写入） */
function zeroSpec(before) {
  return Object.fromEntries(Object.keys(before).map((k) => [k, 0]))
}

/**
 * N-负向 一行化：包裹一段只读操作，断言期间**任何表零变化**。
 * 用法：await expectNoWrites(async () => { ...点来点去... }, 'A2 深链 recycle')
 */
async function expectNoWrites(fn, label = '', tables) {
  const before = snapshotDb(tables)
  await fn()
  const after = snapshotDb(tables)
  expectDelta(before, after, zeroSpec(before), label || '只读零写入')
}

/** U-UI 的 console 零错误（复用既有 collector，便于统一 import） */
function consoleErrors(page, whitelist = []) {
  return attachConsoleErrorCollector(page, { whitelist })
}

module.exports = {
  getPath,
  expectApi,
  snapshotDb,
  expectDelta,
  zeroSpec,
  expectNoWrites,
  consoleErrors,
}
