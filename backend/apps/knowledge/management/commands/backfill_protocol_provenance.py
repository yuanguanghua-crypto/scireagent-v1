"""
backfill_protocol_provenance — 从 BioProCorpus 原始 JSON 回填协议溯源四件套。

背景（2026-10-30 实测）：
  `protocol` 表原本**没有任何来源字段**，14,128 条协议全部无法追溯原文，
  客户和审核专家都无法验证「这份协议是不是编的」。
  而语料侧的覆盖极高：Bio-protocol 4,157/4,157 有 DOI、Protocol-exchange 927/933 有 DOI、
  Protocol-io 9,585/9,585 有 protocols.io URL。
  ⇒ 纯标题精确匹配即可回填 13,945 条（98.7%），**零外部调用、零 LLM**。

铁律：
- 零 LLM、零网络：只读本地语料 JSON。
- 宁 miss 不错配：标题归一化后必须**完全相等**才认；跨源同名（实测 5 条）跳过并报告。
- 只填空，不覆盖：以 `corpus_id` 是否为空判定「未回填」，已回填的一律跳过（幂等）。
- dry-run 默认：必须显式 --apply 才写库。

用法：
  # 预演（默认），打印统计与样本
  python manage.py backfill_protocol_provenance --dry-run
  # 只处理一个源
  python manage.py backfill_protocol_provenance --source bioprotocol
  # 真正写入
  python manage.py backfill_protocol_provenance --apply
  # 落库后核查
  python manage.py backfill_protocol_provenance --verify

语料来源标记（写入 Protocol.corpus_source）：
  bioprotocol / protocol_exchange / protocol_io
"""
import json
import os
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Protocol

DEFAULT_CORPUS_DIR = '/app/backend/data/bioprocorpus'

# 文件名 → corpus_source 取值。只认这三份协议语料；
# ERR/GEN/ORD/PQA.json 是 BioProBench 的其他子集，不含协议 id/url 结构，按白名单排除。
CORPUS_FILES = {
    'Bio-protocol.json': 'bioprotocol',
    'Protocol-exchange.json': 'protocol_exchange',
    'Protocol-io.json': 'protocol_io',
}

DOI_RE = re.compile(r'(10\.\d{4,9}/\S+)')
BATCH = 1000
SAMPLE_N = 5

from apps.knowledge.services.protocol_materials_parser import normalize_title  # noqa: E402  (单一实现，勿在此重复定义)


