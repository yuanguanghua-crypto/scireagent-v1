const { test, expect } = require('@playwright/test');
const { BASE_URL, loginAsCustomer } = require('../helpers/auth');

test('DEBUG quote checkout', async ({ page }) => {
  await loginAsCustomer(page);
  await page.goto(`${BASE_URL}/products/66`, { waitUntil: 'domcontentloaded' });
  await page.getByRole('button', { name: 'Add to Cart' }).first().click();
  await expect(page.locator('.el-message').first()).toBeVisible({ timeout: 8000 });
  await page.goto(`${BASE_URL}/checkout`, { waitUntil: 'domcontentloaded' });
  await expect(page.locator('.checkout-form').first()).toBeVisible({ timeout: 8000 });

  const pmBefore = await page.locator('input[type="radio"][value="quote"]').isChecked().catch(() => 'n/a');
  await page.locator('input[type="radio"][value="quote"]').check();
  await page.getByPlaceholder('Dr. John Smith').fill('Dr. E2E Quote');
  await page.getByPlaceholder('123 Lab Street, Cambridge, MA 02139, USA').fill('123 E2E Street, Test City');
  const btnText = await page.getByRole('button', { name: /Request Quote|Place Order/ }).first().innerText();
  console.log('BUTTON_TEXT=', JSON.stringify(btnText));
  await page.getByRole('button', { name: 'Request Quote' }).click();
  await page.waitForTimeout(4000);
  console.log('URL=', page.url());
  const banner = await page.locator('.error-banner').first().innerText().catch(() => '(no banner)');
  console.log('BANNER=', JSON.stringify(banner));
  const msg = await page.locator('.el-message').first().innerText().catch(() => '(no el-message)');
  console.log('ELMSG=', JSON.stringify(msg));
});
