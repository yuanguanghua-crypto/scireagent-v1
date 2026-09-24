"""三轴融合相关性打分服务（§14 + 决策 Q4 轴C离线持久化）。

轴A 厂商声称：docx 用途(P) × 协议领域词(Q) F-score（0.5·coverage + 0.5·precision）
轴B 文献实证：Bioz 协议级对齐（B1 修复），count 经 BIOZ_TYP_CAP 上限归一
轴C 语义打散：embedding 余弦 (cos+1)/2（all-MiniLM-L6-v2），离线预计算持久化

融合公式（§14.2）：
    relevance_score = 0.70·S_A + 0.10·S_B + 0.20·S_C    权重和=1，wB 硬上限 0.10
    （S_C 缺测 `None` 时按可用轴重归一化：(0.70·S_A + 0.10·S_B) / 0.80）
"""
import json
import os
import re

from django.conf import settings
from django.db import transaction

# 三轴权重（和=1）。wB 为硬上限：即便 S_B=1，对总分贡献封顶 0.10（#338 稀疏实证不喧宾夺主）
WEIGHTS = {'a': 0.70, 'b': 0.10, 'c': 0.20}
# 轴B 归一上限：S_B = min(1, bioz_aligned_count / BIOZ_TYP_CAP)
BIOZ_TYP_CAP = 5

# ★ 低分不落库（2026-09-24，「宁 miss 不错配」）—— 口径于 09-24 晚**与环境解耦**：
#   判据 = **纯零证据**：`tier=='weak'`（S_A=0 且 S_B=0，既无厂商文档、也无文献实证）。
#   ⚠️ 为什么**不再**引用 score_c（原判据 `tier=='weak' and score_c<=0.5`）：
#     那会让**落库结果随 embedding 后端可用性漂移**——同一份代码、不同机器产出不同数据：
#       · 无 embedding（score_c 恒为哨兵 0.5）⇒ 挡掉**全部** weak；
#       · 有真 embedding ⇒ 只挡 cos<=0 的 weak（09-22 实测仅 137/7,678 = 1.8%）⇒ weak 大量回流。
#     解耦后口径**恒定、可解释、与环境无关**（稳定性/健壮性硬要求）。
#   依据：一次全量补算试跑新增 66 条 weak 行（占该次新增 64%）全部属"零证据"，仍是噪声。
#   ⚠️ 只影响**写**：既有行不会被删（与「只增不删」一致），存量清理另行处理。
def is_evidence_free(fused):
    """零证据：仅语义相似、无厂商文档、无文献实证 ⇒ 不落库。"""
    return fused.get('tier') == 'weak'


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


def fuse_relevance(score_a=None, score_b=0.0, score_c=None):
    """三轴融合 + 派生 relevance_basis / tier。

    权重和=1；wB 硬上限由调用方确保 score_b∈[0,1]（其对总分贡献 = 0.10·score_b ≤ 0.10）。

    ★ 轴C 可为 `None`（离线 embedding 作业尚未覆盖该行）：
      `score_c is None` ⇒ 在**可用轴 (A,B)** 上**重归一化**权重，
      避免"缺 C"让所有 relevance 凭空少掉 0.2 权重而被系统性压低。
      ⚠️ `0.0` 与 `None` 语义**不同**：`0.0` = 有值且为零（参与权重），`None` = 缺测（不参与）。
    """
    S_A = score_a if score_a is not None else 0.0
    S_B = score_b if score_b is not None else 0.0
    if score_c is None:
        S_C = None
        w_a, w_b, w_c, denom = WEIGHTS['a'], WEIGHTS['b'], 0.0, (WEIGHTS['a'] + WEIGHTS['b'])
    else:
        S_C = score_c
        w_a, w_b, w_c, denom = WEIGHTS['a'], WEIGHTS['b'], WEIGHTS['c'], 1.0
    relevance = (w_a * S_A + w_b * S_B + w_c * (S_C or 0.0)) / denom

    if S_B > 0 and S_A > 0:
        basis = 'combined'
    elif S_B > 0:
        basis = 'bioz_aligned'
    elif S_A > 0:
        basis = 'vendor_only'
    else:
        basis = 'embedding_break' if (S_C or 0.0) > 0 else ''

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
        'score_c': S_C,
        'relevance_basis': basis,
        'tier': tier,
    }


