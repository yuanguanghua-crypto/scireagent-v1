"""三轴融合相关性打分服务（§14 + 决策 Q4 轴C离线持久化）。

轴A 厂商声称：docx 用途(P) × 协议领域词(Q) F-score（0.5·coverage + 0.5·precision）
轴B 文献实证：Bioz 协议级对齐（B1 修复），count 经 BIOZ_TYP_CAP 上限归一
轴C 语义打散：embedding 余弦 (cos+1)/2（all-MiniLM-L6-v2），离线预计算持久化

融合公式（§14.2）：
    relevance_score = 0.70·S_A + 0.10·S_B + 0.20·S_C    权重和=1，wB 硬上限 0.10
"""
import json
import os
import re

from django.conf import settings

# 三轴权重（和=1）。wB 为硬上限：即便 S_B=1，对总分贡献封顶 0.10（#338 稀疏实证不喧宾夺主）
WEIGHTS = {'a': 0.70, 'b': 0.10, 'c': 0.20}
# 轴B 归一上限：S_B = min(1, bioz_aligned_count / BIOZ_TYP_CAP)
BIOZ_TYP_CAP = 5

_VOCAB_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), 'data', 'domain_vocab.json'
)
_DOMAIN_INDEX = None  # {domain: [synonyms...]}

_TOKEN_RE = re.compile(r"[a-z0-9\-]+")


def _load_vocab():
    global _DOMAIN_INDEX
    if _DOMAIN_INDEX is None:
        try:
            with open(_VOCAB_PATH, 'r', encoding='utf-8') as f:
                _DOMAIN_INDEX = json.load(f)
        except FileNotFoundError:
            _DOMAIN_INDEX = {}
    return _DOMAIN_INDEX


def _domain_terms():
    """展开 vocab 为可匹配的子串集合（含多词短语）。"""
    vocab = _load_vocab()
    terms = set()
    for domain, syns in vocab.items():
        terms.add(domain)
        for s in syns:
            terms.add(s.lower())
    return terms


def _extract_domains(text):
    """从文本抽取命中的领域词：多词短语做子串匹配，单词做词边界匹配。"""
    if not text:
        return set()
    low = (text or '').lower()
    hit = set()
    for term in _domain_terms():
        if ' ' in term:
            if term in low:
                hit.add(term)
        else:
            if re.search(r'\b' + re.escape(term) + r'\b', low):
                hit.add(term)
    return hit


def _protocol_q_text(protocol):
    """协议侧的领域词文本：拼接协议真实的描述性字段（§14.1）。

    仅用 Protocol 模型实际存在的字段，避免引用不存在的 summary/purpose。
    """
    return ' '.join([
        getattr(protocol, 'name', '') or '',
        getattr(protocol, 'objective', '') or '',
        getattr(protocol, 'principle', '') or '',
        getattr(protocol, 'materials', '') or '',
        getattr(protocol, 'reagents', '') or '',
        getattr(protocol, 'expected_results', '') or '',
        getattr(protocol, 'references', '') or '',
    ])


def compute_axis_a(product, protocol):
    """轴A：docx 用途(P) × 协议领域词(Q) F-score。

    无 usage → 返回 None（诚实不冒充，不得用 0 假装"已算过"）。
    """
    usage = getattr(product, 'usage', None)
    if not usage:
        return None
    P = _extract_domains(usage)
    if not P:
        return None
    Q = _extract_domains(_protocol_q_text(protocol))
    if not Q:
        return 0.0
    inter = P & Q
    coverage = len(inter) / len(P)
    precision = len(inter) / len(Q)
    return 0.5 * coverage + 0.5 * precision


def _field_to_text(v):
    """把 bioz 文献字段规整为字符串：列表元素空格连接，None→空串。

    真实 Bioz 记录中 techniques 等字段是 list（见 bioz_client._parse_records），
    直接 ' '.join 会抛 TypeError；此 helper 统一规整，避免轴B 计算在遇到真实
    文献数据时崩溃（此前 S_B 恒为死轴，该路径从未被真实数据执行过）。
    """
    if v is None:
        return ''
    if isinstance(v, (list, tuple)):
        return ' '.join(str(x) for x in v if x is not None)
    return str(v)


def compute_axis_b(product, protocol, bioz_lits=None):
    """轴B：Bioz 协议级对齐（B1 修复）。

    仅当某条 Bioz 文献文本与本协议 Q 重叠才计入对齐（严禁产品级均摊）。
    返回 (S_B, literature_count)。S_B = min(1, count / BIOZ_TYP_CAP)。
    """
    if not bioz_lits:
        return 0.0, 0
    Q = _extract_domains(_protocol_q_text(protocol))
    if not Q:
        return 0.0, 0
    lit_n = 0
    for lit in bioz_lits:
        lit_text = ' '.join(_field_to_text(lit.get(f, '')) for f in
                            ('article_title', 'techniques', 'long', 'medium', 'short'))
        if _extract_domains(lit_text) & Q:
            lit_n += 1
    S_B = min(1.0, lit_n / BIOZ_TYP_CAP)
    return S_B, lit_n


