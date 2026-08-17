"""外部 objective 抽取与最佳匹配选择（A 类补全）。

背景：98 个 Protocol.objective 为空（95 curated + 3 bioprocorpus）。
本模块提供纯函数，供 fetch_external_objectives 命令复用，并便于单测：

- extract_objective(abstract, max_chars): 从论文摘要抽取「目标」句
- title_similarity(a, b): difflib 标题相似度
- choose_best_match(protocol_name, pubmed, bio): 两源取最匹配一条

匹配铁律（AUTO MATCH 十铁律①「宁 miss 不错配」）：
- 仅当标题相似度 ≥ 阈值才采纳，避免把 A 文摘要错写进 B 协议
- 两源都试，取相似度高的一条写入（用户决策：Bio-protocol + PubMed 都试取最匹配）
"""
import difflib
import re

# 采纳门槛：协议名「显著 token 在候选标题中的覆盖率」低于此值视为不匹配 → 跳过。
# 用 token 覆盖率而非 difflib.ratio：方法型协议名（如 "Micro-C XL"）与同名方法论文
# 标题（"Mammalian Micro-C-XL."）长度差异大、ratio 偏低，但 token 覆盖率高、确为同方法。
# 门槛取 0.65 而非 0.50：实测 dry-run 中 id=136「Xenium Spatial Transcriptomics
# Protocol for Human Kidney」因方法名 Xenium/SPATIAL/TRANSCRIPTOMICS 命中一篇
# 「hippocampus in mice with temporal lobe epilepsy」文章得 sim=0.60（器官/疾病主题
# 完全错配），属「宁 miss 不错配」须拒。所有真匹配 sim 均 ≥ 0.67，0.65 恰好隔离此
# 1 个假匹配且不影响其余 18 个真匹配与 79 个本就 <0.50 的跳过项。
PUBMED_THRESHOLD = 0.65
BIOPROTOCOL_THRESHOLD = 0.50
# Europe PMC 采纳门槛：口径与 PubMed 完全一致（同一 token_similarity 函数），
# 故初值取同一 0.65；单列常量是为了将来能独立调参 —— 2026-08-08 探针实测 EPMC
# 自动门放行的 7 条里有 4 条错配（57%，高于 PubMed 批的 33%），因为它额外覆盖
# preprint，召回高的同时噪声也大。当前不下调阈值（无证据支撑具体新值），
# 错配防线仍由「人工复核 --allowlist 白名单」承担。
EUROPEPMC_THRESHOLD = 0.65
# 语义相似度门槛（MiniLM all-MiniLM-L6-v2 cosine）：用于「token 覆盖率 < PUBMED_THRESHOLD
# 但有正确文本」的边界项二次判定。实测对 80 空协议的 60 个边界候选逐条人工复核：
# 真匹配（同名方法、措辞不同）语义 ∈ [0.62, 0.74]；假匹配（主题相关但方法不同 / 器官错配）
# 语义 ∈ [0.07, 0.61]。分界点精确在 0.62 —— 故定 0.62 干净隔离 10 个真匹配、拒 9 个假匹配
# （含 id=136 Xenium-kidney，其抽取 objective 正文竟是「颞叶癫痫」，确为假匹配）。
# 语义分由独立 emb3_venv 进程预计算（backend py3.13 装不了 sentence-transformers），命令经
# --semantic-report 读取 {id: semantic_sim} 注入本门槛，绝不触发 backend 内模型加载。
SEMANTIC_THRESHOLD = 0.62
# objective 文本上限（保持「目标」语义，而非整段摘要）
OBJECTIVE_MAX_CHARS = 600
# objective 最低长度：过短（<12）多为无意义的碎片/期刊行，视为 junk 跳过；
# 正常目标句一般 ≥12。纯引用行（"12. J Mol Biol."）与全大写刊名另由 _JUNK_RE 拦截。
MIN_OBJECTIVE_CHARS = 12
# junk 模式：纯引用行（"12. J Mol Biol."）/ 全大写刊名
_JUNK_RE = re.compile(r'^(\d+\.\s*[A-Z][\w\s.&()-]*\.?|[\sA-Z0-9.,&()-]+)$')

