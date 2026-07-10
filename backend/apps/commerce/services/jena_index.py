"""jena 爬虫数据索引服务（策略 B：本地索引常驻）。

jena JSONL 作为本地静态数据集，进程级单例索引常驻。AI AUTO MATCH 运行时查询：
用研究员输入的标识符（CAS / product_name / catalog_no）匹配 jena 记录，取：
  - systematic_name（核心锚点，驱动 Bioz 文献检索）
  - 规格字段（purity/concentration/storage 等，副产品预填）

jena 数据**永不落库成 Product**（策略 B，与 BioProCorpus 同构）。
详见 docs/FIVE_DATASOURCES.md §3.5、docs/DATASOURCE_RELIABILITY.md §8。
"""
import json
import logging
import os
import threading
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)

# 数据路径：默认项目内 backend/data/jena/，JENA_DATA_DIR 环境变量可指向项目外工作区
JENA_DATA_DIR = os.environ.get(
    "JENA_DATA_DIR",
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))),
        "data", "jena",
    ),
)
JENA_JSONL_FILENAME = "jena_products_v2.jsonl"


@dataclass
class JenaRecord:
    """jena 产品记录（索引后的结构化形式）。

    systematic_name 是核心字段（跨源查询锚点），其余规格字段为副产品。
    字段值保留原始形态，消费方（AI AUTO MATCH）按需清洗（如 concentration 语义分类）。
    """
    catalog_no: str
    product_name: str
    systematic_name: Optional[str] = None  # 核心：跨源查询锚点
    cas_number: Optional[str] = None
    purity: Optional[str] = None
    concentration: Optional[str] = None  # 原始值，消费方按 §4.3 语义分类
    storage_condition: Optional[str] = None
    shipping_condition: Optional[str] = None
    shelf_life: Optional[str] = None
    form: Optional[str] = None
    color: Optional[str] = None
    ph: Optional[str] = None
    category_path: Optional[str] = None
    application_tags: Optional[str] = None
    description: Optional[str] = None
    source_url: Optional[str] = None
    datasheet_pdf_url: Optional[str] = None
    msds_pdf_url: Optional[str] = None
    structural_formula_url: Optional[str] = None
    extras: dict = field(default_factory=dict)  # 其余未显式映射的字段


