"""
backfill_protocol_objective — 任务2：BioProCorpus 协议正文回填（含 B 类改进）。

#400 导入 13971 条 source='bioprocorpus' 的 Protocol 时只写了 name/slug/source，
正文字段全空。相关性三轴中：
  - 轴A `relevance._protocol_q_text()` 拼接 name+objective+principle+...
  - 轴C `embedding_backend._protocol_embedding()` 拼接 name+objective+summary+purpose
两轴的协议侧文本因此退化为"仅标题"。本命令从本地 BioProCorpus 源目录读取
`title` → 最优正文，按 Protocol.name.strip() 回填 objective，让两轴基于内容计算。

B 类改进（本轮）：
- 扩展字段来源（③）：源记录仅含 title+abstract 时同原行为；abstract 为空则按
  `protocol` > `description` > `method` > `hierarchical_protocol` 优先级取首个非空，
  最大化本地源利用率。
- 保守模糊匹配（④，默认关闭，--fuzzy 启用）：先归一化精确命中（大小写/标点/
  空白差异），再对高相似度（difflib ratio >= 0.90）且唯一候选的做回退匹配。
  严守"宁 miss 不错配"——不相关标题绝不误写（AUTO MATCH 十铁律①）。

契约（见 apps/knowledge/tests/test_backfill_protocol_objective.py）：
- 数据源默认 settings.BASE_DIR/data/bioprocorpus，可用 --path 覆盖
- 只取含 title 的记录（ERR/GEN/ORD/PQA 等非协议文件自动跳过）
- 仅回填 source='bioprocorpus'；curated 人工策展库绝不改动
- 空值安全：无可用正文字段 → 跳过
- 不覆盖已有 objective（除非 --force）
- 幂等；--dry-run 只报告不落库
- --fuzzy：启用保守模糊匹配（默认仅精确匹配）
"""
import difflib
import json
import os
import re

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Protocol

DEFAULT_SUBDIR = os.path.join('data', 'bioprocorpus')
BATCH = 1000

# 正文候选字段优先级：abstract(策展摘要) 优先，空则回退其余字段
PRIORITY_FIELDS = ['abstract', 'protocol', 'description', 'method', 'hierarchical_protocol']
# 模糊匹配相似度门槛（越高越保守，避免误配）
FUZZY_RATIO_THRESHOLD = 0.90
# 参与模糊倒排索引的最小 token 长度
MIN_TOKEN_LEN = 4


def _norm(s):
    """归一化：小写 + 仅保留字母数字 + 折叠空白。用于消除大小写/标点差异。"""
    s = (s or '').lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return ' '.join(s.split())


def _to_text(v):
    """任意结构（str/list/dict/标量）安全转为去首尾空白文本。None 视为空。"""
    if v is None:
        return ''
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, dict):
        return '\n'.join(f'{k}: {_to_text(val)}' for k, val in v.items())
    if isinstance(v, list):
        return '\n'.join(_to_text(x) for x in v)
    return str(v).strip()


def _record_text(rec):
    """从单条源记录挑最优正文字段（按优先级首个非空）。结构化字段拼接为文本。"""
    for field in PRIORITY_FIELDS:
        v = _to_text(rec.get(field))
        if v:
            return v
    return ''


def _record_quality(rec):
    """重复 title 取最优记录：(有abstract权重, 正文字段长度) 降序。"""
    bt = _record_text(rec)
    has_abs = 1 if (rec.get('abstract') or '').strip() else 0
    return (has_abs, len(bt))


def iter_json_records(path):
    """流式产出 JSON 数组（或 JSONL）中的顶层对象。

    BioProCorpus 文件为「对象数组」格式，单文件最大 ~205MB。整体 json.load 会把
    全部对象常驻内存；此处只保留文本 + 增量 raw_decode，用完即弃对象。
    """
    with open(path, encoding='utf-8') as f:
        text = f.read()
    dec = json.JSONDecoder()
    n = len(text)
    pos = 0
    while pos < n and text[pos].isspace():
        pos += 1
    if pos < n and text[pos] == '[':
        pos += 1
    while pos < n:
        while pos < n and (text[pos].isspace() or text[pos] == ','):
            pos += 1
        if pos >= n or text[pos] == ']':
            break
        try:
            obj, pos = dec.raw_decode(text, pos)
        except ValueError:
            break
        yield obj


