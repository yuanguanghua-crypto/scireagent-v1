"""
mark_test_fixture_products — 给「e2e / 自动化测试残留」的产品打 is_test_fixture 标记。

## 为什么需要

前台 `/products` 之前报 69 个结果，其中两条是测试残留：
- id=5460 `E2E PO Test Product`（`backend/seed_e2e_po_fixture.py` 每次 e2e 都会重建）
- id=2432 `Product 0`

真实产品 67 个 ⇒ 首页 StatsBar 与分类胶囊也对不上（67+0+0 ≠ 69）。

清库治不了根 —— seed 脚本每次跑都会把夹具造回来。所以：
① Product 加 `is_test_fixture` 字段（migration `0019_product_is_test_fixture`）；
② 本命令负责**给现存残留打标**；
③ seed 脚本创建时直接标 True（已改 `seed_e2e_po_fixture.py`）；
④ 公开读路径（`ProductViewSet` list / `site_home` / `categories`）统一排除。

## 安全约束

- **默认 dry-run**，必须 `--apply` 才写库（标记可逆：`--unmark` 反向操作）
- 只认**显式 id 清单**（`--id`）或**显式名字清单**（`--name`），不做模糊自动判定
- `--suggest` 只**列出**疑似残留供人工确认，绝不自动标记
- 标记不动任何业务字段，不影响 SKU / 订单 / 文档

## 用法

    # 先看有哪些疑似残留
    python manage.py mark_test_fixture_products --suggest

    # 预演
    python manage.py mark_test_fixture_products --id 5460 --id 2432

    # 执行
    python manage.py mark_test_fixture_products --id 5460 --id 2432 --apply

    # 反向（误标回滚）
    python manage.py mark_test_fixture_products --id 5460 --unmark --apply
"""
import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.commerce.models import Product

# 只用于 --suggest 的「疑似」提示，不参与任何自动写库
_SUSPECT_PATTERNS = [
    re.compile(r'^E2E\b', re.I),
    re.compile(r'^E2E[-_ ]', re.I),
    re.compile(r'^Product \d+$'),
    re.compile(r'test product', re.I),
]


def _visible():
    return Product.objects.filter(status__in=['active', 'published'], archived=False)


class Command(BaseCommand):
    help = '给测试残留产品打/撤 is_test_fixture 标记（默认预演，只认显式 id/name）'

    def add_arguments(self, parser):
        parser.add_argument('--id', action='append', type=int, default=[],
                            help='产品 id，可重复')
        parser.add_argument('--name', action='append', default=[],
                            help='产品名（精确匹配），可重复')
        parser.add_argument('--unmark', action='store_true', help='反向：把标记撤回 False')
        parser.add_argument('--apply', action='store_true', help='真正写库（默认只预演）')
        parser.add_argument('--suggest', action='store_true',
                            help='只列出疑似残留的产品，不做任何写库')

    def handle(self, *args, **opts):
        before = _visible().count()

        if opts['suggest']:
            self.stdout.write(f'当前公开可见产品 {before} 个。疑似测试残留：')
            hits = 0
            for p in _visible().order_by('id'):
                if p.is_test_fixture:
                    continue
                if any(rx.search(p.name or '') for rx in _SUSPECT_PATTERNS):
                    hits += 1
                    self.stdout.write(f'  id={p.id} name={p.name!r} status={p.status} '
                                      f'class={p.product_class_id}')
            self.stdout.write(f'共 {hits} 条疑似。确认后用 --id 显式标记。')
            return

        ids = set(opts['id'])
        names = set(opts['name'])
        if not ids and not names:
            raise CommandError('必须提供 --id 或 --name（或先用 --suggest 看候选）。')

        targets = Product.objects.all()
        q = None
        if ids:
            q = targets.filter(id__in=ids)
        if names:
            qn = targets.filter(name__in=names)
            q = qn if q is None else (q | qn)
        targets = q.order_by('id')

        if not targets:
            raise CommandError('没有匹配到任何产品。')

        new_value = not opts['unmark']
        will_change = [p for p in targets if p.is_test_fixture != new_value]
        already = len(list(targets)) - len(will_change)

        self.stdout.write(f'匹配 {len(list(targets))} 个产品：')
        for p in targets:
            flag = '★变更' if p.is_test_fixture != new_value else '  已是'
            self.stdout.write(f'  [{flag}] id={p.id} name={p.name!r} '
                              f'status={p.status} archived={p.archived} '
                              f'当前={p.is_test_fixture} → {new_value}')

        self.stdout.write(f'将变更 {len(will_change)} 条，{already} 条已是目标值。')
        if not will_change:
            self.stdout.write(self.style.SUCCESS('无需动作。'))
            return

        if not opts['apply']:
            self.stdout.write(self.style.WARNING('\n预演，未写库。加 --apply 执行。'))
            return

        with transaction.atomic():
            changed = Product.objects.filter(
                id__in=[p.id for p in will_change]
            ).update(is_test_fixture=new_value)

        after = _visible().count()
        self.stdout.write(self.style.SUCCESS(
            f'已更新 {changed} 条。公开可见产品 {before} → {after}'))
