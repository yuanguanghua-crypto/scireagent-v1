// A-042 回归：分子量不得被 enrich / 候选化合物静默覆盖。
//
// 原始缺陷（PDF A-042，P1，Batch 5）：
//   位置 PRODUCTS > New Product / Edit Product（5454）
//   复现：填 CAS 63-39-2、UTP 式 SMILES、Formula C9H15N2O15P3、MW 484.14，观察 MW 字段
//   预期：MW 保持 484.14
//   实际：MW 被异步改为 469；事后重填 484.14 才保持。无任何提示。
//
// 根因：ProductEditPage 的 4 条 apply* 路径里，smiles/inchi/formula 都有
//   `&& !form.X` 守卫，只有 molecular_weight 没有 ⇒ 无条件覆盖。
//
// 本测试锁住「人填的值是权威」这一条，且要求冲突必须可被 UI 感知（conflict 非空）。

import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve as resolvePath } from 'node:path'

import { resolveMolecularWeight, MW_EPSILON } from '../molecularWeight.js'

describe('resolveMolecularWeight — A-042 分子量静默覆盖', () => {
  it('A-042 原始复现：手填 484.14，库值 469 ⇒ 保留 484.14 并登记冲突', () => {
    const { next, conflict } = resolveMolecularWeight(484.14, 469, 'PubChem')
    expect(next).toBe(484.14)          // 人的值不变
    expect(conflict).not.toBeNull()    // 但不许静默
    expect(conflict.formValue).toBe(484.14)
    expect(conflict.enrichValue).toBe(469)
    expect(conflict.source).toBe('PubChem')
  })

  it('表单为空时允许补空（这是"填"不是"覆盖"）', () => {
    for (const empty of [null, undefined, '']) {
      const { next, conflict } = resolveMolecularWeight(empty, 469, 'PubChem')
      expect(next).toBe(469)
      expect(conflict).toBeNull()
    }
  })

  it('浮点噪声不算差异，且不把人的写法改掉', () => {
    // 484.14 与 484.14000000001 是同一个数
    const { next, conflict } = resolveMolecularWeight(484.14, 484.14000000001, 'PubChem')
    expect(next).toBe(484.14)
    expect(conflict).toBeNull()
  })

  it('容差边界：0.02 视为不同，0.005 视为相同', () => {
    // ⚠️ 刻意不用"差正好 0.01"当边界：float64 下 484.15-484.14 = 0.00999999999999，
    //    会落进容差。这种值本来就不该被用来断言边界，所以取 100 这个整数附近，
    //    让差值本身无歧义。
    expect(resolveMolecularWeight(100, 100.02, 'x').conflict).not.toBeNull()
    expect(resolveMolecularWeight(100, 100.005, 'x').conflict).toBeNull()
    expect(MW_EPSILON).toBe(0.01)
  })

  it('来值无效（空/非数/负数/0）⇒ 完全不动，也不报冲突', () => {
    for (const bad of [null, undefined, '', 'abc', 0, -1, NaN]) {
      const { next, conflict } = resolveMolecularWeight(484.14, bad, 'PubChem')
      expect(next).toBe(484.14)
      expect(conflict).toBeNull()
    }
  })

  it('表单里是非法残留字符串时，当作空值补上（不保留脏值）', () => {
    const { next, conflict } = resolveMolecularWeight('abc', 469, 'PubChem')
    expect(next).toBe(469)
    expect(conflict).toBeNull()
  })

  it('字符串数字能正确比较，不因类型不同误判为冲突', () => {
    const { next, conflict } = resolveMolecularWeight('484.14', '484.14', 'PubChem')
    expect(next).toBe('484.14')
    expect(conflict).toBeNull()
  })

  it('冲突对象带上来源，UI 才能说清"哪个库的值"', () => {
    const { conflict } = resolveMolecularWeight(100, 200)
    expect(conflict.source).toBe('外部数据源')   // 缺省来源也要有名字
  })

  it('任何情况下都不会把非空的人填值改掉（invariant）', () => {
    const inputs = [1, 12.34, 484.14, 999.99, 1000000]
    for (const human of inputs) {
      for (const machine of [1, 12.34, 468.99, 470.01, 999.99, 1000000]) {
        const { next } = resolveMolecularWeight(human, machine, 'x')
        if (human !== machine) expect(next).toBe(human)
      }
    }
  })
})

// ---------------------------------------------------------------------------
// 源码级防线：组件里不允许再出现「裸赋值」分子量
// ---------------------------------------------------------------------------
// 纯函数再好，只要有人在 apply* 里手写 `form.molecular_weight = ...` 就前功尽弃。
// 这里直接扫 .vue 源码，把「允许的赋值点」钉死成白名单 —— 新增一处就会红。
describe('ProductEditPage 源码防线 — 分子量不允许裸赋值', () => {
  // vitest 的 cwd 就是 frontend/ 根目录
  const vuePath = resolvePath(process.cwd(), 'src/views/workspace/ProductEditPage.vue')
  const src = readFileSync(vuePath, 'utf8')

  it('不存在绕过 resolveMolecularWeight 的裸赋值', () => {
    const ALLOWED = [
      // 唯一写入口内部的两处：判定结果回写、研究员显式「改用库值」
      'form.molecular_weight = next',
      'form.molecular_weight = mwConflict.value.enrichValue',
      // Word 导入：整份文档就是权威来源，属于用户主动的批量替换，不是 enrich 静默覆盖
      'form.molecular_weight = parseFloat(data.molecular_weight) || null',
    ]
    const found = [...src.matchAll(/form\.molecular_weight = [^\n]+/g)].map(m => m[0].trim())
    const unexpected = found.filter(line => !ALLOWED.includes(line))
    expect(
      unexpected,
      `发现新的分子量裸赋值，必须改走 applyMolecularWeight()：\n${unexpected.join('\n')}`,
    ).toEqual([])
  })

  it('四条 apply* 路径都调用 applyMolecularWeight', () => {
    // 用 lookbehind 排除函数定义本身，只数调用点
    const calls = [...src.matchAll(/(?<!function )applyMolecularWeight\(([^)]*)\)/g)]
      .map(m => m[1].trim())
    // applyCandidate / applyPubchemProperties / applyVerifiedChemicalToForm / applyAllEnrichResults
    expect(calls.length).toBe(4)
    // 每处都必须带上来源标签，否则冲突提示说不清"是哪个库的值"
    for (const arg of calls) {
      expect(arg).toContain(',')
    }
  })
})
