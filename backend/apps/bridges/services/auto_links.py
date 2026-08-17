"""AUTO 链接重算服务（S3 正规化：原游离脚本 _land_recompute_auto.py 的正式落位）。

对每个产品，从候选协议标题池中按三轴融合分取 Top-N，落 ProductProtocol
(link_source=AUTO)。与 relevance 生产算法同源（content 级）：

  S_A = relevance.compute_axis_a 语义（Q 取 _protocol_q_text）
  S_B = relevance.compute_axis_b 语义（协议级对齐，非产品级均摊）
  S_C = 协议向量 encode(name+objective+summary+purpose) 与 encode(product.usage)
        的余弦 → (cos+1)/2

行为契约（与游离脚本零漂移）：
  - 已在 INHERITED/EXPLICIT 链中的协议跳过，绝不覆盖继承行（铁律①）
  - 幂等：落库前先删本产品旧 AUTO 行，再 upsert 新 Top-N
  - literature_count 写协议级真实 lit_n

嵌入模型经 embedding_backend 惰性加载（路径由 EMB3_VENV 环境变量 /
settings.EMB3_VENV_PATH 决定，本模块不作任何路径假设）；测试可注入 model。
"""
import json
import random
import time

import numpy as np

from apps.bridges.models import ProductProtocol as PP, ProductMethod, MethodProtocol
from apps.bridges.services import relevance as REL
from apps.commerce.models import Product
from apps.knowledge.models import Protocol, Method

DEFAULT_CANDIDATES_PATH = '._candidates.json'
DEFAULT_TOPN = 20
DEFAULT_ENCODE_BATCH = 64
VERIFY_SAMPLE_RATE = 0.05
VERIFY_MAX_PAIRS = 30
# 轴A/B 为纯 Python 复算，容差取机器精度级；轴C 涉及批量 vs 单条 encode，放宽到 1e-6
TOL_EXACT = 1e-9
TOL_EMBED = 1e-6


def load_candidates(path=DEFAULT_CANDIDATES_PATH):
    """读取候选池 {catalog_no: [protocol_title, ...]}。"""
    with open(path, encoding='utf-8') as f:
        return json.load(f)


def _protocol_embedding_text(protocol):
    """严格复刻 embedding_backend._protocol_embedding 的拼接口径。"""
    return " ".join([
        getattr(protocol, 'name', '') or '',
        getattr(protocol, 'objective', '') or '',
        getattr(protocol, 'summary', '') or '',
        getattr(protocol, 'purpose', '') or '',
    ])


def _axis_a(P, Q):
    """复刻 relevance.compute_axis_a：无 P → None；无 Q → 0.0。"""
    if not P:
        return None
    if not Q:
        return 0.0
    inter = P & Q
    return 0.5 * (len(inter) / len(P)) + 0.5 * (len(inter) / len(Q))


def _make_embedding_fn(model):
    """给 VERIFY 用的逐对 embedding_fn：独立重新 encode，构成真实交叉校验。"""
    def fn(product, protocol):
        usage = getattr(product, 'usage', None) or ''
        if not usage:
            return 0.0
        u = np.asarray(model.encode(usage, normalize_embeddings=True), dtype=np.float32)
        v = np.asarray(
            model.encode(_protocol_embedding_text(protocol), normalize_embeddings=True),
            dtype=np.float32,
        )
        return float(np.clip(u @ v, -1.0, 1.0))
    return fn


