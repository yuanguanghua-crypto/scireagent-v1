"""backfill_reference_fields —— 用 PubMed esummary 批量回填 Reference 缺失字段。

背景（2026-09-15 生产只读实测）：
生产库 `knowledge.Reference` 345 条，其中 330 条有 pmid，但 year 仅 167 / doi 194 /
authors 仅 102。根因不是落库丢字段，而是**写库时的缓存记录是精简形状**
（`{"pmid","title","source","doi"}`，pubdate/authors 从未取到）。

本命令按 PMID 批量调 PubMed esummary（`retmode=json`），回填
year / doi / authors / journal —— **只填空字段、绝不覆盖已有非空值**（宁缺毋滥）。

铁律 / 边界：
- 默认 dry-run：只统计 + 打印预测，**绝不写库**；`--apply` 才写。
- `Reference.doi` 与 `Reference.pmid` 均为 `unique`：回填 doi 若与其它行冲突，
  **跳过该字段继续**（不整批失败）。
- 写库用 `update_fields`，不整行覆盖 —— 避免碰 Postgres 的 `search_vector` 等
  由触发器/其它路径维护的列。
- 不改任何 model、不加 migration、不动 `apps/bridges/services/*`。

用法：
    python manage.py backfill_reference_fields                 # dry-run（默认）
    python manage.py backfill_reference_fields --apply         # 写库
    python manage.py backfill_reference_fields --limit 50
    python manage.py backfill_reference_fields --ids 1,2,3
"""
import re

from django.core.management.base import BaseCommand
from django.db import IntegrityError
from django.db.models import Q

from apps.knowledge.models import Reference
from core.datasource_client import request_with_resilience

ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
BATCH_SIZE = 100        # esummary 单次 id 上限
AUTHORS_MAX = 20        # 只取前 20 位作者
DOI_MAX = 100           # 与 Reference.doi max_length 一致
JOURNAL_MAX = 255       # 与 Reference.journal max_length 一致
BACKFILL_FIELDS = ('year', 'doi', 'authors', 'journal')


def _parse_year(pubdate) -> int | None:
    """'2024' / '2024 Jan' / '2023 Dec 15' → 2024 / 2024 / 2023；解析不出返回 None。"""
    if not pubdate:
        return None
    m = re.match(r"\s*(\d{4})", str(pubdate))
    if not m:
        return None
    y = int(m.group(1))
    return y if 1000 <= y <= 2999 else None


def _parse_doi(entry: dict) -> str:
    """优先 elocationid（'doi:10.x/y'），其次 articleids 里 idtype=='doi'。"""
    eloc = (entry.get("elocationid") or "").strip()
    if eloc.lower().startswith("doi:"):
        d = eloc[4:].strip()
        if d:
            return d
    for aid in (entry.get("articleids") or []):
        if isinstance(aid, dict) and (aid.get("idtype") or "").lower() == "doi":
            v = (aid.get("value") or "").strip()
            if v:
                return v
    return ""


def _parse_authors(entry: dict) -> str:
    names = []
    for a in (entry.get("authors") or [])[:AUTHORS_MAX]:
        n = (a.get("name") or "").strip() if isinstance(a, dict) else ""
        if n:
            names.append(n)
    return ", ".join(names)


def _fetch_batch(pmids: list) -> dict:
    """调 esummary，返回 result 字典（含 pmid → entry）。异常向调用方抛出。"""
    params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "json"}
    r = request_with_resilience(
        "GET", ESUMMARY_URL, source="pubmed", timeout=20, params=params)
    r.raise_for_status()
    data = r.json() or {}
    return data.get("result", {}) or {}


def _count_nonempty(field: str) -> int:
    if field == "year":
        return Reference.objects.exclude(year__isnull=True).count()
    return (Reference.objects.exclude(**{f"{field}__isnull": True})
            .exclude(**{field: ""}).count())


def _save_changes(ref, changes: dict) -> None:
    """只写变更列（+ updated_at），不整行覆盖。"""
    for k, v in changes.items():
        setattr(ref, k, v)
    fields = list(changes.keys())
    fields.append("updated_at")  # TimeStampedModel.updated_at=auto_now，需显式列入才刷新
    ref.save(update_fields=fields)


