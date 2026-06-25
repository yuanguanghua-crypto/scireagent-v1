from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('commerce', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='PubChemCache',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cas_number', models.CharField(db_index=True, max_length=20, verbose_name='CAS号')),
                ('cid', models.IntegerField(blank=True, null=True, verbose_name='PubChem CID')),
                ('data_json', models.TextField(help_text='完整的 PubChem 返回数据 JSON', verbose_name='PubChem 数据')),
                ('fetched_at', models.DateTimeField(auto_now=True, verbose_name='获取时间')),
            ],
            options={
                'verbose_name': 'PubChem 缓存',
                'verbose_name_plural': 'PubChem 缓存',
                'db_table': 'pubchem_cache',
            },
        ),
        migrations.CreateModel(
            name='Batch',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lot_number', models.CharField(help_text='例如：SC8001-L2026001', max_length=50, unique=True, verbose_name='批次号')),
                ('produced_at', models.DateField(verbose_name='生产日期')),
                ('retest_at', models.DateField(blank=True, null=True, verbose_name='复检日期')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('sku', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='batches', to='commerce.sku', verbose_name='SKU')),
            ],
            options={
                'verbose_name': '批次',
                'verbose_name_plural': '批次',
                'db_table': 'batch',
                'ordering': ['-produced_at'],
            },
        ),
        migrations.CreateModel(
            name='Coa',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('doc_id', models.CharField(help_text='例如：COA-SC8001-2026-001', max_length=50, unique=True, verbose_name='文档编号')),
                ('status', models.CharField(choices=[('draft', '草稿'), ('approved', '已审批'), ('published', '已发布')], default='draft', max_length=20, verbose_name='状态')),
                ('product_name', models.CharField(max_length=255, verbose_name='产品名称')),
                ('catalog_number', models.CharField(max_length=64, verbose_name='目录号')),
                ('cas_number', models.CharField(blank=True, default='', max_length=20, verbose_name='CAS号')),
                ('molecular_formula', models.CharField(blank=True, default='', max_length=100, verbose_name='分子式')),
                ('molecular_weight', models.CharField(blank=True, default='', max_length=30, verbose_name='分子量')),
                ('storage_condition', models.CharField(blank=True, default='', max_length=200, verbose_name='储存条件')),
                ('appearance_spec', models.CharField(blank=True, default='', max_length=200, verbose_name='外观标准')),
                ('appearance_result', models.CharField(blank=True, default='', max_length=200, verbose_name='外观实测')),
                ('purity_spec', models.CharField(blank=True, default='', max_length=50, verbose_name='纯度标准')),
                ('purity_result', models.CharField(blank=True, default='', max_length=50, verbose_name='纯度实测')),
                ('purity_method', models.CharField(blank=True, default='', max_length=100, verbose_name='纯度方法')),
                ('water_content_spec', models.CharField(blank=True, default='', max_length=50, verbose_name='水分标准')),
                ('water_content_result', models.CharField(blank=True, default='', max_length=50, verbose_name='水分实测')),
                ('melting_point', models.CharField(blank=True, default='', max_length=100, verbose_name='熔点')),
                ('specific_rotation', models.CharField(blank=True, default='', max_length=100, verbose_name='比旋光度')),
                ('residual_solvents', models.CharField(blank=True, default='', max_length=200, verbose_name='残留溶剂')),
                ('heavy_metals', models.CharField(blank=True, default='', max_length=100, verbose_name='重金属')),
                ('nmr_result', models.TextField(blank=True, default='', verbose_name='NMR 结果')),
                ('lcms_result', models.CharField(blank=True, default='', max_length=200, verbose_name='LC-MS 结果')),
                ('hplc_conditions', models.TextField(blank=True, default='', verbose_name='HPLC 条件')),
                ('lcms_conditions', models.TextField(blank=True, default='', verbose_name='LC-MS 条件')),
                ('qc_analyst', models.CharField(blank=True, default='', max_length=100, verbose_name='QC 分析师')),
                ('qa_approval', models.CharField(blank=True, default='', max_length=100, verbose_name='QA 审批')),
                ('approved_at', models.DateTimeField(blank=True, null=True, verbose_name='审批时间')),
                ('pdf_path', models.CharField(blank=True, default='', max_length=500, verbose_name='PDF 路径')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('batch', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='coa', to='documents.batch', verbose_name='批次')),
            ],
            options={
                'verbose_name': 'COA',
                'verbose_name_plural': 'COA',
                'db_table': 'coa',
            },
        ),
        migrations.CreateModel(
            name='SdsRevision',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('revision_no', models.IntegerField(verbose_name='修订版本号')),
                ('revised_at', models.DateField(verbose_name='修订日期')),
                ('change_note', models.TextField(blank=True, default='', verbose_name='修订说明')),
                ('signal_word', models.CharField(blank=True, default='', help_text='Warning 或 Danger', max_length=20, verbose_name='信号词')),
                ('pictograms', models.TextField(blank=True, default='', help_text='JSON 数组，如 ["GHS07","GHS08"]', verbose_name='GHS 象征')),
                ('hazard_codes', models.TextField(blank=True, default='', help_text='JSON 数组，如 ["H302","H315"]', verbose_name='危险代码')),
                ('precaution_codes', models.TextField(blank=True, default='', help_text='JSON 数组，如 ["P261","P280"]', verbose_name='防范代码')),
                ('section_data', models.TextField(blank=True, default='', help_text='JSON 字符串，包含完整的 16 节 SDS 数据', verbose_name='16 节数据')),
                ('pdf_path', models.CharField(blank=True, default='', max_length=500, verbose_name='PDF 路径')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('product', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sds_revisions', to='commerce.product', verbose_name='产品')),
            ],
            options={
                'verbose_name': 'SDS 修订版',
                'verbose_name_plural': 'SDS 修订版',
                'db_table': 'sds_revision',
                'ordering': ['-revision_no'],
                'constraints': [models.UniqueConstraint(fields=('product', 'revision_no'), name='unique_product_sds_revision')],
            },
        ),
    ]
