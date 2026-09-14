"""adopt_cached_evidence —— 批量把外部文献缓存（Bioz / PubMed）落库为产品级证据。

背景：平台已集成 Bioz / PubMed 文献接口，结果缓存在 apps.documents.DataSourceCache
（生产实测：bioz 247 行查询 / 68 行有结果 / 271 篇；pubmed 125 / 68 / 248 篇）。
但落库路径只有"单产品"（apps.commerce.services.bioz_adopter.adopt_bioz_references +
一个 API + admin inline），生产上 ProductReference 仅 4 条、挂在 1 个产品上——
约 519 篇已抓文献躺在缓存里没变成关联边。

本命令提供"批量落库"入口：
- 默认 dry-run：绝不写任何表；只统计 + 产出处置计划 JSONL（--out）。
- --apply：逐产品调 adopt_bioz_references（唯一写入口），汇总增量，打印"预测 vs 实际"。

铁律（防止"双实现"血教训）：
- 复用 apps.commerce.services.bioz_adopter.adopt_bioz_references 作为**唯一写入口**，
  不自己写 Reference / ProductReference 创建逻辑。
- dry-run 用 bioz_adopter._find_existing / _extract_year 判断"是否需新建 Reference"，
  保证 dry-run 与 apply 规则一致（见文件顶部注释）。
- 不改任何模型、不加 migration、不动 relevance.py、不改 adopt_bioz_references 签名。

键解析复刻 apps.bridges.services.relevance.load_product_bioz：
  _product_evidence_keys(product) = [catalog_no] + [sku.sku_code ...]，去空、保序、去重。
（不修改 relevance.py，但 test 证明两者键集合一致。）

确定性顺序：产品按 id 升序 → source 按参数顺序 → 记录按缓存内原始顺序。

用法：
    python manage.py adopt_cached_evidence                       # dry-run（默认，不落库）
    python manage.py adopt_cached_evidence --apply               # 落库
    python manage.py adopt_cached_evidence --source bioz        # 只处理 bioz
    python manage.py adopt_cached_evidence --role primary       # 指定引用角色
    python manage.py adopt_cached_evidence --limit 10
    python manage.py adopt_cached_evidence --only-products SC8001,SC8002
    python manage.py adopt_cached_evidence --out plan.jsonl
"""
# 复用 bioz_adopter 的查重/年份规则，避免 dry-run 与 apply 两套规则漂移。
from apps.commerce.services.bioz_adopter import (
    adopt_bioz_references,
    _find_existing,
    _extract_year,
)

import itertools
import json
import statistics

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.bridges.models import ProductReference
from apps.commerce.models import Product
from apps.documents.models import DataSourceCache
from apps.knowledge.models import Reference


def _product_evidence_keys(product):
    """产品→缓存键集合（复刻 load_product_bioz）。

    = [product.catalog_no] + [sku.sku_code for sku in product.skus.all()]，
    去空值、保序、去重。
    """
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
    # 去空、保序、去重
    seen = set()
    out = []
    for k in keys:
        if k and k not in seen:
            seen.add(k)
            out.append(k)
    return out


def _normalize(rec, source, counts):
    """把一条缓存记录归一化为 bioz 形状的统一 dict。

    返回 (norm_dict, plan_action) 或 (None, 'skip_no_title')。
    norm_dict: {article_title, authors, journal, pub_date, doi, pmid}
    """
    if source == DataSourceCache.Source.PUBMED:
        article_title = (rec.get('title') or '').strip()
        authors = rec.get('authors') or []
        journal = (rec.get('source') or '').strip()
        pub_date = rec.get('pubdate')
        doi = (rec.get('doi') or '').strip()
        pmid = (rec.get('pmid') or '').strip()
    else:  # bioz（默认）
        article_title = (rec.get('article_title') or '').strip()
        authors = rec.get('authors') or []
        journal = (rec.get('journal') or '').strip()
        pub_date = rec.get('pub_date')
        doi = (rec.get('doi') or '').strip()
        pmid = (rec.get('pmid') or '').strip()

    # 空 title → 跳过
    if not article_title:
        counts['skipped_no_title'] += 1
        return None, 'skip_no_title'

    # 字段长度守卫
    if len(article_title) > 500:
        article_title = article_title[:500]
        counts['truncated_title'] += 1
    if len(journal) > 255:
        journal = journal[:255]
        counts['truncated_journal'] += 1
    if len(doi) > 100:
        # 丢弃过长 doi，保留 pmid（若也有）
        doi = ''
        counts['dropped_long_doi'] += 1
    if len(pmid) > 50:
        pmid = ''
        counts['dropped_long_pmid'] += 1

    norm = {
        'article_title': article_title,
        'authors': authors,
        'journal': journal,
        'pub_date': pub_date,
        'doi': doi,
        'pmid': pmid,
    }
    return norm, 'ok'


