/**
 * 分子量「谁来定」的唯一判定入口（A-042）。
 *
 * ## 为什么需要这个模块
 *
 * 产品编辑页有 4 条路径会把 enrich / 候选化合物带来的化学属性套进表单
 * （`applyCandidate` / `applyPubchemProperties` / `applyVerifiedChemicalToForm` /
 * `applyAllEnrichResults`）。这 4 条里 `smiles` / `inchi` / `formula` **都有**
 * 「表单已有值就不填」的守卫，唯独 `molecular_weight` 没有 ——
 * 于是研究员手填的 484.14 会被库值 469 无声盖掉（PDF A-042：
 * 「MW 被异步改为 469……无任何提示」）。
 *
 * 更糟的是 `applyVerifiedChemicalToForm` 的注释写着「仅填空字段，不覆盖人工录入」，
 * 代码却与注释相反 —— 注释在骗下一个读它的人。
 *
 * ## 判定口径（宁 miss 不错配）
 *
 * 1. 来值无效（空 / 非数 / ≤0）⇒ 什么都不做
 * 2. 表单为空 ⇒ 填入（这是"补空"，不是"覆盖"）
 * 3. 两值相差 < 0.01 ⇒ 保持表单原值，不提示（避免 484.14 vs 484.14000001 这种噪声）
 * 4. 两值确实不同 ⇒ **保留人填的值**，只登记冲突，由 UI 明确提示，
 *    人显式点「改用库值」才替换
 *
 * ⇒ 人的输入永远是权威；库值只用于补空和提示，永不静默改写。
 */

/** 视为「同一个分子量」的容差（Da）。只吸收浮点噪声，不吸收真实差异。 */
export const MW_EPSILON = 0.01

function isEmpty(v) {
  return v === null || v === undefined || v === ''
}

function toPositiveNumber(v) {
  if (isEmpty(v)) return null
  const n = Number(v)
  if (!Number.isFinite(n) || n <= 0) return null
  return n
}

/**
 * @param {number|string|null} current 表单当前值（人可能已经填过）
 * @param {number|string|null} incoming 外部来源（enrich / 候选化合物）带来的值
 * @param {string} source 来源标签，用于提示文案（如 'PubChem' / '候选化合物'）
 * @returns {{ next: number|string|null, conflict: null|{formValue:number, enrichValue:number, source:string} }}
 *          `next` 是要写回表单的值（等于 `current` 即表示不改）；
 *          `conflict` 非空表示"有价值差异但被拒绝覆盖"，调用方必须显示出来
 */
export function resolveMolecularWeight(current, incoming, source = '外部数据源') {
  const inc = toPositiveNumber(incoming)
  // 1. 来值无效 ⇒ 不动
  if (inc === null) return { next: current, conflict: null }

  const cur = toPositiveNumber(current)
  // 2a. 表单空值（含非法残留）⇒ 补空
  if (cur === null) return { next: inc, conflict: null }

  // 3. 实质相同 ⇒ 保持原值（不把 484.14 改写成 484.14000000001）
  if (Math.abs(cur - inc) < MW_EPSILON) return { next: current, conflict: null }

  // 4. 真差异 ⇒ 拒绝覆盖 + 登记冲突
  return {
    next: current,
    conflict: { formValue: cur, enrichValue: inc, source: String(source || '外部数据源') },
  }
}
