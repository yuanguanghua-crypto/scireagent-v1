# -*- coding: utf-8 -*-
"""方法定义校验规则（**单一来源**）。

为什么单独成模块：
  同一条规则若在「管理命令」和「本地校验脚本」里各写一份，迟早分叉。
  这里只放**纯函数**（不依赖 Django、不读库、不写库）。

规则来源：`docs/方法定义规范_v3.md` v3.4 §5.1 / §5.3 / §六。

规则清单（11 条）：
  1  version 必须是字符串形式的 `<int>.<int>`（**不能是 float**：3.10 与 3.1 数值相等）
  2  pos_examples ≥2 且 verdict 全为 on_topic
  3  neg_examples ≥5 且 verdict 全为 wrong
  4  edge_examples 的 category ⊆ 5 值
  5  edge_examples ≥5 且覆盖全部 5 个 category
  6  neg/edge 的 exclude_item（若有）必须命中已存在的 E 码
  7  每个 E 码至少被一次引用
  8  author / reviewed_by 非空且不相同
  9  exclude 的形态：YAML 为 list[单键dict]，落库前拍平为 dict
  10 必填字段存在性 + 类型（11 项；`scope_note` **允许缺省**）
  11 **未加引号的新版**（内容 md5 不在祖父白名单）⇒ 硬失败

★ 规则 11 的设计（2026-11-05 按 Muse 意见落地）：
  YAML 里裸写 `version: 3.10` 会被解析成 float 3.1 —— 版本号被静默改掉。
  唯一能识别"这份文件是否已核"的方式是**内容 md5**（文件名键控会被改名绕过，已实测）。
  故：未加引号 ⇒ 只允许内容 md5 在 `LEGACY_MD5` 里的两份密封件；其余一律硬失败。
  **加引号（'3.10'）则无需白名单。**
  刻意**不引入 `sealed: true` 之类标记**：密封件本无此字段，加了要改文件、md5 一变祖父化即破；
  且标记本身可被滥加，防不住。

★ 白名单同源约束：本模块的 `LEGACY_MD5` 必须与 `work/validate_definition.py` 的同名常量
  **集合完全相等**，由 `apps/knowledge/tests/test_definition_rules_parity.py` 断言。
  两边各抄一份必然漂移，所以用相等断言把漂移变成红灯。

**未覆盖（勿当成已验）**：① 作者/复核"不得是模型名"——无黑名单；② 字段英文闸门（另有脚本）。
"""
CATEGORIES = ('upstream', 'downstream', 'variant', 'analogue', 'composite')

# 祖父白名单：**按内容 md5 键控**，是"未加引号"的唯一出口。
# 两份密封定义（SDS v3.1 / PCR v0.1）入库时未给 version 加引号，属历史既成事实。
LEGACY_MD5 = {
    '33125713528c15965a29f50ae2d5eebd',   # sds_page_definition_v3.1_曹操采纳.yaml
    '903fabc8d32bef048dd4f1d345e4b812',   # pcr_definition_v0.1_诸葛亮_reviewed_曹操_20261104.yaml
}

# 必填字段：(字段名, 期望的 Python 类型, 是否允许缺省)
# scope_note 明确**允许缺省**：规范里它是可选、只作描述；PCR 那份本就省略。
REQUIRED_FIELDS = (
    ('essence', str, False),
    ('must', list, False),
    ('on_topic_requires', list, False),
    ('common_but_not_required', list, False),
    ('exclude', list, False),
    ('category_definition', dict, False),
    ('pos_examples', list, False),
    ('neg_examples', list, False),
    ('edge_examples', list, False),
    ('author', str, False),
    ('reviewed_by', str, False),
    ('scope_note', str, True),
)


def flatten_exclude(raw):
    """[{E1: 文本}, ...] → {E1: 文本}。结构不符直接报错，不猜、不跳过。"""
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


def _check_required(d):
    """规则 10：必填字段存在性 + 类型。返回 issues 列表。"""
    out = []
    for name, typ, optional in REQUIRED_FIELDS:
        if name not in d or d[name] is None:
            if optional:
                continue
            out.append('规则10 缺必填字段 %s' % name)
            continue
        val = d[name]
        if not isinstance(val, typ):
            out.append('规则10 字段 %s 类型应为 %s，实际 %s'
                       % (name, typ.__name__, type(val).__name__))
            continue
        if typ is str and not val.strip() and not optional:
            out.append('规则10 字段 %s 不能为空串' % name)
    return out


