# P1 migration 草稿 ①：knowledge.Method 增加草案 §6 字段
# 文件名建议：apps/knowledge/migrations/0018_method_add_topchain_fields.py
# 依赖：0017_alter_protocol_options_and_more（dev 最新）
# ⚠️ 草稿供 review，未执行。执行前须确认依赖 migration 号与 dev/prod 一致。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("knowledge", "0017_alter_protocol_options_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="method",
            name="method_type",
            field=models.CharField(
                max_length=32, blank=True, default="", verbose_name="方法类型",
                choices=[("technique", "技术"), ("assay", "测定"), ("sample_prep", "样本制备"), ("analysis", "分析")],
            ),
        ),
        migrations.AddField(
            model_name="method",
            name="commercial_relevance",
            field=models.CharField(
                max_length=32, blank=True, default="unsupported", verbose_name="商业相关性",
                choices=[("core", "核心"), ("adjacent", "相邻"), ("unsupported", "无对应商品")],
            ),
        ),
        migrations.AddField(
            model_name="method",
            name="reagent_dependency_type",
            field=models.CharField(
                max_length=32, blank=True, default="none", verbose_name="试剂依赖类型",
                choices=[("essential", "必需"), ("enabling", "可替代"), ("optional", "可选"), ("none", "无直接依赖")],
            ),
        ),
        migrations.AddField(
            model_name="method",
            name="canonical_name",
            field=models.CharField(max_length=255, blank=True, default="", verbose_name="英文规范名"),
        ),
        migrations.AddField(
            model_name="method",
            name="definition",
            field=models.TextField(blank=True, default="", verbose_name="定义"),
        ),
        migrations.AddField(
            model_name="method",
            name="experimental_purpose",
            field=models.TextField(blank=True, default="", verbose_name="实验目的"),
        ),
        migrations.AddField(
            model_name="method",
            name="grounded_term",
            field=models.CharField(max_length=500, blank=True, default="", verbose_name="接地术语"),
        ),
        migrations.AddField(
            model_name="method",
            name="grounded_ontology",
            field=models.CharField(max_length=64, blank=True, default="", verbose_name="接地本体"),
        ),
        migrations.AddField(
            model_name="method",
            name="grounded_iri",
            field=models.CharField(max_length=500, blank=True, default="", verbose_name="接地 IRI"),
        ),
        migrations.AddField(
            model_name="method",
            name="match_type",
            field=models.CharField(
                max_length=32, blank=True, default="", verbose_name="接地匹配类型",
                choices=[("exact", "精确"), ("close", "近似"), ("partial", "部分"), ("no_match", "无匹配")],
            ),
        ),
    ]
