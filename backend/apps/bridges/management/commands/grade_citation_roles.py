"""grade_citation_roles —— 按结构式规则给 ProductReference.citation_role 分级。

规则（C1 精化版，2026-09-15 实测校准）：

- **primary**   ：该关联的文献在**同一产品的 bioz 缓存**中命中（doi → pmid → title 任一），
  且该 bioz 记录的**引文上下文**（`long`/`medium`/`short`）里出现了记录自身的
  `catalog_number`（厂商货号）—— 即文献正文明确点名了该货号，属最强证据。
- **supporting**：bioz 命中，但上下文未点名货号。
- **background**：仅 pubmed 命中（DOI/PMID/标题文本匹配），无厂商佐证。
- 既无 bioz 也无 pubmed 命中 → **保持不动**（来源未知，不臆测）。

为什么这样定：
 生产实测 bioz 缓存 271 条记录 **全部带引文上下文**（`WITH_CTX=271/271`），
 故原设想"bioz 有上下文→primary / 无上下文→supporting"会坍缩成"bioz 一律 primary"。
 改用"上下文是否点名货号"这一更硬的结构信号，得到真实的三档（实测 86/107 命中）。

铁律 / 边界：
- **必须 UPDATE 现有行，绝不新建**：`unique_together = ('product','reference','citation_role')`，
  新建会在同 (product, reference) 上产生双行。
- 默认 dry-run：只统计 + 打印，绝不写库；`--apply` 才写。
- 只写变更过的行（`update_fields`），不整行覆盖。
- 不改任何 model、不加 migration、不动 `apps/bridges/services/*`。

用法：
    python manage.py grade_citation_roles                  # dry-run
    python manage.py grade_citation_roles --apply
    python manage.py grade_citation_roles --only-products SC8016,SC8017
    python manage.py grade_citation_roles --limit 20
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import IntegrityError

from apps.bridges.models import ProductReference
from apps.commerce.models import Product
from apps.documents.models import DataSourceCache

CTX_FIELDS = ('long', 'medium', 'short')
ROLE_ORDER = ('primary', 'supporting', 'background')


def _records_of(row):
    """缓存行的 records 列表（容错 dict / list / 其它）。"""
    data = row.get_data()
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def _product_keys(product):
    """产品 → 缓存键（catalog_no + 各 sku_code），去空/保序/去重（同 adopt 口径）。"""
    keys = []
    cat = getattr(product, 'catalog_no', None)
    if cat:
        keys.append(cat)
    for sku in product.skus.all():
        code = getattr(sku, 'sku_code', None)
        if code:
            keys.append(code)
    seen, out = set(), []
    for k in keys:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _empty_idx():
    return {'doi': {}, 'pmid': {}, 'title': {}}


def _build_index(products, key2pids):
    """返回 (bioz_idx, pubmed_idx)。

    每个产品的索引形如 {'doi': {doi: has_cat}, 'pmid': {...}, 'title': {...}}；
    `has_cat` = 该记录的 `catalog_number` 是否出现在它自己的引文上下文里
    （pubmed 记录恒 False）。
    同键多记录时取 OR。
    """
    bioz_idx, pubmed_idx = {}, {}
    rows = DataSourceCache.objects.filter(source__in=['bioz', 'pubmed']).order_by('id')
    for row in rows:
        pids = key2pids.get(row.query_key)
        if not pids:
            continue
        is_bioz = row.source == 'bioz'
        for pid in pids:
            idx = (bioz_idx if is_bioz else pubmed_idx).setdefault(pid, _empty_idx())
            for rec in _records_of(row):
                if not isinstance(rec, dict):
                    continue
                if is_bioz:
                    title = (rec.get('article_title') or '').strip().lower()
                    cat = str(rec.get('catalog_number') or '').strip().lower()
                    ctx = ' '.join(
                        str(rec.get(f) or '') for f in CTX_FIELDS).lower()
                    has_cat = bool(cat) and cat in ctx
                else:
                    title = (rec.get('title') or '').strip().lower()
                    has_cat = False
                doi = (rec.get('doi') or '').strip().lower()
                pmid = (rec.get('pmid') or '').strip()
                if doi:
                    idx['doi'][doi] = idx['doi'].get(doi, False) or has_cat
                if pmid:
                    idx['pmid'][pmid] = idx['pmid'].get(pmid, False) or has_cat
                if title:
                    idx['title'][title] = idx['title'].get(title, False) or has_cat
    return bioz_idx, pubmed_idx


def _match(idx, pid, ref):
    """按 doi → pmid → title 级联匹配；返回 (命中键, has_cat) 或 None。"""
    entry = idx.get(pid)
    if not entry:
        return None
    doi = (ref.doi or '').strip().lower()
    if doi and doi in entry['doi']:
        return ('doi', entry['doi'][doi])
    pmid = (ref.pmid or '').strip()
    if pmid and pmid in entry['pmid']:
        return ('pmid', entry['pmid'][pmid])
    title = (ref.title or '').strip().lower()
    if title and title in entry['title']:
        return ('title', entry['title'][title])
    return None


class Command(BaseCommand):
    help = ("Grade ProductReference.citation_role from cached Bioz/PubMed provenance "
            "(dry-run by default; --apply to persist).")

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='写库（默认 dry-run，绝不写）')
        parser.add_argument('--limit', type=int, default=None,
                            help='只处理前 N 个产品（按 id 升序）')
        parser.add_argument('--only-products', default=None,
                            help='逗号分隔 catalog_no 白名单')

    def handle(self, *args, **options):
        apply = options['apply']

        products = Product.objects.order_by('id')
        if options['only_products']:
            only = [s.strip() for s in options['only_products'].split(',') if s.strip()]
            products = products.filter(catalog_no__in=only)
        if options['limit'] is not None:
            products = products[:options['limit']]
        products = list(products)
        pids = [p.id for p in products]

        # key → product ids（一个键可能被多个产品共用，如共用 SKU）
        key2pids = {}
        for p in products:
            for k in _product_keys(p):
                key2pids.setdefault(k, set()).add(p.id)

        bioz_idx, pubmed_idx = _build_index(products, key2pids)

        self.stdout.write("=== grade_citation_roles ===")
        self.stdout.write("模式：" + ("apply (写库)" if apply else "dry-run (仅统计)"))
        self.stdout.write(
            f"[范围] 产品 {len(products)}；其中 bioz 索引 {len(bioz_idx)} / "
            f"pubmed 索引 {len(pubmed_idx)}")

        prs = (ProductReference.objects.filter(product_id__in=pids)
               .select_related('reference').order_by('id'))
        plan = []           # (pr, new_role)
        plan_dist = Counter()
        unchanged = 0
        for pr in prs:
            ref = pr.reference
            m = _match(bioz_idx, pr.product_id, ref)
            if m:
                new_role = 'primary' if m[1] else 'supporting'
            elif _match(pubmed_idx, pr.product_id, ref):
                new_role = 'background'
            else:
                unchanged += 1
                continue
            if new_role != pr.citation_role:
                plan.append((pr, new_role, m[0] if m else 'pubmed'))
            plan_dist[new_role] += 1

        self.stdout.write("[预测角色分布]（按规则应达成的终态）")
        for role in ROLE_ORDER:
            self.stdout.write(f"  {role:<10}：{plan_dist.get(role, 0)}")
        self.stdout.write(f"  保持不动（来源未知）：{unchanged}")
        self.stdout.write(f"[将更新行数] {len(plan)}")
        by_match = Counter(k for _, _, k in plan)
        self.stdout.write(f"  命中键：{dict(by_match)}")

        if not apply:
            self.stdout.write(self.style.WARNING(
                "\n[dry-run] 本次未写库；加 --apply 才落盘。"))
            return

        before = Counter(ProductReference.objects.filter(product_id__in=pids)
                         .values_list('citation_role', flat=True))
        changed = 0
        errors = 0
        for pr, new_role, _ in plan:
            pr.citation_role = new_role
            try:
                pr.save(update_fields=['citation_role', 'updated_at'])
                changed += 1
            except IntegrityError as e:
                errors += 1
                self.stderr.write(f"  ProductReference id={pr.id} 更新失败：{e}")
        after = Counter(ProductReference.objects.filter(product_id__in=pids)
                        .values_list('citation_role', flat=True))

        self.stdout.write("\n=== apply 结果 ===")
        self.stdout.write(f"  更新行数：{changed}；错误：{errors}")
        self.stdout.write(f"  before：{dict(before)}")
        self.stdout.write(f"  after ：{dict(after)}")
        self.stdout.write(self.style.SUCCESS("\n完成。"))
