"""build_auto_candidates —— 生成 AUTO 重算所需的候选池 JSON。

原先此逻辑重复内嵌在三个游离测量脚本（_measure_sa_only / _measure_fused_light /
_measure_topn_fused）里，产物 ._candidates.json 无正式生产者，链路不可复现。
本命令把它固化为唯一入口。

产物格式：{catalog_no: [protocol_title, ...]}
产品侧查询文本取自 docx 真源（name + usage），与三轴打分的 P 侧口径一致。

用法：
    python manage.py build_auto_candidates \
        [--out ._candidates.json] [--docx docx_products.json] \
        [--top-k 200000] [--force]

安全：默认**拒绝覆盖**已存在的产物（该文件可达 129MB 且重建耗时），须显式 --force。
"""
import json
import os

from django.core.management.base import BaseCommand

DEFAULT_OUT = '._candidates.json'
DEFAULT_DOCX = 'docx_products.json'
DEFAULT_TOP_K = 200000


class Command(BaseCommand):
    help = "Build the candidate protocol pool JSON consumed by recompute_auto_links."

    # 测试/离线注入：recommender（鸭子类型 .recommend_expanded）
    stealth_options = ('recommender',)

    def add_arguments(self, parser):
        parser.add_argument("--out", default=DEFAULT_OUT,
                            help=f"Output JSON path (default: {DEFAULT_OUT})")
        parser.add_argument("--docx", default=DEFAULT_DOCX,
                            help=f"docx product source JSON (default: {DEFAULT_DOCX})")
        parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K,
                            help="Recommender top_k (full pool by default).")
        parser.add_argument("--force", action="store_true", default=False,
                            help="Overwrite an existing output file.")

    def handle(self, *args, **options):
        out = options['out']
        if os.path.exists(out) and not options['force']:
            self.stdout.write(self.style.WARNING(
                f"{out} already exists; refusing to overwrite. Use --force to rebuild."
            ))
            return

        with open(options['docx'], encoding='utf-8') as f:
            docx_rows = json.load(f)
        docx = {
            str(d['catalog']).strip(): d
            for d in docx_rows if d.get('catalog')
        }
        self.stdout.write(f"docx products = {len(docx)}")

        recommender = options.get('recommender')
        if recommender is None:
            from apps.knowledge.services.protocol_recommender import (
                get_shared_recommender,
            )
            recommender = get_shared_recommender()
            self.stdout.write("recommender built")

        pool = {}
        for catalog, row in docx.items():
            text = f"{row.get('name', '')}. {row.get('usage', '')}".strip()
            if not text or text == '.':
                pool[catalog] = []
                continue
            try:
                results = recommender.recommend_expanded(
                    text, category_path=None, synonyms=[], top_k=options['top_k'])
            except Exception as exc:  # 单个产品失败不阻断全量构建
                self.stderr.write(self.style.WARNING(
                    f"{catalog}: recommender failed ({exc}); empty candidate list"))
                results = []
            pool[catalog] = [
                (r.get('title') or r.get('id'))
                for r in results if (r.get('title') or r.get('id'))
            ]

        with open(out, 'w', encoding='utf-8') as f:
            json.dump(pool, f, ensure_ascii=False)

        total = sum(len(v) for v in pool.values())
        unique = len({t for v in pool.values() for t in v})
        self.stdout.write(self.style.SUCCESS(
            f"wrote {out}: {len(pool)} products, {total} candidate slots, "
            f"{unique} unique titles"
        ))
