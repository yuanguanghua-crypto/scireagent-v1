"""Shrink CategoryL1 enum to 3 adopted jena product lines.

Removes proteins/probes_epigenetics/rna_technologies/antibodies_antigens/
crystallography_cryoem/custom_synthesis from category_l1 choices. DB column
retained for historical read-only access; new writes go through product_class_id.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('commerce', '0006_product_current_sds'),
    ]

    operations = [
        migrations.AlterField(
            model_name='product',
            name='category_l1',
            field=models.CharField(
                blank=True,
                choices=[
                    ('nucleotides_nucleosides', 'Nucleotides & Nucleosides / 核苷酸/核苷'),
                    ('click_chemistry', 'Click Chemistry / 点击化学'),
                    ('molecular_biology', 'Molecular Biology / 分子生物学'),
                ],
                default='',
                help_text='已废弃：新写入走 product_class_id。此列保留作历史数据只读。',
                max_length=128,
                verbose_name='一级分类 (L1)',
            ),
        ),
        migrations.AlterField(
            model_name='product',
            name='category_l2',
            field=models.CharField(
                blank=True,
                default='',
                help_text='已废弃：新写入走 product_class_id。此列保留作历史数据只读。',
                max_length=128,
                verbose_name='二级分类 (L2)',
            ),
        ),
    ]
