# 手写 migration（`config/settings/base.py` 禁止在 sqlite 下 makemigrations）

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0029_reference_is_test_fixture'),
    ]

    operations = [
        migrations.AddField(
            model_name='method',
            name='specs_reviewed_at',
            field=models.DateTimeField(
                blank=True, null=True, verbose_name='规格审核时间',
                help_text='为空表示 advantages/limitations/timeline 是 AI 初稿未经审核；'
                          '有值表示已由领域专家确认',
            ),
        ),
    ]
