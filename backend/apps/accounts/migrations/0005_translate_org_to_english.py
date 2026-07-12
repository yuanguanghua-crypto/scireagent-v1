"""Translate the wrongly-imported Chinese Organization name to English.

The initial data import left one Organization (pk=3) with a Chinese name.
The platform is English-only, so this one-off data migration rewrites it.
Runs on both SQLite (dev) and Postgres (prod). Reversible.
"""

from django.db import migrations


def translate_org(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    obj = Organization.objects.filter(pk=3).first()
    if obj:
        obj.name = "Guangzhou Chunxi Technology Co., Ltd."
        obj.save()


def revert_org(apps, schema_editor):
    Organization = apps.get_model('accounts', 'Organization')
    obj = Organization.objects.filter(pk=3).first()
    if obj:
        obj.name = "广州纯析科技有限公司"
        obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0004_address'),
    ]

    operations = [
        migrations.RunPython(translate_org, revert_org),
    ]
