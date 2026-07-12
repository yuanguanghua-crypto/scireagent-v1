from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('knowledge', '0008_search_vectors'),
    ]

    operations = [
        migrations.AlterField(
            model_name='protocol',
            name='name',
            field=models.CharField(
                max_length=500,
                verbose_name='名称',
                help_text='协议全名，例如：CuAAC RNA Fluorescent Labeling Protocol',
            ),
        ),
    ]
