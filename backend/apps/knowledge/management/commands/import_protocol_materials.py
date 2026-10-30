"""
import_protocol_materials — 从 BioProCorpus 原始 JSON 把 `input` 解析成 ProtocolMaterial 逐条清单。

背景（2026-10-30 实测）：
  `protocol` 表的 materials / reagents / equipment 三个 TextField 在
  `source='bioprocorpus'` 的 13,971 条记录上**结构性全零** —— 导入时 `input` 字段被整段丢弃。
  而语料本身是条目化的：Bio-protocol 85.5% 的记录在第一个 `#` 之前有一段编号清单，
  80.6% 的条目带 catalog number。⇒ 纯本地解析即可恢复，零 LLM、零网络。

覆盖边界（**不要把它读成「全库 14,128 条都有材料」**）：
  | 源 | 库内条数 | 可解析 | 备注 |
  |---|---|---|---|
  | Bio-protocol | 4,194 | 4,045 | 结构规整，质量最好 |
  | Protocol-exchange | 930 | 845 | 空行分隔无编号，质量较低 |
  | Protocol-io | 8,821 | **0** | **原始 JSON 无 `input` 字段** ⇒ 语料本身没有 |
  ⇒ 全库最多 34.6% 能长出材料清单。

铁律：
- **零 LLM、零网络**：只读本地语料 JSON。
- **保真硬闸门**：每条 `raw_line` 必须是原文（压缩空白后）的子串；**任一失败即中止**，
  不允许「差不多」写库。
- **宁 miss 不错配**：标题归一化后必须完全相等；同一标题命中多条语料则跳过（歧义）。
- 幂等：默认跳过已有材料的协议；`--purge` 才先删后重建。
- dry-run 默认，必须显式 `--apply` 才写库。

用法：
  python manage.py import_protocol_materials --dry-run
  python manage.py import_protocol_materials --source bioprotocol --apply
  python manage.py import_protocol_materials --source protocol_exchange --apply
  python manage.py import_protocol_materials --purge --apply     # 重建
  python manage.py import_protocol_materials --verify
"""
import json
import os
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Protocol, ProtocolMaterial
from apps.knowledge.services.protocol_materials_parser import (
    is_faithful,
    normalize_title,
    parse_materials,
)

DEFAULT_CORPUS_DIR = '/app/backend/data/bioprocorpus'

# 只认这三份协议语料；ERR/GEN/ORD/PQA.json 是 BioProBench 其他子集，无 input/协议结构
CORPUS_FILES = {
    'Bio-protocol.json': 'bioprotocol',
    'Protocol-exchange.json': 'protocol_exchange',
    'Protocol-io.json': 'protocol_io',   # 无 input 字段，解析必然 0 条，保留以便统计显形
}

BATCH = 2000
SAMPLE_N = 6