class Command(BaseCommand):
    help = "从本地 BioProCorpus 源回填 Protocol.objective（扩展字段来源 + 保守模糊匹配）。"

    def add_arguments(self, parser):
        parser.add_argument(
            '--path', default=None,
            help='BioProCorpus 源目录（默认 settings.BASE_DIR/data/bioprocorpus）',
        )
        parser.add_argument(
            '--force', action='store_true',
            help='覆盖已有 objective（默认只填空值）',
        )
        parser.add_argument(
            '--dry-run', action='store_true',
            help='只报告将要更新的数量，不落库',
        )
        parser.add_argument(
            '--fuzzy', action='store_true',
            help='启用保守模糊匹配（默认仅精确匹配 name==title）',
        )

    def _load_source(self, directory):
        """返回 {title(strip): 最优正文}；仅含 title 非空的记录。"""
        files = sorted(
            f for f in os.listdir(directory)
            if f.lower().endswith('.json')
        )
        mapping = {}
        stats = []
        for fname in files:
            fpath = os.path.join(directory, fname)
            kept = 0
            seen = 0
            for rec in iter_json_records(fpath):
                if not isinstance(rec, dict):
                    continue
                seen += 1
                title = (rec.get('title') or '').strip()
                if not title:
                    continue
                bt = _record_text(rec)
                if not bt:
                    continue
                # 同名多条：保留质量最高的（有abstract优先，其次正文最长）
                prev = mapping.get(title)
                if prev is None or _record_quality(rec) > prev[1]:
                    mapping[title] = (bt, _record_quality(rec))
                kept += 1
            stats.append((fname, seen, kept))
        # 剥掉质量元组，只留正文
        return {t: v[0] for t, v in mapping.items()}, stats

    def _build_fuzzy_index(self, mapping):
        """构建归一化标题字典 + token 倒排索引，供保守模糊匹配。"""
        norm_dict = {_norm(t): text for t, text in mapping.items()}
        inv = {}
        for nt in norm_dict:
            for tok in nt.split():
                if len(tok) >= MIN_TOKEN_LEN:
                    inv.setdefault(tok, set()).add(nt)
        return norm_dict, inv

    def _fuzzy_lookup(self, name, norm_dict, inv):
        """保守模糊匹配：返回 (正文, is_fuzzy)。未命中返回 (None, False)。"""
        nn = _norm(name)
        if not nn:
            return None, False
        # 1) 归一化精确命中（消除大小写/标点/空白差异）
        if nn in norm_dict:
            return norm_dict[nn], True
        # 2) 高相似度唯一候选：先 token 倒排粗筛，再 difflib 精算
        toks = [t for t in nn.split() if len(t) >= MIN_TOKEN_LEN]
        if not toks:
            return None, False
        cands = set()
        for t in toks:
            cands |= inv.get(t, set())
        if not cands:
            return None, False
        best_ratio = 0.0
        best = None
        cnt = 0
        for ct in cands:
            r = difflib.SequenceMatcher(None, nn, ct).ratio()
            if r > best_ratio:
                best_ratio = r
                best = ct
                cnt = 1
            elif r == best_ratio:
                cnt += 1
        if best_ratio >= FUZZY_RATIO_THRESHOLD and cnt == 1:
            return norm_dict[best], True
        return None, False

    def handle(self, *args, **options):
        directory = options['path'] or os.path.join(settings.BASE_DIR, DEFAULT_SUBDIR)
        force = options['force']
        dry_run = options['dry_run']
        fuzzy = options['fuzzy']

        if not os.path.isdir(directory):
            raise CommandError(f"BioProCorpus 源目录不存在：{directory}")

        self.stdout.write(f"数据源目录：{directory}")
        self.stdout.write(f"模糊匹配：{'启用(--fuzzy)' if fuzzy else '关闭(仅精确)'}")
        mapping, stats = self._load_source(directory)
        for fname, seen, kept in stats:
            flag = '' if kept else '  (无 title/可用正文，跳过)'
            self.stdout.write(f"  {fname:26s} 记录 {seen:>7d}  可用 {kept:>7d}{flag}")
        self.stdout.write(f"  唯一 title→正文：{len(mapping)}")

        norm_dict, inv = (self._build_fuzzy_index(mapping) if fuzzy else ({}, {}))

        qs = Protocol.objects.filter(source=Protocol.Source.BIOPROCORPUS)
        if not force:
            qs = qs.filter(objective='')

        updated = 0
        unmatched = 0
        fuzzy_matched = 0
        buf = []
        for proto in qs.only('id', 'name', 'objective').iterator(chunk_size=BATCH):
            name = proto.name.strip()
            text = mapping.get(name)
            is_fuzzy = False
            if not text and fuzzy:
                text, is_fuzzy = self._fuzzy_lookup(name, norm_dict, inv)
                if is_fuzzy:
                    fuzzy_matched += 1
            if not text:
                unmatched += 1
                continue
            if proto.objective == text:
                continue  # 幂等
            updated += 1
            if dry_run:
                continue
            proto.objective = text
            buf.append(proto)
            if len(buf) >= BATCH:
                Protocol.objects.bulk_update(buf, ['objective'])
                buf = []
        if buf and not dry_run:
            Protocol.objects.bulk_update(buf, ['objective'])

        total_bpc = Protocol.objects.filter(source=Protocol.Source.BIOPROCORPUS).count()
        filled = Protocol.objects.filter(
            source=Protocol.Source.BIOPROCORPUS
        ).exclude(objective='').count()

        self.stdout.write(
            f"  BioProCorpus 协议总数：{total_bpc}；"
            f"本次候选未命中源标题：{unmatched}"
            + (f"；模糊命中：{fuzzy_matched}" if fuzzy else "")
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(f"[dry-run] 将要更新 {updated} 条，未落库"))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"完成：更新 {updated} 条 Protocol.objective；"
                f"当前已有正文 {filled}/{total_bpc}"
            ))
