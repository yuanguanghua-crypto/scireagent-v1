# S4 · tier 语义修正 + 广播沉底
# 1) tier 字段新增 'weak' 选择，并把默认由 'featured' 改为 'weak'
#    （'featured' 保留为历史值，仅存量回退兼容，不再自动派生）
# 2) 把存量 tier='featured' 行（dev 实测 974 行）重标为 'weak'
#    幂等、零删除（铁律①）。反向迁移可回滚。

from django.db import migrations, models


def _relabel_featured_to_weak(apps, schema_editor):
    PP = apps.get_model('bridges', 'ProductProtocol')
    PP.objects.filter(tier='featured').update(tier='weak')


def _reverse_relabel(apps, schema_editor):
    PP = apps.get_model('bridges', 'ProductProtocol')
    PP.objects.filter(tier='weak').update(tier='featured')


class Migration(migrations.Migration):

    dependencies = [
        ('bridges', '0003_methodprotocol_explicit'),
    ]

    operations = [
        migrations.AlterField(
            model_name='productprotocol',
            name='tier',
            field=models.CharField(
                choices=[
                    ('document', '文档相关'),
                    ('literature', '文献支持'),
                    ('featured', '编辑精选'),
                    ('weak', '弱相关'),
                ],
                default='weak',
                max_length=16,
                verbose_name='档位',
            ),
        ),
        migrations.RunPython(_relabel_featured_to_weak, _reverse_relabel),
    ]
