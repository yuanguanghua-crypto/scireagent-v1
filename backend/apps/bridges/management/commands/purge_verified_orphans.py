"""purge_verified_orphans — 清理 verified 通道的孤儿行（rejected 残留）。

为什么要用管理命令，而不是新开一个 API DELETE 端点
==================================================
`/verified/` 通道目前只有 approve / reject / patch 三个动作，**没有 DELETE**；
`reject` 只把行 `status` 置为 `rejected`，**行永远留在库中**，于是孤儿行
无限累积（dev 库已有历史遗留 id=609）。E2E 只能靠本地 sqlite 硬删来复原计数，
不可持续。

本工具解决"如何安全移除这些残留行"。之所以做成 **Django 管理命令（运维通道）**
而非在 bridges API 上新增一个 DELETE 端点：

  - 新增 DELETE 端点会**扩大权限面**（谁能删？staff？），并引入新的鉴权、
    限流与审计需求；而"删除"本质是**不可逆的数据清理**，属于低频、人工决策的
    运维动作，不适合暴露成常驻的 HTTP 面。
  - 管理命令天然只在服务器 shell 上、由运维人员**显式执行**，且**默认 dry-run**，
    与「最小权限面 + 显式意图」原则一致；非 API 面，因此这里不做任何
    HTTP / 登录 / 权限判断。

安全纪律（照抄本项目 rc_seed.py 的"默认 dry-run"）
==================================================
  - 不加 `--apply` **绝不删任何行**，只打印"将删除的条数与若干样例"。
  - 只删 `status='rejected'` 的行（`--status` 可覆盖，默认必须是 rejected；
    若显式传非 rejected 值，输出里**显著告警**）。
  - **显式意图护栏**：既没给 `--id`、也没给任何过滤器（`--note-like` /
    `--older-than-days`），且没有 `--all-rejected` → **拒绝执行**并打印用法。
  - dry-run 与实际执行都打印删除前 / 后的 `rejected` 总数。

用法
====
    # 1) dry-run：清点全部 rejected（只报告，不删）
    python manage.py purge_verified_orphans --all-rejected
    # 2) 点名删除（dry-run 先看一遍，再加 --apply）
    python manage.py purge_verified_orphans --id 609
    python manage.py purge_verified_orphans --id 609 --apply
    # 3) 按 evidence_note 子串
    python manage.py purge_verified_orphans --note-like <子串> --apply
    # 4) 按 updated_at 早于 N 天
    python manage.py purge_verified_orphans --older-than-days 30 --apply

删除前请确认已备份 db.sqlite3。
"""
from datetime import timedelta

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.bridges.models import ProductMethodRelation

DEFAULT_STATUS = ProductMethodRelation.Status.REJECTED  # 'rejected'