# 摘要结构化小節标题（用于切分边界）
_SECTION_RE = re.compile(
    r'\b(BACKGROUND|OBJECTIVE|OBJECTIVES|AIM|AIMS|PURPOSE|RATIONALE|'
    r'INTRODUCTION|METHODS|METHOD|RESULTS|CONCLUSIONS|MATERIALS AND METHODS)\b\s*[:\-]',
    re.I,
)
# 各节优先级（去重标签）
_OBJECTIVE_LABELS = ('OBJECTIVE', 'OBJECTIVES')
_GOAL_LABELS = ('AIM', 'AIMS', 'PURPOSE', 'RATIONALE')
_SECONDARY_LABELS = ('BACKGROUND', 'INTRODUCTION')
# 散句层面的目标关键词
_GOAL_RE = re.compile(
    r'(?i)\b(objective|aim|purpose|the goal|we sought|we aimed|this study (aims|seeks|'
    r'investigates|describes|presents)|we developed|we present|we designed|here we)\b',
)


def title_similarity(a: str, b: str) -> float:
    """标题相似度（0~1），difflib ratio。空串返回 0。"""
    a = (a or '').strip()
    b = (b or '').strip()
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


# 通用停用词：方法型协议名里的高频泛词，不参与「显著 token」判定
_STOP = {
    'protocol', 'method', 'methods', 'assay', 'assays', 'experiment', 'experiments',
    'cell', 'cells', 'rna', 'dna', 'high', 'throughput', 'low', 'single',
    'using', 'based', 'with', 'for', 'and', 'the', 'of', 'in', 'on', 'to', 'a',
}


def _tokens(s: str):
    return [t for t in re.findall(r'[a-z0-9]+', (s or '').lower()) if len(t) >= 3]


def _method_tokens(name: str):
    """提取协议名中的「方法 token」（最具区分度的缩写/复合词）。

    判定：含数字 / 全大写 / 含连字符 / CamelCase。停用词与过短词排除。
    例：「BARseq - high-throughput cell typing」→ ['barseq']；
        「Micro-C XL」→ ['micro-c', 'xl']；「HCR - Embryo」→ ['hcr']。
    """
    toks = re.findall(r'[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*', (name or ''))
    out = []
    for t in toks:
        tl = t.lower()
        if tl in _STOP or len(tl) < 2:
            continue
        distinctive = (
            any(ch.isdigit() for ch in t)
            or t.isupper()
            or '-' in t
            or (t[0].isupper() and any(c.islower() for c in t[1:]))
        )
        if distinctive:
            out.append(tl)
    return out


def token_similarity(a: str, b: str) -> float:
    """协议名显著 token 在候选标题中的覆盖率（0~1）。

    覆盖率 = |a 的显著 token ∩ b 的 token| / |a 的显著 token|。
    显著 token = 长度≥3 且非停用词。空串返回 0。
    例：「Micro-C XL」→ {micro, xl} 覆盖于「Mammalian Micro-C-XL.」→ 1.0。
    """
    ta = set(t for t in _tokens(a) if t not in _STOP)
    tb = set(_tokens(b))
    if not ta:
        return 0.0
    return len(ta & tb) / len(ta)


def method_match(name: str, title: str) -> float:
    """方法 token 命中率（0~1）：协议名的方法 token 出现在文章标题的比例。

    用于捕获「全名覆盖率低、但方法缩写命中」的情况：如
    「BARseq - high-throughput...」全名覆盖率仅 0.2，但其方法 token 'barseq'
    出现在文章标题 → method_match=1.0 → 采纳。无方法 token 返回 0。
    """
    mts = _method_tokens(name)
    if not mts:
        return 0.0
    tb = set(_tokens(title))
    hit = sum(1 for m in mts if m in tb)
    return hit / len(mts)


