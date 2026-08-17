# -*- coding: utf-8 -*-
"""受控词表标注纯逻辑（route B 加法部分，无 Django 依赖，可独立单测）。

职责：
1. 把聚类结果（poc_facet_taxonomy.json / poc_application_taxonomy.json）的 cluster_id
   归并到 facet 维度：
   - application / method / study_type 直接映射
   - organism / cell_type / disease 统一归入 biological_context，kind=species/cell/disease
   - drop（模板噪声簇）跳过，不生成 facet
   注：method facet 由既有 k=80 聚类（dimension=technique）改名而来。
2. 保守的交叉检测：对协议文本补标嵌在「技术簇」里的 species/cell/disease，
   作为额外 biological_context facet（source=cross_detect）。

所有规则可复现、确定性、幂等。KMeans 复现与 DB 写入在 management command 中完成。
"""
import json
import re

FACET_TYPE_APPLICATION = "application"
FACET_TYPE_METHOD = "method"
FACET_TYPE_BIOLOGICAL = "biological_context"
FACET_TYPE_STUDY_TYPE = "study_type"

# taxonomy JSON 里原始 dimension 字段 → (facet_type, kind)
# organism / cell_type / disease 三者统一收口到 biological_context
_BIO_RAW_DIMS = {
    "organism": "species",
    "cell_type": "cell",
    "disease": "disease",
}
_DROP_DIM = "drop"

# 保守交叉检测词表：canonical (kind, value) -> 正则（词边界，避免子串误命中）。
# 仅收录高置信度、可归因的物种/细胞/疾病词；宁可漏标不错标。
BIO_KEYWORDS = {
    "species": [
        ("Mus musculus", r"\bmus\s?musculus\b|\bmice\b|\bmouse\b|\bmurine\b"),
        ("Rattus norvegicus", r"\brats?\b|\brattus\b"),
        ("Homo sapiens", r"\bhumans?\b"),
        ("Drosophila melanogaster", r"\bdrosophila\b|\bfruit\s?fly\b"),
        ("Caenorhabditis elegans", r"\bc\.?\s?elegans\b"),
        ("Danio rerio", r"\bzebrafish\b|\bdanio\b"),
        ("Arabidopsis thaliana", r"\barabidopsis\b"),
        ("Escherichia coli", r"\be\.?\s?coli\b"),
        ("Staphylococcus aureus", r"\bstaph\b|\bs\.?\s?aureus\b"),
        ("SARS-CoV-2", r"\bsars-?cov-?2\b|\bcovid-?19\b"),
        ("Saccharomyces cerevisiae", r"\byeast\b|\bs\.?\s?cerevisiae\b"),
    ],
    "cell": [
        ("HEK293", r"\bhek-?293\b|\bhek293\b"),
        ("HeLa", r"\bhela\b"),
        ("Macrophage", r"\bmacrophages?\b"),
        ("Fibroblast", r"\bfibroblasts?\b"),
        ("Epithelial cell", r"\bepithelial\b"),
        ("Endothelial cell", r"\bendothelial\b"),
        ("Neuron", r"\bneuronal\b|\bneurons?\b"),
        ("Stem cell", r"\bstem\s?cells?\b|\bips\s?cells?\b|\bipsc\b"),
        ("T cell", r"\bt-?cells?\b|\bt-?lymphocytes?\b"),
        ("B cell", r"\bb-?cells?\b|\bb-?lymphocytes?\b"),
        ("PBMC", r"\bpbmc\b"),
        ("Lymphocyte", r"\blymphocytes?\b"),
    ],
    "disease": [
        ("Cancer", r"\bcancers?\b|\btumou?rs?\b|\bcarcinomas?\b|\bsarcomas?\b|\boncolog"),
        ("Diabetes", r"\bdiabet"),
        ("Alzheimer", r"\balzheimer"),
        ("Parkinson", r"\bparkinson"),
    ],
}

# 预编译
_BIO_COMPILED = {
    kind: [(value, re.compile(rx, re.IGNORECASE)) for value, rx in vals]
    for kind, vals in BIO_KEYWORDS.items()
}

# 交叉检测扫描的协议文本字段
PROTOCOL_TEXT_FIELDS = (
    "name", "objective", "principle", "materials",
    "reagents", "expected_results", "references",
)


def load_taxonomy(path):
    """读取 poc_facet_taxonomy.json，返回 (data, cluster_map)。

    cluster_map: cluster_id -> {dimension, value, kind, note}
    dimension ∈ {application, technique, organism, cell_type, disease, study_type, drop}
    """
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    cluster_map = {}
    for c in data.get("clusters", []):
        cluster_map[c["cluster_id"]] = c
    return data, cluster_map


def resolve_facet_spec(cluster_id, taxonomy_map):
    """cluster_id → (facet_type, kind, value) 或 None（drop/未知/空值跳过）。

    归并规则：
      - dimension == 'drop'                -> None（模板噪声）
      - dimension ∈ {organism,cell_type,disease} -> (biological_context, kind, value)
      - dimension == 'study_type'          -> (study_type, '', value)
      - dimension == 'application'         -> (application, '', value)
      - 其余（technique）                  -> (method, '', value)
    """
    c = taxonomy_map.get(cluster_id)
    if not c:
        return None
    dim = c.get("dimension")
    value = (c.get("value") or "").strip()
    if not value:
        return None
    if dim == _DROP_DIM:
        return None
    if dim in _BIO_RAW_DIMS:
        return (FACET_TYPE_BIOLOGICAL, _BIO_RAW_DIMS[dim], value)
    if dim == "study_type":
        return (FACET_TYPE_STUDY_TYPE, "", value)
    if dim == "application":
        return (FACET_TYPE_APPLICATION, "", value)
    # 其余（technique）改名为 method
    return (FACET_TYPE_METHOD, "", value)


def detect_biological_context(text):
    """从文本中保守地检测 species/cell/disease，返回去重后的 [(kind, value), ...]。"""
    if not text:
        return []
    found = []
    seen = set()
    for kind, items in _BIO_COMPILED.items():
        for value, rx in items:
            if rx.search(text) and (kind, value) not in seen:
                seen.add((kind, value))
                found.append((kind, value))
    return found


def protocol_text(protocol_obj):
    """拼接协议的描述性文本字段，供交叉检测使用。"""
    parts = []
    for field in PROTOCOL_TEXT_FIELDS:
        v = getattr(protocol_obj, field, None)
        if v:
            parts.append(str(v))
    return " ".join(parts)
