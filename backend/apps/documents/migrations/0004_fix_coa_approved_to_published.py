"""一次性数据迁移：将历史 status='approved' 的 COA 行改写为 'published'。

背景：approve_coa 早期写入 APPROVED，本期改为 PUBLISHED（APPROVED 保留在 choices
中仅作历史兼容）。若存在历史 approved 行，这里统一迁移，保证状态机一致。

幂等：仅影响 status='approved' 的行；无此类行则跳过（无副作用）。
"""
from django.db import migrations


def _forward(apps, schema_editor):
    Coa = apps.get_model('documents', 'Coa')
    updated = Coa.objects.filter(status='approved').update(status='published')
    if updated:
        print(f'[data-migration] Coa approved→published: {updated} row(s) migrated')


def _reverse(apps, schema_editor):
    # 回滚：将刚迁来的 published 行恢复为 approved（仅在确实由本迁移产生时合理）。
    Coa = apps.get_model('documents', 'Coa')
    Coa.objects.filter(status='published').update(status='approved')


class Migration(migrations.Migration):
    dependencies = [
        ('documents', '0003_sdsrevision_data_confidence_and_more'),
    ]

    operations = [
        migrations.RunPython(_forward, _reverse),
    ]
