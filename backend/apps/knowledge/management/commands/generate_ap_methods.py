"""AP → Method 补链命令 — generate_ap_methods（T2）。

为无 Method 的 AP 生成实验方法（新建 Method：status=draft、FK 挂 AP、
origin=ai_extracted）。范围守卫：ACTIVE + 非 fixture + 无 methods。

- 默认 dry-run：只写 JSONL 审计文件，不落库。
- --apply：为每个 AP 新建其方法名对应的 Method 实体（空方法列表不落库）。
- --out <jsonl>：审计输出路径（一行一 AP，methods 含 in_lexicon 标记）。
- --checkpoint <json>：checkpoint 续跑（{'done': ['application:<id>', ...]}）。
  续跑跳过 done 集；JSONL 追加写；不传 = 全新跑，JSONL 覆盖写。
- --workers N / --limit N / --entity-type 保留（--entity-type 恒为 application）。

词表自增：词表来自 Method 表实时查询 → 新名 Method 创建后自动进词表，
后续批次与 T3 自动复用。

用法：
  python manage.py generate_ap_methods
  python manage.py generate_ap_methods --apply --out C:/tmp/ap_methods.jsonl
  python manage.py generate_ap_methods --apply --checkpoint C:/tmp/ap_ckpt.json
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Application
from apps.knowledge.services.ap_method_generator import ApMethodGenerator
from apps.knowledge.services.llm_extractor import LLMExtractor, llm_config

CHUNK_SIZE = 200


class Command(BaseCommand):
    help = '为无 Method 的 AP 补实验方法（新建 Method draft，默认 dry-run）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='真正落库（缺省为 dry-run，只写 JSONL 不写库）')
        parser.add_argument('--out', type=str, default='',
                            help='JSONL 审计输出路径（缺省 ap_methods.jsonl）')
        parser.add_argument('--checkpoint', type=str, default='',
                            help='checkpoint 路径（缺省不持久化 checkpoint）')
        parser.add_argument('--workers', type=int, default=8,
                            help='并发 worker 数（默认 8）')
        parser.add_argument('--limit', type=int, default=0,
                            help='最多处理 N 条（0=全部；小批验证用）')
        parser.add_argument('--entity-type', type=str, default='',
                            choices=['', 'application'],
                            help='保留参数：T2 仅处理 application')
        # 测试注入用：call_command('generate_ap_methods', extractor=...)
        parser.add_argument('--extractor', dest='extractor', default=None,
                            help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        self.apply = options['apply']
        out_path = options['out'] or 'ap_methods.jsonl'
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

        gen = ApMethodGenerator(extractor=extractor)
        done = self._load_checkpoint(ckpt_path)
        append_mode = bool(done)

        items = []
        for ap in gen.fetch_pool():
            key = f'application:{ap.id}'
            if key in done:
                continue
            items.append(gen.build_item(ap))
        if limit and len(items) > limit:
            items = items[:limit]
            self.stdout.write(self.style.WARNING(
                f'--limit {limit}：仅处理前 {limit} 条（小批验证）'
            ))

        lex_size = len(gen.lexicon())
        self.stdout.write(self.style.SUCCESS(
            f'===== generate_ap_methods [{"APPLY" if self.apply else "DRY-RUN"}] ====='
        ))
        self.stdout.write(
            f'待处理 {len(items)} 个 AP（checkpoint done={len(done)}）'
            f' | 词表 {lex_size} | workers={workers} | out={out_path}'
            + (f' | ckpt={ckpt_path}' if ckpt_path else '')
        )

        t0 = time.time()
        n_ok = n_empty = n_err = 0
        n_methods = 0
        n_lex_hit = 0
        rows_written = 0

        for i in range(0, len(items), CHUNK_SIZE):
            chunk = items[i:i + CHUNK_SIZE]
            rows = self._run_chunk(gen, chunk, workers)
            for row in rows:
                # T2 缺陷修复（2026-09-03）：error 行（402/429/空响应）不进 done。
                # 原实现无条件 done.add() → 19,720 条失败被永久跳过，
                # 形成 69% 静默数据缺口。现与 T3 一致：失败即重跑。
                if not row['error']:
                    done.add(f'application:{row["ap_id"]}')
                self._append_jsonl(out_path, json.dumps(row, ensure_ascii=False),
                                   append=append_mode or rows_written > 0)
                rows_written += 1
                if self.apply:
                    n_methods += gen.apply_row(row)
                if row['error']:
                    n_err += 1
                elif row['methods']:
                    n_ok += 1
                    n_lex_hit += sum(1 for m in row['methods'] if m['in_lexicon'])
                else:
                    n_empty += 1
            if ckpt_path:
                self._save_checkpoint(ckpt_path, done)
            self.stdout.write(
                f'  进度 {min(i + CHUNK_SIZE, len(items))}/{len(items)} '
                f'({time.time() - t0:.0f}s)  ok={n_ok} empty={n_empty} err={n_err}'
                + (f' methods={n_methods}' if self.apply else '')
            )

        self.stdout.write('\n=== 汇总 ===')
        self.stdout.write(
            f'有方法 AP={n_ok}  空={n_empty}  失败={n_err}  总={len(items)}'
            f'  耗时 {time.time() - t0:.0f}s'
        )
        if self.apply:
            self.stdout.write(self.style.SUCCESS(
                f'APPLY 完成：新建 Method {n_methods} 条（词表命中 {n_lex_hit} 次）'
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