class Command(BaseCommand):
    help = '从语料 input 解析协议材料清单，写入 ProtocolMaterial（零 LLM、保真校验、幂等）'

    def add_arguments(self, parser):
        parser.add_argument('--corpus-dir', default=DEFAULT_CORPUS_DIR)
        parser.add_argument('--source', default='all',
                            choices=['all', 'bioprotocol', 'protocol_exchange', 'protocol_io'])
        parser.add_argument('--apply', action='store_true', help='真正写库；不加则预演')
        parser.add_argument('--dry-run', action='store_true', help='显式预演（默认行为）')
        parser.add_argument('--purge', action='store_true',
                            help='先删除该协议的已有材料条目再重建（默认跳过已有）')
        parser.add_argument('--verify', action='store_true', help='落库后统计核查')
        parser.add_argument('--limit', type=int, default=0, help='只处理前 N 条语料（调试）')

    # ---------- 主流程 ----------

    def handle(self, *args, **opts):
        if opts['verify']:
            return self._verify()

        corpus_dir = opts['corpus_dir']
        if not os.path.isdir(corpus_dir):
            raise CommandError(f'语料目录不存在：{corpus_dir}')

        wanted = CORPUS_FILES if opts['source'] == 'all' else {
            fn: tag for fn, tag in CORPUS_FILES.items() if tag == opts['source']}
        if not wanted:
            raise CommandError(f'未知的 --source：{opts["source"]}')

        apply_mode, purge = opts['apply'], opts['purge']
        limit = opts['limit']

        self.stdout.write(f'语料目录：{corpus_dir}')
        self.stdout.write(f'模式：{"APPLY（写库）" if apply_mode else "DRY-RUN（不写库）"}'
                          f'｜purge：{"是" if purge else "否"}')

        grand = Counter()
        samples = []
        faithful_failures = []
        claimed = set()   # 跨源去重：一个协议只归第一个命中它的源

        for filename, tag in wanted.items():
            path = os.path.join(corpus_dir, filename)
            if not os.path.isfile(path):
                self.stdout.write(self.style.WARNING(f'  [skip] 缺少 {filename}'))
                continue

            self.stdout.write(f'\n=== {filename} → corpus_source={tag} ===')
            with open(path, 'r', encoding='utf-8') as fh:
                rows = json.load(fh)
            if limit:
                rows = rows[:limit]

            # 语料侧索引：normalized title → [(input_text, corpus_id), ...]
            idx = {}
            with_input = 0
            for r in rows:
                title = r.get('title') or ''
                text = r.get('input') or ''
                cid = (r.get('id') or '').strip()
                if not title or not cid:
                    continue
                if text.strip():
                    with_input += 1
                idx.setdefault(normalize_title(title), []).append((text, cid))

            grand['corpus_rows'] += len(rows)
            grand['corpus_with_input'] += with_input
            self.stdout.write(f'  语料 {len(rows)} 条｜有 input {with_input} 条'
                              f'｜归一化标题 {len(idx)} 个')

            # 库侧：按标题匹配
            qs = Protocol.objects.all().only('id', 'name')
            targets = []      # [(protocol_id, input_text, corpus_id)]
            scanned = ambiguous = 0
            for p in qs.iterator(chunk_size=1000):
                if p.id in claimed:
                    continue
                hits = idx.get(normalize_title(p.name))
                if not hits:
                    continue
                scanned += 1
                if len(hits) > 1:
                    texts = {t for t, _ in hits}
                    if len(texts) != 1:
                        ambiguous += 1
                        continue
                targets.append((p.id, hits[0][0], hits[0][1]))
                claimed.add(p.id)

            grand['matched'] += len(targets)
            grand['ambiguous'] += ambiguous
            self.stdout.write(f'  匹配协议 {len(targets)}｜跨源同名跳过 {ambiguous}')

            # 解析 + 保真校验
            per_protocol = []
            parse_fail = 0
            for pid, text, cid in targets:
                if not (text or '').strip():
                    grand['empty_input'] += 1
                    continue
                try:
                    items = parse_materials(text)
                except Exception as exc:  # 脏数据不该中断整批，但要显形
                    parse_fail += 1
                    if parse_fail <= 3:
                        self.stdout.write(self.style.WARNING(
                            f'    [parse-fail] {cid}: {type(exc).__name__}: {exc}'))
                    continue
                if not items:
                    grand['parsed_zero'] += 1
                    continue
                bad = [it for it in items if not is_faithful(it['raw_line'], text)]
                if bad:
                    faithful_failures.append((cid, len(bad), bad[0]['raw_line'][:120]))
                    continue
                for it in items:
                    grand['items'] += 1
                    grand['kind_' + it['kind']] += 1
                    if it['vendor']:
                        grand['with_vendor'] += 1
                    if it['catalog_no']:
                        grand['with_catalog'] += 1
                grand['parsed_protocols'] += 1
                per_protocol.append((pid, items))
                if len(samples) < SAMPLE_N:
                    samples.append((cid, pid, items[:3]))

            grand['parse_fail'] += parse_fail
            self.stdout.write(f'  解析成功协议 {len(per_protocol)}'
                              f'｜条目 {sum(len(x) for _, x in per_protocol)}'
                              f'｜解析异常 {parse_fail}｜保真失败协议 {len(faithful_failures)}')

            if apply_mode and per_protocol:
                written = self._write(per_protocol, purge)
                grand['written'] += written
                self.stdout.write(self.style.SUCCESS(f'  已写入 {written} 条'))
            elif per_protocol:
                self.stdout.write('  （dry-run 未写库）')

        # ---------- 保真闸门 ----------
        if faithful_failures:
            self.stdout.write(self.style.ERROR(
                f'\n✗ 保真校验失败 {len(faithful_failures)} 个协议 —— 已全部跳过，未写库。'))
            for cid, n, sample in faithful_failures[:5]:
                self.stdout.write(f'    {cid}｜{n} 条不保真｜例：{sample}')
            self.stdout.write(self.style.ERROR(
                '保真失败是硬闸门：说明 raw_line 被改写过，必须修解析器而不是放宽校验。'))

        # ---------- 汇总 ----------
        self.stdout.write('\n' + '=' * 66)
        self.stdout.write(f'  语料条数            {grand["corpus_rows"]}')
        self.stdout.write(f'  语料有 input        {grand["corpus_with_input"]}')
        self.stdout.write(f'  匹配协议            {grand["matched"]}'
                          f'（空 input {grand["empty_input"]}｜解析空 {grand["parsed_zero"]}'
                          f'｜歧义 {grand["ambiguous"]}）')
        self.stdout.write(f'  解析成功协议        {grand["parsed_protocols"]}')
        self.stdout.write(f'  条目总数            {grand["items"]}')
        if grand['items']:
            self.stdout.write(f'    含 vendor         {grand["with_vendor"]}'
                              f' ({grand["with_vendor"] * 100.0 / grand["items"]:.1f}%)')
            self.stdout.write(f'    含 catalog_no     {grand["with_catalog"]}'
                              f' ({grand["with_catalog"] * 100.0 / grand["items"]:.1f}%)')
        self.stdout.write('  kind 分布：')
        for k, v in sorted(((k[5:], v) for k, v in grand.items() if k.startswith('kind_')),
                           key=lambda x: -x[1]):
            self.stdout.write(f'    {k:<22} {v}')
        if apply_mode:
            self.stdout.write(self.style.SUCCESS(f'  实际写入            {grand["written"]}'))

        if samples:
            self.stdout.write(f'\n样本（前 {len(samples)} 个协议）：')
            for cid, pid, items in samples:
                self.stdout.write(f'  {cid} → protocol.id={pid}')
                for it in items:
                    tag = f"{it['vendor']}" + (f" / {it['catalog_no']}" if it['catalog_no'] else '')
                    self.stdout.write(f'    [{it["kind"]:<20}] {it["name"][:46]}'
                                      + (f'  ({tag})' if tag else ''))

        if not apply_mode:
            self.stdout.write('\n这是预演。确认无误后加 --apply 写库。')

    # ---------- 写库 ----------

    def _write(self, per_protocol, purge):
        total = 0
        with transaction.atomic():
            pids = [pid for pid, _ in per_protocol]
            if purge:
                ProtocolMaterial.objects.filter(protocol_id__in=pids).delete()
            else:
                # 默认幂等：已有材料的协议整体跳过，避免半新半旧
                existing = set(
                    ProtocolMaterial.objects.filter(protocol_id__in=pids)
                    .values_list('protocol_id', flat=True).distinct())
                per_protocol = [(pid, items) for pid, items in per_protocol if pid not in existing]

            buf = []
            for pid, items in per_protocol:
                for it in items:
                    buf.append(ProtocolMaterial(
                        protocol_id=pid, seq=it['seq'], kind=it['kind'], ordinal=it['ordinal'],
                        name=it['name'], vendor=it['vendor'], catalog_no=it['catalog_no'],
                        model_no=it['model_no'], section_heading=it['section_heading'],
                        raw_line=it['raw_line'],
                    ))
                if len(buf) >= BATCH:
                    ProtocolMaterial.objects.bulk_create(buf, batch_size=BATCH)
                    total += len(buf)
                    buf = []
            if buf:
                ProtocolMaterial.objects.bulk_create(buf, batch_size=BATCH)
                total += len(buf)
        return total

    # ---------- 核查 ----------

    def _verify(self):
        from django.db.models import Count, Max, Q

        total_protocols = Protocol.objects.count()
        with_items = ProtocolMaterial.objects.values('protocol_id').distinct().count()
        stats = ProtocolMaterial.objects.aggregate(
            n=Count('id'),
            with_vendor=Count('id', filter=Q(vendor__gt='')),
            with_catalog=Count('id', filter=Q(catalog_no__gt='')),
        )
        self.stdout.write(f'协议总数              {total_protocols}')
        self.stdout.write(f'有材料的协议          {with_items}'
                          f'（{with_items * 100.0 / max(total_protocols, 1):.1f}%）')
        self.stdout.write(f'材料条目总数          {stats["n"]}')
        if stats['n']:
            self.stdout.write(f'  含 vendor           {stats["with_vendor"]}'
                              f'（{stats["with_vendor"] * 100.0 / stats["n"]:.1f}%）')
            self.stdout.write(f'  含 catalog_no       {stats["with_catalog"]}'
                              f'（{stats["with_catalog"] * 100.0 / stats["n"]:.1f}%）')

        self.stdout.write('\n按 kind：')
        for row in (ProtocolMaterial.objects.values('kind').annotate(n=Count('id')).order_by('-n')):
            self.stdout.write(f'  {row["kind"]:<22} {row["n"]}')

        # 一致性：每个协议的 seq 必须从 1 起连续（解析器保证），否则视图排序会错位
        gaps = 0
        for row in (ProtocolMaterial.objects.values('protocol_id')
                    .annotate(n=Count('id'), mx=Max('seq'))):
            if row['mx'] != row['n']:
                gaps += 1
        self.stdout.write(f'\nseq 连续性：{gaps} 个协议异常'
                          + (' (OK)' if gaps == 0 else ' (需检查)'))

        self.stdout.write('\n抽样 5 个协议：')
        for pid in (ProtocolMaterial.objects.values_list('protocol_id', flat=True)
                    .distinct().order_by('?')[:5]):
            p = Protocol.objects.filter(pk=pid).first()
            n = ProtocolMaterial.objects.filter(protocol_id=pid).count()
            self.stdout.write(f'  protocol.id={pid}｜{n} 条｜{(p.name if p else "")[:50]}')
