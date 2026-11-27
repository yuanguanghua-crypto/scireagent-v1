/**
 * 协议步骤文本清洗（A-118，2026-11-27）。
 *
 * ## 为什么需要
 * 语料导入的步骤标题里混进了 **HTML 片段**，甚至**缺了左尖括号的半截**：
 * QA 实测第 1 步在页面上显示成
 *   `strong>GENOMIC DNA ISOLATION AND RESTRICTION DIGESTION</strong>`
 *
 * 页面是 `{{ step.title }}` 纯文本插值（不用 v-html，XSS 安全），所以标签不会被解析，
 * 而是**原样当文字显示**。展示层要把它清成纯文本。
 *
 * ⚠️ 这只是兜底：数据本身的清洗属于导入管线/数据治理线，不在这里改库。
 */

/** 去掉完整标签 `<b>…</b>` 与残缺片段 `strong>` / `</strong`，压缩空白 */
export function cleanStepTitle(raw) {
  return String(raw ?? '')
    .replace(/<[^>]*>/g, ' ')                       // 完整标签对/自闭合
    .replace(/\/?[A-Za-z][A-Za-z0-9]*>/g, ' ')      // 残缺：strong> 、/strong
    .replace(/\s+/g, ' ')
    .trim()
}

/** 标题为空时退回「Step N」；N 取自数据，缺失则用顺序号（从 1 开始） */
export function stepTitle(step, idx) {
  const t = cleanStepTitle(step && step.title)
  if (t) return t
  return `Step ${stepNo(step, idx)}`
}

/** 步骤号：数据里缺失（null/0/非数字）时用顺序号，保证每一步都可区分 */
export function stepNo(step, idx) {
  const n = Number(step && step.step_no)
  return Number.isFinite(n) && n > 0 ? n : (Number(idx) || 0) + 1
}
