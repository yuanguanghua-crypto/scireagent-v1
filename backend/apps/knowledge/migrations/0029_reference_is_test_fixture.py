"""Reference 增加 is_test_fixture 标记字段。

背景（2026-10-30 C 批）：本地库 219 条 Reference 里有 32 条 e2e 残留
（31 条 `__e2e_references_*__` + 1 条 `E2E stub reference`）。因为那段 stub
的 `year=2026`，它**排在首页 "Recent Publications" 第一位** —— 一旦把
ReferencesSection 接入首页就会直接暴露。

ResearchGoal / Application / Method / Protocol / Product 都已有该标记，
Reference 是最后一个缺口。本迁移只加列 + 索引，**不回填数据**：
回填走 `manage.py mark_test_fixtures --model Reference`，因为「哪些条算夹具」
要按环境分别核对。

手写而非 makemigrations：`config/settings/base.py` 有守卫，禁止在 sqlite
环境生成迁移（会臆造「删列/删索引」）。本次不触碰任何 PG 专属字段。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0028_method_description_reviewed'),
    ]

    operations = [
        migrations.AddField(
            model_name='reference',
            name='is_test_fixture',
            field=models.BooleanField(
                db_index=True, default=False,
                help_text='True 表示此行由自动化测试残留产生，不参与任何对外展示与统计；'
                          '仅作标记，数据不会被删除',
                verbose_name='测试夹具',
            ),
        ),
    ]
