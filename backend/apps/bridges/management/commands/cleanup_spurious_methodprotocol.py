"""MethodProtocol 桥的诊断报告 + 人工收口清理工具。

## 语义变更历史（#494 收敛冗余 Protocol.method FK 之后）

**旧语义（已失效）**：判定标准是 `link.method_id != protocol.method_id`——拿桥上的
method 与协议的 canonical method（`Protocol.method` 单 FK）对照，不一致即视为旧版
`_sync_protocol_bridges` 笛卡尔积扇出的残留并删除。

**为何失效**：#494 删除了冗余的 `Protocol.method` FK，`MethodProtocol` 桥成为
协议↔方法关系的**唯一真源**。"一个协议合法关联多个方法"正是顶部链 facet 化的
预期形态，不再存在 canonical 对照物，**自动判定"虚假"在架构上永久不可能**。
同时笛卡尔 bug 源 `_sync_protocol_bridges` 已改为纯桥逻辑，不再扇出，新数据不会
再产生该类残留。

**新语义（保守化降级）**：遵循 Knowledge Links 铁律①「最大化数据、不删链」与
objective 补全的教训「自动判定拦不住错配，必须人工收口」：

  1. 不传 `--ids` 时：只做诊断报告，**绝不删除任何行**（即便带 `--no-dry-run`）。
     报告内容：桥总量、explicit 分布、协议扇出 Top N（供人工判断可疑项）。
  2. 传 `--ids` 且带 `--no-dry-run`：仅删除被点名且 `explicit=False` 的行。
  3. `explicit=True` 一律保留——即使被显式点名（#354 保护，不可绕过）。
  4. 传 `--ids` 但不带 `--no-dry-run`：dry-run，只报告将删哪些，不落库。

删除前请确认已备份 db.sqlite3。

用法：
    # 诊断（安全，永不删）
    python manage.py cleanup_spurious_methodprotocol
    # 人工点名后演练
    python manage.py cleanup_spurious_methodprotocol --ids 12,34,56
    # 确认无误后真删
    python manage.py cleanup_spurious_methodprotocol --ids 12,34,56 --no-dry-run
"""
from django.core.management.base import BaseCommand
from django.db.models import Count

from apps.bridges.models import MethodProtocol


class Command(BaseCommand):
    help = (
        "Diagnose MethodProtocol bridge rows; delete only explicitly targeted "
        "non-explicit rows (--ids). Never auto-deletes."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--ids",
            dest="ids",
            default="",
            help=(
                "Comma-separated MethodProtocol ids to delete (human curation). "
                "Without this, the command only reports and deletes nothing."
            ),
        )
        parser.add_argument(
            "--no-dry-run",
            action="store_true",
            dest="no_dry_run",
            default=False,
            help="Actually delete the targeted rows. Requires --ids.",
        )
        parser.add_argument(
            "--top",
            dest="top",
            type=int,
            default=20,
            help="How many highest-fanout protocols to list in the report (default 20).",
        )

    def _parse_ids(self, raw):
        ids = []
        for chunk in (raw or "").replace(" ", "").split(","):
            if not chunk:
                continue
            try:
                ids.append(int(chunk))
            except ValueError:
                self.stdout.write(self.style.ERROR(f"忽略非法 id: {chunk!r}"))
        return ids

    def handle(self, *args, **options):
        no_dry_run = options.get("no_dry_run", False)
        target_ids = self._parse_ids(options.get("ids", ""))
        top_n = options.get("top", 20)

        # ---------- 诊断报告（无论是否删除都输出） ----------
        total = MethodProtocol.objects.count()
        n_explicit = MethodProtocol.objects.filter(explicit=True).count()
        n_implicit = total - n_explicit

        self.stdout.write(self.style.WARNING(f"MethodProtocol 桥总行数 : {total}"))
        self.stdout.write(self.style.WARNING(f"  explicit=True (受保护): {n_explicit}"))
        self.stdout.write(self.style.WARNING(f"  explicit=False        : {n_implicit}"))

        # 协议扇出分布：一个协议挂了多少个方法。高扇出仅供人工审阅参考，
        # 不作为删除依据（多方法关联在 facet 化架构下合法）。
        fanout = (
            MethodProtocol.objects.values("protocol_id", "protocol__name")
            .annotate(c=Count("method_id", distinct=True))
            .filter(c__gt=1)
            .order_by("-c")[:top_n]
        )
        fanout = list(fanout)
        if fanout:
            self.stdout.write(
                f"关联多个方法的协议（Top {len(fanout)}，供人工审阅，非删除依据）："
            )
            for row in fanout:
                self.stdout.write(
                    f"  - [protocol_id={row['protocol_id']}] "
                    f"{row['protocol__name']}: {row['c']} 个方法"
                )
        else:
            self.stdout.write("无协议关联多个方法。")

        # ---------- 未点名 id：只报告，绝不删除 ----------
        if not target_ids:
            self.stdout.write(
                self.style.SUCCESS(
                    "仅诊断模式：未指定 --ids，未删除任何行。\n"
                    "  说明：#494 删除 Protocol.method FK 后，桥是唯一真源，"
                    "无法自动判定「虚假链路」，删除必须人工点名 id 收口。"
                )
            )
            return

        # ---------- 点名 id：过滤保护项 ----------
        targeted = MethodProtocol.objects.filter(id__in=target_ids)
        found_ids = set(targeted.values_list("id", flat=True))
        missing = [i for i in target_ids if i not in found_ids]
        protected = list(
            targeted.filter(explicit=True).values_list("id", flat=True)
        )
        deletable = list(
            targeted.filter(explicit=False).values_list("id", flat=True)
        )

        if missing:
            self.stdout.write(
                self.style.ERROR(f"以下 id 不存在，已忽略: {sorted(missing)}")
            )
        if protected:
            self.stdout.write(
                self.style.WARNING(
                    f"以下 id 为 explicit=True，受 #354 保护一律保留: {sorted(protected)}"
                )
            )
        self.stdout.write(f"可删除（explicit=False）: {sorted(deletable)}")

        if not deletable:
            self.stdout.write(self.style.SUCCESS("无可删除行，结束。"))
            return

        if no_dry_run:
            deleted, _ = MethodProtocol.objects.filter(id__in=deletable).delete()
            self.stdout.write(
                self.style.SUCCESS(f"已删除 {deleted} 行被点名的非显式桥关联。")
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"DRY-RUN：将删除 {len(deletable)} 行。"
                    "确认无误后加 --no-dry-run 真正执行。"
                )
            )
