/**
 * 3 步注册向导 · 多步交互 E2E（补齐 INTERACTION_VERDICT 里 /login 与 /register 的「3步注册」空白）
 *
 * ## 组件真相（先读码，不猜）
 * `/register` 与 `/login` 是**两个不同组件**（`router/index.js:31-34` 只把 /register 指向 RegisterPage；
 * `/login` 指向 LoginPage）。所以「/login 的 3 步注册」= 从登录页点 `Create one`
 * （`LoginPage.vue:218` 的 `<router-link to="/register">Create one</router-link>`）进入同一个向导。
 *
 * 向导状态机（`RegisterPage.vue`）：
 *   - `currentStep` ref(1)（:12）
 *   - `showStep3 = selectedOrgChoice && selectedOrgChoice !== 'solo'`（:89）
 *     ⇒ 选「Independent Researcher（solo）」会**跳过第 3 步直接提交**（:204-206）
 *   - `canProceedStep1`（:91-96）：username≥3 / email 正则 / password≥8 / 两次一致
 *   - `canProceedStep2`（:98-100）：role + orgChoice 都选
 *   - `canCompleteStep3`（:102-107）：join 分支必须有 selectedOrgId；create 分支 name≥2 且有 org_type
 *   - `nextStep()`（:196-211）、`prevStep()`（:213-218）、`handleSubmit()`（:257-321）
 *
 * 实际选择器证据：
 *   - `#reg-username` / `#reg-email` / `#reg-password` / `#reg-password-confirm`（:445/:461/:477/:501）
 *   - 步骤 1 提交按钮 `.auth-submit`（文本 Next）：`:disabled="!canProceedStep1"`（:514）
 *   - 步骤 2 角色卡 `.role-card`（:531），文案 'Independent Researcher' / 'Researcher (Team)' / 'Procurement Manager'（:58-86）
 *   - 步骤 2 的 Next：`:disabled="!canProceedStep2"`（:561）；Back 为 `.btn-back`（:555）
 *   - 步骤 3 tab：`.org-tab`，'Join Existing' / 'Create New'（:579-594）
 *   - 步骤 3 建组织表单：`#org-name`（:651）、`#org-type`（:664，默认 academic）
 *   - 步骤 3 提交按钮文本 'Complete Registration'：`:disabled="!canCompleteStep3 || loading"`（:684-688）
 *   - 服务端错误横幅 `.auth-error-banner`（:430-437）
 *   - 步骤指标 `.step-item` / `.step-label`（:368-393），第 3 个指标 `v-if="showStep3"`（:388-392）
 *
 * ## 关键纪律
 * - ⚠️ **绝不真正注册成功**（会往开发库留垃圾用户 + 撞登录限流）：
 *   所有用例都**停在「校验通过但未点提交」**；唯一的提交动作在最后一个用例里，
 *   且**注入 500 拦截**（请求不出浏览器）⇒ 本 spec **零写入**。
 * - 只用 `page.goto('/register')` 复位步骤，不做真实提交，故不消耗 `/auth/login` 限流。
 *
 * 运行：
 *   cd frontend && npx playwright test e2e/register-wizard.spec.cjs --project=chromium \
 *     --reporter=line --output=/tmp/pw-reg
 */
const { test, expect } = require('@playwright/test');
const { BASE_URL } = require('./helpers/auth.cjs');

const RX_REGISTER = /\/api\/v1\/auth\/register\/?(\?.*)?$/; // api/auth.js:4 `http.post('/auth/register')`

/** 填满步骤 1（不提交）；返回本次使用的用户名，供回退断言用 */
async function fillStep1(page, tag) {
  const suffix = `${Date.now()}${Math.floor(Math.random() * 1000)}`;
  const username = `e2e_wiz_${tag}_${suffix}`.slice(0, 40);
  await page.locator('#reg-username').fill(username);
  await page.locator('#reg-email').fill(`${username}@example.com`);
  await page.locator('#reg-password').fill('E2ePass123!');
  await page.locator('#reg-password-confirm').fill('E2ePass123!');
  return username;
}

/** 步骤 1 → 2 */
async function goStep2(page, tag) {
  await fillStep1(page, tag);
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page.getByText('How will you use SciReagent?')).toBeVisible();
}