class Command(BaseCommand):
    help = (
        "Batch-adopt cached Bioz/PubMed evidence into Reference + ProductReference "
        "(dry-run by default; --apply to persist via adopt_bioz_references)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Persist evidence via adopt_bioz_references '
                 '(default: dry-run only, never writes).',
        )
        parser.add_argument(
            '--source', default='bioz,pubmed',
            help='Comma-separated sources in processing order '
                 '(default: bioz,pubmed).',
        )
        parser.add_argument(
            '--role', default='supporting',
            help='ProductReference.citation_role (primary/supporting/'
                 'validation/background; default supporting).',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Only process the first N products (by id) for a smoke test.',
        )
        parser.add_argument(
            '--only-products', default=None,
            help='Comma-separated catalog_no whitelist.',
        )
        parser.add_argument(
            '--out', default=None,
            help='Write one JSONL disposition-plan line per candidate record.',
        )

    # ------------------------------------------------------------------
    # 跨产品内存模拟（dry-run 预测，保证与 apply 增量一致）
    # ------------------------------------------------------------------
    def _make_sim(self):
        """返回内存模拟状态 dict。"""
        return {
            'sim_doi': {},
            'sim_pmid': {},
            'sim_title': {},
            'sim_links': set(),
            'ref_counter': itertools.count(-1),
        }

    def _find_existing_sim(self, sim, doi, pmid, title):
        """降级查重模拟：先查真实 DB（_find_existing），再查内存 planned 索引。

        返回 ('db', Reference) / ('sim', ref_id) / None。
        """
        real = _find_existing(doi, pmid, title)
        if real is not None:
            return ('db', real)
        doi_s = (doi or '').strip()
        pmid_s = (pmid or '').strip()
        title_s = (title or '').strip().lower()
        if doi_s and doi_s in sim['sim_doi']:
            return ('sim', sim['sim_doi'][doi_s])
        if pmid_s and pmid_s in sim['sim_pmid']:
            return ('sim', sim['sim_pmid'][pmid_s])
        if title_s and title_s in sim['sim_title']:
            return ('sim', sim['sim_title'][title_s])
        return None

    def _simulate_record(self, sim, counts, product, norm, role):
        """对单条归一化记录做跨产品解析模拟，更新计数，返回 (ref_action, link_action)。

        ref_action: 'reuse_db' | 'reuse_planned' | 'plan_new'
        link_action: 'create_link' | 'reuse_link'
        """
        doi = norm['doi']
        pmid = norm['pmid']
        title = norm['article_title']

        res = self._find_existing_sim(sim, doi, pmid, title)
        if res is None:
            # 计划新建 Reference
            counts['refs_planned_new'] += 1
            ref_id = next(sim['ref_counter'])
            doi_s = (doi or '').strip()
            pmid_s = (pmid or '').strip()
            title_s = (title or '').strip().lower()
            if doi_s:
                sim['sim_doi'][doi_s] = ref_id
            if pmid_s:
                sim['sim_pmid'][pmid_s] = ref_id
            if title_s:
                sim['sim_title'][title_s] = ref_id
            ref_action = 'plan_new'
            is_db = False
        elif res[0] == 'db':
            counts['refs_reused_from_db'] += 1
            ref_id = res[1].id
            ref_action = 'reuse_db'
            is_db = True
        else:  # ('sim', ref_id) —— 本 run 内先前计划新建的引用，复用，不重复计数
            counts['refs_reused_from_plan'] += 1
            ref_id = res[1]
            ref_action = 'reuse_planned'
            is_db = False

        # 关联判断
        link_key = (product.id, ref_id, role)
        if is_db:
            # 真实 DB 引用：直接查 ProductReference 表
            exists = ProductReference.objects.filter(
                product_id=product.id, reference_id=ref_id, citation_role=role
            ).exists()
        else:
            # 计划中未落库的引用：用内存 link 集合模拟
            exists = link_key in sim['sim_links']

        if exists:
            counts['links_already_exist'] += 1
            link_action = 'reuse_link'
        else:
            if not is_db:
                sim['sim_links'].add(link_key)
            counts['links_to_create'] += 1
            link_action = 'create_link'

        return ref_action, link_action

    # ------------------------------------------------------------------
    # 主流程
    # ------------------------------------------------------------------
    def handle(self, *args, **options):
        apply = options['apply']
        sources = [s.strip() for s in options['source'].split(',') if s.strip()]
        role = options['role']
        limit = options['limit']
        only = ([s.strip() for s in options['only_products'].split(',') if s.strip()]
                if options['only_products'] else None)
        out_path = options['out']

        # 校验 role
        valid_roles = ProductReference.CitationRole.values
        if role not in valid_roles:
            raise CommandError(
                f"无效 citation_role: {role!r}（合法值：{valid_roles}）"
            )
        # 校验 source
        valid_sources = DataSourceCache.Source.values
        for s in sources:
            if s not in valid_sources:
                raise CommandError(
                    f"无效 source: {s!r}（合法值：{valid_sources}）"
                )

        now = timezone.now()

        # 产品查询集（确定性：id 升序）
        products = Product.objects.order_by('id')
        if only:
            products = products.filter(catalog_no__in=only)
        if limit is not None:
            products = products[:limit]
        product_list = list(products)
        products_total = len(product_list)

        counts = {
            'rows_hit': 0,
            'rows_stale': 0,
            'records_raw': 0,
            'records_unique': 0,
            'refs_reused_from_db': 0,
            'refs_reused_from_plan': 0,
            'refs_planned_new': 0,
            'dup_within_product': 0,
            'skipped_no_title': 0,
            'links_to_create': 0,
            'links_already_exist': 0,
            'truncated_title': 0,
            'truncated_journal': 0,
            'dropped_long_doi': 0,
            'dropped_long_pmid': 0,
        }
        per_source_unique = {s: 0 for s in ('bioz', 'pubmed')}
        per_product_evidence = {}      # product_id -> unique 记录数
        per_product_create_links = {}  # product_id -> planned 新建链接数
        per_product_catalog = {}      # product_id -> catalog_no
        plan_lines = []
        per_product_records = {}      # product_id -> [normalized 唯一 dict]

        products_scanned = 0
        products_with_evidence = 0
        products_no_key = 0

        sim = self._make_sim()

        for product in product_list:
            keys = _product_evidence_keys(product)
            if not keys:
                products_no_key += 1
                per_product_records[product.id] = []
                continue
            products_scanned += 1
            per_product_catalog[product.id] = product.catalog_no

            rows = list(
                DataSourceCache.objects.filter(
                    source__in=sources, query_key__in=keys
                ).order_by('id')
            )
            seen_tuples = set()
            recs_for_product = []
            prod_unique = 0

            for row in rows:
                counts['rows_hit'] += 1
                if (row.expires_at and row.expires_at <= now) or row.is_stale:
                    counts['rows_stale'] += 1
                data = row.get_data()
                recs = (data if isinstance(data, list)
                        else ([data] if isinstance(data, dict) else []))
                for rec in recs:
                    if not isinstance(rec, dict):
                        continue
                    norm, action = _normalize(rec, row.source, counts)
                    if norm is None:
                        # skip_no_title 已在 _normalize 内计数
                        plan_lines.append({
                            'mode': 'preview',
                            'dry_run': not apply,
                            'product_id': product.id,
                            'catalog_no': product.catalog_no,
                            'source': row.source,
                            'action': 'skip_no_title',
                            'article_title': '',
                            'doi': '',
                            'pmid': (rec.get('pmid') or '') if isinstance(rec, dict) else '',
                            'role': role,
                        })
                        continue
                    counts['records_raw'] += 1
                    dkey = (
                        (norm['doi'] or '').lower(),
                        norm['pmid'] or '',
                        norm['article_title'].lower(),
                    )
                    if dkey in seen_tuples:
                        counts['dup_within_product'] += 1
                        continue
                    seen_tuples.add(dkey)

                    ref_action, link_action = self._simulate_record(
                        sim, counts, product, norm, role
                    )
                    per_source_unique[row.source] = (
                        per_source_unique.get(row.source, 0) + 1
                    )
                    plan_lines.append({
                        'mode': 'preview',
                        'dry_run': not apply,
                        'product_id': product.id,
                        'catalog_no': product.catalog_no,
                        'source': row.source,
                        'action': 'adopt',
                        'ref_action': ref_action,
                        'link_action': link_action,
                        'article_title': norm['article_title'],
                        'doi': norm['doi'],
                        'pmid': norm['pmid'],
                        'year': _extract_year(norm['pub_date']),
                        'journal': norm['journal'],
                        'role': role,
                    })
                    recs_for_product.append(norm)
                    prod_unique += 1
                    if link_action == 'create_link':
                        per_product_create_links[product.id] = (
                            per_product_create_links.get(product.id, 0) + 1
                        )

            per_product_records[product.id] = recs_for_product
            if prod_unique > 0:
                products_with_evidence += 1
                per_product_evidence[product.id] = prod_unique

        counts['records_unique'] = counts['records_raw'] - counts['dup_within_product']
        products_zero = products_scanned - products_with_evidence

        # ---------- 报告 ----------
        self._report(
            apply=apply, counts=counts,
            products_total=products_total, products_scanned=products_scanned,
            products_with_evidence=products_with_evidence,
            products_zero=products_zero, products_no_key=products_no_key,
            per_source_unique=per_source_unique,
            per_product_evidence=per_product_evidence,
            per_product_create_links=per_product_create_links,
            per_product_catalog=per_product_catalog,
        )

        # ---------- 审计输出 ----------
        if out_path:
            try:
                with open(out_path, 'w', encoding='utf-8') as f:
                    for line in plan_lines:
                        f.write(json.dumps(line, ensure_ascii=False) + '\n')
            except OSError as e:
                # 发生在落库闸门之前 → 不会留下半写状态
                raise CommandError(f"--out 路径不可写：{out_path}（{e}）")
            self.stdout.write(
                f"\n处置计划已写出：{out_path}（{len(plan_lines)} 行，"
                f"{'preview' if not apply else 'applied'} 模式）"
            )

        # ---------- 落库闸门 ----------
        if not apply:
            self.stdout.write(self.style.WARNING(
                "\n[dry-run] 本次未写库；预测基于单线程确定性模拟，"
                "实际 --apply 可能因并发略少。"
            ))
            return

        # ---------- --apply：落库并对比 ----------
        ref_before = Reference.objects.count()
        link_before = ProductReference.objects.count()
        total_adopted = 0
        total_skipped = 0
        total_created_refs = 0
        apply_errors = []
        for product in product_list:
            recs = per_product_records.get(product.id, [])
            if not recs:
                continue
            res = adopt_bioz_references(product, recs, citation_role=role)
            total_adopted += res['adopted']
            total_skipped += res['skipped']
            total_created_refs += len(res['created_refs'])
            apply_errors.extend(res['errors'])

        actual_refs = Reference.objects.count() - ref_before
        actual_links = ProductReference.objects.count() - link_before

        self.stdout.write("\n=== 预测 vs 实际（--apply）===")
        self.stdout.write(
            f"新建 Reference：预测 {counts['refs_planned_new']} / 实际 {actual_refs}"
        )
        self.stdout.write(
            f"新建关联 links：预测 {counts['links_to_create']} / 实际 {actual_links}"
        )
        self.stdout.write(
            f"复用已有 Reference：{counts['refs_reused_from_db']}"
        )
        self.stdout.write(
            f"关联已存在(跳过)：预测 {counts['links_already_exist']} / "
            f"实际 {total_skipped}"
        )
        self.stdout.write(
            f"adopt_bioz_references 返回：新建引用 {total_created_refs} / "
            f"新建链接 {total_adopted} / 跳过链接 {total_skipped}"
        )

        # 长度守卫 + 错误（最多 20 条）
        self.stdout.write("\n长度守卫计数：")
        self.stdout.write(f"  truncated_title（标题截断>500）：{counts['truncated_title']}")
        self.stdout.write(f"  truncated_journal（期刊截断>255）：{counts['truncated_journal']}")
        self.stdout.write(f"  dropped_long_doi（丢弃过长 doi>100）：{counts['dropped_long_doi']}")
        self.stdout.write(f"  dropped_long_pmid（丢弃过长 pmid>50）：{counts['dropped_long_pmid']}")
        if apply_errors:
            self.stdout.write(f"\n落库错误（前 20 / 共 {len(apply_errors)} 条）：")
            for e in apply_errors[:20]:
                self.stdout.write(f"  - {e}")
        else:
            self.stdout.write("\n落库错误：无")

        self.stdout.write(self.style.SUCCESS(
            f"\n完成：新建 Reference {actual_refs} 条、ProductReference "
            f"{actual_links} 条（role={role}）。"
        ))

    # ------------------------------------------------------------------
    # 报告渲染
    # ------------------------------------------------------------------
    def _report(self, *, apply, counts, products_total, products_scanned,
                products_with_evidence, products_zero, products_no_key,
                per_source_unique, per_product_evidence,
                per_product_create_links, per_product_catalog):
        self.stdout.write("=== adopt_cached_evidence ===")
        self.stdout.write(
            "模式：" + ("apply (落库)" if apply else "dry-run (仅统计，不落库)")
        )

        self.stdout.write("\n[产品]")
        self.stdout.write(f"  products_total（考虑产品总数）：{products_total}")
        self.stdout.write(f"  products_scanned（已扫描/有键）：{products_scanned}")
        self.stdout.write(f"  products_with_evidence（有证据）：{products_with_evidence}")
        self.stdout.write(f"  products_zero（扫描但零证据）：{products_zero}")
        self.stdout.write(f"  products_no_key（无键跳过）：{products_no_key}")

        self.stdout.write("\n[记录]")
        self.stdout.write(f"  rows_hit（命中缓存行）：{counts['rows_hit']}")
        self.stdout.write(f"  rows_stale（过期仍用）：{counts['rows_stale']}")
        self.stdout.write(f"  records_raw（原始记录数）：{counts['records_raw']}")
        self.stdout.write(f"  records_unique（去产品内重后）：{counts['records_unique']}")

        self.stdout.write("\n[文献]")
        self.stdout.write(f"  refs_reused_from_db（复用已有）：{counts['refs_reused_from_db']}")
        self.stdout.write(f"  refs_reused_from_plan（复用本run计划新建）：{counts['refs_reused_from_plan']}")
        self.stdout.write(f"  refs_planned_new（计划新建）：{counts['refs_planned_new']}")
        self.stdout.write(
            "  口径自洽：records_unique = "
            f"{counts['refs_reused_from_db']} + {counts['refs_reused_from_plan']}"
            f" + {counts['refs_planned_new']} = "
            f"{counts['refs_reused_from_db'] + counts['refs_reused_from_plan'] + counts['refs_planned_new']}"
            f"（应为 {counts['records_unique']}）"
        )
        self.stdout.write(f"  dup_within_product（产品内重复）：{counts['dup_within_product']}")
        self.stdout.write(f"  skipped_no_title（空标题跳过）：{counts['skipped_no_title']}")

        self.stdout.write("\n[关联]")
        self.stdout.write(f"  links_to_create（计划新建）：{counts['links_to_create']}")
        self.stdout.write(f"  links_already_exist（已存在）：{counts['links_already_exist']}")

        # 分布：有证据产品的 min / 中位 / max 条文献
        ev_counts = sorted(per_product_evidence.values())
        if ev_counts:
            med = statistics.median(ev_counts)
            dist = (f"min={ev_counts[0]} / 中位={med} / max={ev_counts[-1]}")
        else:
            dist = "min=0 / 中位=0 / max=0"
        self.stdout.write(f"\n[分布] 有证据产品文献数：{dist}")

        self.stdout.write("\n[分源拆分] records_unique：")
        self.stdout.write(f"  bioz：{per_source_unique.get('bioz', 0)}")
        self.stdout.write(f"  pubmed：{per_source_unique.get('pubmed', 0)}")

        # Top 20 产品（按 planned links 降序）
        top = sorted(
            per_product_create_links.items(),
            key=lambda kv: (-kv[1], kv[0])
        )[:20]
        self.stdout.write("\n[Top 20 产品]（按 planned links 降序）")
        if top:
            for pid, n in top:
                self.stdout.write(
                    f"  {per_product_catalog.get(pid, '?')} "
                    f"(id={pid})：{n} links"
                )
        else:
            self.stdout.write("  (无)")

        # 长度守卫计数
        self.stdout.write("\n[长度守卫]")
        self.stdout.write(f"  truncated_title：{counts['truncated_title']}")
        self.stdout.write(f"  truncated_journal：{counts['truncated_journal']}")
        self.stdout.write(f"  dropped_long_doi：{counts['dropped_long_doi']}")
        self.stdout.write(f"  dropped_long_pmid：{counts['dropped_long_pmid']}")
