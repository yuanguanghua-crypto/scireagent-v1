from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0012_product_aggregate_relevance_score'),
    ]

    operations = [
        migrations.AddField(
            model_name='product',
            name='substructure_tags',
            field=models.JSONField(blank=True, help_text='S6：由 detect_substructures --write 离线填充，展示用四轴修饰标签（base / sugar_sub / sugar_type / label）。不进用户写入路径。', null=True, verbose_name='四轴子结构标签'),
        ),
    ]
