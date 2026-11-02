#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""check_definition_coverage.py — 方法定义的结构覆盖闸门

## 为什么需要它

`docs/方法定义规范_v3.md` 里有两条**结构性要求**，但过去**不可机器校验**：
  · §5.1「`exclude` 的**每个 E 都要有对应反例**」
  · §5.3「`edge_examples` **必须覆盖全部 5 个 `category` 值**」+ 各类条数下限

2026-11-02 编写 SDS-PAGE v3 定义时就漏掉了 `E2` 的反例 —— 因为没人能拦。
本脚本把这两条变成可执行判据，与 `check_definition_en.py`（语言闸门）并列跑。

## 能查什么（结构 / tag 层）

| 检查 | 依据 |
|---|---|
| `pos_examples` ≥ 2、`neg_examples` ≥ 5、`edge_examples` ≥ 5 | §5.3 |
| `edge_examples` 覆盖 `category_definition` 的**全部 5 个值** | §5.3 |
| `exclude` 里**每个 E** 都至少被一条例子的 `exclude_item` 引用 | §5.1 |
| `neg_examples` 带 `exclude_item` 的比例 **> 50%**（"多数"按严格过半算） | §5.3 |
| 每条例子的 `exclude_item` **必须是 `exclude` 里真实存在的 E 编号** | 防笔误 |
| **`scope_note` 不得被任何例子当 `exclude_item` 引用** | §5.1.1 第 2 条 |
| `pos_examples` 的 `verdict` 必须 `on_topic`；`neg_examples` 必须 `wrong` | §5.3 |
| `edge_examples` 里 `verdict: wrong` 的必须带 `exclude_item` | §5.3 |

## ⛔ 查不了什么（必须知道，否则会把它当万能）

1. **措辞语义错配** —— 这是最重要的盲区。
   tag 挂对了、文字与 E 的描述对不上，**本脚本看不出来**。
   实例：2026-11-02 恢复 `E2` 反例时，若照 v2 原文（"二维第一维聚焦 IPG"），
   `exclude_item: E2` 在结构上是合法的、本脚本会**判绿**，
   但文字与改写后的 E2（"IEF 单独跑、全程无 SDS 胶"）并不匹配。
   ⇒ **措辞对齐仍需人工复核，脚本永远替代不了这一步。**
2. **判定本身对不对** —— 例子判 on_topic / tangential 是否合理，脚本不管。
3. **must 与 on_topic_requires 是否分离**、`essence` 是否混入判定规则 —— 语义问题。
4. **语言** —— 由 `check_definition_en.py` 负责。
5. **`scope_note` 被当作判定依据**（在 `why` 里写"依 scope_note 判 wrong"）—— 文本语义，查不出。
   本脚本只保证它没被当 `exclude_item` 引用。

## 用法

```bash
python scripts/check_definition_coverage.py <definition.yaml> [more.yaml ...]
python scripts/check_definition_coverage.py --self-test   # 验判据本身：该红时必须红
```

