# -*- coding: utf-8 -*-
"""P0#2 L1：Method 触发词词典自动标注悬空协议。

策略（用户决策 2026-09-01：只做 L1 词典，效果不行再走 LLM 提取）：
  1. 词典来源 = 历史 evidence_source='lexicon_auto' 桥（3,451 条）——与历史标注同源，
     挖掘每个 Method 关联协议名的高频特征词（token 精确匹配，非子串）。
  2. 每 Method 取 top5 高频词；跨方法共用词（被 >=2 个 Method 的 top 列表共享）剔除
     ——无判别力的通用词（dna/protein/mouse/rna/vitro 等）不进入词典。
  3. STRONG 命中 = 协议名命中 >=2 个特征词，且得分严格最高唯一（并列不建，宁 miss 不错配）。
  4. 匹配文本仅用 Protocol.name（objective 噪音大，放大误报）。
  5. 落库：MethodProtocol(evidence_source='lexicon_auto', status='active', explicit=False)，
     与历史 lexicon_auto 桥形态一致。

铁律：宁 miss 不错配。词典未覆盖的 Method（无历史标注）不产生任何匹配，
留待后续 LLM 提取补齐。

2026-09-01 定稿依据（全量枚举审计，见 memory）：
  - 修复复数停用词漏网：STOP 检查必须在词干化之后（'assays'->'assay' 曾漏入词典，
    造成 In vitro Assays 类协议 5 连误报命中 Ubiquitination）。
  - 扩充 STOP：语义重叠/语料伪影词（frozen/fresh/blood/serum/platform/...）频率剔除
    无法覆盖（分布上只属 1 个 Method），只能显式停用。
  - 实测天花板：score=2 层存在词法不可根除的语义噪声，残余误报靠人工核验否决。
"""
import re
from collections import Counter, defaultdict

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Protocol

# 每 Method 取 top 特征词数
TOP_N = 5
# 跨方法共用阈值：被 >= CROSS_METHOD_K 个 Method 的 top 列表共享的词视为无判别力
CROSS_METHOD_K = 2

# 全局通用词：出现在协议名里不代表任何具体 Method 的噪音词。
STOP_WORDS = frozenset('''
the a an of for and in on with to by from using via protocol method assay based kit
buffer solution preparation preparing cell cells analysis quantification detection
generation isolation purification extraction staining labeling labelling human tissue
sample samples study studies group groups time day days new use used two one three
control treatment treated figure data results total concentration medium media culture
cultures sequencing sequence sequences expression expressed activity line lines patient
patients clinical trial trials review introduction background aims material materials
equipment statistical bioinformatics computational workflow pipeline procedures procedure
steps step description include included including general standard high throughput
combined novel assessment evaluation investigation examination role effect effects impact
toward towards among between during after before following derived prepared
experiment experimental vitro vivo rapid simple technique determination measurement
collection common platform characterization frozen fresh blood serum
'''.split())

# 半通用词：跨多个 Method 出现但仍有指向价值的词（rna/dna/cryo 等）不在此列——
# 它们靠「得分最高且唯一」规则 + 跨方法共用剔除（CROSS_METHOD_K）收敛，避免误建。


def _stem(w: str) -> str:
    """轻量复数/词形归一：primers->primer, libraries->library, boxes->box；保留 -is/-us/-ss 结尾。

    es 结尾有歧义：samples->sample（s-复数，只去 s）vs boxes->box（es-复数，去 es）。
    sses/xes/ches/shes/zes 按 es-复数处理（processes->process, boxes->box）；
    其余 es 结尾按 s-复数处理（samples->sample, cultures->culture）。
    """
    if w.endswith('ies') and len(w) > 4:
        return w[:-3] + 'y'
    if w.endswith('es') and len(w) > 4:
        if w.endswith(('sses', 'xes', 'ches', 'shes', 'zes')):
            return w[:-2]
        return w[:-1]
    if w.endswith('s') and len(w) > 3 and not w.endswith(('is', 'us', 'ss')):
        return w[:-1]
    return w


