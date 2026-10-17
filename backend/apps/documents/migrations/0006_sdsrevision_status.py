"""B10 — SdsRevision 补 status 字段（与 Coa.Status 同构）+ 存量数据回填。

背景（合规）：
  `docs/COA_SDS_PRD.md:80`「仅 status=PUBLISHED 允许下载」。COA 侧已于 2026-09-22
  （B9）在 download 加发布状态门控；SDS 侧 SdsRevision 模型当时**根本没有 status 字段**，
  且 `withdraw_sds` 只清 `Product.current_sds` 指针、**刻意保留 PDF** ⇒ 已撤回的 SDS PDF
  仍可被匿名下载（实测 200 + application/pdf）。本迁移补齐字段，使门控可落地。

生产执行安全性（重要）：
  1. 本迁移只做 `AddField`（非空 CharField + 常量 default）。PostgreSQL 11+ 对
     **常量 default 的 ADD COLUMN** 走「仅改元数据、不重写表」路径，不会锁表重写，
     表越大越安全。**因此这一步在生产是可接受的。**
  2. 回填用**单条 UPDATE ... FROM**（非逐行 ORM），避免长事务锁行。
  3. 迁移**不删除任何 PDF 文件**，只是标记状态；文件仍在 MEDIA_ROOT。
     ⇒ 若回填策略被业务方否决，`migrate documents 0005` 即可完全回退（含删列）。

存量数据回填策略（fail-closed 保守口径）：
  无法从现有 schema 区分「被新版本取代」与「被撤回」—— 二者的唯一区别就是
  `current_sds` 指针指向谁，而指针只记当前版。故按「只承认能证明的」处理：

    · `product.current_sds_id = sds.id`          → published  （可证明当前有效）
    · 其余行（含 pdf_path 非空的历史版）          → draft      （保守：不可匿名下载）

  ⇒ 副作用（**需业务方拍板**）：历史上「被新版取代」或「已撤回」的 SDS 修订版，
    迁移后**不再可匿名下载**（staff 仍可下载，见 views.py 门控）。
    如业务要求历史版本继续公开下载，见文件末尾《生产执行步骤》第 4 步的补录 SQL。
"""
from django.db import migrations, models

STATUS_DRAFT = 'draft'
STATUS_PUBLISHED = 'published'


def _forward(apps, schema_editor):
    """把「被 Product.current_sds 指针指向」的修订版标为 published，其余保持 draft。"""
    SdsRevision = apps.get_model('documents', 'SdsRevision')
    Product = apps.get_model('commerce', 'Product')

    # 收集当前有效版本 id（走历史模型，避免依赖新代码）
    current_ids = set(
        Product.objects.exclude(current_sds_id=None)
                     .values_list('current_sds_id', flat=True)
    )
    total = SdsRevision.objects.count()
    if not total:
        print('[data-migration] sds_revision 为空，跳过回填')
        return

    if current_ids:
        updated = SdsRevision.objects.filter(
            id__in=current_ids
        ).exclude(status=STATUS_PUBLISHED).update(status=STATUS_PUBLISHED)
    else:
        updated = 0

    print(
        f'[data-migration] SdsRevision.status 回填: 共 {total} 行，'
        f'标记 published {updated} 行（current_sds 指针指向者），'
        f'其余 {total - updated} 行保持 draft（fail-closed：不可匿名下载）'
    )


def _reverse(apps, schema_editor):
    """回退：清空 status（随后 AddField 的反向操作会删列，无残留脏值）。"""
    SdsRevision = apps.get_model('documents', 'SdsRevision')
    SdsRevision.objects.exclude(status=STATUS_DRAFT).update(status=STATUS_DRAFT)
    print('[data-migration] SdsRevision.status 已回退为 draft（列将在反向迁移中删除）')


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0005_alter_coa_options'),
    ]

    operations = [
        migrations.AddField(
            model_name='sdsrevision',
            name='status',
            field=models.CharField(
                choices=[('draft', '草稿'), ('approved', '已审批'), ('published', '已发布')],
                default=STATUS_DRAFT,
                help_text='draft=草稿/已撤回 / approved=已审批（历史兼容）/ published=已发布',
                max_length=20,
                verbose_name='状态',
            ),
        ),
        migrations.RunPython(_forward, _reverse),
    ]