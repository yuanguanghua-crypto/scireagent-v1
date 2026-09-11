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


def is_chem_specific(product, protocol) -> bool:
    """协议是否与本品化学结构相关（读端静默置顶判据）。

    关键词为空 → False（短路，不读协议文本）；
    否则把 protocol 的 scope_fields（name/objective/principle，从词表读）拼成
    一段文本，先做归一化再小写，任一关键词子串命中即 True。
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
    for kw in kws:
        if kw and kw in text:
            return True
    return False