def _default_embedding_fn(product, protocol):
    """默认轴C：惰性加载 emb3_venv 后算余弦；不可用则降级 0.0。"""
    try:
        from .embedding_backend import embed_similarity
        return embed_similarity(product, protocol)
    except Exception:
        return 0.0


def compute_axis_c(product, protocol, embedding_fn=None):
    """轴C：embedding 余弦 → (cos+1)/2 ∈ [0,1]。embedding_fn 可注入（测试/离线）。"""
    fn = embedding_fn or _default_embedding_fn
    try:
        cos = fn(product, protocol)
    except Exception:
        return 0.0
    if cos is None:
        return 0.0
    return (float(cos) + 1.0) / 2.0


def fuse_relevance(score_a=None, score_b=0.0, score_c=0.0):
    """三轴融合 + 派生 relevance_basis / tier。

    权重和=1；wB 硬上限由调用方确保 score_b∈[0,1]（其对总分贡献 = 0.10·score_b ≤ 0.10）。
    """
    S_A = score_a if score_a is not None else 0.0
    S_B = score_b if score_b is not None else 0.0
    S_C = score_c if score_c is not None else 0.0
    relevance = WEIGHTS['a'] * S_A + WEIGHTS['b'] * S_B + WEIGHTS['c'] * S_C

    if S_B > 0 and S_A > 0:
        basis = 'combined'
    elif S_B > 0:
        basis = 'bioz_aligned'
    elif S_A > 0:
        basis = 'vendor_only'
    else:
        basis = 'embedding_break' if S_C > 0 else ''

    if S_B > 0:
        tier = 'literature'
    elif S_A > 0:
        tier = 'document'
    else:
        tier = 'weak'  # S4：原 'featured'（虚假"编辑精选"徽标）改为 'weak'（仅语义相似/广播桶）

    return {
        'relevance_score': relevance,
        'score_a': score_a,
        'score_b': score_b if score_b is not None else None,
        'score_c': score_c if score_c is not None else None,
        'relevance_basis': basis,
        'tier': tier,
    }


def protocol_link_sort_key(r):
    """Protocol Link 排序键（S4：weak 恒沉底）。

    返回 tuple 供 list.sort(key=...) 使用：
      1) weak（广播/仅语义相似桶）主键=1，其余=0 —— weak 永远排最后；
      2) -relevance_score 降序；
      3) -score_c 降序（第三级，#357）；
      4) id 升序（稳定终判）。

    `r` 为序列化行 dict（含 tier/relevance_score/score_c/id）。零假设缺失字段。
    """
    sink = 1 if (r.get('tier') == 'weak') else 0
    return (
        sink,
        -float(r.get('relevance_score') or 0.0),
        -float(r.get('score_c') or 0.0),
        r.get('id') or 0,
    )


def _aggregate_scores(scores, operator='mean'):
    """把一组逐 (商品×协议) 相关性分聚合成单一商品级分（S5）。

    支持算子：
      - 'mean'     : 均值（默认；S5 选定，区分度与 Top20 跨度双优）
      - 'max'      : 最大值（只看最强单链，区分度低）
      - 'top3_mean': 前三均值（兼顾广度与强度）
      - 'logsumexp': 平滑最大值（t=5），对离群稳健
    输入为空、或有效分全为 None/NaN -> 返回 None（诚实不冒充 0：
    无 evidenced 链接的商品聚合分=空，排序应沉底而非被 0 顶起）。
    """
    import math
    valid = []
    for s in (scores or []):
        if s is None:
            continue
        try:
            f = float(s)
        except (TypeError, ValueError):
            continue
        if math.isnan(f):
            continue
        valid.append(f)
    if not valid:
        return None
    if operator == 'mean':
        return sum(valid) / len(valid)
    if operator == 'max':
        return max(valid)
    if operator == 'top3_mean':
        top = sorted(valid, reverse=True)[:3]
        return sum(top) / len(top)
    if operator == 'logsumexp':
        t = 5.0
        m = max(valid)
        return m + math.log(sum(math.exp(t * (v - m)) for v in valid)) / t
    raise ValueError(f"unknown operator: {operator}")


def aggregate_product_relevance(pp_rows, operator='mean'):
    """从一组 ProductProtocol 行聚合出商品级分（S5）。

    仅聚合 tier != 'weak' 的行（排除广播/仅语义相似，保区分度，呼应
    v2「坏输入上调统计量没意义」——把弱相关稀释掉而非并入均值）。
    无任何 non-weak 行 -> None；None/NaN 分跳过；operator 透传。
    """
    scores = [
        r.relevance_score
        for r in pp_rows
        if getattr(r, 'tier', None) != 'weak'
    ]
    return _aggregate_scores(scores, operator)


