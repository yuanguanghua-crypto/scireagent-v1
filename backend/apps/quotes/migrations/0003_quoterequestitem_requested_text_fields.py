"""QuoteRequestItem 增加「手填产品名 / 货号」两列（A-026）。

## 改前是什么样（实测）
客户端的 RFQ 表单允许**只填产品名、不挂产品**（`product_id` 可为 null）。
但提交时前端 `.map()` 只送 `product_id / quantity / note` —— 手填的名称与货号被丢掉，
`sku` 更是从来没送过。于是后端只能落一条 `product=NULL, sku=NULL, note=''` 的明细：
运营在 RFQ Inbox 里看到 **PRODUCT "—" / SKU "—"**，只想知道客户要什么全靠猜。

dev 实测：`quote_request_item` 91 行里 **91 行** product 与 sku **同时为 NULL**。

## 本迁移
只加两个文本列（`requested_product_name` / `requested_catalog_no`），**不加索引、不改既有列**，
零 DDL 风险（两张 varchar）。历史行留空 —— 那批数据本来就没有保存过名称，无法回填。

手写而非 makemigrations：`config/settings/base.py` 有守卫禁止在 sqlite 下生成迁移
（会臆造「删 search_vector / 删 GIN 索引」的破坏性操作）。CI 有
`makemigrations --check --dry-run` 闸门 ⇒ 迁移状态必须与模型一致，故手写一份等价的 AddField。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('quotes', '0002_quoterequest_quoted_at_quoterequest_quoted_currency_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='quoterequestitem',
            name='requested_product_name',
            field=models.CharField(
                blank=True, default='', max_length=300,
                verbose_name='客户填写的产品名',
                help_text='客户只填名字、未挂库内产品时保存到这里',
            ),
        ),
        migrations.AddField(
            model_name='quoterequestitem',
            name='requested_catalog_no',
            field=models.CharField(
                blank=True, default='', max_length=100,
                verbose_name='客户填写的货号',
                help_text='客户手填的目录号/SKU 文本（未匹配到库内 SKU 时）',
            ),
        ),
    ]
