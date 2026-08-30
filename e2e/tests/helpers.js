// Shared helpers + fixtures for the SciReAgent E2E suite.
// - `page` fixture is overridden to attach a console-error / pageerror guard so that
//   any unexpected JS error on a visited page fails the test (per QA requirement).
// - login() performs the UI login flow with the provided admin credentials.
// - selectFirstCascader() drives the Element Plus el-cascader Category selector.
const { test: base, expect } = require('@playwright/test')

const ADMIN_USER = 'admin'
const ADMIN_PASS = 'admin123'

// Console noise that is benign (asset/network load failures) — keep real JS errors.
const IGNORE_CONSOLE = /Failed to load resource|net::ERR|favicon|DevTools|\[vite\]|WebSocket/i

// Dev-server shim: the Ketcher editor (ketcher-standalone / ketcher-react) pulls in the
// Node `util`/`assert` polyfills which reference the bare global `process`. Vite's dev
// server does not define `process`, so any page that imports KetcherEditor (i.e.
// ProductEditPage) throws `ReferenceError: process is not defined` and fails to render.
// We inject a minimal browser polyfill so the E2E suite can drive ProductEditPage against
// `npm run dev`. NOTE: this is a test-harness workaround — the proper fix is to add a
// `process` polyfill to vite.config.js (or lazy-load KetcherEditor). See KNOWN ISSUES.
const PROCESS_POLYFILL = () => {
  /* eslint-disable no-undef */
  window.process = window.process || {
    env: { NODE_ENV: 'development' },
    browser: true,
    nextTick: (cb) => setTimeout(cb, 0),
    title: 'browser',
  }
  window.process.env = window.process.env || { NODE_ENV: 'development' }
  if (typeof window.Buffer === 'undefined') {
    try { window.Buffer = { isBuffer: () => false, from: () => ({}), alloc: () => ({}) } } catch (e) { /* noop */ }
  }
  if (typeof window.global === 'undefined') {
    try { window.global = window } catch (e) { /* noop */ }
  }
  /* eslint-enable no-undef */
}

const test = base.extend({
  page: async ({ page }, use) => {
    const errors = { console: [], pageerror: [] }
    // Restore `process` for the dev server (see PROCESS_POLYFILL note above).
    await page.addInitScript(PROCESS_POLYFILL)
    page.on('console', (msg) => {
      if (msg.type() === 'error' && !IGNORE_CONSOLE.test(msg.text())) {
        errors.console.push(msg.text())
      }
    })
    page.on('pageerror', (err) => {
      errors.pageerror.push(err.message)
    })
    await use(page)
    // Teardown: fail the test if any unexpected JS error surfaced.
    if (errors.pageerror.length) {
      throw new Error('Uncaught JS exception(s): ' + errors.pageerror.join(' | '))
    }
    if (errors.console.length) {
      throw new Error('Unexpected console.error(s): ' + errors.console.join(' | '))
    }
  },
})

// Perform / re-establish the staff session. This is intentionally idempotent
// and resilient to BOTH bounce scenarios:
//   1. Sticky bounce (getMe() failed → token wiped from localStorage): visiting
//      /login shows the form, so we perform the UI login.
//   2. Transient bounce (token still valid, getMe() just slow): visiting /login
//      auto-redirects to /workspace, so we must NOT try to fill the (absent)
//      login form — we just wait for the hydrated Dashboard.
// Either way we wait for `.stat-card` (rendered only under a staff session),
// which proves `isStaff` has hydrated and defeats the auth-race bounce.
async function login(page) {
  // Already on a hydrated workspace? Nothing to do.
  if (page.url().includes('/workspace')) {
    try {
      await page.waitForSelector('.stat-card', { timeout: 5000 })
      return
    } catch {
      // Not hydrated yet — fall through and (re)establish the session.
    }
  }

  await page.goto('/login')
  let formShown = false
  try {
    await page.waitForSelector('#login-username', { timeout: 4000 })
    formShown = true
  } catch {
    formShown = false
  }
  if (formShown) {
    await page.fill('#login-username', ADMIN_USER)
    await page.fill('#login-password', ADMIN_PASS)
    await page.getByRole('button', { name: 'Sign In' }).click()
  }
  // Wait for the hydrated Dashboard (proves isStaff resolved).
  await page.waitForURL(/\/workspace$/, { timeout: 20000 })
  await page.waitForSelector('.stat-card', { timeout: 20000 })
}

