"""jena 爬虫数据索引服务（策略 B：本地索引常驻）。

jena JSONL 作为本地静态数据集，进程级单例索引常驻。AI AUTO MATCH 运行时查询：
用研究员输入的标识符（CAS / product_name / catalog_no）匹配 jena 记录，取：
  - systematic_name（核心锚点，驱动 Bioz 文献检索）
  - 规格字段（purity/concentration/storage 等，副产品预填）

jena 数据**永不落库成 Product**（策略 B，与 BioProCorpus 同构）。
详见 docs/FIVE_DATASOURCES.md §3.5、docs/DATASOURCE_RELIABILITY.md §8。
"""
import json
import re
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

# catalog 形态快速识别（L10：name 命名空间下若标识符形如 catalog 号，优先精确 catalog 匹配）。
# CANONICAL Jena 货号语法（与 build_safe_clean.CAT_RE / validate_clean.CAT_RE 三处同步）：
#   1~4 字母前缀 + 段内字母数字混排 + 多段后缀，容纳单字母前缀(X-/C-)、字母数字混排
#   (PR-BA120VS8 / EN-E2006-01)、多段染料货号(CLK-1277-AZ-5 / NU-821-BIOX-HC)。
#   CAS(纯数字段)与产品名(含空格/小写)均不命中，避免误分类。
_CATALOG_RE = re.compile(r'^[A-Z]{1,4}-[A-Z0-9]+(?:-[A-Z0-9]+)*$')


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
        # P1-5：CAS 可能对应多个记录（同化合物不同盐型），改为 list 防止后者覆盖前者
        self._by_cas: dict[str, list[JenaRecord]] = {}

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
                        # P1-5：同 CAS 多记录追加，不覆盖
                        self._by_cas.setdefault(record.cas_number.upper(), []).append(record)
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
        """精确匹配 CAS 号（大小写不敏感）。同 CAS 多记录时返回首选（list 首条），
        P1-5：全部候选取 self.get_cas_records(cas)。"""
        if not cas:
            return None
        recs = self._by_cas.get(cas.strip().upper())
        return recs[0] if recs else None

    def get_cas_records(self, cas: Optional[str]) -> list[JenaRecord]:
        """同 CAS 的全部记录（P1-5：防止覆盖导致的静默丢失）。"""
        if not cas:
            return []
        return list(self._by_cas.get(cas.strip().upper(), []))

    @staticmethod
    def _name_match_score(pn: str, q: str) -> int:
        """partial 排序评分：越低越优。

        - 词边界命中（query 是名字中的独立 token，如 "atp" ∈ "atp, disodium salt"）
          优先于任意子串命中；
        - 同组内短名优先（短名更可能是规范名，避免 ATP→2'-MeSe-ATP 长名错配）。
        L10 修正核心：用此评分替代旧的「JSONL 迭代顺序取首条」。
        """
        tokens = re.split(r'[^a-z0-9]+', pn)
        if q in tokens:
            return len(pn)        # token 命中组：短名优先
        return 10000 + len(pn)    # 非 token 子串：靠后，且短名优先

    def find_by_name(self, name: Optional[str], limit: int = 5) -> list[JenaRecord]:
        """按 product_name 查找（L10 修正：精确优先 + 子串歧义排序，不盲取首条）。

        排序：精确匹配（大小写不敏感）恒排最前；部分匹配按 _name_match_score 升序
        （词边界命中 > 短名）。返回前 `limit` 条，精确匹配不占 limit 额度。
        """
        if not name:
            return []
        q = name.strip().lower()
        exact, partial = [], []
        for r in self._records:
            pn = (r.product_name or "").lower()
            if pn == q:
                exact.append(r)
            elif q in pn or pn in q:
                partial.append(r)
        partial.sort(key=lambda r: self._name_match_score((r.product_name or "").lower(), q))
        return exact + partial[:max(0, limit - len(exact))]

    def lookup(self, identifier: Optional[str], namespace: str = "name") -> Optional[JenaRecord]:
        """统一查询入口（仿 PubChemEnhancer.resolve_to_properties 的 namespace 模式）。

        Args:
            identifier: 查询标识符
            namespace: cas / catalog_no / name（默认 name）

        Returns:
            匹配到的 JenaRecord，或 None。
            L10 修正：
              - catalog 精确匹配优先：identifier 形如 catalog 号时先精确查 catalog；
              - name 模式歧义检测：精确匹配或唯一部分匹配才返回；多条部分匹配视为
                歧义，不盲取首条，返回 None 交由 synonyms / 研究员裁决。
        """
        if not identifier:
            return None
        if namespace == "cas":
            return self.lookup_by_cas(identifier)
        if namespace == "catalog_no":
            return self.lookup_by_catalog_no(identifier)
        # name 模式
        q = identifier.strip().lower()
        # catalog 形态优先精确 catalog 匹配（防御：调用方误把 catalog 当 name 传入）
        if _CATALOG_RE.match(identifier.strip()):
            cat_rec = self.lookup_by_catalog_no(identifier)
            if cat_rec:
                return cat_rec
        results = self.find_by_name(identifier, limit=100)
        exact = [r for r in results if (r.product_name or "").lower() == q]
        if exact:
            return exact[0]
        partial = [r for r in results if r not in exact]
        if len(partial) == 1:
            return partial[0]
        return None  # 歧义：候选不唯一，不盲取首条


