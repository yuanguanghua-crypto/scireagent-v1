# P1 migration 草稿 ②：bridges.MethodProtocol 增加 evidence_source（来源标记）
# 文件名建议：apps/bridges/migrations/0005_methodprotocol_evidence_source.py
# 依赖：0004_tier_weak_relabel（dev 最新）
# ⚠️ 草稿供 review，未执行。
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("bridges", "0004_tier_weak_relabel"),
    ]

    operations = [
        migrations.AddField(
            model_name="methodprotocol",
            name="evidence_source",
            field=models.CharField(
                max_length=32, blank=True, default="legacy", verbose_name="关联来源",
                help_text="lexicon_auto=词典自动标注；manual_curated=人工策展；llm_reviewed=LLM 判定；legacy=历史遗留映射",
                choices=[
                    ("lexicon_auto", "词典自动标注"),
                    ("manual_curated", "人工策展"),
                    ("llm_reviewed", "LLM 判定"),
                    ("legacy", "历史遗留"),
                ],
            ),
        ),
    ]