class JenaIndex:
    """jena 数据索引：按 catalog_no / cas / product_name 查询。

    索引在 build() 时一次性构建（精确索引 by catalog_no/cas + 全量记录列表供 name 查找）。
    进程级单例由 get_shared_jena_index() 管理。
    """

    def __init__(self, data_dir: Optional[str] = None, jsonl_filename: str = JENA_JSONL_FILENAME):
        self.data_dir = data_dir or JENA_DATA_DIR
        self.jsonl_filename = jsonl_filename
        self._records: list[JenaRecord] = []
        self._by_catalog_no: dict[str, JenaRecord] = {}
        self._by_cas: dict[str, JenaRecord] = {}

    def build(self) -> None:
        """从 JSONL 构建索引。文件不存在时静默（索引为空），不抛异常。"""
        self._records = []
        self._by_catalog_no = {}
        self._by_cas = {}
        path = os.path.join(self.data_dir, self.jsonl_filename)
        if not os.path.exists(path):
            logger.warning(f"jena JSONL not found, index empty: {path}")
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    record = self._parse(rec)
                    if record is None:
                        continue
                    self._records.append(record)
                    if record.catalog_no:
                        self._by_catalog_no[record.catalog_no.upper()] = record
                    if record.cas_number:
                        self._by_cas[record.cas_number.upper()] = record
        except Exception as e:
            logger.warning(f"jena index build failed: {e}")
        logger.info(f"jena index built: {len(self._records)} records from {path}")

    @staticmethod
    def _parse(rec: dict) -> Optional[JenaRecord]:
        """解析单条 JSONL 记录为 JenaRecord。缺 catalog_no 或 product_name 则跳过。"""
        def clean(v):
            s = (v or "").strip() if isinstance(v, str) else v
            return s if s not in ("", None) else None

        catalog_no = clean(rec.get("jena_catalog_no"))
        name = clean(rec.get("product_name"))
        if not catalog_no or not name:
            return None

        # 已显式映射的字段
        mapped = {
            "catalog_no": catalog_no,
            "product_name": name,
            "systematic_name": clean(rec.get("systematic_name")),
            "cas_number": clean(rec.get("cas_number")),
            "purity": clean(rec.get("purity")),
            "concentration": clean(rec.get("concentration")),
            "storage_condition": clean(rec.get("storage_condition")),
            "shipping_condition": clean(rec.get("shipping_condition")),
            "shelf_life": clean(rec.get("shelf_life")),
            "form": clean(rec.get("form")),
            "color": clean(rec.get("color")),
            "ph": clean(rec.get("ph")),
            "category_path": clean(rec.get("category_path")),
            "application_tags": clean(rec.get("application_tags")),
            "description": clean(rec.get("description")),
            "source_url": clean(rec.get("source_url")),
            "datasheet_pdf_url": clean(rec.get("datasheet_pdf_url")),
            "msds_pdf_url": clean(rec.get("msds_pdf_url")),
            "structural_formula_url": clean(rec.get("structural_formula_url")),
        }
        # 其余字段进 extras
        known_keys = {
            "jena_catalog_no", "product_name", "systematic_name", "cas_number",
            "purity", "concentration", "storage_condition", "shipping_condition",
            "shelf_life", "form", "color", "ph", "category_path", "application_tags",
            "description", "source_url", "datasheet_pdf_url", "msds_pdf_url",
            "structural_formula_url",
        }
        extras = {k: v for k, v in rec.items() if k not in known_keys and not k.startswith("jena_catalog_no")}
        mapped["extras"] = extras
        return JenaRecord(**mapped)

    def size(self) -> int:
        return len(self._records)

    def list_sources(self) -> list:
        """列出所有产品线（category_path L1 去重）"""
        seen = set()
        for r in self._records:
            if r.category_path:
                seen.add(r.category_path.split("|")[0].strip())
        return sorted(seen)

    def lookup_by_catalog_no(self, catalog_no: Optional[str]) -> Optional[JenaRecord]:
        """精确匹配 catalog_no（大小写不敏感）"""
        if not catalog_no:
            return None
        return self._by_catalog_no.get(catalog_no.strip().upper())

    def lookup_by_cas(self, cas: Optional[str]) -> Optional[JenaRecord]:
        """精确匹配 CAS 号（大小写不敏感）"""
        if not cas:
            return None
        return self._by_cas.get(cas.strip().upper())

    def find_by_name(self, name: Optional[str], limit: int = 5) -> list[JenaRecord]:
        """按 product_name 查找：精确匹配优先，其次包含关系。返回有序列表（精确在前）。"""
        if not name:
            return []
        name_lower = name.strip().lower()
        exact, partial = [], []
        for r in self._records:
            pn = r.product_name.lower()
            if pn == name_lower:
                exact.append(r)
            elif name_lower in pn or pn in name_lower:
                partial.append(r)
        # 精确优先，部分限 limit
        return exact + partial[:max(0, limit - len(exact))]

    def lookup(self, identifier: Optional[str], namespace: str = "name") -> Optional[JenaRecord]:
        """统一查询入口（仿 PubChemEnhancer.resolve_to_properties 的 namespace 模式）。

        Args:
            identifier: 查询标识符
            namespace: cas / catalog_no / name（默认 name）

        Returns:
            匹配到的首条 JenaRecord，或 None。name 模式下精确匹配优先于部分匹配。
        """
        if not identifier:
            return None
        if namespace == "cas":
            return self.lookup_by_cas(identifier)
        if namespace == "catalog_no":
            return self.lookup_by_catalog_no(identifier)
        # name: find_by_name 取首条（精确优先）
        results = self.find_by_name(identifier, limit=1)
        return results[0] if results else None


# ── 进程级共享单例（惰性构建，线程安全）──────────────────────────────────────
# 仿 BioProCorpus get_shared_retriever 模式（见 protocol_recommender.py:251）。
# 索引在首次调用时构建一次，之后全进程复用。生产调用点（AI AUTO MATCH）用此函数。
# 测试请直接 new JenaIndex(data_dir=...) 注入独立实例，不用单例。
# 详见 docs/DATASOURCE_RELIABILITY.md §8
_shared_index: Optional[JenaIndex] = None
_shared_index_lock = threading.Lock()


def get_shared_jena_index() -> JenaIndex:
    """获取进程级共享 JenaIndex 单例（惰性、线程安全、双检锁）。

    首次调用时构建索引（读取并解析 jena JSONL），之后全进程复用。
    AI AUTO MATCH 的 jena 查询应通过此函数获取索引。
    """
    global _shared_index
    if _shared_index is None:
        with _shared_index_lock:
            if _shared_index is None:
                logger.info("Building jena shared index (one-time, process-level)...")
                index = JenaIndex()
                index.build()
                logger.info(f"jena shared index ready: {index.size()} records")
                _shared_index = index
    return _shared_index


# ── 归一化函数（jena 原始值 → Product choices）──────────────────────────────
# AI AUTO MATCH 查到 jena 记录后调用，把原始规格值归一化到 Product 模型的
# choices 枚举（前端 select 是 choices 绑定，不归一化则选不中）。
# 详见 docs/FIVE_DATASOURCES.md §4.3、docs/jena_scraper_spec.md
import re as _re
from apps.commerce.models import Product as _Product