# ── 进程级共享单例（惰性构建，线程安全）──────────────────────────────────────
# 仿 BioProCorpus get_shared_retriever 模式（见 protocol_recommender.py:251）。
# 索引在首次调用时构建一次，之后全进程复用。生产调用点（AI AUTO MATCH）用此函数。
# 测试请直接 new JenaIndex(data_dir=...) 注入独立实例，不用单例。
# 详见 docs/DATASOURCE_RELIABILITY.md §8
_shared_index: Optional[JenaIndex] = None
_shared_index_meta: Optional[tuple] = None  # (path, mtime, size) —— P1-4 失效校验
_shared_index_lock = threading.Lock()


def _build_shared_index() -> None:
    """（重）构建共享索引并记录文件指纹。"""
    global _shared_index, _shared_index_meta
    index = JenaIndex()
    index.build()
    _shared_index = index
    path = os.path.join(JENA_DATA_DIR, JENA_JSONL_FILENAME)
    try:
        _shared_index_meta = (path, os.path.getmtime(path), os.path.getsize(path))
    except OSError:
        _shared_index_meta = None
    logger.info(f"jena shared index ready: {index.size()} records")


def get_shared_jena_index() -> JenaIndex:
    """获取进程级共享 JenaIndex 单例（惰性、线程安全、双检锁）。

    首次调用时构建索引（读取并解析 jena JSONL），之后全进程复用。
    P1-4：每次调用校验 JSONL 文件指纹（mtime+size），重爬后线上自动刷新，
    避免长驻 worker 一直服务旧索引。
    """
    global _shared_index
    if _shared_index is None:
        with _shared_index_lock:
            if _shared_index is None:
                _build_shared_index()
        return _shared_index
    # 已有索引：检查文件是否变更
    path = os.path.join(JENA_DATA_DIR, JENA_JSONL_FILENAME)
    changed = False
    try:
        if _shared_index_meta is None or _shared_index_meta[0] != path:
            changed = True
        else:
            changed = (os.path.getmtime(path) != _shared_index_meta[1]
                       or os.path.getsize(path) != _shared_index_meta[2])
    except OSError:
        changed = False
    if changed:
        with _shared_index_lock:
            _build_shared_index()
    return _shared_index


# ── 归一化函数（jena 原始值 → Product choices）──────────────────────────────
# AI AUTO MATCH 查到 jena 记录后调用，把原始规格值归一化到 Product 模型的
# choices 枚举（前端 select 是 choices 绑定，不归一化则选不中）。
# 详见 docs/FIVE_DATASOURCES.md §4.3、docs/jena_scraper_spec.md
import re as _re
from apps.commerce.models import Product as _Product