class Command(BaseCommand):
    help = ("Backfill Reference year/doi/authors/journal from PubMed esummary "
            "(dry-run by default; --apply to persist).")

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='写库（默认 dry-run，绝不写）')
        parser.add_argument('--limit', type=int, default=None,
                            help='只处理前 N 条（按 id 升序）')
        parser.add_argument('--ids', default=None,
                            help='只处理指定 Reference id，逗号分隔')

    def handle(self, *args, **options):
        apply = options['apply']

        qs = Reference.objects.exclude(
            Q(pmid__isnull=True) | Q(pmid='')).order_by('id')
        if options['ids']:
            try:
                ids = [int(x) for x in options['ids'].split(',') if x.strip()]
            except ValueError:
                self.stderr.write(self.style.ERROR("--ids 必须是逗号分隔的整数"))
                return
            qs = qs.filter(id__in=ids)
        if options['limit'] is not None:
            qs = qs[:options['limit']]
        refs = list(qs)
        total = len(refs)

        self.stdout.write("=== backfill_reference_fields ===")
        self.stdout.write("模式：" + ("apply (写库)" if apply else "dry-run (仅统计)"))
        self.stdout.write(f"[目标] 有 pmid 的 Reference：{total}")

        # ---- 取数（分批）----
        pmids = [r.pmid for r in refs]
        entries = {}
        batches = 0
        fail_batches = 0
        for i in range(0, len(pmids), BATCH_SIZE):
            chunk = pmids[i:i + BATCH_SIZE]
            batches += 1
            try:
                res = _fetch_batch(chunk)
            except Exception as e:  # noqa: BLE001 —— 单批失败不阻塞整体
                fail_batches += 1
                self.stderr.write(f"  批次 {batches} 失败：{e}")
                continue
            for pmid in chunk:
                ent = res.get(pmid)
                if isinstance(ent, dict):
                    entries[pmid] = ent
        self.stdout.write(
            f"[取数] 请求 {batches} 批（失败 {fail_batches}），命中 {len(entries)}/{total}")

        # ---- 生成回填计划 ----
        existing_doi = dict(
            Reference.objects.exclude(doi__isnull=True).exclude(doi='')
            .values_list('doi', 'id'))
        plan = []
        counts = {f: 0 for f in BACKFILL_FIELDS}
        for r in refs:
            ent = entries.get(r.pmid)
            if not ent:
                continue
            changes = {}
            if r.year is None:
                y = _parse_year(ent.get('pubdate'))
                if y:
                    changes['year'] = y
            if not r.doi:
                d = _parse_doi(ent)
                if d and len(d) <= DOI_MAX:
                    changes['doi'] = d
            if not r.authors:
                a = _parse_authors(ent)
                if a:
                    changes['authors'] = a
            if not r.journal:
                j = (ent.get('source') or '').strip()
                if j:
                    changes['journal'] = j[:JOURNAL_MAX]
            if changes:
                plan.append((r, changes))
                for f in changes:
                    counts[f] += 1

        self.stdout.write("[预测将回填]")
        for f in BACKFILL_FIELDS:
            self.stdout.write(f"  {f:<8}：{counts[f]}")
        self.stdout.write(f"  (合计待更新行：{len(plan)})")

        if not apply:
            self.stdout.write(self.style.WARNING(
                "\n[dry-run] 本次未写库；加 --apply 才落盘。"))
            return

        # ---- 落库 ----
        before = {f: _count_nonempty(f) for f in BACKFILL_FIELDS}
        applied = 0
        skipped_doi = 0
        errors = 0
        for r, changes in plan:
            if 'doi' in changes:
                other = existing_doi.get(changes['doi'])
                if other is not None and other != r.id:
                    skipped_doi += 1
                    changes = {k: v for k, v in changes.items() if k != 'doi'}
                    if not changes:
                        continue
            try:
                _save_changes(r, changes)
                applied += 1
                if 'doi' in changes:
                    existing_doi[changes['doi']] = r.id
            except IntegrityError as e:
                errors += 1
                self.stderr.write(f"  id={r.id} 保存失败：{e}")
        after = {f: _count_nonempty(f) for f in BACKFILL_FIELDS}

        self.stdout.write("\n=== apply 结果 ===")
        self.stdout.write(
            f"  更新行数：{applied}；doi 冲突跳过：{skipped_doi}；错误：{errors}")
        for f in BACKFILL_FIELDS:
            self.stdout.write(f"  {f:<8}：{before[f]} -> {after[f]}")
        self.stdout.write(self.style.SUCCESS("\n完成。"))
