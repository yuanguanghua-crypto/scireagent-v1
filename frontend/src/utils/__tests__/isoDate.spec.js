/**
 * `normalizeIsoDate` —— A-249。
 *
 * 这些用例对应的是"运营真实会打出来的东西"，不是虚构的边界：
 *   ① 照屏幕上的格式手打 `2026-11-27`（全站日期显示都是这个格式）；
 *   ② 赶时间只打 8 位数字 `20261127`；
 *   ③ 用 `/` 或 `.` 当分隔符（Excel/邮件里常见）；
 *   ④ 格式对但日期不存在（`2026-02-30`）—— 必须拦，不能"就近取一天"；
 *   ⑤ 有歧义的 `03/04/2026` —— 宁可报错也不猜（与项目「宁 miss 不错配」一致）。
 */
import { describe, it, expect } from 'vitest'
import { normalizeIsoDate } from '../isoDate'

describe('normalizeIsoDate', () => {
  it('空输入合法（表示"不填"）', () => {
    for (const v of ['', '   ', null, undefined]) {
      expect(normalizeIsoDate(v)).toEqual({ ok: true, value: '', error: '' })
    }
  })

  it('标准 ISO 原样通过', () => {
    expect(normalizeIsoDate('2026-11-27')).toMatchObject({ ok: true, value: '2026-11-27' })
  })

  it('单位数月/日补零', () => {
    expect(normalizeIsoDate('2026-1-7')).toMatchObject({ ok: true, value: '2026-01-07' })
  })

  it('8 位纯数字', () => {
    expect(normalizeIsoDate('20261127')).toMatchObject({ ok: true, value: '2026-11-27' })
  })

  it('★ 8 位但日在前（11272026）⇒ 拒绝，并说清"8 位按 YYYYMMDD 读"', () => {
    const r = normalizeIsoDate('11272026')
    expect(r.ok).toBe(false)
    // 不猜 11/27：03112026 会是 3 月 11 还是 11 月 3？⇒ 只给可操作提示
    expect(r.error).toMatch(/YYYYMMDD/)
    expect(r.error).toMatch(/20261127/)
  })

  it('/ 与 . 作分隔符', () => {
    expect(normalizeIsoDate('2026/11/27')).toMatchObject({ ok: true, value: '2026-11-27' })
    expect(normalizeIsoDate('2026.11.27')).toMatchObject({ ok: true, value: '2026-11-27' })
  })

  it('前后空格忽略', () => {
    expect(normalizeIsoDate('  2026-11-27  ')).toMatchObject({ ok: true, value: '2026-11-27' })
  })

  it('★ 手打 ISO 后浏览器吃出来的脏值 202611-02-07 必须被拒', () => {
    // 6 位年份不是合法写法 ⇒ 走"格式不对"分支，并给出可操作提示
    // （这个脏值是 type=date 分段输入吃出来的；换成文本框后不会再产生，
    //   万一从粘贴/历史数据进来，也必须拒绝而不是当成年份 202611）
    const r = normalizeIsoDate('202611-02-07')
    expect(r.ok).toBe(false)
    expect(r.error).toMatch(/YYYY-MM-DD/)
  })

  it('格式对但日期不存在 ⇒ 拒绝，不就近取整', () => {
    expect(normalizeIsoDate('2026-02-30')).toMatchObject({ ok: false })
    expect(normalizeIsoDate('2026-13-01').ok).toBe(false)
    expect(normalizeIsoDate('2026-00-10').ok).toBe(false)
    expect(normalizeIsoDate('2026-11-00').ok).toBe(false)
  })

  it('闰年 2 月 29 合法，平年不合法', () => {
    expect(normalizeIsoDate('2028-02-29')).toMatchObject({ ok: true, value: '2028-02-29' })
    expect(normalizeIsoDate('2026-02-29').ok).toBe(false)
  })

  it('★ 有歧义的 mm/dd/yyyy 拒绝并给出可操作提示（不猜）', () => {
    const r = normalizeIsoDate('03/04/2026')
    expect(r.ok).toBe(false)
    expect(r.error).toMatch(/YYYY-MM-DD/)
  })

  it('年份范围 2000–2100', () => {
    expect(normalizeIsoDate('1999-12-31').ok).toBe(false)
    expect(normalizeIsoDate('2101-01-01').ok).toBe(false)
  })

  it('乱七八糟的输入不抛异常，只报错', () => {
    for (const v of ['abc', '2026', '2026-11', '27-11-2026', '2026年11月27日', '--']) {
      expect(() => normalizeIsoDate(v)).not.toThrow()
      expect(normalizeIsoDate(v).ok).toBe(false)
    }
  })
})
