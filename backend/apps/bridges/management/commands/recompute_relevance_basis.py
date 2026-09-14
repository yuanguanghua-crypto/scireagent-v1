"""recompute_relevance_basis —— 重算 ProductProtocol.relevance_basis 派生字段（仅此字段）。

背景：relevance_basis 是 fuse_relevance 推导的**派生字段**，定义在
apps.bridges.services.relevance.fuse_relevance。生产实测 4,517 行（19.28%）的
relevance_basis 与已存 score_a/score_b/score_c 矛盾（陈旧值）。

本命令**复用** apps.bridges.services.relevance.fuse_relevance 推导，禁止复制/重写
分支逻辑（防双实现）。仅重算 relevance_basis 这**一个**字段：
- 不改变 relevance_score / tier / score_* / link_source / literature_count；
- 不影响详情页/编辑页的展示顺序（排序键依赖 relevance_score 与 tier，二者不动）。

铁律：
- 默认 dry-run：绝不写库。
- --apply 才 bulk_update 发生变化的行，且**只更新 relevance_basis**，分批 --batch-size（默认 1000）。
- 幂等：--apply 跑完再跑，变化数必须为 0（所有行 basis 已与分数一致）。
- --limit N：只处理前 N 行（按 id 升序），用于小样冒烟。
- --out <jsonl>：每条变更写一行审计 {"id","product_id","protocol_id","old","new"}。

用法：
    python manage.py recompute_relevance_basis            # dry-run（默认，不落库）
    python manage.py recompute_relevance_basis --apply    # 落库修正
    python manage.py recompute_relevance_basis --limit 100
    python manage.py recompute_relevance_basis --apply --out audit.jsonl
"""
import json

from django.core.management.base import BaseCommand

from apps.bridges.models import ProductProtocol
from apps.bridges.services.relevance import fuse_relevance

DEFAULT_BATCH = 1000
# 终态分布展示顺序（其余按字母序追加）
_BASIS_ORDER = ['combined', 'bioz_aligned', 'vendor_only', 'embedding_break', '']


class Command(BaseCommand):
    help = (
        "Recompute the derived ProductProtocol.relevance_basis from stored "
        "score_a/score_b/score_c (dry-run by default; --apply to persist)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true',
            help='Persist recomputed relevance_basis via bulk_update '
                 '(default: dry-run only, never writes).',
        )
        parser.add_argument(
            '--limit', type=int, default=None,
            help='Only process the first N rows (by id) for a smoke test.',
        )
        parser.add_argument(
            '--batch-size', type=int, default=DEFAULT_BATCH,
            help='bulk_update batch size when applying (default 1000).',
        )
        parser.add_argument(
            '--out', default=None,
            help='Write one JSONL audit line per changed row to this file.',
        )

    def handle(self, *args, **options):
        apply = options['apply']
        limit = options['limit']
        batch_size = options['batch_size']
        out_path = options['out']

        qs = ProductProtocol.objects.all().order_by('id')
        if limit is not None:
            qs = qs[:limit]

        total = 0
        mismatched = 0
        transition = {}   # "old -> new": count
        final_dist = {}   # recomputed basis -> count (修复后终态分布)
        changed = []      # 发生变化的 model 实例（staged for bulk_update）
        audit_lines = []

        for pp in qs.iterator():
            total += 1
            fused = fuse_relevance(pp.score_a, pp.score_b, pp.score_c)
            new_basis = fused['relevance_basis']
            old_basis = pp.relevance_basis or ''
            final_dist[new_basis] = final_dist.get(new_basis, 0) + 1
            if new_basis != old_basis:
                mismatched += 1
                key = f'{old_basis or "<empty>"} -> {new_basis}'
                transition[key] = transition.get(key, 0) + 1
                pp.relevance_basis = new_basis  # 仅 staged，dry-run 不写
                changed.append(pp)
                audit_lines.append({
                    'id': pp.id,
                    'product_id': pp.product_id,
                    'protocol_id': pp.protocol_id,
                    'old': old_basis,
                    'new': new_basis,
                })

        # ---------- 报告 ----------
        self.stdout.write("=== recompute_relevance_basis ===")
        self.stdout.write(
            "模式：" + ("apply (落库修正)" if apply else "dry-run (仅统计，不落库)")
        )
        self.stdout.write(f"扫描总行数：{total}")
        self.stdout.write(f"失配（需修正）行数：{mismatched}")

        self.stdout.write("\n(old -> new) 明细分布：")
        if transition:
            for key in sorted(transition, key=lambda k: (-transition[k], k)):
                self.stdout.write(f"  {key} : {transition[key]}")
        else:
            self.stdout.write("  (无)")

        self.stdout.write("\n修复后 basis 终态分布：")
        ordered = [b for b in _BASIS_ORDER if b in final_dist]
        ordered += sorted(b for b in final_dist if b not in _BASIS_ORDER)
        for basis in ordered:
            label = basis or "<empty>"
            self.stdout.write(f"  {label} : {final_dist[basis]}")

        # ---------- 审计输出 ----------
        if out_path:
            with open(out_path, 'w', encoding='utf-8') as f:
                for line in audit_lines:
                    f.write(json.dumps(line, ensure_ascii=False) + '\n')
            self.stdout.write(f"\n审计已写出：{out_path}（{len(audit_lines)} 行）")

        # ---------- 落库闸门 ----------
        if not apply:
            self.stdout.write(self.style.WARNING(
                "[dry-run] 未落库；修正 {0} 行需加 --apply。".format(mismatched)
            ))
            return

        if changed:
            # 只更新 relevance_basis 这一个字段
            ProductProtocol.objects.bulk_update(
                changed, ['relevance_basis'], batch_size=batch_size
            )
        self.stdout.write(self.style.SUCCESS(
            f"完成：bulk_update 修正 {len(changed)} 行（仅 relevance_basis）。"
        ))
