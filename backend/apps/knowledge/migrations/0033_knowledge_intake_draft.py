"""知识录入草稿表（A-070 方案 A，用户 2026-11-28 定）。

⚠️ **手写迁移**：本仓库禁止直接跑 `makemigrations` —— 模型与 DB 存在历史漂移，
`makemigrations` 会连带生成 `RemoveField search_vector` 与
`RemoveIndex product_search_gin / method_search_gin / protocol_name_objective_trgm /
reference_search_gin`（见 `settings/base.py` 顶部守卫与该处注释），提交即连根拔掉全文检索。

本迁移只做一件事：建 `knowledge_intake_draft` 表。
"""
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0032_alter_method_definition_methoddefinition'),
        ('commerce', '0020_product_shelf_life_4y'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='KnowledgeIntakeDraft',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True, serialize=False,
                    verbose_name='ID')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='创建时间')),
                ('updated_at', models.DateTimeField(auto_now=True, verbose_name='更新时间')),
                ('form_json', models.JSONField(
                    default=dict,
                    help_text='Intake 表单的原始提交内容（用于回填，不参与业务判定）',
                    verbose_name='表单内容')),
                ('product', models.OneToOneField(
                    help_text='一个产品只保留当前一份草稿；保存即覆盖',
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='intake_draft', to='commerce.product',
                    verbose_name='产品')),
                ('created_by', models.ForeignKey(
                    blank=True, null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='intake_drafts',
                    to=settings.AUTH_USER_MODEL, verbose_name='最后保存人')),
            ],
            options={
                'verbose_name': '知识录入草稿',
                'verbose_name_plural': '知识录入草稿',
                'db_table': 'knowledge_intake_draft',
                'ordering': ['-updated_at'],
            },
        ),
    ]
