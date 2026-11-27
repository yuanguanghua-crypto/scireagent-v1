/**
 * 协议步骤文本清洗（A-118，2026-11-27）。
 *
 * 本地 dev 库里没有"标题带 strong 片段"的步骤（该数据条件不存在），
 * 所以用单测钉住正则本身 —— 这是本修复唯一有风险的部分。
 */
import { describe, it, expect } from 'vitest'
import { cleanStepTitle, stepTitle, stepNo } from '../stepText'

describe('cleanStepTitle', () => {
  it('去掉完整标签对', () => {
    expect(cleanStepTitle('<strong>GENOMIC DNA ISOLATION</strong>'))
      .toBe('GENOMIC DNA ISOLATION')
  })

  it('★ 去掉残缺片段（QA 实测的 strong> 形态）', () => {
    expect(cleanStepTitle('strong>GENOMIC DNA ISOLATION AND RESTRICTION DIGESTION</strong>'))
      .toBe('GENOMIC DNA ISOLATION AND RESTRICTION DIGESTION')
  })

  it('多个标签 + 换行/多空格压缩成一个空格', () => {
    expect(cleanStepTitle('<p>Heat  <b>5 min</b>\n at 95°C</p>')).toBe('Heat 5 min at 95°C')
  })

  it('纯文本原样保留（含 5°C、1/2、µL 这类字符）', () => {
    expect(cleanStepTitle('Incubate at 5°C for 1/2 h (100 µL)'))
      .toBe('Incubate at 5°C for 1/2 h (100 µL)')
  })

  it('空值/undefined 不抛异常', () => {
    expect(cleanStepTitle('')).toBe('')
    expect(cleanStepTitle(null)).toBe('')
    expect(cleanStepTitle(undefined)).toBe('')
  })

  it('只剩标签时结果为空（交给 stepTitle 兜底）', () => {
    expect(cleanStepTitle('<br/>')).toBe('')
  })
})

describe('stepNo', () => {
  it('数据有合法序号时用它', () => {
    expect(stepNo({ step_no: 7 }, 0)).toBe(7)
  })

  it('缺失/null/0/非数字 ⇒ 用顺序号（从 1 开始）', () => {
    expect(stepNo({ step_no: null }, 0)).toBe(1)
    expect(stepNo({ step_no: 0 }, 4)).toBe(5)
    expect(stepNo({}, 2)).toBe(3)
    expect(stepNo({ step_no: 'x' }, 1)).toBe(2)
  })
})

describe('stepTitle', () => {
  it('有标题用清洗后的标题', () => {
    expect(stepTitle({ title: 'strong>Digest</strong>', step_no: 1 }, 0)).toBe('Digest')
  })

  it('标题为空时退回 Step N（不再只显示一个 "Step"）', () => {
    expect(stepTitle({ title: '', step_no: 3 }, 0)).toBe('Step 3')
    expect(stepTitle({ title: '<br/>' }, 0)).toBe('Step 1')
  })
})
