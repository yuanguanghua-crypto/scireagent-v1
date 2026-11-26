/**
 * `selectTruncationHint` —— A-206（2026-11-18 / S4）。
 *
 * 这四个下拉的截断是**静默**的：首屏 200/500、搜索 50，其余既不显示也不提示，
 * 用户会得出"库里没有这个实体"的结论。函数本身很小，但两种措辞的边界
 * （未搜索 vs 已搜索 / 没有总数 vs 有总数）一旦写错就会给出**错误指令**，
 * 所以逐条钉住。
 */
import { describe, it, expect } from 'vitest'
import { selectTruncationHint } from '@/utils/selectHint'

describe('selectTruncationHint（A-206）', () => {
  it('首屏预加载被截断 ⇒ 让用户去搜索，而不是"继续输入"', () => {
    const s = selectTruncationHint({ searched: false, shown: 200, total: 11047 })
    expect(s).toContain('200')
    expect(s).toContain('11047')
    expect(s).toMatch(/type to search/i)
    expect(s, '对还没输入过的人说"继续输入"没有意义').not.toMatch(/keep typing/i)
  })

  it('搜索结果被截断 ⇒ 让用户继续输入缩小范围', () => {
    const s = selectTruncationHint({ searched: true, shown: 50, total: 812 })
    expect(s).toContain('50')
    expect(s).toContain('812')
    expect(s).toMatch(/keep typing/i)
  })

  it('全部列出（total == shown）⇒ 不提示', () => {
    expect(selectTruncationHint({ searched: false, shown: 88, total: 88 })).toBe('')
    expect(selectTruncationHint({ searched: true, shown: 3, total: 3 })).toBe('')
  })

  it('总数比已显示还少（分页抖动/并发删除）⇒ 也不提示，不能说"只显示了 200 of 88"', () => {
    expect(selectTruncationHint({ searched: false, shown: 200, total: 88 })).toBe('')
  })

  it('拿不到服务端总数（数组直出，无分页 meta）⇒ 不猜、不提示', () => {
    expect(selectTruncationHint({ searched: false, shown: 200, total: null })).toBe('')
    expect(selectTruncationHint({ searched: true, shown: 50, total: undefined })).toBe('')
  })
})