// Navigate to a staff-only workspace route while tolerating the auth-store
// rehydration race. On a FULL page reload the app's `isStaff` flag is only
// populated by an async /me fetch, so a guarded page's <script setup> guard
// (`if (!auth.isStaff) router.replace('/')`) momentarily bounces the page back
// to the PUBLIC home before the flag is ready. In the normal (recovering) case
// the public Home auto-redirects back to /workspace once getMe() resolves, so
// the workspace marker appears within a second or two. In the STICKY case
// (getMe() failed → token wiped) the page stays on the public home.
//
// Strategy: retry the navigation until the workspace content actually renders
// (proving isStaff hydrated). The per-attempt wait (8s) comfortably covers the
// bounce→recover cycle. Only if we are genuinely stuck on the public home do we
// RE-ESTABLISH the staff session via login() (which lands hydrated on
// /workspace) and retry — directly defeating the auth race rather than only
// waiting it out. The retry budget (10 × 8s, plus re-logins) fits comfortably
// inside the 90s per-test timeout set in playwright.config.js.
async function gotoWorkspace(page, path) {
  const marker = '.stat-card, .products-table, .entity-page, .product-edit, .ki-page'
  let lastErr
  for (let attempt = 0; attempt < 10; attempt++) {
    await page.goto(path)
    try {
      await page.waitForSelector(marker, { timeout: 8000, state: 'visible' })
      return
    } catch (e) {
      lastErr = e
      // Detect a genuine (sticky) auth-race bounce: the guarded page is still
      // on the public home. A passing/recovering bounce would already have
      // rendered the marker, so reaching here means re-login is warranted.
      const onPublic = (await page.locator('a:has-text("Sign In")').count()) > 0
      const url = page.url()
      const bounced =
        onPublic || url === '/' || url.endsWith('/login') || url.endsWith('/login/')
      if (bounced && attempt < 9) {
        await login(page)
        continue
      }
      throw e
    }
  }
  throw lastErr
}

// Always remove the E2E_TEST product we created (success OR failure), so the
// suite never leaves an orphan behind. Steps:
//  1. Prefer the UI delete (verifies the real delete flow). NOTE: the confirm button
//     is the English "Permanently delete" (ProductsPage.vue), NOT the Chinese text.
//  2. Regardless of UI outcome, issue an authoritative `hard-delete` via API.
//     Rationale: `DELETE /api/v1/products/{id}/` only SOFT-archives (archived=True,
//     product row + catalog_no stay in DB — this was the root cause of the 20+ orphan
//     `E2E_TEST_AI_*` rows found by QA), while `POST /{id}/hard-delete/` physically
//     deletes (admin is a superuser, so the permission check passes). Only the
//     hard-delete guarantees "no E2E_TEST residue after a run".
async function cleanupE2EProduct(page, id, catNo) {
  let uiOk = false
  try {
    await gotoWorkspace(page, '/workspace/products')
    const row = page.locator('.products-table tbody tr', { hasText: catNo }).first()
    if ((await row.count()) > 0) {
      await row.locator('.menu-trigger').click()
      await row.locator('.menu-item--danger').click()
      await page.locator('.confirm-check input[type="checkbox"]').check()
      await page.getByRole('button', { name: 'Permanently delete' }).click()
      try {
        await expect(row).toHaveCount(0, { timeout: 8000 })
        uiOk = true
      } catch (e) {
        // UI delete didn't take effect — fall through to API.
      }
    }
  } catch (e) {
    console.log('REPORT: UI cleanup skipped/failed, using API fallback:', e.message)
  }
  // Authoritative physical delete against the dev (SQLite) DB via the Vite proxy.
  let token = await page.evaluate(() => localStorage.getItem('token'))
  if (!token) {
    // Session lost (auth-race wiped the token) — re-auth via API for a fresh token.
    try {
      const resp = await page.request.post('/api/v1/auth/login', {
        data: { username: ADMIN_USER, password: ADMIN_PASS },
      })
      if (resp.ok()) {
        const body = await resp.json()
        token = (body && (body.data && body.data.token)) || (body && body.token) || null
      }
    } catch (e) {
      console.log('REPORT: API re-auth failed:', e.message)
    }
  }
  if (token) {
    const resp = await page.request.post(`/api/v1/products/${id}/hard-delete/`, {
      headers: { Authorization: `Token ${token}` },
    })
    console.log(`REPORT: API hard-delete status=${resp.status()}${uiOk ? ' (UI soft-delete ran first)' : ''}`)
  } else {
    console.log('REPORT: cleanup WARNING — no session token available for API hard-delete (orphan risk)')
  }
}

