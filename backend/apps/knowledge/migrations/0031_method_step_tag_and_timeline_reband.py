# 手写 migration（`config/settings/base.py` 禁止在 sqlite 下 makemigrations）
#
# 两件事：
#   ① Timeline 枚举重设（原 minutes/hours/days/weeks 作废，改 4h/10h/20h 三切点）
#   ② Method 加 is_step_tag（通用步骤标签，决策 1B）
#
# ⚠️ ① **不会自动转换已有数据**。旧值 `days`/`hours`/`weeks` 迁移后成为
#    「不在 choices 内」的历史值，必须紧跟 `retag_method_specs` 命令重算，
#    否则 `--verify` 会报大量非法值。

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('knowledge', '0030_method_specs_reviewed'),
    ]

    operations = [
        migrations.AlterField(
            model_name='method',
            name='timeline',
            field=models.CharField(
                blank=True, default='',
                choices=[
                    ('lt_4h', '4 小时内'),
                    ('h4_10', '4–10 小时'),
                    ('h10_20', '10–20 小时'),
                    ('gt_20h', '超过 20 小时'),
                    ('', '未确定'),
                ],
                help_text='完成一次实验所需的大致时间', max_length=100,
                verbose_name='时间线',
            ),
        ),
        migrations.AddField(
            model_name='method',
            name='is_step_tag',
            field=models.BooleanField(
                db_index=True, default=False,
                help_text='True = 实为其他实验的必经工序（协议共享度≥85% 且定义分歧高），'
                          '不作为独立方法展示',
                verbose_name='通用步骤标签',
            ),
        ),
    ]
