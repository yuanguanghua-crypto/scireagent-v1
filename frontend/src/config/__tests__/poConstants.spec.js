/**
 * `@/config/poConstants` 状态色表守卫。
 *
 * 为什么需要这组测试（2026-10-28）：
 *   ① 此前 5 个页面各自内联 statusColors，其中 3 个缺 `po_received` / `in_production` /
 *      `delivered` ⇒ 徽章没有颜色（PO 主流程正好全缺）。
 *   ② 底色写的是 `statusColors[s] + '15'`，想拼 8 位十六进制；但令牌值是 `var(--x)`，
 *      拼出来 `var(--x)15` **不是合法颜色** ⇒ 整条 background 声明作废，底色恒透明。
 *      （实测：`background: var(--color-success)15` 计算值 = rgba(0,0,0,0)）
 *   这组用例把「两表键集合必须完全一致」「底色必须是合法 var() 引用」钉死，
 *   以后新增状态忘了配底色、或又有人写 `+ '15'`，立刻变红。
 */
import { describe, it, expect } from 'vitest'
import {
  ORDER_STATUS_COLORS,
  ORDER_STATUS_BG,
  statusBadgeStyle,
  formatStatus,
} from '@/config/poConstants'

/** 后端 `Order.Status` 的全部 15 态（apps/transactions/models.py:19-36）。 */
const BACKEND_STATUSES = [
  // PO 主流程
  'po_received', 'confirmed', 'in_production', 'shipped', 'delivered',
  'invoiced', 'paid', 'completed', 'cancelled',
  // legacy（库内仍有历史单）
  'draft', 'processing', 'quote_pending', 'quoted', 'quote_accepted', 'quote_rejected',
]

describe('ORDER_STATUS_COLORS / ORDER_STATUS_BG', () => {
  it('覆盖后端全部 15 态（前端不认识的态会渲染成无颜色的普通文字）', () => {
    for (const s of BACKEND_STATUSES) {
      expect(ORDER_STATUS_COLORS[s], `ORDER_STATUS_COLORS 缺少 ${s}`).toBeTruthy()
      expect(ORDER_STATUS_BG[s], `ORDER_STATUS_BG 缺少 ${s}`).toBeTruthy()
    }
  })

  it('两张表的键集合完全一致（防止只加文字色忘了配底色）', () => {
    expect(Object.keys(ORDER_STATUS_BG).sort()).toEqual(Object.keys(ORDER_STATUS_COLORS).sort())
  })

  it('文字色与底色都必须是 var(--color-*) 引用，不是字面色值', () => {
    for (const [k, v] of [...Object.entries(ORDER_STATUS_COLORS), ...Object.entries(ORDER_STATUS_BG)]) {
      expect(v, `${k} 的取值应引用语义令牌`).toMatch(/^var\(--color-[a-z0-9-]+\)$/)
    }
  })

  it('底色不得出现 "…15" 后缀（历史缺陷：var(--x)15 是非法颜色）', () => {
    for (const [k, v] of Object.entries(ORDER_STATUS_BG)) {
      expect(v, `${k} 的底色不能拼透明度后缀`).not.toMatch(/\)\d+$/)
    }
  })
})

describe('statusBadgeStyle', () => {
  it('已知状态返回 {color, background} 两条声明', () => {
    const style = statusBadgeStyle('paid')
    expect(style.color).toBe('var(--color-success)')
    expect(style.background).toBe('var(--color-success-bg)')
  })

  it('15 个状态都能拿到非空底色（不是 transparent 兜底）', () => {
    for (const s of BACKEND_STATUSES) {
      const style = statusBadgeStyle(s)
      expect(style.color, `${s} 无文字色`).toBeTruthy()
      expect(style.background, `${s} 无底色`).not.toBe('transparent')
    }
  })

  it('未知/空状态返回空对象（不写任何声明，避免拼出 undefined 值）', () => {
    expect(statusBadgeStyle('something_new')).toEqual({})
    expect(statusBadgeStyle('')).toEqual({})
    expect(statusBadgeStyle(undefined)).toEqual({})
  })
})

describe('formatStatus', () => {
  it('下划线转空格并首字母大写', () => {
    expect(formatStatus('po_received')).toBe('Po Received')
    expect(formatStatus('in_production')).toBe('In Production')
    expect(formatStatus('quote_accepted')).toBe('Quote Accepted')
  })

  it('空值原样返回（模板里不抛错）', () => {
    expect(formatStatus('')).toBe('')
    expect(formatStatus(null)).toBe(null)
    expect(formatStatus(undefined)).toBe(undefined)
  })
})
