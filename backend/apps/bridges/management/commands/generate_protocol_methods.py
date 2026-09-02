"""协议无 Method 补链命令 — generate_protocol_methods（T3）。

为「悬空协议」（PUBLISHED + 无 MethodProtocol 桥）补 Method 关联：
LLM 从词表召回候选并选名，命中的方法直写 MethodProtocol 桥
（evidence_source='llm_reviewed'、explicit=False、status='active'、bulk_create 去重）。
范围守卫：PUBLISHED + 无桥；召回为空直接真空（不调 LLM，宁 miss 不错配）。

**T2 教训落地**：error 行（如 HTTP 429）写 JSONL 但**不进 checkpoint done** →
重启自动重跑，杜绝静默数据缺口。

- 默认 dry-run：只写 JSONL 审计文件，不落库。
- --apply：落库建桥。
- --out <jsonl> / --checkpoint <json>：JSONL 追加写 + checkpoint 续跑（{'done': ['protocol:<id>', ...]}）。
- --workers N / --limit N：并发与上限（小批验证用）。

用法：
  python manage.py generate_protocol_methods
  python manage.py generate_protocol_methods --apply --out C:/tmp/proto_methods.jsonl
  python manage.py generate_protocol_methods --apply --checkpoint C:/tmp/proto_ckpt.json
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError

from apps.bridges.services.protocol_method_generator import ProtocolMethodGenerator
from apps.knowledge.services.llm_extractor import LLMExtractor, llm_config

CHUNK_SIZE = 200


class Command(BaseCommand):
    help = '为悬空协议（PUBLISHED 无桥）补 Method 关联（LLM 词表召回选名，默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='真正落库（缺省为 dry-run，只写 JSONL 不写库）')
        parser.add_argument('--out', type=str, default='',
                            help='JSONL 审计输出路径（缺省 proto_methods.jsonl）')
        parser.add_argument('--checkpoint', type=str, default='',
                            help='checkpoint 路径（缺省不持久化 checkpoint）')
        parser.add_argument('--workers', type=int, default=8,
                            help='并发 worker 数（默认 8）')
        parser.add_argument('--limit', type=int, default=0,
                            help='最多处理 N 条（0=全部；小批验证用）')
        # 测试注入用：call_command('generate_protocol_methods', extractor=...)
        parser.add_argument('--extractor', dest='extractor', default=None,
                            help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        self.apply = options['apply']
        out_path = options['out'] or 'proto_methods.jsonl'
        ckpt_path = options['checkpoint']
        workers = options['workers']
        limit = options['limit']

        extractor = options.get('extractor')
        if extractor is None:
            cfg = llm_config()
            if not cfg['available']:
                raise CommandError(
                    'SCIREAGENT_LLM_API_KEY 未配置——LLM 方法识别不可用。'
                    '配置 key 后重跑，或传 extractor= 注入测试桩。'
                )
            extractor = LLMExtractor(api_key=cfg['api_key'],
                                     base_url=cfg['base_url'],
                                     model=cfg['model'])

        gen = ProtocolMethodGenerator(extractor=extractor)
        done = self._load_checkpoint(ckpt_path)
        append_mode = bool(done)

        items = []
        for proto in gen.fetch_pool():
            key = f'protocol:{proto.id}'
            if key in done:
                continue
            items.append(gen.build_item(proto))
        if limit and len(items) > limit:
            items = items[:limit]
            self.stdout.write(self.style.WARNING(
                f'--limit {limit}：仅处理前 {limit} 条（小批验证）'
            ))

        lex_size = len(gen.lexicon())
        self.stdout.write(self.style.SUCCESS(
            f'===== generate_protocol_methods [{"APPLY" if self.apply else "DRY-RUN"}] ====='
        ))
        self.stdout.write(
            f'待处理 {len(items)} 个协议（checkpoint done={len(done)}）'
            f' | 词表 {lex_size} | workers={workers} | out={out_path}'
            + (f' | ckpt={ckpt_path}' if ckpt_path else '')
        )

        t0 = time.time()
        n_ok = n_empty = n_err = 0
        n_bridges = 0
        rows_written = 0

        for i in range(0, len(items), CHUNK_SIZE):
            chunk = items[i:i + CHUNK_SIZE]
            rows = self._run_chunk(gen, chunk, workers)
            for row in rows:
                # T2 教训：error 行不进 done —— 重启自动重跑
                if not row['error']:
                    done.add(f'protocol:{row["protocol_id"]}')
                self._append_jsonl(out_path, json.dumps(row, ensure_ascii=False),
                                   append=append_mode or rows_written > 0)
                rows_written += 1
                if row['error']:
                    n_err += 1
                elif row['method_names']:
                    n_ok += 1
                    if self.apply:
                        n_bridges += gen.apply_row(row)
                else:
                    n_empty += 1
            if ckpt_path:
                self._save_checkpoint(ckpt_path, done)
            self.stdout.write(
                f'  进度 {min(i + CHUNK_SIZE, len(items))}/{len(items)} '
                f'({time.time() - t0:.0f}s)  ok={n_ok} empty={n_empty} err={n_err}'
                + (f' bridges={n_bridges}' if self.apply else '')
            )

        self.stdout.write('\n=== 汇总 ===')
        self.stdout.write(
            f'有方法协议={n_ok}  空={n_empty}  失败={n_err}  总={len(items)}'
            f'  耗时 {time.time() - t0:.0f}s'
        )
        if self.apply:
            self.stdout.write(self.style.SUCCESS(
                f'APPLY 完成：新建 MethodProtocol 桥 {n_bridges} 条'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN：未落库。确认 JSONL 质量后加 --apply 真正写库。'
            ))

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    def _run_chunk(self, gen, items, workers):
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(gen.probe_one, it): it for it in items}
            return [fut.result() for fut in as_completed(futures)]

    @staticmethod
    def _load_checkpoint(path):
        if not path or not os.path.exists(path):
            return set()
        with open(path, encoding='utf-8') as f:
            data = json.load(f)
        return set(data.get('done') or [])

    @staticmethod
    def _save_checkpoint(path, done):
        with open(path, 'w', encoding='utf-8') as f:
            json.dump({'done': sorted(done)}, f, ensure_ascii=False, indent=2)

    @staticmethod
    def _append_jsonl(path, line, append=False):
        mode = 'a' if append else 'w'
        with open(path, mode, encoding='utf-8') as f:
            f.write(line + '\n')
