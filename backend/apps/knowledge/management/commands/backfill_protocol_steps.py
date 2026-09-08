"""
backfill_protocol_steps — P2 协议富化回填（零 LLM，纯程序化解析 hierarchical_protocol）。

将 BioProCorpus 源目录中协议记录的 `hierarchical_protocol` 层级步骤树解析为
ProtocolStep 行，回填给 source='bioprocorpus' 且尚无 steps 的空壳协议。

铁律：
- 零 LLM：本次是纯解析，绝无 LLM 调用（项目成本铁律）。
- 只新增，绝不删改任何已有数据（含 94 条 curated 协议的 steps）。
- 宁 miss 不错配：title 匹配不到就跳过，不做模糊凑数。
- 幂等：已有 steps 的协议（curated / 历史残留 / 重复运行）一律跳过。

语料文件：仅 3 个协议语料含 hierarchical_protocol：
  Bio-protocol.json / Protocol-exchange.json / Protocol-io.json
其余（ERR/GEN/ORD/PQA.json）是 BioProBench 其他子集，按文件名白名单排除。

契约（见 apps/knowledge/tests/test_backfill_protocol_steps.py）：
- --corpus-dir（默认 /app/backend/data/bioprocorpus）
- 默认 dry-run：统计匹配数 / 将建步骤数 / 平均步骤数 / 跳过数 + 打印样本
- --apply 用 bulk_create 分批建 ProtocolStep（每批 2000）
- --verify 落库后核查步骤总数
- --limit N 只处理前 N 条
- --checkpoint-file（可选，记录已处理协议 id，支持断点续跑）
"""
import json
import os

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Protocol, ProtocolStep
from apps.knowledge.services.protocol_steps_parser import parse_hierarchical_protocol

DEFAULT_CORPUS_DIR = '/app/backend/data/bioprocorpus'
# 仅这 3 个文件是协议语料（含 hierarchical_protocol）；其余按白名单排除
PROTOCOL_CORPUS_FILES = {
    'bio-protocol.json',
    'protocol-exchange.json',
    'protocol-io.json',
}
BATCH = 2000
SAMPLE_PROTOCOLS = 5   # dry-run 打印样本数
SAMPLE_STEPS = 3       # 每个样本打印前 N 步


def iter_json_records(path):
    """流式产出 JSON 数组（或 JSONL）中的顶层对象，避免把 514MB 语料整体载入内存。"""
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


def _load_title_map(directory):
    """返回 {title.strip(): [{'step_no','title','body'}, ...]}；仅含可解析出步骤的协议记录。

    同名多条记录保留叶子步骤更多的（覆盖率更高）。无 hierarchical_protocol / 无步骤的
    记录不进入 map。
    """
    mapping = {}
    stats = []
    for fname in sorted(os.listdir(directory)):
        if fname.lower() not in PROTOCOL_CORPUS_FILES:
            continue
        fpath = os.path.join(directory, fname)
        seen = 0
        kept = 0
        for rec in iter_json_records(fpath):
            if not isinstance(rec, dict):
                continue
            seen += 1
            title = (rec.get('title') or '').strip()
            if not title:
                continue
            hp = rec.get('hierarchical_protocol')
            if not isinstance(hp, dict):
                continue
            parsed = parse_hierarchical_protocol(hp)
            if not parsed:
                continue
            prev = mapping.get(title)
            if prev is None or len(parsed) > len(prev):
                mapping[title] = parsed
            kept += 1
        stats.append((fname, seen, kept))
    return mapping, stats


def _load_checkpoint(path):
    if not path or not os.path.exists(path):
        return set()
    try:
        with open(path, encoding='utf-8') as f:
            return set(json.load(f))
    except (ValueError, OSError):
        return set()


def _save_checkpoint(path, processed_ids):
    if not path:
        return
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(sorted(processed_ids), f)


