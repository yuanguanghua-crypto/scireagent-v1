"""recompute_auto_links —— 重算 AUTO 链接（原游离脚本 _land_recompute_auto.py）。

用法：
    python manage.py recompute_auto_links \
        [--candidates ._candidates.json] [--topn 20] [--encode-batch 64] \
        [--verify] [--dry-run]

环境变量向后兼容（未显式传参时生效）：
    AUTO_CANDIDATES / AUTO_TOPN / AUTO_ENCODE_BATCH / AUTO_VERIFY

嵌入模型路径不在此声明：由 embedding_backend 依 EMB3_VENV 环境变量 /
settings.EMB3_VENV_PATH 解析，本命令对部署环境零假设。

幂等：逐产品先删旧 AUTO 行再 upsert，重跑安全；不覆盖 INHERITED/EXPLICIT。
"""
import os

from django.core.management.base import BaseCommand, CommandError

from apps.bridges.services import auto_links as SVC


def _env_int(name, default):
    raw = os.environ.get(name)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


class Command(BaseCommand):
    help = "Recompute AUTO ProductProtocol links from a candidate pool (Top-N per product)."

    # 测试/离线注入：model（鸭子类型 .encode）与 candidates（内存候选池）
    stealth_options = ('model', 'candidates')

    def add_arguments(self, parser):
        parser.add_argument(
            "--candidates", default=None,
            help="Candidate pool JSON path {catalog_no: [protocol_title,...]}. "
                 "Default: env AUTO_CANDIDATES or ._candidates.json",
        )
        parser.add_argument(
            "--topn", type=int, default=None,
            help="Top-N protocols per product. Default: env AUTO_TOPN or 20",
        )
        parser.add_argument(
            "--encode-batch", type=int, default=None,
            help="Embedding batch size. Default: env AUTO_ENCODE_BATCH or 64",
        )
        parser.add_argument(
            "--verify", action="store_true", default=False,
            help="Sample-check vectorized results against relevance production functions.",
        )
        parser.add_argument(
            "--dry-run", action="store_true", default=False,
            help="Compute and report without writing any row.",
        )
        parser.add_argument(
            "--seed", type=int, default=None,
            help="Seed the verify sampler for reproducible self-checks.",
        )

    def handle(self, *args, **options):
        candidates = options.get('candidates')
        if isinstance(candidates, str) or candidates is None:
            path = candidates or os.environ.get(
                'AUTO_CANDIDATES') or SVC.DEFAULT_CANDIDATES_PATH
            try:
                candidates = SVC.load_candidates(path)
            except FileNotFoundError:
                raise CommandError(
                    f"Candidate pool not found: {path}. "
                    f"Build it first: python manage.py build_auto_candidates"
                )
        if not isinstance(candidates, dict):
            raise CommandError("candidates must be a dict {catalog_no: [titles]}")

        topn = options.get('topn') or _env_int('AUTO_TOPN', SVC.DEFAULT_TOPN)
        encode_batch = options.get('encode_batch') or _env_int(
            'AUTO_ENCODE_BATCH', SVC.DEFAULT_ENCODE_BATCH)
        verify = options.get('verify') or (
            os.environ.get('AUTO_VERIFY', '') not in ('', '0'))

        stats = SVC.recompute_auto_links(
            candidates,
            topn=topn,
            encode_batch=encode_batch,
            model=options.get('model'),
            verify=verify,
            dry_run=options.get('dry_run', False),
            seed=options.get('seed'),
            log=lambda m: self.stdout.write(m),
        )

        if stats['mismatches']:
            raise CommandError(
                f"VERIFY FAILED: {stats['mismatches']}/{stats['verified']} pairs "
                f"diverge from production relevance functions."
            )

        prefix = "[DRY-RUN] " if stats['dry_run'] else ""
        self.stdout.write(self.style.SUCCESS(
            f"{prefix}{stats['products']} products, wrote {stats['written']} AUTO rows, "
            f"skipped {stats['skipped_linked']} already-inherited; "
            f"AUTO rows in DB = {stats['auto_total']}"
            + (f"; verified {stats['verified']} pairs OK" if verify else "")
        ))