// Drive the Category el-cascader (expandTrigger: 'hover', emitPath: true).
// Hover each parent node to reveal its children menu; click the first leaf to select.
async function selectFirstCascader(page) {
  await page.locator('.el-cascader').first().click()
  await page.waitForSelector('.el-cascader-panel', { timeout: 8000 })
  let level = 0
  while (level < 4) {
    const menus = page.locator('.el-cascader-panel .el-cascader-menu')
    if ((await menus.count()) <= level) break
    const node = menus.nth(level).locator('.el-cascader-node').first()
    if ((await node.count()) === 0) break
    const isParent = await node.evaluate((el) => el.classList.contains('el-cascader-node--parent'))
    if (isParent) {
      await node.hover()
      await page.waitForTimeout(350)
      level++
    } else {
      await node.click()
      break
    }
  }
}

// ── API-side helpers (use the Vite /api proxy → backend, with session token) ──

// Read the session token from localStorage (for authoritative API cleanup).
async function getToken(page) {
  return await page.evaluate(() => localStorage.getItem('token'))
}

// Normalize an envelope-style or bare response into a plain JS array (list endpoints).
function _asList(j) {
  const data = j && j.data !== undefined ? j.data : j
  if (Array.isArray(data)) return data
  if (data && Array.isArray(data.results)) return data.results
  if (data && Array.isArray(data.items)) return data.items
  return []
}

// Normalize an envelope-style or bare response into a plain object (detail endpoints).
function _asObj(j) {
  if (j && j.data !== undefined && j.data !== null && typeof j.data === 'object') return j.data
  return j
}

// GET a list endpoint → array of entities.
async function apiGetList(page, path, token) {
  const r = await page.request.get(path, {
    headers: { Authorization: `Token ${token}` },
    failOnStatusCode: false,
  })
  const j = await r.json().catch(() => ({}))
  return _asList(j)
}

// GET a detail endpoint → object.
async function apiGet(page, path, token) {
  const r = await page.request.get(path, {
    headers: { Authorization: `Token ${token}` },
    failOnStatusCode: false,
  })
  const j = await r.json().catch(() => ({}))
  return _asObj(j)
}

// DELETE an entity by id (authoritative cleanup for dev SQLite DB).
async function apiDelete(page, path, token) {
  return await page.request.delete(path, {
    headers: { Authorization: `Token ${token}` },
    failOnStatusCode: false,
  })
}

// Delete every entity of `type` (e.g. 'research-goals' | 'applications' | 'methods')
// whose name exactly equals `name`. Used to remove orphans created by KnowledgeIntake
// get_or_create without touching any seeded (Chinese-named) entities.
async function deleteEntityByName(page, token, type, name) {
  const list = await apiGetList(page, `/api/v1/${type}/?page_size=500`, token)
  for (const e of list) {
    if (e && e.name === name) {
      await apiDelete(page, `/api/v1/${type}/${e.id}/`, token)
    }
  }
}

// Clean up KnowledgeIntake orphans: the form uses chip option names that are NOT
// present in the seeded (Chinese) DB, so get_or_create would create them. We remove
// exactly those names so the database returns to baseline.
async function cleanupKnowledgeIntakeOrphans(page, token, selections) {
  for (const n of selections.research_goals || []) await deleteEntityByName(page, token, 'research-goals', n)
  for (const n of selections.applications || []) await deleteEntityByName(page, token, 'applications', n)
  for (const n of selections.methods || []) await deleteEntityByName(page, token, 'methods', n)
}

// GET product detail (persisted fields) by id.
async function getProductDetail(page, id, token) {
  return await apiGet(page, `/api/v1/products/${id}/`, token)
}

// ── Mock helpers (page.route) ──

