#!/usr/bin/env node
/**
 * audit_frontend_links — 知识实体页面渲染层审计（Playwright）。
 *
 * ## 为什么单独一个脚本
 *
 * 后端命令 `manage.py audit_entity_links` 只断言「数据与接口自洽」；
 * 而 2026-10-30 走查里真正踩到的问题之一是**渲染层**的：产品页用自定义 tab
 * （`.pd-tab-btn`）而非 Element Plus 的 `.el-tabs__item`，按后者查得到 0 个，
 * 差点误报「产品页没有知识实体区块」。
 *
 * ⇒ 本脚本的两条铁律：
 *   1. **tab 探测必须通用** —— 依次尝试多种选择器，任一命中即用，不写死一种
 *   2. **id 从 API 拉，不写死** —— 本地与生产 id 空间不同（用生产 id 打本地
 *      会全是 "not found"，这是同一天踩的另一个坑）
 *
 * ## 用法
 *
 *   cd frontend
 *   node ../scripts/audit_frontend_links.cjs                       # 默认本地 5173
 *   node ../scripts/audit_frontend_links.cjs --base http://127.0.0.1:5173 --sample 20
 *   node ../scripts/audit_frontend_links.cjs --api  http://127.0.0.1:8010/api/v1
 *
 * 退出码：有异常页（非 200 / not found / 正文过短）则 1。
 */
const path = require('path')
const { chromium } = require(path.join(__dirname, '..', 'frontend', 'node_modules', 'playwright'))

function arg(name, def) {
  const i = process.argv.indexOf('--' + name)
  return i >= 0 && process.argv[i + 1] ? process.argv[i + 1] : def
}

const BASE = arg('base', 'http://127.0.0.1:5173')
const API = arg('api', 'http://127.0.0.1:8010/api/v1')
const SAMPLE = parseInt(arg('sample', '12'), 10)

const KINDS = [
  { key: 'protocols', path: '/protocols/', label: 'Protocol' },
  { key: 'applications', path: '/applications/', label: 'Application' },
  { key: 'methods', path: '/methods/', label: 'Method' },
  { key: 'research-goals', path: '/research-goals/', label: 'ResearchGoal' },
  { key: 'products', path: '/products/', label: 'Product' },
]

// ★ 通用 tab 探测：任一选择器命中即用（自定义 tab 与 Element Plus 都覆盖）
const TAB_SELECTORS = ['.el-tabs__item', '.pd-tab-btn', '.tab-btn', '[role="tab"]']

async function fetchIds(kind, n) {
  try {
    const r = await fetch(`${API}/${kind}/?page_size=${Math.max(n, 20)}`)
    const j = await r.json()
    return (j.data || []).slice(0, n).map(x => x.id)
  } catch (e) {
    return []
  }
}

async function inspect(page, url) {
  const errs = []
  const onErr = e => errs.push('pageerror: ' + e.message.slice(0, 80))
  const onCon = m => { if (m.type() === 'error') errs.push('console: ' + m.text().slice(0, 80)) }
  page.on('pageerror', onErr)
  page.on('console', onCon)

  let status = 0
  try {
    const resp = await page.goto(BASE + url, { waitUntil: 'networkidle', timeout: 30000 })
    status = resp ? resp.status() : 0
  } catch (e) {
    page.off('pageerror', onErr); page.off('console', onCon)
    return { url, status: -1, error: e.message.slice(0, 90) }
  }
  await page.waitForTimeout(700)

  const r = await page.evaluate((sels) => {
    const txt = document.body.innerText
    let tabs = []
    for (const s of sels) {
      const els = document.querySelectorAll(s)
      if (els.length) { tabs = [...els].map(e => e.innerText.trim()); break }
    }
    const links = [...new Set(
      [...document.querySelectorAll('a[href]')]
        .map(a => a.getAttribute('href'))
        .filter(h => /^\/(protocols|methods|applications|research-goals|products)\/\d/.test(h))
    )]
    return {
      notFound: /not found/i.test(txt),
      len: txt.length,
      tabs,
      links: links.length,
      hint: (txt.match(/No |not yet|being |does not list|only/g) || []).length,
    }
  }, TAB_SELECTORS)

  page.off('pageerror', onErr)
  page.off('console', onCon)
  return { url, status, ...r, errs }
}

;(async () => {
  const browser = await chromium.launch({ channel: 'msedge' })
  const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()

  const rows = []
  for (const k of KINDS) {
    const ids = await fetchIds(k.key, SAMPLE)
    if (!ids.length) {
      rows.push({ label: k.label, url: '-', status: 'SKIP', note: 'API 无数据' })
      continue
    }
    for (const id of ids) {
      try {
        rows.push({ label: k.label, ...(await inspect(page, k.path + id)) })
      } catch (e) {
        rows.push({ label: k.label, url: k.path + id, status: 'ERR', note: e.message.slice(0, 70) })
      }
    }
  }

  const bad = []
  console.log('label          url                          st   len    tabs  links hint')
  console.log('-'.repeat(84))
  for (const r of rows) {
    const tabsN = r.tabs ? r.tabs.length : 0
    const flag = (r.status !== 200 || r.notFound || (r.len && r.len < 500)) ? '✗' : ' '
    console.log(
      `${flag} ${(r.label || '').padEnd(13)} ${(r.url || '').padEnd(28)} ${String(r.status).padEnd(4)} ` +
      `${String(r.len || '').padEnd(6)} ${String(tabsN).padEnd(5)} ${String(r.links ?? '').padEnd(5)} ${r.hint ?? ''}` +
      (r.tabs && r.tabs.length ? '  ' + JSON.stringify(r.tabs).slice(0, 70) : '')
    )
    if (r.status !== 200 || r.notFound || (r.len && r.len < 500)) bad.push(r)
  }

  console.log('\n' + '='.repeat(84))
  if (bad.length) {
    console.log(`✗ 异常 ${bad.length} / ${rows.length}`)
    for (const r of bad.slice(0, 10)) console.log('   ', r.url, r.status, r.notFound ? 'notFound' : '', r.error || '')
  } else {
    console.log(`✅ 全部 ${rows.length} 页正常（200、非 notFound、正文 ≥500 字符）`)
  }
  await browser.close()
  process.exit(bad.length ? 1 : 0)
})().catch(e => { console.error('FATAL', e.message); process.exit(1) })
