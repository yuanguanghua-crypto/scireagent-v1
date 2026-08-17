"""recompute_protocol_relevance —— 重算并落 ProductProtocol 三轴相关性（§7/§14）。

离线预计算：轴C(embedding) 经可注入 embedding_fn 计算并持久化到 score_c；
默认路径惰性加载 emb3_venv 模型（决策 Q4：轴C 离线预计算持久化，运行时只读）。

用法：
    python manage.py recompute_protocol_relevance [--product SC8001] [--force]

幂等：逐产品 update_or_create，重跑安全。
"""
from django.core.management.base import BaseCommand

from apps.commerce.models import Product
from apps.bridges.services.relevance import recompute_product


class Command(BaseCommand):
    help = "Recompute three-axis relevance and upsert ProductProtocol rows."

    # embedding_fn 为测试/离线注入的可调用（返回 cosine），不经 argparse 强制；
    # 列为 stealth option 使 call_command(embedding_fn=fn) 透传且不要求 CLI 声明。
    stealth_options = ('embedding_fn',)

    def add_arguments(self, parser):
        parser.add_argument(
            "--product", default=None,
            help="Only recompute this product (by id or catalog_no).",
        )
        parser.add_argument(
            "--force", action="store_true", default=False,
            help="Force recompute even if rows exist (upsert is idempotent anyway).",
        )

    def handle(self, *args, **options):
        # embedding_fn 由调用方通过 call_command(..., embedding_fn=fn) 注入（测试/离线）
        embedding_fn = options.get('embedding_fn')

        product_arg = options.get('product')
        if product_arg:
            # 兼容数字 id 与 catalog_no 字符串（避免对字符串 catalog 做 id 过滤抛 ValueError）
            try:
                qs = Product.objects.filter(id=int(product_arg))
            except (ValueError, TypeError):
                qs = Product.objects.filter(catalog_no=product_arg)
            if not qs.exists():
                self.stderr.write(self.style.ERROR(
                    f"Product not found: {product_arg}"))
                return
        else:
            qs = Product.objects.all()

        total = 0
        products_processed = 0
        for product in qs.iterator():
            n = recompute_product(product, embedding_fn=embedding_fn)
            total += n
            products_processed += 1

        self.stdout.write(self.style.SUCCESS(
            f"Recomputed {products_processed} products, wrote/updated "
            f"{total} ProductProtocol rows."
        ))