class Command(BaseCommand):
    help = "从 BioProCorpus 源解析 hierarchical_protocol，回填空壳协议的 ProtocolStep（零 LLM）。"

    def add_arguments(self, parser):
        parser.add_argument(
            '--corpus-dir', default=None,
            help='BioProCorpus 源目录（默认 /app/backend/data/bioprocorpus）',
        )
        parser.add_argument(
            '--apply', action='store_true',
            help='落库建 ProtocolStep（默认仅 dry-run 统计，不落库）',
        )
        parser.add_argument(
            '--verify', action='store_true',
            help='落库后核查步骤总数并打印报告',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='只处理前 N 条协议',
        )
        parser.add_argument(
            '--checkpoint-file', default=None,
            help='记录已处理协议 id 的文件（支持断点续跑）',
        )

    def handle(self, *args, **options):
        directory = options['corpus_dir'] or DEFAULT_CORPUS_DIR
        apply = options['apply']
        verify = options['verify']
        limit = options['limit']
        checkpoint_file = options['checkpoint_file']

        if not os.path.isdir(directory):
            raise CommandError(f"BioProCorpus 源目录不存在：{directory}")

        self.stdout.write(f"数据源目录：{directory}")
        self.stdout.write(f"模式：{'apply(落库)' if apply else 'dry-run(仅统计)'}")

        title_map, stats = _load_title_map(directory)
        for fname, seen, kept in stats:
            self.stdout.write(f"  {fname:26s} 记录 {seen:>7d}  可用(有步骤) {kept:>7d}")
        self.stdout.write(f"  唯一 title→步骤树：{len(title_map)}")

        processed_ids = _load_checkpoint(checkpoint_file)

        # 已存在 steps 的协议（含 94 条 curated 及历史残留）一律跳过 —— 幂等 + 不覆盖
        with_steps = set(ProtocolStep.objects.values_list('protocol_id', flat=True))
        qs = Protocol.objects.filter(
            source=Protocol.Source.BIOPROCORPUS,
        ).exclude(id__in=with_steps).order_by('id')
        if processed_ids:
            qs = qs.exclude(id__in=processed_ids)

        matched = 0
        unmatched = 0
        skipped_curated_like = 0
        will_create = 0
        step_counts = []
        samples = []
        buf = []
        created_total = 0

        for proto in qs.iterator(chunk_size=2000):
            if limit is not None and (matched + unmatched) >= limit:
                break
            name = proto.name.strip()
            parsed = title_map.get(name)
            processed_ids.add(proto.id)
            if not parsed:
                unmatched += 1
                continue
            matched += 1
            step_counts.append(len(parsed))
            will_create += len(parsed)
            if len(samples) < SAMPLE_PROTOCOLS:
                samples.append((proto.name, parsed[:SAMPLE_STEPS]))

            if not apply:
                continue

            for s in parsed:
                buf.append(ProtocolStep(
                    protocol_id=proto.id,
                    step_no=s['step_no'],
                    title=s['title'],
                    body=s['body'],
                ))
            if len(buf) >= BATCH:
                ProtocolStep.objects.bulk_create(buf, batch_size=BATCH)
                created_total += len(buf)
                buf = []

        if buf and apply:
            ProtocolStep.objects.bulk_create(buf, batch_size=BATCH)
            created_total += len(buf)
            buf = []

        avg = (sum(step_counts) / len(step_counts)) if step_counts else 0.0
        self.stdout.write(
            f"\n=== 统计 ===\n"
            f"  匹配（将回填）协议：{matched}\n"
            f"  未匹配（title 无对应语料，已跳过）：{unmatched}\n"
            f"  将建/已建步骤总数：{will_create if not apply else created_total}\n"
            f"  平均步骤数：{avg:.1f}\n"
            f"  已存在 steps 被跳过（curated/幂等）：{len(with_steps)}"
        )

        if samples:
            self.stdout.write("\n--- 样本（协议名 + 前 %d 步）---" % SAMPLE_STEPS)
            for pname, sps in samples:
                self.stdout.write(f"  * {pname}")
                for s in sps:
                    body_snip = s['body'][:80].replace('\n', ' ')
                    title_snip = (s['title'] or '（无章节标题）')[:60]
                    self.stdout.write(f"      {s['step_no']}. [{title_snip}] {body_snip}")

        if verify and apply:
            total_steps = ProtocolStep.objects.filter(
                protocol__source=Protocol.Source.BIOPROCORPUS,
            ).count()
            self.stdout.write(
                self.style.SUCCESS(
                    f"[verify] bioprocorpus 协议当前步骤总数：{total_steps}"
                )
            )

        _save_checkpoint(checkpoint_file, processed_ids)

        if not apply:
            self.stdout.write(self.style.WARNING(
                f"[dry-run] 未落库；将建步骤 {will_create} 条。加 --apply 执行回填。"
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"完成：新增 ProtocolStep {created_total} 条（覆盖 {matched} 个协议）。"
            ))