def update_product_aggregate(product):
    """重算并落库某商品的聚合分（仅 non-weak，S5）。

    幂等可回滚：直接覆盖 Product.aggregate_relevance_score；无 evidenced
    链接 -> None（沉底）。由 recompute_product / recompute_auto_links
    （非 dry_run）在写完该商品 PP 行后调用。
    """
    from apps.bridges.models import ProductProtocol
    rows = ProductProtocol.objects.filter(product=product).exclude(tier='weak')
    agg = _aggregate_scores([r.relevance_score for r in rows], 'mean')
    product.aggregate_relevance_score = agg
    product.save(update_fields=['aggregate_relevance_score'])


def load_product_bioz(product):
    """加载产品级 Bioz 文献缓存（用于轴B 协议级对齐）。

    修复 #473-B2：原实现从 apps.knowledge.models 导入 DataSourceCache（模型实属
    apps.documents.models）致 ImportError 被吞、永远返回 []；且 filter 用不存在的
    resolved_catalog 列、取 r.payload（真实是 get_data()）。三处缺陷叠加使轴B 文献轴
    全库恒为 0（literature 档从未触发）。

    现从正确模块导入；按产品的可解析键（catalog_no + 关联 SKU.sku_code）查询 bioz 缓存
    （跨 namespace），返回载荷列表。任何异常均安全降级 []（轴B 退化为 0，不阻断 recompute）。

    注：生产库 bioz 缓存按厂商货号（如 'Jena Bioscience:36544'）键入，而产品仅持内部
    catalog_no / sku_code，无厂商货号映射 → 即便 loader 正确，S_B 仍无法接通，需另行
    按 SC catalog_no 重键 bioz 缓存（数据/导入缺口，非本 loader 缺陷）。
    """
    try:
        from apps.documents.models import DataSourceCache
    except Exception:
        return []
    try:
        keys = []
        cat = getattr(product, 'catalog_no', None)
        if cat:
            keys.append(cat)
        skus = getattr(product, 'skus', None)
        if skus is not None:
            try:
                for sku in skus.all():
                    code = getattr(sku, 'sku_code', None)
                    if code:
                        keys.append(code)
            except Exception:
                pass
        if not keys:
            return []
        rows = DataSourceCache.objects.filter(source='bioz', query_key__in=keys)
        out = []
        for r in rows:
            data = r.get_data()
            if isinstance(data, list):
                out.extend(d for d in data if isinstance(d, dict))
            elif isinstance(data, dict):
                out.append(data)
        return out
    except Exception:
        return []


def recompute_product(product, embedding_fn=None):
    """为单个产品重算并落/更新 ProductProtocol 行（幂等 upsert）。

    派生协议集取自产品的 MethodProtocol 链路（铁律①全量保留，不丢）。
    返回写入/更新的协议数。
    """
    from apps.bridges.models import (
        ProductMethod, MethodProtocol, ProductProtocol,
    )
    from apps.knowledge.models import Protocol

    method_ids = list(
        ProductMethod.objects.filter(product=product).values_list('method_id', flat=True)
    )
    if not method_ids:
        update_product_aggregate(product)  # 无派生链，仍刷新聚合分（可能仅 AUTO/EXPLICIT）
        return 0
    protocol_ids = list(
        MethodProtocol.objects.filter(method_id__in=method_ids)
        .values_list('protocol_id', flat=True).distinct()
    )
    if not protocol_ids:
        update_product_aggregate(product)
        return 0

    bioz_lits = load_product_bioz(product)
    n = 0
    for pid in protocol_ids:
        protocol = Protocol.objects.filter(id=pid).first()
        if protocol is None:
            continue
        s_a = compute_axis_a(product, protocol)
        s_b, lit_n = compute_axis_b(product, protocol, bioz_lits=bioz_lits)
        s_c = compute_axis_c(product, protocol, embedding_fn=embedding_fn)
        fused = fuse_relevance(score_a=s_a, score_b=s_b, score_c=s_c)
        ProductProtocol.objects.update_or_create(
            product=product, protocol=protocol,
            defaults={
                'relevance_score': fused['relevance_score'],
                'score_a': fused['score_a'],
                'score_b': fused['score_b'],
                'score_c': fused['score_c'],
                'literature_count': lit_n,
                'relevance_basis': fused['relevance_basis'],
                'tier': fused['tier'],
                'link_source': ProductProtocol.LinkSource.INHERITED,
            },
        )
        n += 1
    update_product_aggregate(product)  # S5：写完该商品 PP 行后刷新商品级聚合分
    return n