# jena 产品线 L1 → 平台 CategoryL1 映射（v1 只保留 3 个采纳 L1）
_CATEGORY_L1_MAP = [
    ('nucleotides', 'nucleotides_nucleosides'),
    ('click chemistry', 'click_chemistry'),
    ('molecular biology', 'molecular_biology'),
    # 以下 jena 产品线平台暂不采纳，映射返回空字符串
    # ('proteins', ...), ('probes', ...), ('epigenetics', ...),
    # ('rna', ...), ('crystallography', ...), ('cryo-em', ...),
    # LEXSY Expression 等无对应平台分类 → 留空
]

_PURITY_CHOICES = set(_Product.PurityLevel.values)


def normalize_purity(raw) -> str:
    """jena 纯度 → PurityLevel。'≥ 99 % (HPLC)' → '≥ 99% (HPLC)'。

    归一化后匹配 choices；匹配不上则保留归一化值（字段允许任意字符串，保信息不丢失）。
    """
    if not raw:
        return ''
    s = _re.sub(r'\s+', ' ', str(raw).strip())
    s = _re.sub(r'\s*%\s*', '% ', s).strip().rstrip(',').strip()  # '99 %' → '99%'
    s = _re.sub(r'\s+', ' ', s)
    return s if s in _PURITY_CHOICES else s  # 保留归一化值


def classify_concentration(raw) -> str:
    """浓度语义分类（FIVE_DATASOURCES.md §4.3）。

    - 小分子浓度（mM/M/%/w/v 等）：保留
    - 酶活（units/μl）、浓缩倍数（x）：保留
    - 污染（photometrically 等无量纲描述）：丢弃（返回空）
    """
    if not raw:
        return ''
    s = str(raw).strip()
    if _re.search(r'photometrically|spectrophotometric', s, _re.I):
        return ''
    if _re.search(r'\d', s) and _re.search(
        r'mM|μM|µM|nM|pM|\bM\b|%|w/v|mg/m|units|ul|μl|x\s*conc|x$', s, _re.I
    ):
        return s
    return ''  # 无量纲无数字 → 丢弃


def normalize_storage(raw) -> str:
    """jena 储存条件 → StorageCondition。'store at -20 °C' → '-20°C'。"""
    if not raw:
        return ''
    s = str(raw).lower()
    if '-20' in s:
        return '-20°C, protect from light' if ('light' in s or 'protect' in s) else '-20°C'
    if '-80' in s:
        return '-80°C'
    if _re.search(r'\b[4-9]\s*°?\s*c', s) or '8-10' in s:  # 4°C ~ 9°C 近似为 4°C
        return '4°C, protect from light' if ('light' in s or 'protect' in s) else '4°C'
    if 'ambient' in s or 'room' in s:
        return 'Room temperature, dry' if 'dry' in s else 'Room temperature'
    return ''


def normalize_shipping(raw) -> str:
    """jena 运输条件 → ShippingCondition。'shipped on gel packs' → 'Cold Pack'。"""
    if not raw:
        return ''
    s = str(raw).lower()
    if 'dry ice' in s:
        return 'Dry Ice'
    if 'gel pack' in s or 'cold pack' in s or 'blue ice' in s or 'ice pack' in s:
        return 'Cold Pack'
    if 'ambient' in s or 'room' in s:
        return 'Ambient'
    return ''


def normalize_shelf_life(raw) -> str:
    """jena 保质期 → ShelfLifeOption。'12 months' → 'P1Y'。"""
    if not raw:
        return ''
    s = str(raw).lower()
    if 'n/a' in s or 'not' in s:
        return ''
    m = _re.search(r'(\d+)\s*month', s)
    if m:
        months = int(m.group(1))
        if months >= 60:
            return 'P5Y'
        if months >= 36:
            return 'P3Y'
        if months >= 24:
            return 'P2Y'
        if months >= 12:
            return 'P1Y'
        return ''  # <12 月无对应枚举，留空
    m = _re.search(r'(\d+)\s*year', s)
    if m:
        years = int(m.group(1))
        return {1: 'P1Y', 2: 'P2Y', 3: 'P3Y', 5: 'P5Y'}.get(years, f'P{years}Y' if years >= 5 else '')
    return ''


def map_category_l1(category_path) -> str:
    """jena category_path 第一级 → 平台 CategoryL1 枚举值。匹配不上返回空。"""
    if not category_path:
        return ''
    first = str(category_path).split('|')[0].strip().lower()
    for keyword, l1_value in _CATEGORY_L1_MAP:
        if keyword in first:
            return l1_value
    return ''