def _cap(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    if ' ' in cut:
        cut = cut[: cut.rfind(' ')]
    return cut.rstrip() + '…'


def _first_sentences(text: str, n: int) -> str:
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    return ' '.join(sents[:n]).strip()


def extract_objective(abstract: str, max_chars: int = OBJECTIVE_MAX_CHARS) -> str:
    """从摘要抽取 objective 文本。

    优先级：
      1) 结构化小節 OBJECTIVE/OBJECTIVES → 取该节全文
      2) 结构化小節 AIM/PURPOSE/RATIONALE → 取该节首句
      3) 结构化小節 BACKGROUND/INTRODUCTION → 取前两句（兜底语义）
      4) 散句中含目标关键词（objective/aim/we sought/...）→ 取该句
      5) 兜底：取前 1~2 句作为概述
    空摘要返回 ''；过短/纯引用行（junk）返回 ''（调用方据此跳过，宁 miss 不错配）。
    """
    if not abstract:
        return ''
    text = re.sub(r'\s+', ' ', abstract).strip()
    if not text:
        return ''
    text = _strip_leading_citation(text)
    obj = _extract_body(text, max_chars)
    # 抽取出的句子可能仍以悬挂引用片段开头（如 'Nat Methods 10:1096-1098, 2013), we developed'），
    # 需再次清洗（抽取前只在整段层面洗过一次）。
    obj = _strip_leading_citation(obj)
    if len(obj) < MIN_OBJECTIVE_CHARS or _JUNK_RE.match(obj):
        return ''
    return obj


_STRIP_CITATION_RE = re.compile(
    # 期刊/文献引用签名： "Nat Methods 10:1096-1098, 2013), " 或
    # "Hahaut V et al. (Nat Methods 10:1096-1098, 2013), "（括号在字符类内）。
    # 关键锚点 \d+:\d+（卷:页），使普通以年份开头的句子（无卷期）不被误删。
    r"^\s*[A-Z][\w\s.,:&()/-]*?\d+:\d+[^\n]*?\b(1[89]|20)\d{2}\b\s*[),]+\s*",
    re.S,
)


def _strip_leading_citation(text: str) -> str:
    """去掉摘要/抽取句开头常见的文献引用片段，如：

    - 'Nat Methods 10:1096-1098, 2013), we developed…'（悬挂引用）
    - 'Hahaut V et al. (Nat Methods 10:1096-1098, 2013), we developed…'（作者+文献）

    这类片段来自结构化摘要/书籍章节的卷期年或作者署名，不应作为 objective 开头。
    以「卷:页 + 年份」为锚点（开头匹配 卷:页 后跟 19xx/20xx），仅在开头匹配，
    不误伤句中/普通以年份开头的句子。
    """
    return _STRIP_CITATION_RE.sub('', text).strip()


def _extract_body(text: str, max_chars: int) -> str:
    """抽取主体（不含 junk 判定）。"""
    # 结构化小節切分：parts = [pre, header1, body1, header2, body2, ...]
    parts = _SECTION_RE.split(text)

    def _section_body(i):
        return parts[i + 1].strip() if i + 1 < len(parts) else ''

    # 1) OBJECTIVE 节（全文）
    for i in range(1, len(parts), 2):
        header = (parts[i] or '').upper()
        body = _section_body(i)
        if body and any(k in header for k in _OBJECTIVE_LABELS):
            return _cap(body, max_chars)
    # 2) AIM/PURPOSE/RATIONALE 节（首句）
    for i in range(1, len(parts), 2):
        header = (parts[i] or '').upper()
        body = _section_body(i)
        if body and any(k in header for k in _GOAL_LABELS):
            return _cap(_first_sentences(body, 1) or body, max_chars)
    # 3) BACKGROUND/INTRODUCTION 节（前两句）
    for i in range(1, len(parts), 2):
        header = (parts[i] or '').upper()
        body = _section_body(i)
        if body and any(k in header for k in _SECONDARY_LABELS):
            return _cap(_first_sentences(body, 2) or body, max_chars)

    # 4) 散句关键词
    sentences = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if s.strip()]
    for s in sentences:
        if _GOAL_RE.search(s):
            return _cap(s, max_chars)

    # 5) 兜底：前两句
    if sentences:
        return _cap(' '.join(sentences[:2]), max_chars)
    return _cap(text, max_chars)


def _norm_src_title(entry: dict, default: str) -> str:
    return (entry or {}).get('source_title') or (entry or {}).get('title') or default


def reference_tag(source_label: str, source_ref: str) -> str:
    """把来源标识规整成 Protocol.references 里的归因 tag。

    为什么需要：PubMed 候选的 source_ref 恒为 PMID（纯数字），但 Europe PMC 的
    PPR（预印本）源没有 PMID，只有 DOI —— 若沿用旧的「统一加 PMID: 前缀」逻辑，
    会写出 'PMID:10.21203/rs.3.pex-1840/v1' 这种错误归因。

    规则：纯数字 → PMID:；10./doi: 开头 → DOI:；PMC 开头 → PMCID:；
    bioprotocol（URL）原样保留；空值返回空串。
    """
    ref = (source_ref or '').strip()
    if not ref:
        return ''
    if source_label == 'bioprotocol':
        return ref  # Bio-protocol 归因是 URL，原样写入
    if re.fullmatch(r'\d+', ref):
        return f'PMID:{ref}'
    if ref.lower().startswith('doi:'):
        return 'DOI:' + re.sub(r'^doi:\s*', '', ref, flags=re.I)
    if ref.startswith('10.'):
        return f'DOI:{ref}'
    if ref.upper().startswith('PMC'):
        return f'PMCID:{ref}'
    return ref