def check(definition, version, quoted, file_md5):
    """校验一份定义。返回 (ok, issues:list[str], exclude_obj)。

    definition : YAML 原始结构的 dict
    version    : **原始 token 字符串**（不要传 float —— 那是规则 1 要禁的东西）
    quoted     : version 在 YAML 里是否加引号（False = 裸写，可能被解析成 float）
    file_md5   : 该 YAML **文件内容**的 md5（十六进制字符串）

    ★ quoted / file_md5 **无默认值**：调用方必须显式给出。
      给默认值等于留后门；两个参数都必填，规则 11 才真的生效。
    """
    issues = []
    d = definition or {}

    # ---- 规则 1：version 原始 token ----
    if not isinstance(version, str):
        issues.append('规则1 version 必须是 str，实际 %s（float 会让 3.10 与 3.1 相等）'
                      % type(version).__name__)
    else:
        parts = version.split('.')
        if len(parts) != 2 or not all(p.isdigit() for p in parts):
            issues.append('规则1 version 格式须为 <int>.<int>，实际 %r' % version)

    # ---- 规则 10：必填字段 ----
    issues.extend(_check_required(d))

    pos = d.get('pos_examples') or []
    neg = d.get('neg_examples') or []
    edge = d.get('edge_examples') or []

    # ---- 规则 2 / 3 ----
    if len(pos) < 2 or any((e or {}).get('verdict') != 'on_topic' for e in pos):
        issues.append('规则2 pos_examples 需 ≥2 且 verdict 全为 on_topic（当前 %d 条）' % len(pos))
    if len(neg) < 5 or any((e or {}).get('verdict') != 'wrong' for e in neg):
        issues.append('规则3 neg_examples 需 ≥5 且 verdict 全为 wrong（当前 %d 条）' % len(neg))

    # ---- 规则 4 / 5 ----
    cats = {(e or {}).get('category') for e in edge}
    bad_cat = sorted(c for c in cats if c not in CATEGORIES)
    if bad_cat:
        issues.append('规则4 edge category 出现非法值 %s' % bad_cat)
    missing = [c for c in CATEGORIES if c not in cats]
    if len(edge) < 5 or missing:
        issues.append('规则5 edge_examples 需 ≥5 且覆盖 5 类（当前 %d 条，缺 %s）'
                      % (len(edge), missing))

    # ---- 规则 9：exclude 形态 ----
    ex_obj, ex_err = flatten_exclude(d.get('exclude'))
    if ex_err:
        issues.append('规则9 %s' % ex_err)
        ex_obj = {}
    codes = set(ex_obj)

    # ---- 规则 6 / 7：E 码引用闭环 ----
    used = []
    for grp in (neg, edge):
        for e in grp:
            x = (e or {}).get('exclude_item') or ''
            if x:
                used.append(x)
    dangling = sorted({u for u in used if u not in codes})
    if dangling:
        issues.append('规则6 exclude_item 悬空（无对应 E 码）：%s' % dangling)
    orphan = sorted(codes - set(used))
    if orphan:
        issues.append('规则7 以下 E 码从未被引用：%s' % orphan)

    # ---- 规则 8：作者 / 复核 ----
    a, r = (d.get('author') or '').strip(), (d.get('reviewed_by') or '').strip()
    if not a or not r:
        issues.append('规则8 author/reviewed_by 不能为空')
    elif a == r:
        issues.append('规则8 author 与 reviewed_by 不能是同一人（%s）' % a)

    # ---- 规则 11：未加引号的新版 ----
    if not quoted:
        if not file_md5:
            issues.append('规则11 版本未加引号且取不到文件 md5 ⇒ 无法判定是否已核，按失败处理')
        elif file_md5 not in LEGACY_MD5:
            issues.append('规则11 版本未加引号，且文件 md5 %s… 不在祖父白名单 ⇒ 拒绝'
                          '（新版须写成 version: "3.10" 这样的字符串）' % file_md5[:12])

    return (not issues), issues, ex_obj
