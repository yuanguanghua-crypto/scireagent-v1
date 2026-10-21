/**
 * `/po/addresses` · I 维空白补齐 —— Address CRUD 完整闭环（新增 → 改 → 删）
 *
 * 背景：INTERACTION_VERDICT.md 里 `/po/addresses` 的「CRUD」为 **✗**（只测过 showForm 弹层
 * 与 confirm 删除）。本 spec 用**真 UI** 走完整闭环，并验「效果」（列表行出现/改了/消失），
 * 不以 toast 作为通过依据。
 *
 * ## 为什么用 procurement（e2e_proc）登录，而不是 admin
 * 后端 `AddressPermission`（backend/apps/accounts/api/v1/views.py:254-265）规定：
 *   读 = 任意登录用户（但只可见本机构）；写 = **采购或管理员**。
 * 而 `AddressViewSet.create`（views.py:295-304）在 `request.user.organization` 为空时直接
 * 返回 400 `NO_ORGANIZATION`。dev 库里 admin(id=1) **没有 organization**，e2e_proc(id=15)
 * 属于 org 6「E2E Supplier Ops」⇒ 只有 procurement 这条路径能真正走通写操作。
 * /po/addresses 的路由守卫只要求 requiresAuth（frontend/src/router/index.js:206-209），
 * 因此 procurement 可以正常进入该页。
 *
 * ## 数据标记 / 清理
 * Attention 一律为 `E2E-<ts>-<4位随机>`；`afterAll` 按该标记**精确**匹配后删除自己创建的那条。
 * 删除走接口仅用于**清理**（本页 UI 也有删除入口，被测路径仍全部走 UI），代码里有注释说明。
 *
 * ## 运行
 *   npx playwright test e2e/po-addresses-crud.spec.cjs --project=chromium \
 *     --reporter=line --output=/tmp/pw-po
 */
const { test, expect, request } = require('@playwright/test');
const {
  BASE_URL, loginAsProcurement, PROC_USER, PROC_PASS,
} = require('./helpers/auth.cjs');

const ROOT = 'http://localhost:8000';
const API = '/api/v1';

// 本轮创建的地址标记（afterAll 精确清理）
const createdTags = [];