/**
 * 精确定位角色卡：必须限定在 `.role-card__title`（:537）上做匹配。
 * ⚠️ 直接对 `.role-card` 用 hasText='Procurement Manager' 会同时命中
 *   「Researcher (Team)」卡的描述文案 "My organization has a procurement manager" ⇒ strict mode 冲突。
 */
function roleCard(page, title) {
  return page.locator('.role-card').filter({ has: page.locator('.role-card__title', { hasText: title }) });
}

/** 步骤 2 → 3（必须选 orgChoice !== 'solo' 的角色，否则会直接提交） */
async function goStep3(page, tag, cardText = 'Procurement Manager') {
  await goStep2(page, tag);
  await roleCard(page, cardText).click();
  await page.getByRole('button', { name: 'Next' }).click();
  await expect(page.getByText('Find or create your organization')).toBeVisible();
}

test.describe('3 步注册向导（零写入）', () => {
  test('/login 点 "Create one" 进入 /register，初始为步骤 1 且只有 2 个步骤指标', async ({ page }) => {
    await page.goto(`${BASE_URL}/login`, { waitUntil: 'domcontentloaded' });

    // LoginPage.vue:218 —— 登录页到注册页的唯一入口
    await page.getByRole('link', { name: 'Create one' }).click();
    await expect(page).toHaveURL(/\/register/);

    // 步骤 1 内容（RegisterPage.vue:440-441）
    await expect(page.locator('#reg-username')).toBeVisible();
    await expect(page.getByText('Create Account')).toBeVisible();

    // 步骤指标：Basics / Identity 常在；Organization 要等步骤 2 选了非 solo 角色才出现（:388 v-if="showStep3"）
    await expect(page.locator('.step-item')).toHaveCount(2);
    await expect(page.locator('.step-label').nth(0)).toHaveText('Basics');
    await expect(page.locator('.step-label').nth(1)).toHaveText('Identity');
    await expect(page.getByText('Organization', { exact: true })).toHaveCount(0);
  });

  test('步骤 1 必填校验：Next 禁用 + 4 条字段错误文案逐条出现', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`, { waitUntil: 'domcontentloaded' });

    const next = page.getByRole('button', { name: 'Next' });
    await expect(next).toBeDisabled(); // :514 :disabled="!canProceedStep1"

    // 用户名过短（RegisterPage.vue:124-125）
    await page.locator('#reg-username').fill('ab');
    await page.locator('#reg-email').click(); // blur 触发 validateField('username')
    await expect(page.locator('.form-error').filter({ hasText: 'Username must be at least 3 characters' })).toBeVisible();

    // 邮箱格式错误（:135-136）
    await page.locator('#reg-email').fill('not-an-email');
    await page.locator('#reg-password').click();
    await expect(page.locator('.form-error').filter({ hasText: 'Please enter a valid email address' })).toBeVisible();

    // 密码过短（:144-145）
    await page.locator('#reg-password').fill('short');
    await page.locator('#reg-password-confirm').click();
    await expect(page.locator('.form-error').filter({ hasText: 'Password must be at least 8 characters' })).toBeVisible();

    // 两次密码不一致（:155-156）
    await page.locator('#reg-password').fill('E2ePass123!');
    await page.locator('#reg-password-confirm').fill('E2ePass999!');
    await page.locator('#reg-username').click();
    await expect(page.locator('.form-error').filter({ hasText: 'Passwords do not match' })).toBeVisible();

    // 拦截有效：仍然停在步骤 1，没有进入角色选择
    await expect(page.locator('#reg-username')).toBeVisible();
    await expect(page.getByText('How will you use SciReagent?')).toHaveCount(0);
    await expect(next).toBeDisabled();
  });

  test('步骤 1 → 2 → 3 推进；第 3 步指标出现；Back 回退保留已填值', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`, { waitUntil: 'domcontentloaded' });
    const username = await fillStep1(page, 'fwd');

    // 校验全绿后 Next 才可点（:514）
    const next1 = page.getByRole('button', { name: 'Next' });
    await expect(next1).toBeEnabled();
    await next1.click();

    // ── 步骤 2 ──
    await expect(page.getByText('How will you use SciReagent?')).toBeVisible();
    await expect(page.locator('.role-card')).toHaveCount(3); // :58-86 三张角色卡
    const next2 = page.getByRole('button', { name: 'Next' });
    await expect(next2).toBeDisabled(); // :561 未选角色

    await roleCard(page, 'Researcher (Team)').click();
    await expect(page.locator('.role-card--selected')).toHaveCount(1); // 选中态（:532）
    await expect(next2).toBeEnabled();
    await next2.click();

    // ── 步骤 3 ──
    await expect(page.getByText('Find or create your organization')).toBeVisible();
    await expect(page.locator('.step-item')).toHaveCount(3); // Organization 指标出现（:388-392）
    await expect(page.getByText('Organization', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Join Existing' })).toBeVisible();
    await expect(page.getByRole('button', { name: 'Create New' })).toBeVisible();
    // 未选组织前不可提交（:102-107 + :687）
    await expect(page.getByRole('button', { name: 'Complete Registration' })).toBeDisabled();

    // ── 回退：3 → 2 → 1，且步骤 1 的值被保留（currentStep 只是切换，不清 form）──
    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.getByText('How will you use SciReagent?')).toBeVisible();
    await expect(page.locator('.role-card--selected')).toHaveCount(1); // 角色选择也保留

    await page.getByRole('button', { name: 'Back' }).click();
    await expect(page.locator('#reg-username')).toBeVisible();
    await expect(page.locator('#reg-username')).toHaveValue(username);
    await expect(page.locator('#reg-email')).toHaveValue(`${username}@example.com`);
    await expect(page.locator('#reg-password')).toHaveValue('E2ePass123!');
  });

  test('步骤 3「Create New」分支：组织名为空/过短时不可提交，填够后按钮才可用（停在提交前）', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`, { waitUntil: 'domcontentloaded' });
    await goStep3(page, 'org');

    await page.getByRole('button', { name: 'Create New' }).click();
    const submit = page.getByRole('button', { name: 'Complete Registration' });

    // canCompleteStep3 的 create 分支：name ≥ 2 且 org_type 非空（:106）
    await expect(submit).toBeDisabled();
    await page.locator('#org-name').fill('A');
    await expect(submit).toBeDisabled();
    await page.locator('#org-name').fill('E2E Demo Org');
    await expect(submit).toBeEnabled();

    // ⚠️ 到此为止 —— 不点击提交，全程零写入
    await expect(page.locator('#org-name')).toHaveValue('E2E Demo Org');
    // 切回 Join 分支同样应是禁用（selectedOrgId 已清空，见 :339-345 的 watch）
    await page.getByRole('button', { name: 'Join Existing' }).click();
    await expect(submit).toBeDisabled();
  });

  test('最后一步提交命中 500 ⇒ .auth-error-banner 出现；不进「查收验证邮件」页（零写入）', async ({ page }) => {
    await page.goto(`${BASE_URL}/register`, { waitUntil: 'domcontentloaded' });
    await goStep3(page, 'fail');

    await page.getByRole('button', { name: 'Create New' }).click();
    await page.locator('#org-name').fill('E2E Injected Org');
    const submit = page.getByRole('button', { name: 'Complete Registration' });
    await expect(submit).toBeEnabled();

    // 注入失败：POST /api/v1/auth/register 被打回 500，请求不出浏览器
    await page.route(RX_REGISTER, (route) =>
      route.fulfill({
        status: 500,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Injected failure for E2E' }),
      }),
    );

    await submit.click();

    // RegisterPage.vue:430-437 的持久错误横幅；文案来自 :309-313 的 errData.detail
    await expect(page.locator('.auth-error-banner')).toBeVisible({ timeout: 10000 });
    await expect(page.locator('.auth-error-banner')).toContainText('Injected failure for E2E');

    // 没成功：不出现「We've sent a verification link」内联页（:396-407），仍停在步骤 3
    await expect(page.getByText(/We've sent a verification link/)).toHaveCount(0);
    await expect(page.getByText('Create Account')).toBeVisible();
    await expect(page.locator('#org-name')).toBeVisible();
    await expect(page).toHaveURL(/\/register/);
  });
});
