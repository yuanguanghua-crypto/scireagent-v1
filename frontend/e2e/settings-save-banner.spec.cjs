/**
 * I 维补白（2/3）：`/settings` 的 `saveMessage` 横幅
 *
 * ## 为什么需要
 * `docs/e2e/INTERACTION_VERDICT.md` 里 `/settings` 的「保存」已被 cascader-workflow /
 * knowledge-intake 等 spec 关键词命中，但「saveMessage 横幅」是 **✗ 无 spec**。
 * 也就是说：既往用例只证明"点了保存没报错"，**没证明页面对用户给出了成功反馈**。
 *
 * ## 读码结论（选择器证据）
 * - 横幅：`SettingsPage.vue:269-283`
 *     `<div v-if="saveMessage" class="save-message" :class="`save-message--${type}`">`
 *     ⇒ 成功态类名 `save-message--success`（`:679-682`）
 * - 文案：`showSaveMessage('Profile updated successfully.', 'success')`（`:135`）
 * - 自动消失：`showSaveMessage()` 里 `setTimeout(clearSaveMessage, 4000)`（`:228-232`）
 * - 切 tab 也会清：`switchTab()` → `clearSaveMessage()`（`:238-242`）
 * - 保存动作：Profile 页签表单 `@submit.prevent="saveProfile"`（`:292`），按钮 `.btn-save`（`:354`）
 *
 * ## 幂等纪律（关键）
 * 保存会**真写后端**（`authStore.updateProfile` → `PUT /api/v1/auth/profile`，`:128-134`）。
 * 为不污染共享 dev 库：
 *   1. 先把输入框的**当前值原样回填**（值不变 ⇒ 写回同样的值）
 *   2. 保存前用 `GET /api/v1/auth/me` 核对"页面预填 == 服务端值"，
 *      否则（例如 user 未加载导致输入框全空）立即失败 —— **绝不把空值写回去**
 *   3. 保存后再 GET 一次，断言字段**没有变化**（幂等证据）
 * 这里没有 snapshotDb()，也没有 Δ 计数断言。
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/settings-save-banner.spec.cjs --project=chromium --output=/tmp/pw-ui
 */

const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsStaff } = require('./helpers/auth.cjs');

/** Profile 页签的 5 个字段（SettingsPage.vue:294-350 的 id） */
const PROFILE_FIELDS = {
  '#avatar-url': 'avatar_url',
  '#nickname': 'nickname',
  '#phone': 'phone',
  '#department': 'department',
  '#title': 'title',
};

/** 用页面里已有的 token 读 /auth/me（不额外登录，避免 5 次/分钟限流） */
async function fetchMe(page) {
  const token = await page.evaluate(() => localStorage.getItem('token'));
  const resp = await page.request.get(`${BASE_URL}/api/v1/auth/me`, {
    headers: { 'X-Auth-Token': token },
  });
  expect(resp.status(), 'GET /auth/me 应 200（token 有效）').toBe(200);
  const body = await resp.json();
  return body.data || body;
}

/** 打开 /settings 并等到 Profile 表单预填完成 */
async function openSettings(page) {
  await loginAsStaff(page);
  await page.goto(`${BASE_URL}/settings`, { waitUntil: 'domcontentloaded' });
  await page.waitForSelector('.settings-page', { timeout: 15000 });
  await expect(page.locator('.sidebar-tab--active')).toHaveText(/Profile/, { timeout: 10000 });
  await expect(page.locator('#nickname')).toBeVisible({ timeout: 15000 });
}

/** 把输入框当前值原样再填一次，并校验与服务端一致（幂等 + 防清空） */
async function fillSameValues(page) {
  const me = await fetchMe(page);
  for (const [selector, key] of Object.entries(PROFILE_FIELDS)) {
    const inp = page.locator(selector);
    const shown = (await inp.inputValue()) ?? '';
    expect(
      shown,
      `「${key}」预填值应与服务端一致（若此处失败=页面没加载出用户，继续保存会把字段清空）`,
    ).toBe(String(me[key] ?? ''));
    // 原样回填：确保 v-model 与 DOM 同步，值不发生任何改变
    await inp.fill(shown);
  }
  return me;
}

test.describe('@settings 保存成功横幅', { tag: ['@write', '@local-only'] }, () => {
  test('保存 Profile（值不变）⇒ 出现 save-message success 横幅', async ({ page }) => {
    await openSettings(page);
    const before = await fillSameValues(page);

    await page.locator('.btn-save').click();

    // 横幅：SettingsPage.vue:271（class 含 save-message--success）
    const banner = page.locator('.save-message');
    await expect(banner, '保存后应出现 saveMessage 横幅').toBeVisible({ timeout: 15000 });
    await expect(banner).toHaveClass(/save-message--success/);
    await expect(banner).toHaveText(/Profile updated successfully/i);

    // 幂等证据：服务端字段没被改动
    const after = await fetchMe(page);
    for (const key of Object.values(PROFILE_FIELDS)) {
      expect(String(after[key] ?? ''), `「${key}」保存后应保持不变`).toBe(String(before[key] ?? ''));
    }
    expect(page.url(), '保存后应仍停在 /settings').toContain('/settings');
    console.log(`__E2E__ settings 横幅出现：${((await banner.textContent()) || '').trim()}`);
  });

  test('横幅 4s 后自动消失（瞬时提示，非常驻）', async ({ page }) => {
    await openSettings(page);
    await fillSameValues(page);

    await page.locator('.btn-save').click();
    await expect(page.locator('.save-message')).toBeVisible({ timeout: 15000 });

    // setTimeout(clearSaveMessage, 4000)（SettingsPage.vue:231）⇒ 8s 内必须消失
    await expect(page.locator('.save-message'), '横幅应在 4s 后自动消失').toHaveCount(0, {
      timeout: 10000,
    });
  });

  test('切到其它页签 ⇒ 横幅被清空（switchTab 行为）', async ({ page }) => {
    await openSettings(page);
    await fillSameValues(page);

    await page.locator('.btn-save').click();
    await expect(page.locator('.save-message')).toBeVisible({ timeout: 15000 });

    // SettingsPage.vue:238-242：switchTab → clearSaveMessage
    await page.locator('.sidebar-tab', { hasText: 'Contact' }).click();
    await expect(page.locator('.save-message')).toHaveCount(0, { timeout: 5000 });
    await expect(page.locator('#alt-email'), '切到 Contact 应渲染联系页表单').toBeVisible();
  });
});
