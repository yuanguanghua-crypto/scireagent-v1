"""EPMC 命中的「逐字可核验」闸门 —— 宁 miss 不错配。

背景（2026-09-15 审计，见 memory `2026-09-15.md` §16）：
  对 47 个零证据产品跑 Europe PMC 全文检索得 166 条命中，但**EPMC 的引号短语检索并非
  严格逐字**：约 10% 命中的记录里根本没有那个产品名（例：查 `"5-Propargylamino-dCTP-Cy3"`
  会返回一篇长新冠舌转录组论文）。反过来，单纯用「目录名逐字」校验又会**误杀真阳性**——
  论文很少按厂商目录名写，`N1-Methylpseudo-UTP` 在文中写作 `n1-methylpseudouridine` / `m1ψ` /
  `m1ψtp`，`7-Deaza-7-Propargylamino-dGTP` 写作 `7-propargylamino-dGTP`。

本模块提供闸门所需的纯函数 + 取全文：
  - `canonical(s)`      归一（撇号/破折号统一、**删全部空白**、小写）后用于子串比对；
  - `load_aliases()`    读 `data/epmc_product_synonyms.json` 的实证别名表；
  - `patterns_for()`    某产品可接受的写法集合（目录名 + 实证别名 + 去 Cy 染料后缀的基名）；
  - `verify_text()`     文本是否命中任一写法，返回命中的写法（否则 None）；
  - `fetch_fulltext()`  取 EPMC OA 全文 XML → canonical 文本（带磁盘缓存 + 容错）。

**删空白是必需的**：EPMC 的 fullTextXML 把化学式的下角标包成标签，剥标签后
`N1-Methylpseudo-UTP` 会变成 `n 1 -methylpseudo-utp`，不删空白就永远匹配不上。

调用方：`apps.bridges.management.commands.crawl_europepmc_evidence`（--verify）。
"""
import json
import os
import re
import tempfile

from core.datasource_client import request_with_resilience

# 归一时要统一掉的字符类（撇号 / 破折号），与审计脚本保持一致
_APOSTROPHES = "\u2018\u2019\u02bc\u2032\u00b4\u0060"
_DASHES = "\u2010\u2011\u2012\u2013\u2014\u2015\u2212"
_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
# 染料后缀（产品名形如 `5-Propargylamino-CTP-Cy5`）：核验时允许去掉它，
# 因为论文通常在正文用基名、另述标记染料。
_DYE_RE = re.compile(r"-cy\d+$")

DATA_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "data", "epmc_product_synonyms.json",
)

EPMC_FULLTEXT_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/{pmcid}/fullTextXML"
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def canonical(s: str) -> str:
    """归一为可比对形式：剥 XML 标签 → 撇号统一 `'` → 破折号统一 `-` → 删全部空白 → 小写。"""
    if not s:
        return ""
    s = _TAG_RE.sub(" ", s)
    for a in _APOSTROPHES:
        s = s.replace(a, "'")
    for d in _DASHES:
        s = s.replace(d, "-")
    s = _WS_RE.sub("", s)
    return s.lower()


_ALIAS_CACHE = None


def load_aliases(path: str = None) -> dict:
    """读别名表 → {catalog_no: [alias, ...]}；失败返回 {}（宁 miss：无别名即只认目录名）。"""
    global _ALIAS_CACHE
    if path is None and _ALIAS_CACHE is not None:
        return _ALIAS_CACHE
    target = path or DATA_FILE
    try:
        with open(target, encoding="utf-8") as f:
            data = json.load(f)
        aliases = data.get("aliases") or {}
        if not isinstance(aliases, dict):
            aliases = {}
    except Exception:
        aliases = {}
    if path is None:
        _ALIAS_CACHE = aliases
    return aliases


def patterns_for(catalog_no: str, name: str, aliases: dict = None) -> list:
    """返回该产品可接受的写法（canonical、去重、去空）。

    组成：目录名 + 去 Cy 染料后缀的基名 + 该 catalog_no 的实证别名。
    """
    aliases = load_aliases() if aliases is None else aliases
    raw = [name or ""]
    base = _DYE_RE.sub("", canonical(name or ""))
    if base and base != canonical(name or ""):
        raw.append(base)
    raw.extend(aliases.get(catalog_no or "", []) or [])
    out = []
    for item in raw:
        c = canonical(item)
        if c and c not in out:
            out.append(c)
    return out


def verify_text(text_canonical: str, patterns) -> str:
    """命中任一写法则返回该写法（canonical），否则 None。"""
    if not text_canonical:
        return None
    for p in patterns or []:
        if p and p in text_canonical:
            return p
    return None


def cache_dir() -> str:
    """全文缓存目录（可经环境变量 EPMC_FULLTEXT_CACHE 覆盖）。"""
    return os.environ.get("EPMC_FULLTEXT_CACHE") or os.path.join(
        tempfile.gettempdir(), "scireagent_epmc_fulltext")


def fetch_fulltext(pmcid: str, timeout: float = 45.0) -> str:
    """取 EPMC OA 全文并 canonical 化；不可得返回 ""（非 OA / 404 均为空）。

    带磁盘缓存：同一 pmcid 只取一次（166 条命中里不少共用同一篇，实测省 ~30% 请求）。
    """
    if not pmcid:
        return ""
    d = cache_dir()
    path = os.path.join(d, f"{pmcid}.txt")
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read()
        except Exception:
            pass
    try:
        resp = request_with_resilience(
            "GET", EPMC_FULLTEXT_URL.format(pmcid=pmcid), source="europepmc",
            timeout=timeout, headers={"User-Agent": _UA},
        )
    except Exception:
        return ""
    if resp.status_code != 200:
        # 404 = 不在 EPMC OA 子集（永久不可得）；5xx 已经在容错层重试过
        return ""
    txt = canonical(resp.text)
    try:
        os.makedirs(d, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(txt)
    except Exception:
        pass
    return txt


def verify_records(records, catalog_no: str, name: str, aliases: dict = None) -> list:
    """逐条核验；返回 (record, verdict, evidence) 三元组列表。

    verdict: "verified"（命中）/ "unverified"（拿到全文但没命中）/
             "unknown"（无 pmcid 或全文不可得 → 逐字不可校验）。
    """
    patterns = patterns_for(catalog_no, name, aliases)
    out = []
    for rec in records:
        pmcid = rec.get("_pmcid") or ""
        text = fetch_fulltext(pmcid) if pmcid else ""
        hit = verify_text(text, patterns)
        if hit:
            verdict, evidence = "verified", hit
        elif text:
            verdict, evidence = "unverified", ""
        else:
            verdict, evidence = "unknown", ""
        out.append((rec, verdict, evidence))
    return out