退出码：0 = 全绿；1 = 有违规；2 = 参数/解析问题
"""
from __future__ import annotations

import argparse
import io
import sys

try:
    import yaml
except ImportError:
    print('❌ 缺少 PyYAML；用 backend/venv 的 python 跑')
    sys.exit(2)

MIN_POS, MIN_NEG, MIN_EDGE = 2, 5, 5
NEG_TAGGED_RATIO = 0.5          # 必须 > 0.5（严格过半；3/6 = 0.5 不算多数）
CATEGORY_VALUES = ('upstream', 'downstream', 'variant', 'analogue', 'composite')
SPEC_FIELDS = (
    'essence', 'must', 'on_topic_requires', 'common_but_not_required', 'exclude',
    'category_definition', 'pos_examples', 'neg_examples', 'edge_examples', 'scope_note',
)
META_FIELDS = ('method', 'version', 'author', 'reviewed_by', 'status')


def _e_ids(doc) -> list[str]:
    """从 exclude 取 E 编号。支持 [{E1: "..."}] 与 ["E1: ..."] 两种写法。"""
    out = []
    for item in doc.get('exclude') or []:
        if isinstance(item, dict):
            out.extend(str(k) for k in item)
        else:
            out.append(str(item).split(':')[0].strip())
    return out


def _examples(doc, key):
    v = doc.get(key) or []
    return [e for e in v if isinstance(e, dict)]


def check(doc) -> list[str]:
    """返回违规描述列表；空列表 = 全绿。纯函数，不碰 IO —— 便于自检。"""
    errs: list[str] = []

    # 0) 字段是否齐（category_definition 自 v3.4 起为必填）
    missing = [f for f in SPEC_FIELDS if f not in doc]
    # scope_note 是可选字段，缺了不算错
    missing = [f for f in missing if f != 'scope_note']
    if missing:
        errs.append(f'缺必填字段：{missing}')

    pos, neg, edge = _examples(doc, 'pos_examples'), _examples(doc, 'neg_examples'), _examples(doc, 'edge_examples')

    # 1) 条数下限
    if len(pos) < MIN_POS:
        errs.append(f'pos_examples 只有 {len(pos)} 条，下限 {MIN_POS}')
    if len(neg) < MIN_NEG:
        errs.append(f'neg_examples 只有 {len(neg)} 条，下限 {MIN_NEG}')
    if len(edge) < MIN_EDGE:
        errs.append(f'edge_examples 只有 {len(edge)} 条，下限 {MIN_EDGE}')

    # 2) edge 覆盖全部 category 值
    have = {(e.get('category') or '').strip() for e in edge if e.get('category')}
    defined = set(doc.get('category_definition') or {}) or set(CATEGORY_VALUES)
    miss_cat = sorted(defined - have)
    if miss_cat:
        errs.append(f'edge_examples 未覆盖这些 category 值：{miss_cat}')
    bad_cat = sorted(have - set(defined))
    if bad_cat:
        errs.append(f'edge_examples 用了未定义的 category 值：{bad_cat}')

    # 3) 每个 E 都要有反例
    eids = _e_ids(doc)
    if not eids:
        errs.append('exclude 为空或无法解析出 E 编号')
    used = set()
    for grp in (neg, edge):
        for e in grp:
            it = e.get('exclude_item')
            if it:
                used.add(str(it).strip())
    zero = sorted(set(eids) - used)
    if zero:
        errs.append(f'这些 E 没有任何对应反例（§5.1）：{zero}')

    # 4) neg 带项比例 > 50%
    if neg:
        tagged = sum(1 for e in neg if e.get('exclude_item'))
        ratio = tagged / len(neg)
        if ratio <= NEG_TAGGED_RATIO:
            errs.append(
                f'neg_examples 带 exclude_item 的比例 {tagged}/{len(neg)} = {ratio:.0%}，'
                f'未超过 50%（§5.3「多数应带」）')

    # 5) exclude_item 必须引真实存在的 E，且不得引 scope_note（§5.1.1 第 2 条）
    for grp_name, grp in (('neg_examples', neg), ('edge_examples', edge)):
        for i, e in enumerate(grp, 1):
            it = e.get('exclude_item')
            if not it:
                continue
            it = str(it).strip()
            if it == 'scope_note':
                errs.append(f'{grp_name} 第 {i} 条把 scope_note 当 exclude_item 引用（§5.1.1 禁止）')
            elif it not in eids:
                errs.append(f'{grp_name} 第 {i} 条的 exclude_item「{it}」不在 exclude 里（笔误或漏定义）')

    # 6) verdict 与组别一致
    for i, e in enumerate(pos, 1):
        if (e.get('verdict') or '') != 'on_topic':
            errs.append(f'pos_examples 第 {i} 条 verdict 应为 on_topic，实际 {e.get("verdict")!r}')
    for i, e in enumerate(neg, 1):
        if (e.get('verdict') or '') != 'wrong':
            errs.append(f'neg_examples 第 {i} 条 verdict 应为 wrong，实际 {e.get("verdict")!r}')
    for i, e in enumerate(edge, 1):
        if (e.get('verdict') or '') == 'wrong' and not e.get('exclude_item'):
            errs.append(f'edge_examples 第 {i} 条 verdict=wrong 但缺 exclude_item（§5.3）')

    return errs


def _fmt(errs, name):
    if not errs:
        print(f'✓ {name}: 结构覆盖通过')
        return
    print(f'✗ {name}: {len(errs)} 处违规')
    for e in errs:
        print(f'    - {e}')
    print('  → 提醒：结构对了不等于措辞对。措辞语义错配（tag 对、文字不匹配）本脚本查不出，仍需人工复核。')


def self_test() -> int:
    """★ 判据自检：喂已知结果，断言该红时必须红。不读任何文件。"""
    base = {
        'must': ['a'], 'on_topic_requires': ['b'], 'common_but_not_required': [],
        'exclude': [{'E1': 'x'}, {'E2': 'y'}],
        'category_definition': {k: 'd' for k in CATEGORY_VALUES},
        'pos_examples': [{'verdict': 'on_topic'}, {'verdict': 'on_topic'}],
        'neg_examples': [
            {'verdict': 'wrong', 'exclude_item': 'E1'},
            {'verdict': 'wrong', 'exclude_item': 'E2'},
            {'verdict': 'wrong', 'exclude_item': 'E1'},
            {'verdict': 'wrong', 'exclude_item': 'E2'},
            {'verdict': 'wrong', 'exclude_item': 'E1'},
        ],
        'edge_examples': [
            {'verdict': 'tangential', 'category': 'upstream'},
            {'verdict': 'tangential', 'category': 'downstream'},
            {'verdict': 'on_topic', 'category': 'variant'},
            {'verdict': 'wrong', 'category': 'analogue', 'exclude_item': 'E1'},
            {'verdict': 'on_topic', 'category': 'composite'},
        ],
        'essence': 'e',
    }
    import copy
    ok = True

    def run(name, mutate, want_red, hint=''):
        nonlocal ok
        d = copy.deepcopy(base)
        mutate(d)
        errs = check(d)
        got_red = bool(errs)
        good = (got_red == want_red)
        ok &= good
        print(f'  {"✓" if good else "✗"} {name}: 期望{"红" if want_red else "绿"} / '
              f'实际{"红" if got_red else "绿"}' + (f'  [{hint}]' if hint and not good else ''))

    run('用例1 合规稿', lambda d: None, False)
    run('用例2 E 无覆盖（本次 E2 那类真事故）',
        lambda d: d['exclude'].append({'E9': 'z'}), True, '新增 E9 但没例子引它')
    run('用例3 category 缺一个',
        lambda d: d['edge_examples'].pop(), True, '删掉 composite 那条')
    run('用例4 edge 少于 5 条',
        lambda d: d.__setitem__('edge_examples', d['edge_examples'][:4]), True)
    run('用例5 neg 带项比例正好 50%（3/6）—— 边界，不算多数',
        lambda d: d.__setitem__('neg_examples', [
            {'verdict': 'wrong', 'exclude_item': 'E1'},
            {'verdict': 'wrong', 'exclude_item': 'E2'},
            {'verdict': 'wrong', 'exclude_item': 'E1'},
            {'verdict': 'wrong'}, {'verdict': 'wrong'}, {'verdict': 'wrong'},
        ]), True, '3/6 = 50%，按"严格过半"应判红')
    run('用例6 scope_note 被当 exclude_item',
        lambda d: d['neg_examples'][0].__setitem__('exclude_item', 'scope_note'), True, '§5.1.1 禁止')
    run('用例7 exclude_item 笔误',
        lambda d: d['neg_examples'][0].__setitem__('exclude_item', 'E99'), True)
    run('用例8 pos 的 verdict 写错',
        lambda d: d['pos_examples'][0].__setitem__('verdict', 'tangential'), True)
    run('用例9 edge 里 wrong 缺 exclude_item',
        lambda d: d['edge_examples'][3].pop('exclude_item'), True)
    run('用例10 缺 category_definition',
        lambda d: d.pop('category_definition'), True)

    print()
    if ok:
        print('✅ 自检通过：10/10 用例符合预期 ⇒ 该红时会红')
        return 0
    print('❌ 自检失败：判据本身有问题 ⇒ 不可用于验收')
    return 1


def main() -> int:
    ap = argparse.ArgumentParser(description='方法定义结构覆盖闸门（E 覆盖 / category 覆盖 / 条数 / 带项比例）')
    ap.add_argument('files', nargs='*', help='定义 YAML 路径，可多个')
    ap.add_argument('--self-test', action='store_true', help='只验判据本身（不读文件）')
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if not a.files:
        ap.error('给至少一个定义文件，或用 --self-test')

    bad = 0
    for p in a.files:
        try:
            with io.open(p, encoding='utf-8') as f:
                doc = yaml.safe_load(f)
        except Exception as e:
            print(f'❌ 解析失败 {p}: {e}')
            return 2
        if not isinstance(doc, dict):
            print(f'❌ {p} 不是 YAML 映射')
            return 2
        errs = check(doc)
        _fmt(errs, p)
        bad += bool(errs)
    return 1 if bad else 0


if __name__ == '__main__':
    sys.exit(main())