class Command(BaseCommand):
    help = (
        'Purge orphan ProductMethodRelation rows (default status=rejected). '
        'Dry-run by default; only --apply deletes.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply', action='store_true', default=False,
            help='真正删除（默认 dry-run，仅报告将删除的条数）。',
        )
        parser.add_argument(
            '--status', default=DEFAULT_STATUS,
            help=f'要删除的 status（默认 {DEFAULT_STATUS!r}）。'
                 '若设为其它值（如 active）请务必二次确认。',
        )
        parser.add_argument(
            '--id', dest='ids', action='append', type=int, default=[],
            help='按 id 删除；可多次传入（--id 609 --id 610）。',
        )
        parser.add_argument(
            '--note-like', dest='note_like', default='',
            help='按 evidence_note 子串过滤（icontains）。',
        )
        parser.add_argument(
            '--older-than-days', dest='older_than_days', type=int, default=None,
            help='按 updated_at 早于 N 天过滤。',
        )
        parser.add_argument(
            '--all-rejected', dest='all_rejected', action='store_true',
            default=False,
            help='显式确认「清理全部 rejected 行」（默认 status 下等价全清）。',
        )
        parser.add_argument(
            '--sample', dest='sample', type=int, default=10,
            help='dry-run / apply 时打印的样例条数（默认 10）。',
        )

    def _usage(self):
        return (
            '用法（至少给出一个显式选择器）：\n'
            '  python manage.py purge_verified_orphans --all-rejected\n'
            '  python manage.py purge_verified_orphans --id <id> [--apply]\n'
            '  python manage.py purge_verified_orphans --note-like <子串> [--apply]\n'
            '  python manage.py purge_verified_orphans --older-than-days <N> [--apply]'
        )

    def handle(self, *args, **options):
        apply_ = options['apply']
        status = options['status']
        ids = options.get('ids') or []
        note_like = (options.get('note_like') or '').strip()
        older_than_days = options.get('older_than_days')
        all_rejected = options.get('all_rejected')
        sample_n = max(0, options.get('sample', 10))

        # ---------- 护栏 1：必须有显式意图 ----------
        has_filter = bool(ids) or bool(note_like) or (older_than_days is not None)
        if not has_filter and not all_rejected:
            raise CommandError(
                '拒绝执行：未给出任何显式选择器（--id / --note-like / '
                '--older-than-days），也未给 --all-rejected。\n' + self._usage()
            )

        # ---------- 护栏 2：允许非 rejected，但显著告警 ----------
        if status != DEFAULT_STATUS:
            self.stdout.write(self.style.ERROR(
                f'⚠ 告警：--status={status!r} 不是默认的 {DEFAULT_STATUS!r}，'
                f'将按此状态删除（风险更高，请确认你清楚在做什么）。'
            ))

        # ---------- 组查询 ----------
        qs = ProductMethodRelation.objects.filter(status=status)
        if ids:
            qs = qs.filter(id__in=ids)
        if note_like:
            qs = qs.filter(evidence_note__icontains=note_like)
        if older_than_days is not None:
            cutoff = timezone.now() - timedelta(days=older_than_days)
            qs = qs.filter(updated_at__lt=cutoff)

        rejected_total = ProductMethodRelation.objects.filter(
            status=DEFAULT_STATUS).count()
        target = list(
            qs.values('id', 'product_id', 'method_id', 'status', 'evidence_note')
        )
        n = len(target)

        mode = 'APPLY' if apply_ else 'DRY-RUN'
        self.stdout.write(self.style.WARNING(
            f'=== purge_verified_orphans [{mode}] status={status} ==='
        ))
        self.stdout.write(f'rejected 总数（删除前）: {rejected_total}')
        self.stdout.write(f'命中条件、将删除的行数: {n}')

        if n == 0:
            self.stdout.write(self.style.SUCCESS('没有命中任何行，结束（未写库）。'))
            self.stdout.write(
                f'rejected 总数（删除后）: {rejected_total}（未变）'
            )
            return

        for row in target[:sample_n]:
            note = (row['evidence_note'] or '')[:60].replace('\n', ' ')
            self.stdout.write(
                f"  - id={row['id']} product_id={row['product_id']} "
                f"method_id={row['method_id']} status={row['status']} "
                f"note={note!r}"
            )
        if n > sample_n:
            self.stdout.write(f'  … 其余 {n - sample_n} 条略。')

        # ---------- 默认 dry-run：绝不写库 ----------
        if not apply_:
            self.stdout.write(self.style.SUCCESS(
                f'DRY-RUN：将删除 {n} 行，未写库。确认无误后加 --apply。'
            ))
            self.stdout.write(
                f'rejected 总数（删除后，dry-run 未写库）: '
                f'{rejected_total}（不变）'
            )
            return

        # ---------- 实际执行 ----------
        deleted, _ = ProductMethodRelation.objects.filter(
            id__in=[r['id'] for r in target]
        ).delete()
        rejected_after = ProductMethodRelation.objects.filter(
            status=DEFAULT_STATUS).count()
        self.stdout.write(self.style.SUCCESS(
            f'已删除 {deleted} 行。rejected 总数（删除后）: {rejected_after} '
            f'(删除前 {rejected_total})'
        ))
