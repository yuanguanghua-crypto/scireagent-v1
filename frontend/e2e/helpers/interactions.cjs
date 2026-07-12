/**
 * 交互 helper —— 基于真实组件（混合使用 Element Plus 与自定义组件）。
 *
 * 真实组件事实（来自 INTERACTION_INVENTORY.md + 现有 spec 核对）：
 *  - 弹窗：自定义 `.dialog` + `.dialog-overlay`（也可用 `.modal-*` 变体），非 el-dialog
 *  - Toast：自定义 `.toast` / `.save-message` / `.ki-toast` + Element Plus `.el-message`
 *          （`.el-message--error` / `.el-message--success`）
 *  - 原生 alert / confirm：PoSubmit / PoAddressList / OrderDetailPage / AdminOrderDetail
 *  - 排序：`<th class="sortable" @click>`
 *  - 分页：`<DataPagination>`（`:total` / `:page-size` / `@current-change`）
 *  - 选择：少量 el-select；多选/分类用原生 <select> 或 AppSelect
 *
 * 选择器策略：优先 data-testid，其次文本 / 角色 / 真实 class，兼容两种组件库。
 */
const { expect } = require('@playwright/test');

async function clickButton(page, { text, testId, exact = false, role = 'button' } = {}) {
  let loc;
  if (testId) loc = page.locator(`[data-testid="${testId}"]`);
  else if (text) {
    loc = exact
      ? page.getByRole(role, { name: text, exact: true })
      : page.getByRole(role, { name: text });
    // 退化：某些按钮是 <a class="btn"> 或自定义组件，role 匹配不到时回落到文本
    if ((await loc.count()) === 0) {
      loc = page.locator(`button:has-text("${text}"), a:has-text("${text}")`).first();
    }
  } else loc = page.locator('button').first();
  await loc.first().click();
  return loc.first();
}

async function waitForDialog(page, { timeout = 5000 } = {}) {
  await expect(page.locator('.dialog-overlay, .dialog, .modal-overlay, .modal').first()).toBeVisible({ timeout });
}

async function closeDialogByCancel(page) {
  const dlg = page.locator('.dialog-overlay, .dialog, .modal-overlay, .modal').first();
  const cancel = dlg
    .locator('button', { hasText: /Cancel|Close|取消|关闭|No/ })
    .first();
  await cancel.click();
}

async function fillField(page, { placeholder, testId, label, value, textarea = false } = {}) {
  let loc;
  if (testId) loc = page.locator(`[data-testid="${testId}"]`);
  else if (placeholder) {
    const sel = textarea
      ? `textarea[placeholder*="${placeholder}"], textarea[placeholder="${placeholder}"]`
      : `input[placeholder*="${placeholder}"], input[placeholder="${placeholder}"]`;
    loc = page.locator(sel).first();
  } else if (label) {
    loc = page.locator(`input[aria-label="${label}"], textarea[aria-label="${label}"]`).first();
  } else throw new Error('fillField: 需提供 placeholder / testId / label');
  await loc.fill(value);
  return loc;
}

async function waitForToast(page, text, { timeout = 8000, type = null } = {}) {
  const base = '.toast, .save-message, .ki-toast, .el-message, .el-message--error, .el-message--success';
  const loc = page.locator(base).filter({ hasText: text }).first();
  await expect(loc).toBeVisible({ timeout });
  return loc;
}

async function handleDialog(page, { accept = true } = {}) {
  // 处理原生 alert / confirm
  page.on('dialog', async (d) => {
    if (accept) await d.accept();
    else await d.dismiss();
  });
}

async function waitForLoadingGone(page, { timeout = 20000 } = {}) {
  const loc = page
    .locator('[v-loading="true"], [aria-busy="true"], .loading-spinner, .v-loading, .loading')
    .first();
  // 加载态可能不存在（直接通过），用 catch 容错
  await expect(loc).toHaveCount(0, { timeout }).catch(() => {});
}

async function sortByColumn(page, thText) {
  const th = page.locator('th.sortable', { hasText: thText }).first();
  await th.click();
}

async function paginate(page, { page: p } = {}) {
  const btn = page.locator('.data-pagination button', { hasText: String(p) }).first();
  await btn.click();
}

async function selectNative(page, selectLocator, value) {
  await selectLocator.selectOption({ label: value });
}

module.exports = {
  clickButton,
  waitForDialog,
  closeDialogByCancel,
  fillField,
  waitForToast,
  handleDialog,
  waitForLoadingGone,
  sortByColumn,
  paginate,
  selectNative,
};
