/**
 * 页内确认框驱动助手（S4 丙族）
 *
 * 背景：2026-11-18 起，全站 10 处 `window.confirm` 全换成 `<ConfirmHost>`
 * 驱动的页内对话框（`@/composables/useConfirm`）。
 *
 * ⚠️ 这对 e2e 是**机制变更**，不是文案变更：
 *   原来的 `page.on('dialog', d => d.accept())` 现在**一次都不会触发** ——
 *   它不会报错，只会让断言悄悄失真。已实测到的两种失真：
 *     · 正向用例（"应弹 1 次 confirm"）→ 直接红（dialogs=0）
 *     · 负向用例（"取消 ⇒ 零写入"）→ **假绿**：没有原生弹框可 dismiss，
 *       动作压根没被执行，"零写入"自然成立，等于什么都没测
 *   ⇒ 任何涉及确认框的 spec 都必须改成这里的 DOM 驱动方式。
 *
 * 用法：
 *   const { installConfirmCounter, confirmCount, waitConfirm, acceptConfirm, dismissConfirm } =
 *     require('./helpers/confirm.cjs')
 *   await installConfirmCounter(page)   // 必须在页面加载后、点击前
 *   await clickTheDangerousButton()
 *   await waitConfirm(page)
 *   expect(await confirmCount(page)).toBe(1)   // 真的只弹了一次
 *   await acceptConfirm(page)
 */

const MSG = '[data-testid="confirm-message"]';
const INPUT = '[data-testid="confirm-input"]';
const OK = '[data-testid="confirm-ok"]';
const CANCEL = '[data-testid="confirm-cancel"]';

/**
 * 在页面上装一个 MutationObserver 统计确认框被挂载的次数。
 * 必须在触发动作**之前**调用；同页多次调用会重置计数。
 */
async function installConfirmCounter(page) {
  await page.evaluate((sel) => {
    window.__confirmCount = 0;
    window.__confirmObserver?.disconnect?.();
    window.__confirmObserver = new MutationObserver((mutations) => {
      for (const m of mutations) {
        for (const n of m.addedNodes) {
          if (n.nodeType !== 1) continue;
          // Teleport 到 body 的 overlay 是整棵插入的，所以要在子树里找
          if (n.matches?.(sel) || n.querySelector?.(sel)) {
            window.__confirmCount += 1;
          }
        }
      }
    });
    window.__confirmObserver.observe(document.documentElement, {
      childList: true,
      subtree: true,
    });
  }, MSG);
}

/** 读计数（确认框出现过几次） */
async function confirmCount(page) {
  return page.evaluate(() => window.__confirmCount || 0);
}

/** 等确认框可见 */
async function waitConfirm(page, timeout = 10000) {
  await page.locator(MSG).waitFor({ state: 'visible', timeout });
}

/** 等确认框消失 */
async function waitConfirmGone(page, timeout = 10000) {
  await page.locator(MSG).waitFor({ state: 'hidden', timeout });
}

/** 点确认 */
async function acceptConfirm(page) {
  await page.locator(OK).click();
}

/** 点取消 / 留在此页 */
async function dismissConfirm(page) {
  await page.locator(CANCEL).click();
}

/**
 * 在页内输入框里填内容 —— 供 `askText`（替代 `window.prompt` 的形态）使用。
 *
 * ★ 为什么必须有这个 helper：`window.prompt` 下线后，`page.on('dialog', d => d.accept(x))`
 *   **一次都不会触发**，而对应的动作（拒绝付款凭证 / 拒绝 verified 结论）也就
 *   根本不会发出请求 —— 断言会以"等不到响应"超时的方式红掉，而不是报错。
 *
 * ⚠️ 语义提醒：确认框返回 `null` = 用户取消，`''` = 确认但未填。
 *   所以「留空确认」应调 `acceptConfirm()`（不填），而不是 `dismissConfirm()`。
 */
async function fillConfirmInput(page, text) {
  await page.locator(INPUT).fill(text);
}

/** 读确认框正文（多行用 \n 保留） */
async function confirmMessage(page) {
  return (await page.locator(MSG).innerText()).trim();
}

/** 确认框是否可见（不等待） */
async function isConfirmVisible(page) {
  return page.locator(MSG).isVisible().catch(() => false);
}

module.exports = {
  MSG,
  INPUT,
  OK,
  CANCEL,
  installConfirmCounter,
  confirmCount,
  waitConfirm,
  waitConfirmGone,
  acceptConfirm,
  dismissConfirm,
  fillConfirmInput,
  confirmMessage,
  isConfirmVisible,
};