def recompute_auto_links(candidates, *, topn=DEFAULT_TOPN,
                         encode_batch=DEFAULT_ENCODE_BATCH, model=None,
                         verify=False, verify_sample_rate=VERIFY_SAMPLE_RATE,
                         verify_max_pairs=VERIFY_MAX_PAIRS, dry_run=False,
                         log=None, seed=None):
    """按候选池重算 AUTO 链接。返回统计 dict。

    candidates: {catalog_no: [protocol_title, ...]}
    model:      鸭子类型 .encode(texts, batch_size=, normalize_embeddings=, show_progress_bar=)
                缺省惰性加载生产模型
    """
    t0 = time.time()

    def _log(msg):
        if log:
            log(f"[{time.time() - t0:7.1f}s] {msg}")

    if seed is not None:
        random.seed(seed)

    if model is None:
        from apps.bridges.services import embedding_backend as EMB
        model = EMB._get_model()
        _log("embedding model loaded")

    cand_titles = sorted({
        t.strip() for ts in candidates.values() for t in (ts or []) if t and t.strip()
    })
    _log(f"candidates: {len(candidates)} products / {len(cand_titles)} unique titles")

    # ---------- 协议对象（按 name 索引） ----------
    protos = {}
    for p in Protocol.objects.all().only(
        'id', 'name', 'objective', 'principle', 'materials',
        'reagents', 'expected_results', 'references',
    ):
        protos[(p.name or '').strip()] = p

    used = [protos[t] for t in cand_titles if t in protos]
    _log(f"candidate titles with Protocol row = {len(used)} / {len(cand_titles)}")

    stats = {
        'products': 0, 'written': 0, 'skipped_linked': 0,
        'candidates': len(candidates), 'unique_titles': len(cand_titles),
        'matched_protocols': len(used), 'verified': 0, 'mismatches': 0,
        'dry_run': bool(dry_run),
        # {catalog_no: [protocol_id 按融合分降序]} —— 供 dry-run 平价核对与审计
        'selection': {},
    }
    if not used:
        stats['auto_total'] = PP.objects.filter(link_source=PP.LinkSource.AUTO).count()
        return stats

    # ---------- 协议侧领域词 Q（content 级） ----------
    REL._load_vocab()
    proto_Q = {p.id: REL._extract_domains(REL._protocol_q_text(p)) for p in used}

    # ---------- 协议 embedding（批量） ----------
    proto_mat = np.asarray(
        model.encode(
            [_protocol_embedding_text(p) for p in used],
            batch_size=encode_batch, normalize_embeddings=True,
            show_progress_bar=False,
        ),
        dtype=np.float32,
    )
    row_of = {p.id: i for i, p in enumerate(used)}
    _log(f"protocol embeddings: {proto_mat.shape}")

    # ---------- 产品 ----------
    products = {
        p.catalog_no: p
        for p in Product.objects.filter(catalog_no__in=list(candidates.keys()))
    }
    catalogs = [c for c in candidates.keys() if c in products]
    _log(f"products in DB = {len(products)} / {len(candidates)}")

    prod_vec = {}
    for cat in catalogs:
        usage = getattr(products[cat], 'usage', None) or ''
        if usage:
            prod_vec[cat] = np.asarray(
                model.encode(usage, normalize_embeddings=True), dtype=np.float32)

    verify_pairs = []

    for idx, cat in enumerate(catalogs):
        prod = products[cat]
        valid = []
        for t in (candidates[cat] or []):
            t = (t or '').strip()
            p = protos.get(t)
            if p is None or p.id not in row_of:
                continue
            valid.append(p)
        if not valid:
            continue
        stats['products'] += 1

        usage = getattr(prod, 'usage', None) or ''
        P = REL._extract_domains(usage) if usage else set()

        # --- 轴A ---
        s_a = [_axis_a(P, proto_Q[p.id]) for p in valid]

        # --- 轴B（协议级对齐） ---
        bioz_lits = REL.load_product_bioz(prod)
        lit_doms = []
        for lit in bioz_lits:
            lit_doms.append(REL._extract_domains(' '.join([
                lit.get('article_title', '') or '', lit.get('techniques', '') or '',
                lit.get('long', '') or '', lit.get('medium', '') or '',
                lit.get('short', '') or '',
            ])))
        s_b, lit_ns = [], []
        for p in valid:
            Q = proto_Q[p.id]
            if not lit_doms or not Q:
                s_b.append(0.0)
                lit_ns.append(0)
                continue
            n = sum(1 for bd in lit_doms if bd & Q)
            s_b.append(min(1.0, n / REL.BIOZ_TYP_CAP))
            lit_ns.append(n)

        # --- 轴C ---
        uv = prod_vec.get(cat)
        if uv is None:
            s_c = np.zeros(len(valid), dtype=np.float64)
        else:
            rows = np.array([row_of[p.id] for p in valid], dtype=np.int64)
            cos = proto_mat[rows] @ uv
            s_c = (np.clip(cos, -1.0, 1.0).astype(np.float64) + 1.0) / 2.0

        fused_scores = np.array([
            REL.WEIGHTS['a'] * (s_a[i] if s_a[i] is not None else 0.0)
            + REL.WEIGHTS['b'] * s_b[i]
            + REL.WEIGHTS['c'] * s_c[i]
            for i in range(len(valid))
        ])

        linked = set(PP.objects.filter(
            product=prod,
            link_source__in=[PP.LinkSource.INHERITED, PP.LinkSource.EXPLICIT],
        ).values_list('protocol_id', flat=True))

        if not dry_run:
            PP.objects.filter(product=prod, link_source=PP.LinkSource.AUTO).delete()

        order = np.argsort(-fused_scores)[:topn]
        n_written = 0
        picked = []
        for i in order:
            p = valid[i]
            if p.id in linked:
                stats['skipped_linked'] += 1
                continue
            picked.append(p.id)
            fd = REL.fuse_relevance(
                score_a=s_a[i], score_b=float(s_b[i]), score_c=float(s_c[i]))
            if not dry_run:
                PP.objects.update_or_create(
                    product=prod, protocol_id=p.id,
                    defaults={
                        'relevance_score': fd['relevance_score'],
                        'score_a': fd['score_a'],
                        'score_b': fd['score_b'],
                        'score_c': fd['score_c'],
                        'literature_count': lit_ns[i],
                        'relevance_basis': fd['relevance_basis'],
                        'tier': fd['tier'],
                        'link_source': PP.LinkSource.AUTO,
                    },
                )
            n_written += 1
            if (verify and len(verify_pairs) < verify_max_pairs
                    and random.random() < verify_sample_rate):
                verify_pairs.append(
                    (prod, p, s_a[i], float(s_b[i]), lit_ns[i], float(s_c[i])))
        stats['written'] += n_written
        if not dry_run:
            # S5：写完该商品 AUTO 行后刷新商品级聚合分（含其 INHERITED/EXPLICIT 行）
            REL.update_product_aggregate(prod)
        stats['selection'][cat] = picked
        if (idx + 1) % 20 == 0 or idx == 0:
            _log(f"  [{idx+1}/{len(catalogs)}] {cat}: {n_written} AUTO "
                 f"(cands={len(valid)}, usage={'Y' if usage else 'N'}, "
                 f"bioz={len(lit_doms)})")

    # ---------- 等价性自检 ----------
    if verify and verify_pairs:
        emb_fn = _make_embedding_fn(model)
        _log(f"VERIFY: 抽样 {len(verify_pairs)} 对，与 relevance 生产函数逐一比对 ...")
        for prod, proto, va, vb, vlit, vc in verify_pairs:
            ga = REL.compute_axis_a(prod, proto)
            gb, glit = REL.compute_axis_b(
                prod, proto, bioz_lits=REL.load_product_bioz(prod))
            gc = REL.compute_axis_c(prod, proto, embedding_fn=emb_fn)
            ok = (
                ((ga is None and va is None)
                 or (ga is not None and va is not None and abs(ga - va) < TOL_EXACT))
                and abs(gb - vb) < TOL_EXACT and glit == vlit
                and abs(gc - vc) < TOL_EMBED
            )
            stats['verified'] += 1
            if not ok:
                stats['mismatches'] += 1
                _log(f"  MISMATCH {prod.catalog_no} × P{proto.id}: "
                     f"a {va} vs {ga} | b {vb}/{vlit} vs {gb}/{glit} | c {vc} vs {gc}")

    stats['auto_total'] = PP.objects.filter(link_source=PP.LinkSource.AUTO).count()
    _log(f"TOTAL AUTO written = {stats['written']}; "
         f"skipped(inherited) = {stats['skipped_linked']}; "
         f"AUTO rows in DB = {stats['auto_total']}")
    return stats


