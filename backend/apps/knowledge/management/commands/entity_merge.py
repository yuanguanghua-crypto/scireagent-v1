"""语义聚类安全合并落库命令 — entity_merge。

读取语义聚类报告（cluster_report.json），把每簇细粒度成员实体合并到代表实体：
- 只处理 size>=2 的簇；group='rg' → ResearchGoal，group='ap' → Application。
- 过滤：跳过 is_test_fixture=True 与名字以 `__e2e_` 开头的成员（e2e 残留）；
  策展守卫——has_curated=True 的簇其代表 origin 必须是 human_curated/imported，
  否则报错并整簇跳过（策展实体只当代表，绝不能被代表、被删）。
- 关联迁移：RG 成员把 protocols / application_collection 收拢到代表（M2M add
  天然幂等去重）；AP 成员把 research_goal_collections（反向 M2M）的引用迁到代表；
  AP.research_goal FK 指向被删 RG 时改指代表，防止 CASCADE 误删 AP。
- 硬删成员；已删实体自动跳过 → 二次 --apply 零改动。
- 事务边界：按 --chunk-size 个簇一个 transaction.atomic()；某 chunk 抛异常 →
  回滚该 chunk、记录错误到报告、继续后续 chunk。
- 默认 dry-run（只统计不写库）；加 --apply 才真正落库。

用法：
  python manage.py entity_merge --report <cluster_report.json>
  python manage.py entity_merge --report <cluster_report.json> --apply
  python manage.py entity_merge --report <path> --report-out <abs-path>.json
"""
import json
import os
from contextlib import nullcontext

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.knowledge.models import Application, OriginChoices, ResearchGoal

# 允许作为策展簇代表的来源（human_curated=人工策展 / imported=存量导入）
_CURATED_ORIGINS = (OriginChoices.HUMAN_CURATED, OriginChoices.IMPORTED)


