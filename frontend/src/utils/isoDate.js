/**
 * ISO 日期输入的归一化 —— A-249（S6 第三批）。
 *
 * ## 为什么需要它（实测证据，不是推测）
 * 原控件是 `<input type="date">`，而**全站日期显示都是 `YYYY-MM-DD`**（订单详情、
 * AR 账龄、发票到期日都是这个格式）。运营照着屏幕上的格式往那个框里打，实测在
 * Edge（zh-CN）下得到的是脏值：
 *
 *     type="date" 里手打 `2026-11-27`  ⇒  value 变成 `202611-02-07`
 *     type="date" 里手打 `11272026`    ⇒  value 变成 `""`（段值非法被丢弃）
 *
 * 原因是 `type=date` 的输入是**分段**的，`-` 不推进分段，浏览器按 locale 顺序把数字
 * 塞进 年/月/日。值一旦变脏，用户原意已经丢了（`202611-02-07` 还原不回 `2026-11-27`），
 * 所以没法在 `type=date` 上"事后修正"——只能换成文本框自己收。
 *
 * ## 口径
 * 只接受**无歧义**的写法，遇到含糊就报错而不是猜（与项目「宁 miss 不错配」一致）：
 *   2026-11-27 / 2026-1-7 / 2026/11/27 / 2026.11.27 / 20261127  ⇒ 都归一成 2026-11-27
 *   03/04/2026（到底是 3 月 4 日还是 4 月 3 日？）              ⇒ 拒绝，提示改写法
 *
 * 返回值三态，调用方据此决定"能不能提交"：
 *   { ok: true,  value: '2026-11-27' }   —— 合法（空串也算合法：表示"不填"）
 *   { ok: false, value: '', error: '…' } —— 写了但看不懂/不存在，必须拦下
 */

const ISO_RE = /^(\d{4})-(\d{2})-(\d{2})$/

/** 该年该月有多少天（含闰年） */
function daysInMonth(y, m) {
  return new Date(y, m, 0).getDate()
}

/**
 * @param {string} raw 用户输入
 * @returns {{ok: boolean, value: string, error: string}}
 */
export function normalizeIsoDate(raw) {
  const s = String(raw ?? '').trim()
  if (!s) return { ok: true, value: '', error: '' }

  let y
  let m
  let d

  // ① 纯 8 位数字：20261127（年在前）
  if (/^\d{8}$/.test(s)) {
    y = Number(s.slice(0, 4))
    m = Number(s.slice(4, 6))
    d = Number(s.slice(6, 8))
    // ★ 8 位数字里"年不在前"是最常见的误打（`11272026` = 11/27/2026）。
    //   但这个写法**本身有歧义**：`03112026` 到底是 3 月 11 还是 11 月 3？
    //   所以不猜，只把话说清楚 —— 让用户知道该打 `20261127`。
    if (y < 2000 || y > 2100) {
      return {
        ok: false,
        value: '',
        error: `8 digits are read as YYYYMMDD, so "${s}" means year ${y}. `
          + `For 2026-11-27 type 20261127 (year first) or 2026-11-27.`,
      }
    }
  } else {
    // ② 年在前、三段式（- / . 分隔）：只认这种，因为「年在前」不会歧义
    const m3 = s.match(/^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})$/)
    if (!m3) {
      // ③ 其余写法一律拒绝并给出可操作的提示（含 mm/dd/yyyy 这种有歧义的）
      return {
        ok: false,
        value: '',
        error: 'Use YYYY-MM-DD (e.g. 2026-11-27). Digits-only 20261127 also works.',
      }
    }
    y = Number(m3[1])
    m = Number(m3[2])
    d = Number(m3[3])
  }

  // ④ 年份范围：挡住 "202611-02-07" 那种把手打内容吃成 6 位年份的脏值
  if (y < 2000 || y > 2100) {
    return { ok: false, value: '', error: `Year ${y} is out of range (2000–2100).` }
  }
  if (m < 1 || m > 12) {
    return { ok: false, value: '', error: `Month ${m} does not exist.` }
  }
  // ⑤ 真实日历校验：2026-02-30 这种格式对但不存在的日期必须拦
  if (d < 1 || d > daysInMonth(y, m)) {
    return { ok: false, value: '', error: `${y}-${String(m).padStart(2, '0')} has no day ${d}.` }
  }

  const iso = `${String(y).padStart(4, '0')}-${String(m).padStart(2, '0')}-${String(d).padStart(2, '0')}`
  // 双保险：拼出来的必须是浏览器也认的日期（挡住 padStart 之外的意外）
  if (!ISO_RE.test(iso)) {
    return { ok: false, value: '', error: 'Use YYYY-MM-DD (e.g. 2026-11-27).' }
  }
  return { ok: true, value: iso, error: '' }
}

/** 只取「能不能提交」：空串合法（= 不填） */
export function isoDateOrNull(raw) {
  const r = normalizeIsoDate(raw)
  return r.ok ? (r.value || null) : null
}