# ─────────────────────────────────────────────────────────────────────────────
# R1：enrich 预览协议/方法推荐改走 auto_links 真 relevance（与正式 auto-link 同源）
# ─────────────────────────────────────────────────────────────────────────────
_PROTO_Q_CACHE = None


def _get_proto_q_cache():
    """协议侧领域词 Q 集合缓存：首次调用时对所有协议预计算，之后复用。"""
    global _PROTO_Q_CACHE
    if _PROTO_Q_CACHE is None:
        REL._load_vocab()
        cache = {}
        for p in Protocol.objects.all().only(
            'id', 'name', 'objective', 'principle', 'materials',
            'reagents', 'expected_results', 'references',
        ):
            cache[p.id] = REL._extract_domains(REL._protocol_q_text(p))
        _PROTO_Q_CACHE = cache
    return _PROTO_Q_CACHE


def _serialize_pp(pp):
    """把一条落库 ProductProtocol 行序列化为 enrich 预览协议 dict（带真实三轴分）。"""
    p = pp.protocol
    return {
        'id': p.id,
        'source': 'auto_links',
        'title': p.name,
        'abstract': getattr(p, 'objective', '') or '',
        'url': '',
        'score': pp.relevance_score or 0.0,
        'score_a': pp.score_a,
        'score_b': pp.score_b,
        'score_c': pp.score_c,
        'relevance_score': pp.relevance_score,
        'tier': pp.tier,
        'link_source': pp.link_source,
        'relevance_basis': pp.relevance_basis,
        'literature_count': pp.literature_count,
        'method_hint': '',
        'matched_query': '',
        'steps': [],
    }


