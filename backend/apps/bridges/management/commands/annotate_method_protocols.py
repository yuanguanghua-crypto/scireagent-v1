# -*- coding: utf-8 -*-
"""annotate_method_protocols —— P0#2 L1：词典自动标注悬空协议的 Method 关联。

词典 = 历史 evidence_source='lexicon_auto' 桥（3,451 条）挖掘的 Method 特征词
（top5 + 跨方法共用词剔除 + 扩充 STOP）；STRONG 命中（>=2 特征词且最高分唯一）才建桥；
匹配文本仅用 Protocol.name。建桥形态与历史 lexicon_auto 一致：
evidence_source='lexicon_auto', status='active'。

铁律：宁 miss 不错配（用户决策 2026-09-01：只做 L1 词典，效果不行再走 LLM 提取）。

用法：
    python manage.py annotate_method_protocols                     # dry-run：统计 + 样本
    python manage.py annotate_method_protocols --apply             # 落库建桥
    python manage.py annotate_method_protocols --sample 10         # 样本数（默认 15）
"""
from django.core.management.base import BaseCommand

from apps.bridges.models import MethodProtocol
from apps.bridges.services.method_lexicon import (
    build_lexicon, match_protocol, annotate_orphan_protocols,
)
from apps.knowledge.models import Method, Protocol


class Command(BaseCommand):
    help = "L1 词典自动标注悬空协议的 Method 关联（dry-run 默认，--apply 落库）。"

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true', default=False,
                            help='落库建桥（默认 dry-run 只统计）。')
        parser.add_argument('--sample', type=int, default=15,
                            help='打印的命中样本数（默认 15）。')

    def handle(self, *args, **options):
        apply = options['apply']
        sample_n = options['sample']

        lexicon = build_lexicon()
        self.stdout.write(self.style.SUCCESS(
            f'词典：{len(lexicon)} 个 Method 有历史 lexicon_auto 特征词'
        ))
        if not lexicon:
            self.stdout.write(self.style.WARNING('无词典可用，退出。'))
            return

        # 先枚举命中（apply 之前），保证两种模式都能打印完整命中名单供人工复核
        linked = set(MethodProtocol.objects.values_list('protocol_id', flat=True).distinct())
        orphans = list(Protocol.objects.exclude(id__in=linked).only('id', 'name').order_by('id'))
        matched_rows = []
        for proto in orphans:
            hits = match_protocol(proto.name, lexicon)
            if hits:
                method = Method.objects.get(pk=hits[0][0])
                matched_rows.append((proto.id, proto.name, method.name, hits[0][1]))

        self.stdout.write(
            f'悬空协议总数: {len(orphans)} | STRONG 命中: {len(matched_rows)}'
        )
        for pid, pname, mname, score in matched_rows[:sample_n]:
            self.stdout.write(
                f'  [{pid}] {pname[:60]:62s} -> {mname} (score={score})'
            )

        if apply:
            stats = annotate_orphan_protocols(apply=True)
            self.stdout.write(self.style.SUCCESS(
                f'--apply 完成，共创建 {stats["created"]} 条桥。'
            ))
        else:
            self.stdout.write(self.style.WARNING(
                'dry-run：未落库。确认样本质量后加 --apply 落库。'
            ))
