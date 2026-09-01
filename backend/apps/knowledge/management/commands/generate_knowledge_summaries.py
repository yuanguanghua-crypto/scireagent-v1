"""知识实体 summary 回填命令 — generate_knowledge_summaries（T1）。

为 ResearchGoal / Application 的空 summary 批量生成英文摘要（prompt v2，
宁缺毋滥）。范围守卫：ACTIVE + 非 fixture + summary=''。

- 默认 dry-run：只写 JSONL 审计文件，不落库。
- --apply：把非空 summary 落库（空 summary 保留空态，不覆盖）。
- --out <jsonl>：审计输出路径（一行一实体，含 error 字段）。
- --checkpoint <json>：checkpoint 续跑（{'done': ['research_goal:<id>', ...]}）。
  续跑跳过 done 集内实体（不重复调 LLM）；JSONL 追加写不丢已写行；
  不传 checkpoint = 全新跑，JSONL 覆盖写。
- --workers N：ThreadPoolExecutor 并发数（默认 8）。

用法：
  python manage.py generate_knowledge_summaries
  python manage.py generate_knowledge_summaries --apply --out /tmp/summaries.jsonl
  python manage.py generate_knowledge_summaries --apply --checkpoint /tmp/ckpt.json
"""
import argparse
import json
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.core.management.base import BaseCommand, CommandError

from apps.knowledge.models import Application, ResearchGoal
from apps.knowledge.services.llm_extractor import LLMExtractor, llm_config
from apps.knowledge.services.summary_generator import SummaryGenerator

CHUNK_SIZE = 200  # 每块并发跑完后统一落盘 checkpoint，控制内存与持久化粒度


class Command(BaseCommand):
    help = '为 RG/AP 空 summary 生成英文摘要（默认 dry-run，--apply 落库）'

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='真正落库（缺省为 dry-run，只写 JSONL 不写库）')
        parser.add_argument('--out', type=str, default='',
                            help='JSONL 审计输出路径（缺省 knowledge_summaries.jsonl）')
        parser.add_argument('--checkpoint', type=str, default='',
                            help='checkpoint 路径（缺省不持久化 checkpoint）')
        parser.add_argument('--workers', type=int, default=8,
                            help='并发 worker 数（默认 8）')
        parser.add_argument('--limit', type=int, default=0,
                            help='最多处理 N 条（0=全部；小批验证用，如 --limit 50）')
        parser.add_argument('--entity-type', type=str, default='',
                            choices=['', 'research_goal', 'application'],
                            help='只处理指定类型（缺省全部；分类型小批验证用）')
        # 测试注入用：call_command('generate_knowledge_summaries', extractor=...)。
        # 声明在 parser 中以便 Django 接受该 kwarg；help=SUPPRESS 不暴露给 --help。
        parser.add_argument('--extractor', dest='extractor', default=None,
                            help=argparse.SUPPRESS)

    def handle(self, *args, **options):
        self.apply = options['apply']
        out_path = options['out'] or 'knowledge_summaries.jsonl'
        ckpt_path = options['checkpoint']
        workers = options['workers']
        limit = options['limit']
        entity_type = options['entity_type']

        # extractor：测试注入（call_command 传 extractor=）或按环境变量构造
        extractor = options.get('extractor')
        if extractor is None:
            cfg = llm_config()
            if not cfg['available']:
                raise CommandError(
                    'SCIREAGENT_LLM_API_KEY 未配置——LLM summary 生成不可用。'
                    '配置 key 后重跑，或传 extractor= 注入测试桩。'
                )
            extractor = LLMExtractor(api_key=cfg['api_key'],
                                     base_url=cfg['base_url'],
                                     model=cfg['model'])

        gen = SummaryGenerator(extractor=extractor)

        # checkpoint 载入：done 集非空 = 续跑 → JSONL 追加；空 = 全新跑 → 覆盖
        done = self._load_checkpoint(ckpt_path)
        append_mode = bool(done)

        # 范围守卫 + done 过滤 → 待办 items
        items = []
        for entity in gen.fetch_pool():
            if isinstance(entity, ResearchGoal):
                et = 'research_goal'
            elif isinstance(entity, Application):
                et = 'application'
            else:
                continue
            if entity_type and et != entity_type:
                continue
            key = f'{et}:{entity.id}'
            if key in done:
                continue
            items.append(gen.build_item(et, entity))

        if limit and len(items) > limit:
            items = items[:limit]
            self.stdout.write(self.style.WARNING(
                f'--limit {limit}：仅处理前 {limit} 条（小批验证）'
            ))

        self.stdout.write(self.style.SUCCESS(
            f'===== generate_knowledge_summaries '
            f'[{"APPLY" if self.apply else "DRY-RUN"}] ====='
        ))
        self.stdout.write(
            f'待处理 {len(items)} 条（RG+AP，checkpoint done={len(done)}）'
            f' | workers={workers} | out={out_path}'
            + (f' | ckpt={ckpt_path}' if ckpt_path else '')
        )

        t0 = time.time()
        n_ok = n_empty = n_err = 0
        rows_written = 0

        for i in range(0, len(items), CHUNK_SIZE):
            chunk = items[i:i + CHUNK_SIZE]
            rows = self._run_chunk(gen, chunk, workers)
            for row in rows:
                key = f"{row['entity_type']}:{row['entity_id']}"
                done.add(key)
                self._append_jsonl(out_path, gen.to_jsonl_line(row),
                                   append=append_mode or rows_written > 0)
                rows_written += 1
                if self.apply:
                    gen.apply_row(row)
                if row['error']:
                    n_err += 1
                elif row['summary']:
                    n_ok += 1
                else:
                    n_empty += 1
            if ckpt_path:
                self._save_checkpoint(ckpt_path, done)
            self.stdout.write(
                f'  进度 {min(i + CHUNK_SIZE, len(items))}/{len(items)} '
                f'({time.time() - t0:.0f}s)  ok={n_ok} empty={n_empty} err={n_err}'
            )

        elapsed = time.time() - t0
        self.stdout.write('\n=== 汇总 ===')
        self.stdout.write(
            f'成功(有文本)={n_ok}  空 summary={n_empty}  失败={n_err}  '
            f'总={len(items)}  耗时 {elapsed:.1f}s'
        )
        if self.apply:
            self.stdout.write(self.style.SUCCESS(
                f'APPLY 完成：非空 summary 已落库，空 summary 保留空态。'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'DRY-RUN：未落库。确认 JSONL 质量后加 --apply 真正写库。'
            ))

    # ------------------------------------------------------------------ #
    # 辅助
    # ------------------------------------------------------------------ #
    def _run_chunk(self, gen, items, workers):
        """并发跑一块：ThreadPoolExecutor，worker 只调 LLM 不碰 ORM。"""
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(gen.summarize_one, it): it for it in items}
            return [fut.result() for fut in as_completed(futures)]

    @staticmethod
    def _load_checkpoint(path):
        """载入 checkpoint → done 集（key = 'research_goal:<id>'）。"""
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