def recommend_protocols_for_enrich(product_name, product_pk=None, top_k=10):
    """R1 核心：为 enrich 预览返回真实 auto_links 相关协议。

    - 已有商品(product_pk 有效)：直接返回其落库的真实 ProductProtocol 行
      (AUTO/INHERITED/EXPLICIT)，带真实 S_A/S_B/S_C 与 tier —— 与正式 auto-link
      同源，即 SC8058 实证合法的那类（带分、可归因、文档相关）。零新计算。
    - 草稿(无 product_pk)：以 product_name 为伪 usage，在协议语料上算 S_A（领域词
      F-score）+ S_B（名能解析出货号则有 bioz），S_C 暂为 0（草稿无 embedding 上下文，
      避免每次请求加载 14k 协议向量）。返回 Top-K 真实分。

    返回协议 dict 列表，字段向后兼容 enrich 预览（id/source/title/abstract/score
    等）+ 真实三轴分（score_a/score_b/score_c/relevance_score/tier/link_source）。
    """
    if product_pk:
        try:
            prod = Product.objects.get(pk=product_pk)
        except (Product.DoesNotExist, ValueError, TypeError):
            prod = None
        if prod is not None:
            rows = (PP.objects
                    .filter(product=prod,
                            link_source__in=[PP.LinkSource.AUTO,
                                             PP.LinkSource.INHERITED,
                                             PP.LinkSource.EXPLICIT])
                    .select_related('protocol')
                    .order_by('-relevance_score', '-score_c', 'id')[:top_k])
            return [_serialize_pp(pp) for pp in rows]

    # 草稿 → S_A/S_B 实时排序（无嵌入，S_C=0）
    REL._load_vocab()
    P = REL._extract_domains(product_name or '')
    if not P:
        return []
    proto_q = _get_proto_q_cache()
    scored = []
    for pid, Q in proto_q.items():
        if not Q:
            continue
        inter = P & Q
        if not inter:
            continue
        coverage = len(inter) / len(P)
        precision = len(inter) / len(Q)
        s_a = 0.5 * coverage + 0.5 * precision
        fused = REL.fuse_relevance(score_a=s_a, score_b=0.0, score_c=0.0)
        scored.append((s_a, fused, pid))
    scored.sort(key=lambda x: (-x[0], x[2]))
    out = []
    for s_a, fused, pid in scored[:top_k]:
        p = Protocol.objects.filter(id=pid).only('id', 'name', 'objective').first()
        if not p:
            continue
        out.append({
            'id': p.id,
            'source': 'auto_links',
            'title': p.name,
            'abstract': getattr(p, 'objective', '') or '',
            'url': '',
            'score': fused['relevance_score'],
            'score_a': fused['score_a'],
            'score_b': fused['score_b'],
            'score_c': fused['score_c'],
            'relevance_score': fused['relevance_score'],
            'tier': fused['tier'],
            'link_source': 'auto',
            'relevance_basis': fused['relevance_basis'],
            'literature_count': 0,
            'method_hint': '',
            'matched_query': '',
            'steps': [],
        })
    return out


def recommend_methods_for_enrich(product_name, product_pk=None, top_k=10):
    """R1：enrich 预览方法推荐改走 auto_links 图（取代 LiteratureRecommender 关键词子串命中）。

    - 已有商品：返回其已链方法（ProductMethod → Method），真实、可归因。
    - 草稿：从 Top-K 协议经 MethodProtocol 桥派生方法（真实图关联，非关键词巧合）。

    返回 enrich 预览期望的 matched_methods 形状：[{keyword, matches:[{id,name,...}]}]。
    """
    method_ids = []
    if product_pk:
        try:
            prod = Product.objects.get(pk=product_pk)
        except (Product.DoesNotExist, ValueError, TypeError):
            prod = None
        if prod is not None:
            method_ids = list(ProductMethod.objects.filter(product=prod)
                              .values_list('method_id', flat=True))
    if not method_ids:
        protos = recommend_protocols_for_enrich(
            product_name or "", product_pk=product_pk, top_k=top_k)
        pids = [p['id'] for p in protos]
        if pids:
            method_ids = list(MethodProtocol.objects
                              .filter(protocol_id__in=pids)
                              .values_list('method_id', flat=True).distinct())
    if not method_ids:
        return []
    methods = Method.objects.filter(id__in=method_ids).values(
        'id', 'name', 'slug', 'application_id')[:top_k]
    return [{'keyword': 'auto_links', 'matches': list(methods)}]