def protocol_link_sort_key(r):
    """Protocol Link 排序键（S4：weak 恒沉底 + chem-specific 静默置顶）。

    返回 tuple 供 list.sort(key=...) 使用：
      1) weak（广播/仅语义相似桶）主键=1，其余=0 —— weak 永远排最后；
      2) chem（化学特异置顶键）：非 weak 且 chem_specific 的行=0，其余=1
         —— chem_specific 行静默顶到非 weak 区最前；weak 行恒沉底，不可被顶起；
      3) -relevance_score 降序；
      4) -score_c 降序（第四级，#357）；
      5) id 升序（稳定终判）。

    `r` 为序列化行 dict（含 tier/chem_specific/relevance_score/score_c/id）。
    零假设缺失字段。
    """
    is_weak = 1 if (r.get('tier') == 'weak') else 0
    # chem_specific 仅对非 weak 行生效（weak 恒沉底，不可被顶起）
    chem = 0 if (r.get('chem_specific') and not is_weak) else 1
    return (
        is_weak,
        chem,
        -float(r.get('relevance_score') or 0.0),
        -float(r.get('score_c') or 0.0),
        r.get('id') or 0,
    )


def build_protocol_links(product):
    """构建产品协议链行（P0#3 方案A「读端打通」）。

    数据源：ProductProtocol 直接表（select_related('protocol')，含 INHERITED/EXPLICIT/AUTO
    全量行）——覆盖全库 23,431 行 PP 真实数据，避免详情页死数据不可见。
    无 PP 行（recompute 未跑的存量产品）时回退 MethodProtocol 桥派生协议（旧逻辑形状，
    tier='weak'/score=0），确保任何产品都不丢数据。

    排序：protocol_link_sort_key（weak 恒沉底 → chem 置顶 → 相关性降序 →
    score_c 降序 → id 升序），与 ProductDetailSerializer.get_protocol_links 的
    既有排序规则一致。

    返回行 dict 列表，字段命名与 get_protocol_links 输出一致：
    id/name/slug/relevance_score/score_a/score_b/score_c/relevance_basis/
    link_source/tier/literature_count/chem_specific。
    （chem_specific 为读端叠加标记，绝不修改 relevance_score/tier/link_source。）
    """
    from apps.bridges.models import ProductMethod, MethodProtocol, ProductProtocol
    from apps.knowledge.models import Protocol
    from apps.bridges.services.chem_specificity import is_chem_specific

    pp_rows = list(
        ProductProtocol.objects.filter(product=product).select_related('protocol')
    )

    def _row(pid, proto, pp):
        # 读端叠加：chem_specific 仅基于既有 PP 行带出的 protocol + 产品子结构标签，
        # 纯内存判定，不新增 DB 查询（proto 已由 select_related 带出）。
        chem = is_chem_specific(product, proto) if proto is not None else False
        if pp is not None:
            return {
                'id': proto.id if proto else pid,
                'name': getattr(proto, 'name', None),
                'slug': getattr(proto, 'slug', None),
                'relevance_score': pp.relevance_score,
                'score_a': pp.score_a,
                'score_b': pp.score_b,
                'score_c': pp.score_c,
                'relevance_basis': pp.relevance_basis,
                'link_source': pp.link_source,
                'tier': pp.tier,
                'literature_count': pp.literature_count,
                'chem_specific': chem,
            }
        # 回退（仅 MethodProtocol 桥派生）：重算未跑，诚实以 weak/0 呈现
        return {
            'id': proto.id if proto else pid,
            'name': getattr(proto, 'name', None),
            'slug': getattr(proto, 'slug', None),
            'relevance_score': 0.0,
            'score_a': None,
            'score_b': None,
            'score_c': None,
            'relevance_basis': '',
            'link_source': ProductProtocol.LinkSource.INHERITED,
            'tier': ProductProtocol.Tier.WEAK,
            'literature_count': 0,
            'chem_specific': chem,
        }

    if pp_rows:
        rows = [_row(pp.protocol_id, pp.protocol, pp) for pp in pp_rows]
    else:
        # fallback：MethodProtocol 桥派生协议
        method_ids = list(
            ProductMethod.objects.filter(product=product).values_list('method_id', flat=True)
        )
        protocol_ids = list(
            MethodProtocol.objects.filter(method_id__in=method_ids)
            .values_list('protocol_id', flat=True).distinct()
        )
        if not protocol_ids:
            return []
        proto_map = {p.id: p for p in Protocol.objects.filter(id__in=protocol_ids)}
        rows = [_row(pid, proto_map.get(pid), None) for pid in protocol_ids]

    rows.sort(key=protocol_link_sort_key)
    return rows


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
    """加载产品级文献缓存（Bioz + PubMed，用于轴B 协议级对齐）。

    修复 #473-B2：原实现从 apps.knowledge.models 导入 DataSourceCache（模型实属
    apps.documents.models）致 ImportError 被吞、永远返回 []；且 filter 用不存在的
    resolved_catalog 列、取 r.payload（真实是 get_data()）。三处缺陷叠加使轴B 文献轴
    全库恒为 0（literature 档从未触发）。

    2026-08-19 固化：并入 PubMed 证据源——按产品的可解析键（catalog_no + 关联
    SKU.sku_code）同时查询 bioz 与 pubmed 缓存（同键），PubMed 条目（title 结构）
    转成 Bioz 兼容结构（article_title/long/medium/short）合并返回，使 S_B 获得
    多源文献证据（Bioz 26 产品 + PubMed 68 产品 → 78 产品，weak 降 12%）。

    任何异常均安全降级 []（轴B 退化为 0，不阻断 recompute）。
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
        # PubMed 文献并入（title 结构 → Bioz 兼容结构）
        p_rows = DataSourceCache.objects.filter(source='pubmed', query_key__in=keys)
        for r in p_rows:
            data = r.get_data()
            if not isinstance(data, list):
                continue
            for d in data:
                if not isinstance(d, dict):
                    continue
                title = (d.get('title') or '').strip()
                if not title:
                    continue
                out.append({
                    'article_title': title,
                    'techniques': '',
                    'long': title,
                    'medium': '',
                    'short': '',
                    '_source': 'pubmed',
                })
        return out
    except Exception:
        return []


def recompute_product(product, embedding_fn=None):
    """为单个产品重算并落/更新 ProductProtocol 行（幂等 upsert）。

    派生协议集取自产品的 MethodProtocol 链路（铁律①全量保留，不丢）。
    返回写入/更新的协议数。

    ★ 2026-09-24 R2 —— **轴C 的写权独占给"能真正算出 embedding"的路径**：
      仅当 `embedding_fn` 被注入（离线作业）**或**本机后端 `embedding_available()`
      为真时，才计算并写 `score_c`；否则**保留库中现值**（无则留 NULL，等离线作业补算）。
      ❌ 绝不在运行时写 embedding 哨兵 0.5 —— 生产容器无 `sentence_transformers`，
         `compute_axis_c` 恒返 0.5，旧代码会把每次产品保存变成"抹平该产品离线算好的 score_c"。
    """
    from apps.bridges.models import (
        ProductMethod, MethodProtocol, ProductProtocol,
    )
    from apps.knowledge.models import Protocol
    from .embedding_backend import embedding_available

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

    # 轴C 可算性：离线注入优先，其次探测本机后端（结果缓存）
    compute_c = (embedding_fn is not None) or embedding_available()
    # 库中现值（保留用）—— 一次查询拿全，避免 N+1
    existing_c = dict(
        ProductProtocol.objects.filter(product=product).values_list('protocol_id', 'score_c')
    )

    # ★ 2026-09-22 修 **B8**（两段式，关键）：
    #   原先**每个协议一次 `update_or_create`** ⇒ 一次独立事务提交 = N+1 写入 × N 次提交。
    #   cProfile 实测（SC8075，268 个协议）：`commit` 累计 **7.76s / 共 9.21s（97%）**。
    #   教训（第一版改错）：**不能把整个循环直接包进 `atomic()`** —— 那样会把 268 个协议的
    #   CPU 计算（轴 A/B/C + 嵌入）也关进事务，**写锁被连续持有**；而本地 dev 的 E2E 快照助手
    #   是独立进程在读同一个 SQLite ⇒ 实测立刻出现 `database is locked` ⇒ create 500 + worker 挂死。
    #   ⇒ 正解：**CPU 在事务外算好，事务里只做写入**（锁只覆盖写入，不覆盖计算）。
    rows = []
    for pid in protocol_ids:
        protocol = Protocol.objects.filter(id=pid).first()
        if protocol is None:
            continue
        s_a = compute_axis_a(product, protocol)
        s_b, lit_n = compute_axis_b(product, protocol, bioz_lits=bioz_lits)
        if compute_c:
            s_c = compute_axis_c(product, protocol, embedding_fn=embedding_fn)
        else:
            s_c = existing_c.get(pid)   # ★ 保留现值（可能为 None）；绝不写哨兵
        fused = fuse_relevance(score_a=s_a, score_b=s_b, score_c=s_c)
        if is_evidence_free(fused):
            continue          # ★ 低分不落库：零证据的协议不写行
        rows.append((protocol, fused, lit_n, s_c))

    n = 0
    with transaction.atomic():                      # 只包写入 ⇒ 提交从 268 次降到 1 次
        for protocol, fused, lit_n, s_c in rows:
            defaults = {
                'relevance_score': fused['relevance_score'],
                'score_a': fused['score_a'],
                'score_b': fused['score_b'],
                'literature_count': lit_n,
                'relevance_basis': fused['relevance_basis'],
                'tier': fused['tier'],
                'link_source': ProductProtocol.LinkSource.INHERITED,
            }
            if compute_c:
                defaults['score_c'] = s_c    # ★ 仅"能算出"时才写；否则保留库中现值
            ProductProtocol.objects.update_or_create(
                product=product, protocol=protocol,
                defaults=defaults,
            )
            n += 1
    update_product_aggregate(product)  # S5：写完该商品 PP 行后刷新商品级聚合分
    return n
