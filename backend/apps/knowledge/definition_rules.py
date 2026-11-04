# -*- coding: utf-8 -*-
"""方法定义校验规则（单一来源）。

为什么单独成模块：
  同一条规则若在「管理命令」和「本地校验脚本」里各写一份，迟早分叉。
  这里只放**纯函数**（不依赖 Django、不读库、不写库），
  管理命令与任何脚本都 import 它，规则只维护一处。

规则来源：`docs/方法定义规范_v3.md` v3.4 §5.1 / §5.3 / §六。
9 条：
  1 version 必须是字符串形式的 `<int>.<int>`（**不能是 float**：3.10 与 3.1 数值相等）
  2 pos_examples ≥2 且 verdict 全为 on_topic
  3 neg_examples ≥5 且 verdict 全为 wrong
  4 edge_examples 的 category ⊆ 5 值
  5 edge_examples ≥5 且覆盖全部 5 个 category
  6 neg/edge 的 exclude_item（若有）必须命中已存在的 E 码
  7 每个 E 码至少被一次引用
  8 author / reviewed_by 非空且不相同
  9 exclude 的形态：YAML 为 list[单键dict]，落库前拍平为 dict

**未覆盖（勿当成已验）**：① 作者/复核"不得是模型名"——无黑名单；② 字段英文闸门（另有脚本）。
"""
CATEGORIES = ('upstream', 'downstream', 'variant', 'analogue', 'composite')


def flatten_exclude(raw):
    """[{E1: 文本}, ...] → {E1: 文本}。结构不符直接抛错，不猜、不跳过。"""
    if raw is None:
        return {}, None
    if not isinstance(raw, list):
        return None, 'exclude 应为 list，实际 %s' % type(raw).__name__
    out = {}
    for i, item in enumerate(raw):
        if not (isinstance(item, dict) and len(item) == 1):
            return None, 'exclude[%d] 不是单键字典：%r' % (i, item)
        code = list(item)[0]
        if code in out:
            return None, 'exclude 出现重复码 %s' % code
        out[code] = item[code]
    return out, None


def check(definition, version):
    """校验一份定义。返回 (ok, issues:list[str], exclude_obj)。

    definition 用 YAML 原始结构的 dict；version 用**原始 token 字符串**
    （不要传 float —— 那是本条规则要禁的东西）。
    """
    issues = []
    d = definition or {}

    if not isinstance(version, str):
        issues.append('规则1 version 必须是 str，实际 %s（float 会让 3.10 与 3.1 相等）'
                      % type(version).__name__)
    else:
        parts = version.split('.')
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            issues.append('规则1 version 格式须为 <int>.<int>，实际 %r' % version)

    pos = d.get('pos_examples') or []
    neg = d.get('neg_examples') or []
    edge = d.get('edge_examples') or []

    if len(pos) < 2 or any(e.get('verdict') != 'on_topic' for e in pos):
        issues.append('规则2 pos_examples 需 ≥2 且 verdict 全为 on_topic（当前 %d 条）' % len(pos))
    if len(neg) < 5 or any(e.get('verdict') != 'wrong' for e in neg):
        issues.append('规则3 neg_examples 需 ≥5 且 verdict 全为 wrong（当前 %d 条）' % len(neg))

    cats = {e.get('category') for e in edge}
    bad_cat = sorted(c for c in cats if c not in CATEGORIES)
    if bad_cat:
        issues.append('规则4 edge category 出现非法值 %s' % bad_cat)
    missing = [c for c in CATEGORIES if c not in cats]
    if len(edge) < 5 or missing:
        issues.append('规则5 edge_examples 需 ≥5 且覆盖 5 类（当前 %d 条，缺 %s）'
                      % (len(edge), missing))

    ex_obj, ex_err = flatten_exclude(d.get('exclude'))
    if ex_err:
        issues.append('规则9 %s' % ex_err)
        ex_obj = {}
    codes = set(ex_obj)

    used = []
    for grp in (neg, edge):
        for e in grp:
            x = e.get('exclude_item') or ''
            if x:
                used.append(x)
    dangling = sorted({u for u in used if u not in codes})
    if dangling:
        issues.append('规则6 exclude_item 悬空（无对应 E 码）：%s' % dangling)
    orphan = sorted(codes - set(used))
    if orphan:
        issues.append('规则7 以下 E 码从未被引用：%s' % orphan)

    a, r = (d.get('author') or '').strip(), (d.get('reviewed_by') or '').strip()
    if not a or not r:
        issues.append('规则8 author/reviewed_by 不能为空')
    elif a == r:
        issues.append('规则8 author 与 reviewed_by 不能是同一人（%s）' % a)

    return (not issues), issues, ex_obj