class Command(BaseCommand):
    help = '按语义聚类报告把细粒度知识实体合并到代表实体（默认 dry-run）'

    # 统计键（chunk 局部与全局 totals 共用）
    _TOTAL_KEYS = (
        'processed_clusters', 'merged_entities', 'reloc_fk_aps',
        'skipped_e2e', 'skipped_missing', 'skipped_guard', 'created_entities',
    )

    def add_arguments(self, parser):
        parser.add_argument('--report', required=True,
                            help='语义聚类报告 JSON 路径（含 summary/clusters）')
        parser.add_argument('--apply', action='store_true', default=False,
                            help='真正落库（缺省为 dry-run，只统计不写库）')
        parser.add_argument('--chunk-size', type=int, default=200,
                            help='每个事务提交的簇数（默认 200）')
        parser.add_argument('--report-out', type=str, default='',
                            help='汇总报告 JSON 输出路径（缺省仅打印到 stdout）')

    # ------------------------------------------------------------------ #
    # handle 主流程
    # ------------------------------------------------------------------ #
    def handle(self, *args, **options):
        self.apply = options['apply']
        chunk_size = options['chunk_size']
        report_out = options['report_out']
        if chunk_size < 1:
            raise CommandError('--chunk-size 必须 >= 1')

        # 1) 读取聚类报告，只保留 size>=2 的簇
        report_data = self._load_report(options['report'])
        all_clusters = report_data.get('clusters', [])
        clusters = [c for c in all_clusters if c.get('size', 0) >= 2]
        self.stdout.write(
            f'读取完成：总簇 {len(all_clusters)}，size>=2 待处理簇 {len(clusters)}')

        # 2) 预载实体 by id（代表查询一次性，成员按簇 in_bulk 取最新）
        self.rg_by_id = ResearchGoal.objects.in_bulk()
        self.ap_by_id = Application.objects.in_bulk()

        # 3) 逐 chunk 合并/统计
        totals = {k: 0 for k in self._TOTAL_KEYS}
        chunk_failures = []
        for start in range(0, len(clusters), chunk_size):
            chunk = clusters[start:start + chunk_size]
            local = None
            try:
                ctx = transaction.atomic() if self.apply else nullcontext()
                with ctx:
                    local = self._process_chunk(chunk)
            except Exception as exc:  # noqa: BLE001 —— 单 chunk 失败回滚后继续
                chunk_failures.append({
                    'chunk': start // chunk_size + 1,
                    'clusters': [c.get('cluster') for c in chunk],
                    'error': str(exc),
                })
                self.stderr.write(
                    f'[chunk {start // chunk_size + 1}] 处理失败，已回滚 '
                    f'（簇 {chunk[0].get("cluster")}..{chunk[-1].get("cluster")}，'
                    f'共 {len(chunk)} 簇）: {exc}')
                continue
            for k in totals:
                totals[k] += local[k]

        # 4) 汇总报告
        stats = {'mode': 'apply' if self.apply else 'dry-run', **totals}
        report = {'stats': stats, 'chunk_failures': chunk_failures}
        self._write_report(report, report_out)

    # ------------------------------------------------------------------ #
    # 读取
    # ------------------------------------------------------------------ #
    def _load_report(self, path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    # ------------------------------------------------------------------ #
    # chunk 处理
    # ------------------------------------------------------------------ #
    def _process_chunk(self, chunk):
        """处理一个 chunk 的若干簇（apply 时在调用方 atomic 事务内执行）。

        返回本地统计 dict（键同 _TOTAL_KEYS）。
        """
        local = {k: 0 for k in self._TOTAL_KEYS}
        for cluster in chunk:
            sub = self._process_cluster(cluster)
            for k in local:
                local[k] += sub[k]
        return local

    def _process_cluster(self, cluster):
        """处理单个簇：过滤 → 守卫 → 收集成员 → 合并/删除。

        返回本地统计 dict。
        """
        local = {k: 0 for k in self._TOTAL_KEYS}
        group = cluster.get('group')
        if group == 'rg':
            model = ResearchGoal
            by_id = self.rg_by_id
        elif group == 'ap':
            model = Application
            by_id = self.ap_by_id
        else:
            return local

        # 代表：不存在（已被删）→ 跳过该簇（天然幂等）
        rep = by_id.get(cluster.get('representative_id'))
        if rep is None:
            local['skipped_missing'] += 1
            return local

        # 策展守卫：has_curated 簇的代表必须为策展/导入来源
        if cluster.get('has_curated') and rep.origin not in _CURATED_ORIGINS:
            local['skipped_guard'] += 1
            self.stderr.write(
                f'[guard] 簇 {cluster.get("cluster")} has_curated 但代表 '
                f'"{rep.name}"（id={rep.id}, origin={rep.origin}）非策展，跳过整簇')
            return local

        # 成员：排除代表自己；缺失自动跳过；e2e/测试夹具跳过
        member_ids = [mid for mid in (cluster.get('member_ids') or [])
                      if mid != cluster.get('representative_id')]
        members_by_id = model.objects.in_bulk(member_ids) if member_ids else {}
        members = []
        for mid in member_ids:
            member = members_by_id.get(mid)
            if member is None:
                local['skipped_missing'] += 1
                continue
            if member.is_test_fixture or member.name.startswith('__e2e_'):
                local['skipped_e2e'] += 1
                continue
            members.append(member)

        if not members:
            return local

        local['processed_clusters'] += 1
        if self.apply:
            local['merged_entities'] += self._apply_cluster(group, rep, members, local)
        else:
            # dry-run 预估
            local['merged_entities'] += len(members)
            if group == 'rg':
                local['reloc_fk_aps'] += Application.objects.filter(
                    research_goal__in=[m.id for m in members]).count()
        return local

    # ------------------------------------------------------------------ #
    # apply：关联迁移 + 硬删
    # ------------------------------------------------------------------ #
    def _apply_cluster(self, group, rep, members, local):
        """合并一个簇的成员到代表并硬删成员。返回被删实体数。

        前置保证：成员已通过 e2e/夹具/策展守卫过滤。
        """
        deleted = 0
        if group == 'rg':
            for member in members:
                # RG 成员：protocols / application_collection 收拢到代表
                rep.protocols.add(*member.protocols.all())
                rep.application_collection.add(*member.application_collection.all())
                # FK 防护：把指向被删 RG 的 AP 改指代表，防止 CASCADE 误删
                n = Application.objects.filter(research_goal=member) \
                    .update(research_goal=rep)
                local['reloc_fk_aps'] += n
                member.delete()
                deleted += 1
        else:  # 'ap'
            for member in members:
                # AP 成员：把引用它的 RG 的 application_collection 从成员迁到代表
                # （research_goal_collections 为 Application 上的反向 M2M）
                for rg in member.research_goal_collections.all():
                    rg.application_collection.remove(member)
                    rg.application_collection.add(rep)
                member.delete()
                deleted += 1
        return deleted

    # ------------------------------------------------------------------ #
    # 报告
    # ------------------------------------------------------------------ #
    def _write_report(self, report, path):
        s = report['stats']
        self.stdout.write('=' * 64)
        self.stdout.write(f"模式：{s['mode']}  "
                          f"处理簇数：{s['processed_clusters']}  "
                          f"合并实体数：{s['merged_entities']}")
        self.stdout.write(f"FK 迁移 AP 数：{s['reloc_fk_aps']}  "
                          f"跳过(e2e/夹具)：{s['skipped_e2e']}  "
                          f"跳过(缺失)：{s['skipped_missing']}  "
                          f"跳过(策展守卫)：{s['skipped_guard']}")
        failures = report['chunk_failures']
        if failures:
            self.stdout.write(f"失败 chunk 数：{len(failures)}")
            for f in failures:
                self.stdout.write(
                    f"  [chunk {f['chunk']}] 簇 {len(f['clusters'])} 个: {f['error']}")
        else:
            self.stdout.write('失败 chunk 数：0')
        self.stdout.write('=' * 64)

        if path:
            os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            self.stdout.write(f'报告已写入 {path}')