def _tokens(text: str) -> list:
    """token 精确分词：小写、词干归一、去 STOP、去短词；有序去重（稳定词典序）。

    注意：先词干后 STOP 检查——复数停用词（assays->assay, protocols->protocol）若在
    词干化之前检查会漏网，导致无判别力的停用词进入词典/参与匹配（L1 定稿已修复）。
    """
    out, seen = [], set()
    for w in re.findall(r'[a-z0-9-]+', text.lower()):
        w = _stem(w)
        if w in STOP_WORDS or len(w) <= 2:
            continue
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def build_lexicon() -> dict:
    """从历史 lexicon_auto 桥挖掘 {method_id: [特征词 top5（已剔除跨方法共用词）]}。

    - 每 Method 取关联协议名的高频 token（top TOP_N）。
    - 被 >= CROSS_METHOD_K 个 Method 共享的词剔除（dna/protein/mouse/vitro 类）。
    - 无 lexicon_auto 历史桥的 Method 不在词典中（L1 不覆盖，留待 LLM）。
    """
    pairs = list(
        MethodProtocol.objects.filter(evidence_source='lexicon_auto')
        .select_related('method', 'protocol')
        .values_list('method_id', 'protocol__name')
    )
    by_method = defaultdict(Counter)
    for method_id, pname in pairs:
        if not pname:
            continue
        by_method[method_id].update(_tokens(pname))
    top = {
        mid: [w for w, _ in c.most_common(TOP_N)]
        for mid, c in by_method.items() if c
    }
    # 跨方法共用词剔除
    word_methods = defaultdict(set)
    for mid, words in top.items():
        for w in words:
            word_methods[w].add(mid)
    shared = {w for w, s in word_methods.items() if len(s) >= CROSS_METHOD_K}
    return {
        mid: [w for w in words if w not in shared]
        for mid, words in top.items() if any(w not in shared for w in words)
    }


def match_protocol(name: str, lexicon: dict) -> list:
    """单协议匹配：返回得分最高且唯一、且 >=2 的 [(method_id, score)]（0 或 1 项）。

    - score < 2：不构成 STRONG，宁 miss。
    - 最高分并列多个 Method：无法区分，不建（宁 miss 不错配）。
    """
    if not name:
        return []
    toks = _tokens(name)
    if not toks:
        return []
    scored = []
    for mid, words in lexicon.items():
        hit = len(set(words) & set(toks))
        if hit >= 2:
            scored.append((mid, hit))
    if not scored:
        return []
    scored.sort(key=lambda x: x[1], reverse=True)
    best = scored[0]
    ties = [s for s in scored if s[1] == best[1]]
    if len(ties) > 1:
        return []
    return [best]


def annotate_orphan_protocols(apply: bool = False) -> dict:
    """对无 MethodProtocol 桥的悬空协议跑 L1 词典匹配。

    apply=False（默认）：只统计不落库（dry-run，闸门）。
    apply=True：创建 MethodProtocol(evidence_source='lexicon_auto', status='active')。
    """
    lexicon = build_lexicon()
    if not lexicon:
        return {'total_orphans': 0, 'matched': 0, 'created': 0, 'no_lexicon': True}

    linked = set(
        MethodProtocol.objects.values_list('protocol_id', flat=True).distinct()
    )
    orphans = list(Protocol.objects.exclude(id__in=linked).only('id', 'name'))
    stats = {'total_orphans': len(orphans), 'matched': 0, 'created': 0, 'no_lexicon': False}
    to_create = []
    for proto in orphans:
        hits = match_protocol(proto.name, lexicon)
        if hits:
            stats['matched'] += 1
            if apply:
                to_create.append(
                    MethodProtocol(
                        method_id=hits[0][0], protocol_id=proto.id,
                        evidence_source='lexicon_auto', status='active', explicit=False,
                    )
                )
    if to_create:
        MethodProtocol.objects.bulk_create(to_create, ignore_conflicts=True)
        stats['created'] = len(to_create)
    return stats
