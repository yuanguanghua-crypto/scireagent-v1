// Apps/Methods/Protocols FK dropdown E2E — covers gap ③.
// Each editor exposes a FK <el-select> bound to research_goal_id / application_id / method_id.
// We open the editor, select an existing parent entity, save, then assert via the API that
// the FK id was persisted (not just that the UI shows it).
const {
  test, expect, login, gotoWorkspace, getToken, apiGetList, apiGet, apiDelete,
} = require('./helpers')

// Pick an existing parent entity to link, via the API.
async function pickParent(page, token, type) {
  const list = await apiGetList(page, `/api/v1/${type}/?page_size=200`, token)
  expect(list.length).toBeGreaterThan(0)
  return list[0] // { id, name, ... }
}

// Drive an Element Plus el-select: locate the select by its placeholder text (Element Plus
// renders the placeholder inside the .el-select wrapper, NOT on an <input[placeholder]>),
// open it, then click the option whose text matches.
async function selectElOption(page, placeholder, optionText) {
  const select = page.locator('.el-select', { hasText: placeholder })
  await expect(select).toBeVisible({ timeout: 8000 })
  await select.click()
  const item = page
    .locator('.el-select-dropdown:not(.is-hidden) .el-select-dropdown__item', { hasText: optionText })
    .first()
  await expect(item).toBeVisible({ timeout: 8000 })
  await item.click()
}

// Find a freshly created entity by its unique name and return its id.
async function findEntityIdByName(page, token, type, name) {
  const list = await apiGetList(page, `/api/v1/${type}/?page_size=500`, token)
  const found = list.find((e) => e.name === name)
  return found ? found.id : null
}

test.describe('Apps/Methods/Protocols FK dropdowns (gap ③)', () => {
  test.beforeEach(async ({ page }) => {
    await login(page)
  })

  test('Applications editor: select Research Goal FK and persist it', async ({ page }) => {
    const token = await getToken(page)
    const goal = await pickParent(page, token, 'research-goals') // { id, name }
    const ts = Date.now()
    const name = `E2E_App_${ts}`

    await gotoWorkspace(page, '/workspace/applications')
    await expect(page.locator('.entity-page')).toBeVisible()
    await page.getByRole('button', { name: '+ New Application' }).click()
    await expect(page.locator('.dialog')).toBeVisible()

    await page.locator('.dialog input.input-full').first().fill(name)
    await selectElOption(page, 'Select research goal', goal.name)

    await page.getByRole('button', { name: 'Save' }).click()
    await expect(page.locator('.dialog')).toBeHidden({ timeout: 15000 })

    // Row appears in the list.
    await expect(page.locator('.entity-table tbody tr', { hasText: name }).first()).toBeVisible()

    // API GET → assert FK persisted.
    const id = await findEntityIdByName(page, token, 'applications', name)
    expect(id).not.toBeNull()
    const detail = await apiGet(page, `/api/v1/applications/${id}/`, token)
    expect(detail.research_goal_id).toBe(goal.id)
    console.log(`REPORT: Application ${id} → research_goal_id=${detail.research_goal_id} (expected ${goal.id})`)

    // Cleanup.
    await apiDelete(page, `/api/v1/applications/${id}/`, token)
  })

  test('Methods editor: select Application FK and persist it', async ({ page }) => {
    const token = await getToken(page)
    const app = await pickParent(page, token, 'applications')
    const ts = Date.now()
    const name = `E2E_Method_${ts}`

    await gotoWorkspace(page, '/workspace/methods')
    await expect(page.locator('.entity-page')).toBeVisible()
    await page.getByRole('button', { name: '+ New Method' }).click()
    await expect(page.locator('.dialog')).toBeVisible()

    await page.locator('.dialog input.input-full').first().fill(name)
    await selectElOption(page, 'Select application', app.name)

    await page.getByRole('button', { name: 'Save' }).click()
    await expect(page.locator('.dialog')).toBeHidden({ timeout: 15000 })

    await expect(page.locator('.entity-table tbody tr', { hasText: name }).first()).toBeVisible()

    const id = await findEntityIdByName(page, token, 'methods', name)
    expect(id).not.toBeNull()
    const detail = await apiGet(page, `/api/v1/methods/${id}/`, token)
    expect(detail.application_id).toBe(app.id)
    console.log(`REPORT: Method ${id} → application_id=${detail.application_id} (expected ${app.id})`)

    await apiDelete(page, `/api/v1/methods/${id}/`, token)
  })

  test('Protocols editor: select Method FK and persist it', async ({ page }) => {
    const token = await getToken(page)
    const method = await pickParent(page, token, 'methods')
    const ts = Date.now()
    const name = `E2E_Protocol_${ts}`

    await gotoWorkspace(page, '/workspace/protocols')
    await expect(page.locator('.entity-page')).toBeVisible()
    await page.getByRole('button', { name: '+ New Protocol' }).click()
    await expect(page.locator('.dialog')).toBeVisible()

    await page.locator('.dialog input.input-full').first().fill(name)
    await selectElOption(page, 'Select method', method.name)

    await page.getByRole('button', { name: 'Save' }).click()
    await expect(page.locator('.dialog')).toBeHidden({ timeout: 15000 })

    await expect(page.locator('.entity-table tbody tr', { hasText: name }).first()).toBeVisible()

    const id = await findEntityIdByName(page, token, 'protocols', name)
    expect(id).not.toBeNull()
    const detail = await apiGet(page, `/api/v1/protocols/${id}/`, token)
    expect(detail.method_id).toBe(method.id)
    console.log(`REPORT: Protocol ${id} → method_id=${detail.method_id} (expected ${method.id})`)

    await apiDelete(page, `/api/v1/protocols/${id}/`, token)
  })
})
