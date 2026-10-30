/**
 * Method 的 cost_band / timeline 是**枚举**，后端只回原始值（`low`、`hours`）。
 * 直接渲染会让客户看到 `low` 和 `hours` 这种数据库代号 —— 实测 MethodDetail.vue
 * 与 MethodCard.vue 此前都是裸值直出，零映射。
 *
 * 标签必须与后端 `Method.CostBand` / `Method.Timeline` 的 `choices` 逐字对齐
 * （backend/apps/knowledge/models.py:180-191），否则两边会漂移。
 */

export const COST_BAND_LABELS = {
  low: 'Low (<$50/sample)',
  medium: 'Medium ($50–200/sample)',
  high: 'High (>$200/sample)',
}

export const COST_BAND_SHORT = {
  low: 'Low cost',
  medium: 'Mid cost',
  high: 'High cost',
}

export const TIMELINE_LABELS = {
  minutes: 'Minutes (<30 min)',
  hours: 'Hours (30 min–4 h)',
  days: 'Days (1–7 d)',
  weeks: 'Weeks (>1 week)',
}

export const TIMELINE_SHORT = {
  minutes: '<30 min',
  hours: '30 min–4 h',
  days: '1–7 d',
  weeks: '>1 week',
}

/**
 * 枚举值 → 可读标签。未知值原样返回（人工可能填了自由文本，不能吞掉）；
 * 空值返回 ''，让调用方的 `v-if` 直接生效。
 */
function label(table, value) {
  if (!value) return ''
  return table[value] || value
}

export function costBandLabel(value) {
  return label(COST_BAND_LABELS, value)
}

export function timelineLabel(value) {
  return label(TIMELINE_LABELS, value)
}

export function costBandShort(value) {
  return label(COST_BAND_SHORT, value)
}

export function timelineShort(value) {
  return label(TIMELINE_SHORT, value)
}

/**
 * advantages / limitations 按「每条一行」存储（见模型 help_text）。
 * 单行数据（历史人工录入可能用分号连成一段）按分号拆开。
 *
 * 刻意不用 lookbehind（`(?<=...)`）：Safari 16.4 以下不支持，会让整个模块
 * 直接抛 SyntaxError ⇒ 方法页白屏。也刻意不按句号拆，避免 `e.g.` / `i.e.` 误伤。
 */
export function splitSpecLines(text) {
  if (!text) return []
  const raw = String(text)
  const parts = /[\r\n]/.test(raw) ? raw.split(/[\r\n]+/) : raw.split(/[;；]/)
  return parts.map((s) => trimItem(s)).filter((s) => s.length > 0)
}

// 缩写结尾不能削句号，否则 `useful, e.g.` 会变成 `useful, e.g`
const ABBREV_END = /\b(e\.g|i\.e|etc|vs|Fig|No|approx)$/i

function trimItem(line) {
  const s = line.trim().replace(/^[-•*·]\s*/, '').trim()
  const m = s.match(/^(.*?)([.。；;]+)$/)
  if (!m) return s
  if (ABBREV_END.test(m[1])) return s
  return m[1].trim()
}