# 择优排序时的同分优先级：pubmed > europepmc > bioprotocol
# （pubmed 最权威可归因；europepmc 次之且含 DOI；bioprotocol 为离线 overrides）
_SOURCE_RANK = {'pubmed': 2, 'europepmc': 1, 'bioprotocol': 0}


def choose_best_match(protocol_name: str, pubmed: dict | None, bio: dict | None,
                      epmc: dict | None = None):
    """多源候选取最匹配一条。

    pubmed: {"objective","pmid","article_title","similarity"} | None
    bio:    {"objective","url","source_title","similarity"} | None
    epmc:   {"objective","source_ref","article_title","similarity"} | None
    返回 (objective, source_label, source_ref, similarity) 或 None（皆空/低于门槛）。
    epmc 为关键字可选参数，保持既有两源调用方式向后兼容。
    """
    candidates = []
    if pubmed and pubmed.get('objective'):
        candidates.append((
            pubmed['objective'], 'pubmed',
            pubmed.get('pmid') or '', pubmed.get('similarity', 0.0),
        ))
    if epmc and epmc.get('objective'):
        candidates.append((
            epmc['objective'], 'europepmc',
            epmc.get('source_ref') or epmc.get('pmid') or epmc.get('doi') or '',
            epmc.get('similarity', 0.0),
        ))
    if bio and bio.get('objective'):
        candidates.append((
            bio['objective'], 'bioprotocol',
            bio.get('url') or '', bio.get('similarity', 0.0),
        ))
    if not candidates:
        return None
    # 相似度高者优先；同分按来源权威度（pubmed > europepmc > bioprotocol）
    candidates.sort(key=lambda c: (c[3], _SOURCE_RANK.get(c[1], -1)), reverse=True)
    return candidates[0]


def _radioactive_conflict(protocol_name: str, title: str, abstract: str) -> bool:
    """放射性 / 非放射性 语义相反守卫（PubMed 与 Europe PMC 两路共用）。

    典型错配（id=178）：协议名 'Radioactive in vitro transcription'，命中的文章
    却是「非放射性替代法」—— 主题词高度重叠但结论相反，属必须拒的错配。

    注意 rad_name 要排除 nonrad_name：'non-radioactive' 里也含子串 'radioactive'，
    不排除的话「非放射性协议命中非放射性文章」这种正确匹配会被误判为矛盾而拒掉。
    """
    nl = (protocol_name or '').lower()
    combined = ((title or '') + ' ' + (abstract or '')).lower()
    nonrad_name = 'non-radioactive' in nl or 'nonradioactive' in nl
    rad_name = 'radioactive' in nl and not nonrad_name
    nonrad_art = 'non-radioactive' in combined or 'nonradioactive' in combined
    if rad_name and nonrad_art:
        return True
    if nonrad_name and 'radioactive' in combined and not nonrad_art:
        return True
    return False


def _gate(sim: float, threshold: float, semantic_sim: float | None):
    """采纳门判定：主门 token 覆盖率，补充门 MiniLM 语义。返回 (accepted, reason)。"""
    accepted = sim >= threshold
    sem_accept = (semantic_sim is not None
                  and float(semantic_sim) >= SEMANTIC_THRESHOLD)
    return (accepted or sem_accept,
            'token' if accepted else ('semantic' if sem_accept else 'below'))


def epmc_candidate(client, protocol_name: str, threshold: float = EUROPEPMC_THRESHOLD,
                   semantic_sim: float | None = None):
    """用 EuropePMCClient 检索，产出候选 dict（含 accepted 标记）或 None。

    与 pubmed_candidate 的差异只有一处：摘要随检索结果内嵌返回（resultType=core），
    不需要第二次 fetch。采纳门、放射性守卫、objective 抽取全部复用同一套逻辑，
    保证两源判定口径一致（否则同一协议换个源就会出现不同结论，无法审计）。

    source_ref 优先 PMID（最稳的可引用标识），无 PMID 时用 DOI（PPR 预印本只有 DOI），
    再无则 PMCID —— 归因 tag 由 reference_tag() 按形态成型。
    """
    if not protocol_name:
        return None
    cands = client.search_by_protocol_name(protocol_name, max_results=8)
    if not cands:
        return None
    best = max(
        cands,
        key=lambda c: token_similarity(protocol_name, c.get('title') or ''),
    )
    title = best.get('title') or ''
    sim = token_similarity(protocol_name, title)
    abstract = best.get('abstract') or ''
    if _radioactive_conflict(protocol_name, title, abstract):
        return None
    obj = extract_objective(abstract)
    if not obj:
        return None
    accepted, reason = _gate(sim, threshold, semantic_sim)
    return {
        'objective': obj,
        'source_ref': best.get('pmid') or best.get('doi') or best.get('pmcid') or '',
        'pmid': best.get('pmid') or '',
        'doi': best.get('doi') or '',
        'article_title': title,
        'similarity': sim,
        'semantic_similarity': semantic_sim,
        'is_preprint': bool(best.get('is_preprint')),
        'accepted': accepted,
        'accept_reason': reason,
    }


