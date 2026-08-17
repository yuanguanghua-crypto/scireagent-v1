"""清理 MethodProtocol 中的虚假交叉链路（派生冗余 bug 的数据残留）。

背景：旧版 `_sync_protocol_bridges` 用 method_ids × protocol_ids 笛卡尔积，
把「本仅属某方法 M1 的协议 P」额外挂到产品的所有方法（M1、M2…），
向共享的 MethodProtocol 表注入 link.method != protocol.method 的虚假交叉链路。
这些链路污染了其他产品的派生协议集（编辑页协议铺满 19~26 条泛化协议的放大器）。

判定标准：MethodProtocol 行的 `explicit=False` 且 `link.method_id != protocol.method_id`
即视为笛卡尔 bug 产物。**显式关联（explicit=True）一概保留**——即使 method 与
protocol 的 canonical method 不同，也视为研究者合法建立的跨方法关联，绝不误删。

默认 --dry-run 只报告不删除；加 --no-dry-run 才真正删除。
删除前请确认已备份 db.sqlite3。
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Q

from apps.bridges.models import MethodProtocol
from apps.knowledge.models import Protocol


class Command(BaseCommand):
    help = "Remove spurious cross-links in MethodProtocol (link.method != protocol.method)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            dest="no_dry_run",
            default=False,
            help="Actually delete the spurious rows. Without this, only report (dry-run).",
        )

    def handle(self, *args, **options):
        no_dry_run = options.get("no_dry_run", False)

        # protocol_id -> canonical method_id
        proto_method = dict(
            Protocol.objects.values_list("id", "method_id")
        )

        spurious_ids = []
        for mp in MethodProtocol.objects.select_related("method", "protocol").iterator():
            # 显式关联一律保留（保护合法跨方法链接，#354）
            if mp.explicit:
                continue
            pmethod = proto_method.get(mp.protocol_id)
            if pmethod is None:
                # protocol without a canonical method -> cannot judge; skip (do not delete)
                continue
            if mp.method_id != pmethod:
                spurious_ids.append(mp.id)

        total = MethodProtocol.objects.count()
        n_spurious = len(spurious_ids)

        self.stdout.write(
            self.style.WARNING(f"MethodProtocol total rows : {total}")
        )
        self.stdout.write(
            self.style.WARNING(f"Spurious cross-links   : {n_spurious}")
        )

        # Group by protocol for visibility
        if n_spurious:
            affected = (
                MethodProtocol.objects.filter(id__in=spurious_ids)
                .values("protocol__name")
                .annotate(c=Count("id"))
                .order_by("-c")[:20]
            )
            self.stdout.write("Top affected protocols:")
            for row in affected:
                self.stdout.write(f"  - {row['protocol__name']}: {row['c']}")

        if no_dry_run:
            deleted, _ = MethodProtocol.objects.filter(id__in=spurious_ids).delete()
            self.stdout.write(
                self.style.SUCCESS(f"DELETED {deleted} spurious cross-links.")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "DRY-RUN only. Re-run with --no-dry-run to actually delete."
                )
            )