# jena 产品线 L1 → 平台 CategoryL1 映射（v1 只保留 3 个采纳 L1）
#
# P1-3 决策记录（勿轻易扩这张表）：
#   平台分类权威是 ProductClass 自引用树（setup_categories.CATEGORY_TREE v1），
#   刻意只采纳 3 条 L1；CategoryL1 枚举同样只有这 3 个值。其余 5 条 jena 产品线
#   （proteins / probes & epigenetics / rna technologies / crystallography & cryo-em /
#    LEXSY expression）平台 v1 不采纳 —— 这是产品/目录决策，不是映射器缺陷。
#   ⚠ 绝不可在此把它们映射到 'proteins_...' / 'probes_epigenetics' 等不存在的 slug：
#     那正是 jena_matcher.MAPPER_VERSION 记载的 SC8001 幻影 slug bug（映射到分类树
#     里不存在的 'probes_epigenetics'，污染了 L1 缓存）。
#   真要采纳某条线：先在 setup_categories.CATEGORY_TREE 加 L1 节点 + CategoryL1 枚举加值，
#     再回来这里加一行；顺序反了就会再造幻影 slug。
_CATEGORY_L1_MAP = [
    ('nucleotides', 'nucleotides_nucleosides'),
    ('click chemistry', 'click_chemistry'),
    ('molecular biology', 'molecular_biology'),
]

# 平台已采纳 L1 全集（与 CategoryL1 枚举同源）。map_category_l1 的输出必须 ∈ 此集合或 ''，
# 作为杜绝幻影 slug 回归的 fail-safe 边界。
_ADOPTED_L1 = set(_Product.CategoryL1.values)

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


# P2-2：concentration 合法性判定的单位/稀释比正则，与清洗程序
# verify_jena_products.concentration_has_unit（canonical，单一真相源）逐字对齐。
# 后端无法跨项目 import 桌面爬虫模块，故在此复刻同一份正则——三处
# （scraper_v3.clean_concentration / verify_jena_products.concentration_has_unit /
#   本函数）须同步维护；任一改动务必三处一起改，避免校验器再度漂移。
_CONC_UNIT_RE = _re.compile(
    r'\d[\d.,]*\s*(?:mm|µm|um|nm|pm|mg|µg|ug|ng|g|ml|µl|ul|l|units?|u|m|%|×|x)\b', _re.I)
_CONC_DILUTION_RE = _re.compile(r'\d+\s*:\s*\d+')  # 1:1000 稀释比也算有效浓度表达


def classify_concentration(raw) -> str:
    """浓度语义分类（FIVE_DATASOURCES.md §4.3）。

    合法性判定与清洗程序 concentration_has_unit（canonical）完全对齐：
    - 含单位（mM/M/µg/ml/%/x/units/µl…）的数值表达：保留
    - 稀释比（1:1000）：保留
    - 无单位散文（photometrically 等无量纲描述）：视为污染，丢弃（返回空）

    注：原实现是第三套独立正则且额外显式丢弃 photometrically，与 canonical 漂移；
    现改为复用同一份 _CONC_UNIT_RE/_CONC_DILUTION_RE。纯散文（如 "determined
    photometrically"）本就无单位 → 仍丢弃；而 "5 mg/ml (photometrically)" 含单位
    → 按 canonical 保留（旧实现会误丢，此为对齐后的正确行为）。
    """
    if not raw:
        return ''
    s = str(raw).strip()
    if _CONC_UNIT_RE.search(s) or _CONC_DILUTION_RE.search(s):
        return s
    return ''  # 无单位、无稀释比 → 污染散文，丢弃


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
    """jena category_path 任意段 → 平台 CategoryL1 枚举值。匹配不上返回空。

    扫描 | 分隔的全部层级（不只第一段），以覆盖
    'Probes & Epigenetics | … | Amine-modified Nucleotides' 这类
    正确 L1 藏在深层段的记录（SC8001 真实案例：L1=nucleotides_nucleosides
    在第四段，旧实现只取第一段 → 漏匹配 → Category 空）。

    P1-3 fail-safe：命中的映射值必须 ∈ 平台已采纳 L1 全集（_ADOPTED_L1），否则
    返回 ''。这保证本函数永远不会吐出分类树里不存在的幻影 slug —— 即使日后有人
    误在 _CATEGORY_L1_MAP 加了一条指向未采纳枚举的映射（SC8001 幻影 slug bug 的根因），
    也会被这道边界拦成 ''，不会再污染 L1 缓存。
    """
    if not category_path:
        return ''
    segments = [s.strip().lower() for s in str(category_path).split('|')]
    for keyword, l1_value in _CATEGORY_L1_MAP:
        for seg in segments:
            if keyword in seg:
                # 幻影 slug 边界：只放行平台真实存在的 L1，否则 fail-safe 到 ''。
                return l1_value if l1_value in _ADOPTED_L1 else ''
    return ''