function makeTag() {
  return `E2E-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
}

async function procToken() {
  const ctx = await request.newContext({ baseURL: ROOT });
  try {
    const res = await ctx.post(`${API}/auth/login`, { data: { username: PROC_USER, password: PROC_PASS } });
    return (await res.json())?.data?.token || null;
  } finally {
    await ctx.dispose();
  }
}

/**
 * 清理：只删「attention 里带我这次标记」的地址（精确 startsWith），绝不清空全表。
 * 说明：清理不属于被测路径（被测路径 = 页面上的 New/Edit/Delete 按钮），
 * 这里只是兜底 —— 若用例中途失败没走到 UI 删除，不至于把脏数据留在共享 dev 库。
 */
test.afterAll(async () => {
  if (!createdTags.length) return;
  const token = await procToken();
  if (!token) return;
  const ctx = await request.newContext({ baseURL: ROOT });
  try {
    const res = await ctx.get(`${API}/addresses/`, { headers: { Authorization: `Token ${token}` } });
    const body = await res.json();
    const rows = body?.data?.results || body?.data || [];
    for (const a of rows) {
      if (!createdTags.some((t) => (a.attention || '').startsWith(t))) continue;
      const del = await ctx.delete(`${API}/addresses/${a.id}/`, {
        headers: { Authorization: `Token ${token}` },
      });
      if (!del.ok()) console.warn(`[cleanup] 删除地址 id=${a.id} 失败：${del.status()}`);
    }
  } finally {
    await ctx.dispose();
  }
});

/* ─────────────── 表单填写（选择器证据见 src/views/po/PoAddressList.vue） ───────────────
 *  - 「+ New Address」按钮            :72
 *  - 表单卡片标题 New/Edit Address     :80
 *  - 字段：Attention :94 / Line1 :102 / City :108 / State :109 / Postal :110 / Country :90
 *  - Save :118 / Cancel :119
 *  - 列表行：Type/Attention/Address/Country + Edit :136 / Delete :137
 */
function field(page, label) {
  return page.locator('.po-field').filter({ hasText: label }).locator('input').first();
}

async function fillAddressForm(page, { attention, line1, city, state, postal }) {
  await field(page, 'Attention').fill(attention);
  await field(page, 'Address Line 1').fill(line1);
  await field(page, 'City').fill(city);
  await field(page, 'State').fill(state);
  await field(page, 'Postal Code').fill(postal);
}

test.describe('@local-only /po/addresses · CRUD 闭环', { tag: ['@local-only'] }, () => {
  /** ★ D9 回归（2026-10-21 已修）：页面曾挂着一条过期 callout
   *  「Backend /addresses/ CRUD is scheduled for P1. Save actions will surface an error toast
   *   until the endpoint ships.」—— 实测 CRUD 早已全通，留着会让用户以为功能不可用。 */
  test('页面不得再显示「CRUD 未上线」的过期提示', async ({ page }) => {
    // 该页 requiresAuth 即可访问；沿用本文件既有角色（procurement）
    await loginAsProcurement(page)
    await page.goto(`${BASE_URL}/po/addresses`, { waitUntil: 'domcontentloaded' })
    await expect(page.locator('.po-page')).toBeVisible({ timeout: 20000 })
    await expect(
      page.getByText(/scheduled for P1|until the endpoint ships/i),
      '过期文案「CRUD 计划 P1 落地」必须已删除',
    ).toHaveCount(0)
  })

  test('新增 → 列表出现该行 → 编辑 → 行内容更新 → 删除 → 行消失（且刷新后仍消失）', async ({ page }) => {
    test.setTimeout(120000);

    const tag = makeTag();
    createdTags.push(tag);
    const editedTag = `${tag}-EDITED`;

    await loginAsProcurement(page);
    await page.goto(`${BASE_URL}/po/addresses`, { waitUntil: 'domcontentloaded' });
    await expect(page.locator('h1.po-page-title', { hasText: 'Address Book' })).toBeVisible();

    /* ── ① 新增 ── */
    await page.getByRole('button', { name: '+ New Address' }).click();
    const form = page.locator('.po-card').filter({ hasText: 'New Address' });
    await expect(form).toBeVisible({ timeout: 10000 });
    await fillAddressForm(page, {
      attention: tag,
      line1: `${tag} 1 Lab Way`,
      city: 'Boston',
      state: 'MA',
      postal: '02115',
    });
    await form.getByRole('button', { name: 'Save' }).click();

    // 断言效果 1：表单收起
    await expect(form).toBeHidden({ timeout: 15000 });
    // 断言效果 2：列表里出现这一行（按唯一标记定位，不断言总行数）
    const createdRow = page.locator('tbody tr').filter({ hasText: tag });
    await expect(createdRow).toBeVisible({ timeout: 15000 });
    await expect(createdRow).toContainText('Boston');
    await expect(createdRow).toContainText('02115');

    // 断言效果 3：刷新后仍在（落库，非前端乐观插入）
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('tbody tr').filter({ hasText: tag })).toBeVisible({ timeout: 15000 });

    /* ── ② 编辑（只改 Attention / City） ── */
    const rowToEdit = page.locator('tbody tr').filter({ hasText: tag });
    await rowToEdit.getByRole('button', { name: 'Edit' }).click();
    const editForm = page.locator('.po-card').filter({ hasText: 'Edit Address' });
    await expect(editForm).toBeVisible({ timeout: 10000 });
    // 打开编辑时应回填原值（真实交互，不是空表单）
    await expect(field(page, 'Attention')).toHaveValue(tag);
    await field(page, 'Attention').fill(editedTag);
    await field(page, 'City').fill('Cambridge');
    await editForm.getByRole('button', { name: 'Save' }).click();

    // 断言效果 4：同一行内容更新为新值（旧 attention 不再作为该行文本）
    const editedRow = page.locator('tbody tr').filter({ hasText: editedTag });
    await expect(editedRow).toBeVisible({ timeout: 15000 });
    await expect(editedRow).toContainText('Cambridge');
    await expect(page.locator('tbody tr').filter({ hasText: tag }).filter({ hasNotText: editedTag })).toHaveCount(0);

    /* ── ③ 删除（window.confirm 需 accept） ── */
    page.once('dialog', (d) => d.accept());
    await editedRow.getByRole('button', { name: 'Delete' }).click();

    // 断言效果 5：该行从列表消失
    await expect(page.locator('tbody tr').filter({ hasText: editedTag })).toHaveCount(0, { timeout: 15000 });
    // 断言效果 6：刷新后依然不存在（服务端已删）
    await page.reload({ waitUntil: 'domcontentloaded' });
    await expect(page.locator('tbody tr').filter({ hasText: editedTag })).toHaveCount(0, { timeout: 15000 });
  });
});
