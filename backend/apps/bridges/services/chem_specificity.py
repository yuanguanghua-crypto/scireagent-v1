"""化学特异性读端判定（chem-specific silent re-rank overlay）。

本模块是「读端」纯函数层：基于产品已有的 S6 子结构标签
(Product.substructure_tags) 与一份受控化学词表 (chem_lexicon.json)，
对协议的 name/objective/principle 文本做子串命中判定，供排序时静默置顶。

铁律（仅排序/标注，不写库、不改 relevance/tier/link_source）：
- 不引入任何模型/DB 访问；
- 只 import json / os / unicodedata / django.conf.settings；
- 不 import relevance（避免循环依赖）。
"""
import json
import os
import unicodedata

from django.conf import settings

# 词表相对本文件：services/ -> ../data/chem_lexicon.json
_LEXICON_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'data', 'chem_lexicon.json'
)
_LEXICON = None  # 模块级缓存


def _normalize(s):
    """文本归一化：NFKC 折叠 + 非 ASCII 撇号/连字符统一为 ASCII。

    真实数据里存在 U+2010 连字符与 U+2018/U+2019 撇号（例如品名
    `5‑Propargylamino‑dUTP`），匹配前必须归一化，否则子串判定失效。
    关键词侧与协议文本侧共用同一函数。
    """
    s = unicodedata.normalize('NFKC', s or '')
    for ch in ('\u2018', '\u2019'):   # ‘ ’ -> '
        s = s.replace(ch, "'")
    for ch in ('\u2010', '\u2011', '\u2013', '\u2014'):  # ‐ ‑ – — -> -
        s = s.replace(ch, '-')
    return s.lower()


def load_lexicon():
    """模块级缓存读取 chem_lexicon.json；文件缺失返回空 dict，绝不抛异常。"""
    global _LEXICON
    if _LEXICON is None:
        try:
            with open(_LEXICON_PATH, 'r', encoding='utf-8') as f:
                _LEXICON = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            _LEXICON = {}
    return _LEXICON


def keywords_for_product(product) -> set:
    """读 product.substructure_tags → 受控词表关键词集合。

    - substructure_tags 不是 dict，或 parsed 为假 → 返回空 set（诚实不冒充）；
    - 取其中的 labels 列表，按 lexicon['labels'] 映射展开；
    - 没有词表条目的标签（U/deoxy/NTP 等）自然被过滤掉。
    """
    tags = getattr(product, 'substructure_tags', None)
    if not isinstance(tags, dict) or not tags.get('parsed'):
        return set()
    labels = tags.get('labels') or []
    lexicon = load_lexicon()
    label_map = lexicon.get('labels', {})
    kws = set()
    for label in labels:
        for kw in label_map.get(label, []):
            kws.add(_normalize(kw))
    return kws


def _protocol_field(protocol, field):
    """兼容 model 实例与 dict 两种传参（测试用 SimpleNamespace/dict 皆可）。"""
    if isinstance(protocol, dict):
        return protocol.get(field)
    return getattr(protocol, field, None)


def _find_occurrences(text, term, word_boundary):
    """在已归一化文本中找出 `term` 的全部起始下标。

    `word_boundary=True` 时要求匹配两侧为非字母数字边界（如 `dna` 不会在
    `cdna`/`mrna` 内误中、`atp` 不会在 `datp` 内误中）。用于长度 < 5 的短词，
    严格按契约执行，绝不裸子串。
    """
    if not term:
        return
    L = len(term)
    n = len(text)
    start = 0
    while True:
        idx = text.find(term, start)
        if idx == -1:
            return
        if word_boundary:
            left_ok = idx == 0 or not text[idx - 1].isalnum()
            right_ok = (idx + L == n) or not text[idx + L].isalnum()
            if left_ok and right_ok:
                yield idx
        else:
            yield idx
        start = idx + 1


def _any_domain_term(text, domain_terms):
    """document 模式：归一化文本中出现任一 domain term 即 True。"""
    for term in domain_terms:
        if not term:
            continue
        wb = len(term) < 5
        for _ in _find_occurrences(text, term, wb):
            return True
    return False


def _proximity_match(text, domain_terms, matched_kw, window):
    """proximity 模式：已命中的化学关键词需在 ±window 字符内出现任一 domain term。

    按关键词区间与 domain term 区间的间隙（gap，重叠则为 0）判定。
    """
    kw_ranges = [(i, i + len(matched_kw))
                 for i in _find_occurrences(text, matched_kw, False)]
    if not kw_ranges:
        return False
    for term in domain_terms:
        if not term:
            continue
        wb = len(term) < 5
        for dpos in _find_occurrences(text, term, wb):
            d_start, d_end = dpos, dpos + len(term)
            for kw_start, kw_end in kw_ranges:
                gap = max(d_start - kw_end, kw_start - d_end, 0)
                if gap <= window:
                    return True
    return False


def _domain_ok(text, gate, domain_terms, matched_kw=None):
    """纯函数：归一化文本 `text`（已命中某化学关键词）是否满足 domain_gate。

    - 'off'      ：放行（caller 已在 is_chem_specific 中短路，此处仅为完整）；
    - 'document' ：任一 domain term 出现在文本任意位置即 True；
    - 'proximity'：某 domain term 落在已命中关键词 ±window 字符内即 True
                   （需 matched_kw；缺失则保守判 False）；
    未知 mode 保守判 False（宁 miss 不错配）。
    """
    gate = gate or {}
    mode = gate.get('mode', 'proximity')
    if mode == 'off':
        return True
    if mode == 'document':
        return _any_domain_term(text, domain_terms)
    if mode == 'proximity':
        window = int(gate.get('window', 300))
        if not matched_kw:
            return False
        return _proximity_match(text, domain_terms, matched_kw, window)
    return False


def is_chem_specific(product, protocol) -> bool:
    """协议是否与本品化学结构相关（读端静默置顶判据）。

    关键词为空 → False（短路，不读协议文本）；否则把 protocol 的
    scope_fields（name/objective/principle，从词表读）拼成一段归一化文本，
    任一关键词子串命中后，再经 domain_gate 校验（默认 proximity：关键词须在
    ±window 字符内出现「核苷酸专有」术语）。注意：mode='off' 仅跳过 gate，
    关键词表本身已在 v2 收紧（移除裸 click/alkyn），故 off 复现的是
    「关键词收紧后」的行为（实测约 65 条），并非修复前的 110 条——切勿据此
    与 110 对照。签名保持不变。
    """
    kws = keywords_for_product(product)
    if not kws:
        return False
    lexicon = load_lexicon()
    scope_fields = lexicon.get('scope_fields', ['name', 'objective', 'principle'])
    parts = []
    for field in scope_fields:
        val = _protocol_field(protocol, field)
        if val:
            parts.append(_normalize(val))
    text = ' '.join(parts)
    if not text:
        return False
    gate = lexicon.get('domain_gate')
    mode = (gate or {}).get('mode', 'proximity') if gate else 'proximity'
    # 'off' 精确复现旧行为（无 gate），供 A/B 测量
    if mode == 'off':
        for kw in kws:
            if kw and kw in text:
                return True
        return False
    domain_terms = lexicon.get('domain_terms') or []
    for kw in kws:
        if kw and kw in text:
            if _domain_ok(text, gate, domain_terms, matched_kw=kw):
                return True
    return False