// Mock the outbound PubMed literature endpoint. Pattern covers both the edit-mode
// `/products/<pk>/recommend-literature/` and the unsaved `/products/recommend-literature-unsaved/`.
// Returns a full envelope `{success, data}` (closest to real backend shape).
function mockRecommendLiterature(page, { failure = false, refs = null } = {}) {
  const handler = (route) => {
    if (failure) {
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        json: { success: false, data: null, meta: { error: { code: 'error', message: 'recommend literature failed' } } },
      })
    }
    const data = refs || [
      { pmid: '24151973', title: 'Sample E2E Literature A', authors: 'Doe J, Smith A', journal: 'Nature', year: 2020 },
      { pmid: '25959142', title: 'Sample E2E Literature B', authors: 'Lee K', journal: 'Cell', year: 2021 },
    ]
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: { success: true, data },
    })
  }
  // Pattern covers BOTH the edit-mode `/products/<pk>/recommend-literature/` AND the
  // new/unsaved `/products/recommend-literature-unsaved/` endpoints.
  return page.route('**/products/**/recommend-literature**', handler)
}

// Delay a real (offline) endpoint so the UI loading state is observable, then continue
// to the real backend. Used to deterministically assert the "loading" state. We re-fetch
// the real response and replay it after a delay (more deterministic than continue()+timer,
// which can race with the route lifecycle and silently drop the response).
function delayRoute(page, pattern, ms) {
  return page.route(pattern, async (route) => {
    try {
      const response = await route.fetch()
      await new Promise((resolve) => setTimeout(resolve, ms))
      await route.fulfill({ response })
    } catch (e) {
      // If the real fetch fails, fall back to continuing the original request.
      try { await route.continue() } catch (_) { /* noop */ }
    }
  })
}

// ── AI AUTO MATCH (enrich) mock ──
// Mock the one-stop enrich endpoint `POST /api/v1/products/enrich/` (merged from the
// former AI Tools: Validate / Recommend Protocols / Recommend Literature, see commit
// f324de0). The real endpoint calls external LLM / PubChem APIs which would burn tokens
// in e2e, so every AI AUTO MATCH interaction in the suite is mocked here.
// Returns a full envelope `{ success, data }` matching what the http.js interceptor
// unwraps (`resp.data` → `{ chemical, literature, protocols, jena, bioz }`).
const DEFAULT_ENRICH_DATA = {
  chemical: {
    found: true,
    source: 'pubchem',
    cid: '999999',
    resolved_name: 'E2E Mock Compound',
    identity_verified: true,
    confidence: 'high',
    fallback_used: false,
    cas_resolved: '62-53-3',
    search_note: null,
    doc_value_mismatch: false,
    candidates: [],
    lipinski: {
      passed: true,
      violations: [],
      details: { mw_ok: true, logp_ok: true, hbd_ok: true, hba_ok: true, rot_ok: true },
    },
    mismatches: [],
    similar_compounds: [],
    properties: {
      canonical_smiles: 'C1=CC=C(C=C1)N',
      molecular_formula: 'C6H7N',
      molecular_weight: 93.13,
    },
  },
  literature: { references: [] },
  protocols: [],
  jena: null,
  bioz: null,
}
function mockEnrich(page, { failure = false, delay = 0, data = null } = {}) {
  const handler = async (route) => {
    if (delay > 0) {
      await new Promise((resolve) => setTimeout(resolve, delay))
    }
    if (failure) {
      // 注意：必须返回 HTTP 500 而非「200 + success:false」。http.js 拦截器对 2xx 响应
      // 无条件透传（status>=200 直接 return data），200+success:false 会被当作成功，
      // 前端拿到 resp.data=null 而不会进入 catch 渲染错误态。
      return route.fulfill({
        status: 500,
        contentType: 'application/json',
        json: { meta: { error: { code: 'error', message: 'Enrich failed' } } },
      })
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      json: { success: true, data: data || DEFAULT_ENRICH_DATA },
    })
  }
  // 注意 `enrich**` 用双星号：URL 以尾斜杠结尾（.../enrich/），单星号 `enrich*` 不匹配 `/`
  return page.route('**/api/v1/products/enrich**', handler)
}

module.exports = {
  test, expect, login, gotoWorkspace, cleanupE2EProduct, selectFirstCascader,
  getToken, apiGetList, apiGet, apiDelete, deleteEntityByName,
  cleanupKnowledgeIntakeOrphans, getProductDetail,
  mockRecommendLiterature, delayRoute, mockEnrich, PROCESS_POLYFILL,
  ADMIN_USER, ADMIN_PASS,
}
