"""QuoteRequest 增加客户答复态与答复时间（A-264）。

## 改前
状态枚举只有 pending / reviewing / quoted / closed —— **没有任何表示
"客户接受了报价"或"客户拒绝了报价"的终态**。配套地，客户侧四个页面
（/orders、/po/orders、/po/reorder、/po/downloads）也没有查看/接受/拒绝的入口。
⇒ 「客户收到报价后能不能答复」这件事在整个系统里无法表达（QA A-264）。

## 本迁移
1. `status` 的 choices 增加 `accepted` / `rejected`（纯 choices，**PostgreSQL 上零 DDL**）；
2. 新增 `customer_responded_at`（可空时间戳），记录答复发生的时刻。
历史行的 `customer_responded_at` 保持 NULL（那批单子本来就没有答复过）。

手写而非 makemigrations：`config/settings/base.py` 有守卫禁止在 sqlite 下生成迁移
（会臆造「删 search_vector / 删 GIN 索引」的破坏性操作）；CI 有
`makemigrations --check --dry-run` 闸门，故手写一份与模型等价的变更。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotes', '0003_quoterequestitem_requested_text_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quoterequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending', '待处理'),
                    ('reviewing', '审核中'),
                    ('quoted', '已报价'),
                    ('accepted', '已接受'),
                    ('rejected', '已拒绝'),
                    ('closed', '已关闭'),
                ],
                default='pending',
                max_length=20,
                verbose_name='状态',
            ),
        ),
        migrations.AddField(
            model_name='quoterequest',
            name='customer_responded_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='客户答复时间',
            ),
        ),
    ]