class Command(BaseCommand):
    help = '从 BioProCorpus 原始 JSON 回填 Protocol 的 doi/source_url/corpus_id/corpus_source'

    def add_arguments(self, parser):
        parser.add_argument('--corpus-dir', default=DEFAULT_CORPUS_DIR,
                            help=f'语料目录（默认 {DEFAULT_CORPUS_DIR}）')
        parser.add_argument('--source', default='all',
                            choices=['all', 'bioprotocol', 'protocol_exchange', 'protocol_io'],
                            help='只处理指定语料源（默认 all）')
        parser.add_argument('--apply', action='store_true',
                            help='真正写库；不加则只预演')
        parser.add_argument('--dry-run', action='store_true',
                            help='显式声明预演（与默认行为一致，仅为可读性）')
        parser.add_argument('--verify', action='store_true',
                            help='落库后核查四个字段的填充数量与一致性')
        parser.add_argument('--force', action='store_true',
                            help='覆盖已有 corpus_id 的记录（默认跳过，保证幂等）')
        parser.add_argument('--limit', type=int, default=0,
                            help='只处理前 N 条语料（调试用）')

    # ---------- 语料侧 ----------

    def _load_corpus(self, path, source_tag):
        """返回 {normalized_title: [(doi, url, corpus_id), ...]}"""
        with open(path, 'r', encoding='utf-8') as fh:
            rows = json.load(fh)

        idx = {}
        for r in rows:
            title = r.get('title') or ''
            url = (r.get('url') or '').strip()
            corpus_id = (r.get('id') or '').strip()
            if not title or not corpus_id:
                continue
            m = DOI_RE.search(url)
            doi = m.group(1).rstrip('.').strip() if m else ''
            key = normalize_title(title)
            if not key:
                continue
            idx.setdefault(key, []).append((doi, url, corpus_id))
        return idx, len(rows)

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

        apply_mode = opts['apply']
        force = opts['force']
        limit = opts['limit']

        self.stdout.write(f'语料目录：{corpus_dir}')
        self.stdout.write(f'模式：{"APPLY（写库）" if apply_mode else "DRY-RUN（不写库）"}'
                          f'｜覆盖已有：{"是" if force else "否"}')

        grand = {'corpus_records': 0, 'db_scanned': 0, 'matched': 0, 'with_doi': 0,
                 'with_url': 0, 'skipped_filled': 0, 'ambiguous': 0, 'unmatched': 0, 'written': 0}
        samples = []

        # ★ 跨源去重：一个协议只归第一个命中它的源。
        #   dry-run 必须与 apply 行为一致，否则预演数字会虚高（三源各算一遍全会重复计数）。
        claimed = set()
        first_round = True

        for filename, tag in wanted.items():
            path = os.path.join(corpus_dir, filename)
            if not os.path.isfile(path):
                self.stdout.write(self.style.WARNING(f'  [skip] 缺少 {filename}'))
                continue

            self.stdout.write(f'\n=== {filename} → corpus_source={tag} ===')
            idx, n_corpus = self._load_corpus(path, tag)
            grand['corpus_records'] += n_corpus
            self.stdout.write(f'  语料记录 {n_corpus} 条｜归一化标题 {len(idx)} 个')

            qs = Protocol.objects.all().only(
                'id', 'name', 'doi', 'source_url', 'corpus_id', 'corpus_source')
            if limit:
                qs = qs[:limit]

            to_update = []
            seen_ids = set()
            scanned = 0
            for p in qs.iterator(chunk_size=1000):
                scanned += 1
                if p.corpus_id and not force:
                    if first_round:
                        grand['skipped_filled'] += 1
                    continue
                if p.id in claimed:
                    continue
                hits = idx.get(normalize_title(p.name))
                if not hits:
                    continue
                if len(hits) > 1:
                    # 同一归一化标题在语料里出现多次：只有全部指向**同一个 (DOI, URL)**
                    # 才敢用。★ 判重必须用 (doi, url) 组合而不是只比 DOI ——
                    # 两条 protocols.io 记录没有 DOI（都是 ''），只比 DOI 会误判成
                    # "一致"从而随便挑一条，可能挂错原文链接。
                    targets = {(h[0], h[1]) for h in hits}
                    if len(targets) != 1:
                        grand['ambiguous'] += 1
                        continue
                doi, url, cid = hits[0]
                if not doi and not url:
                    continue
                if p.id in seen_ids:
                    continue
                seen_ids.add(p.id)
                p.doi = doi or ''
                p.source_url = url or ''
                p.corpus_id = cid
                p.corpus_source = tag
                to_update.append(p)
                claimed.add(p.id)
                grand['matched'] += 1
                if doi:
                    grand['with_doi'] += 1
                if url:
                    grand['with_url'] += 1
                if len(samples) < SAMPLE_N:
                    samples.append((p.id, p.name[:52], doi, url[:56], cid))

            if first_round:
                grand['db_scanned'] = scanned
            first_round = False
            self.stdout.write(f'  扫描协议 {scanned}｜本源命中 {len(to_update)}'
                              f'｜已回填跳过 {grand["skipped_filled"]}'
                              f'｜跨源歧义 {grand["ambiguous"]}')

            if apply_mode and to_update:
                written = 0
                with transaction.atomic():
                    for i in range(0, len(to_update), BATCH):
                        chunk = to_update[i:i + BATCH]
                        Protocol.objects.bulk_update(
                            chunk, ['doi', 'source_url', 'corpus_id', 'corpus_source'])
                        written += len(chunk)
                grand['written'] += written
                self.stdout.write(self.style.SUCCESS(f'  已写入 {written} 条'))
            elif to_update:
                self.stdout.write('  （dry-run 未写库）')

        # ---------- 汇总 ----------
        self.stdout.write('\n' + '=' * 66)
        self.stdout.write('汇总')
        self.stdout.write(f'  语料记录总数        {grand["corpus_records"]}')
        self.stdout.write(f'  扫描协议数          {grand["db_scanned"]}')
        self.stdout.write(f'  匹配成功            {grand["matched"]}'
                          f'（带 DOI {grand["with_doi"]}｜带 URL {grand["with_url"]}）')
        self.stdout.write(f'  已回填跳过（幂等）  {grand["skipped_filled"]}')
        grand['unmatched'] = (grand['db_scanned'] - grand['matched']
                              - grand['ambiguous'] - grand['skipped_filled'])
        self.stdout.write(f'  跨源歧义跳过        {grand["ambiguous"]}')
        self.stdout.write(f'  未匹配              {grand["unmatched"]}')
        if apply_mode:
            self.stdout.write(self.style.SUCCESS(f'  实际写入            {grand["written"]}'))

        if samples:
            self.stdout.write('\n样本（前 %d 条）：' % len(samples))
            for pid, name, doi, url, cid in samples:
                self.stdout.write(f'  id={pid:<6} {name}')
                self.stdout.write(f'         doi={doi or "-"}  corpus_id={cid}')
                self.stdout.write(f'         url={url}')

        if not apply_mode:
            self.stdout.write('\n这是预演。确认无误后加 --apply 写库。')

    # ---------- 核查 ----------

    def _verify(self):
        from django.db.models import Count, Q

        total = Protocol.objects.count()
        stats = Protocol.objects.aggregate(
            with_doi=Count('id', filter=Q(doi__gt='')),
            with_url=Count('id', filter=Q(source_url__gt='')),
            with_cid=Count('id', filter=Q(corpus_id__gt='')),
        )
        self.stdout.write(f'协议总数              {total}')
        self.stdout.write(f'doi 非空              {stats["with_doi"]}')
        self.stdout.write(f'source_url 非空       {stats["with_url"]}')
        self.stdout.write(f'corpus_id 非空        {stats["with_cid"]}')

        self.stdout.write('\n按 corpus_source：')
        for row in (Protocol.objects.values('corpus_source')
                    .annotate(n=Count('id')).order_by('-n')):
            self.stdout.write(f'  {row["corpus_source"] or "(空)":<20} {row["n"]}')

        # 一致性：有 DOI 就必须有 URL
        bad = Protocol.objects.filter(doi__gt='', source_url='').count()
        self.stdout.write(f'\n一致性检查：doi 非空但 source_url 为空 → {bad}'
                          + (' (OK)' if bad == 0 else ' (异常)'))

        # 抽样来验证 DOI 形态
        self.stdout.write('\n抽样 8 条：')
        for p in Protocol.objects.filter(doi__gt='').order_by('?')[:8]:
            self.stdout.write(f'  id={p.id:<6} {p.doi:<32} {p.name[:44]}')