def pubmed_candidate(client, protocol_name: str, threshold: float = PUBMED_THRESHOLD,
                     semantic_sim: float | None = None):
    """用 PubMedClient 搜索+取摘要，产出候选 dict（含 accepted 标记）或 None。

    返回 None 仅当：无搜索结果 或 摘要无法抽取 objective。
    采纳决策：token_similarity >= threshold（主门，宁 miss）→ 采纳；
    否则若 semantic_sim（外部 MiniLM 预计算，见 SEMANTIC_THRESHOLD）>= SEMANTIC_THRESHOLD
    → 仍采纳（捕获「同名方法但措辞不同」导致 token 低覆盖的真匹配）。
    两者皆低 → accepted=False（供 dry-run 报告未采纳原因）。
    """
    if not protocol_name:
        return None
    cands = client.search_by_protocol_name(protocol_name, max_results=5)
    if not cands:
        return None
    # 采纳相似度只用 token_similarity（显著 token 覆盖率）。
    # 不用 method_match：其底层 _method_tokens 的 CamelCase 启发式会把普通首字母大写词
    # （Adult/Human/Cell）误判为「方法 token」，导致 "Adult human small intestine
    # cell dissociation" 对任意含 "adult" 的论文算出 method_match=1.0 → 错配采纳。
    # token_similarity 已能覆盖 barseq/flash/scrinshot/micro-c 等方法名，故弃用 method_match。
    best = max(
        cands,
        key=lambda c: token_similarity(protocol_name, c.get('title') or ''),
    )
    title = best.get('title') or ''
    sim = token_similarity(protocol_name, title)
    abstract = client.fetch_abstract(best.get('pmid') or '')
    # 放射性 / 非放射性 矛盾保护：协议名说放射性但文章是非放射性（或反之）→ 拒
    if _radioactive_conflict(protocol_name, title, abstract):
        return None
    obj = extract_objective(abstract)
    if not obj:
        return None
    # 主门：token 覆盖率；补充门：MiniLM 语义（仅当外部预计算提供时生效）
    accepted, reason = _gate(sim, threshold, semantic_sim)
    return {
        'objective': obj,
        'pmid': best.get('pmid') or '',
        'article_title': title,
        'similarity': sim,
        'semantic_similarity': semantic_sim,
        'accepted': accepted,
        'accept_reason': reason,
    }


def replay_candidate(cand: dict | None, threshold: float = PUBMED_THRESHOLD,
                     semantic_sim: float | None = None):
    """对已抓取报告（--report 产物）里的候选重放采纳门 —— 纯函数、零网络。

    为什么需要：PubMed 会间歇 502，联网重跑会让 --apply 结果不可复现；
    重放让「审核时看到的候选」与「落库写入的候选」逐字一致，可复现可审计。

    重放**不盲信报告里的 accepted 字段**：门槛（PUBMED_THRESHOLD / SEMANTIC_THRESHOLD）
    始终是唯一权威，报告只提供 objective 文本与已算好的相似度。
    semantic_sim 显式传入时优先；否则沿用报告内嵌的 semantic_similarity。
    """
    if not cand or not cand.get('objective'):
        return None
    sim = float(cand.get('similarity') or 0.0)
    if semantic_sim is None:
        semantic_sim = cand.get('semantic_similarity')
    accepted, reason = _gate(sim, threshold, semantic_sim)
    out = dict(cand)
    out['similarity'] = sim
    out['semantic_similarity'] = semantic_sim
    out['accepted'] = bool(accepted)
    out['accept_reason'] = reason
    return out


def bio_candidate(protocol_name: str, override: dict | None,
                  threshold: float = BIOPROTOCOL_THRESHOLD):
    """从 Bio-protocol overrides 条目产出候选 dict（含 accepted 标记）或 None。

    override: {"objective","source_title","url"}（经 WebFetch 离线路预取）
    相似度低于 threshold → 返回候选但 accepted=False。
    """
    if not override or not override.get('objective'):
        return None
    src_title = override.get('source_title') or protocol_name
    sim = token_similarity(protocol_name, src_title)
    return {
        'objective': override['objective'],
        'url': override.get('url') or '',
        'source_title': src_title,
        'similarity': sim,
        'accepted': sim >= threshold,
    }
