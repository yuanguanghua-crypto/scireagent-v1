"""A-254 — SdsRevision 补 identity_conflict / identity_conflict_detail（身份矛盾闸门）。

背景（2026-11-18 S2 乙组）：
  产品的 CAS 与其 SMILES/InChI 可能指向**完全不同的化合物**。生产实测产品 5456：
  `cas=63-39-2`（ATP）+ `smiles=CCO`（乙醇）。旧实现 CAS 查不到就静默降级到 SMILES，
  生成的 SDS 描述的是乙醇，而产品标称是 ATP —— 而且这份 SDS 还能被审批发布成
  对外的合规文件。纪律：「身份未验证的匹配不得进入下游」。
  落地口径（用户 2026-11-18 拍板 (b)）：**允许存草稿、禁止审批发布**。
  草稿是研究员的工作区；发布才是对外出具合规文件。

为什么用「两个字段」而不是塞进 data_source_detail：
  审批闸门要读它做判定。让判定依赖解析自由文本（`PubChem CID \\d+`）是脆弱设计，
  一旦文案微调就静默失去保护。用结构化字段，闸门只读布尔值。

生产执行安全性：
  1. 仅 `AddField`：BooleanField(default=False) 与 TextField(default='') 都是
     PostgreSQL 11+ 的「仅改元数据」ADD COLUMN（常量 default），不重写表、不锁表。
  2. **不回填**：存量 SDS 一律视为「无矛盾」（default）。理由：矛盾与否取决于当时
     联网解析结果，事后无法在没有网络的情况下重放；且存量 revision 绝大多数已是
     draft。真要复核，用 `python manage.py detect_sds_identity_conflicts` 一条命令重扫。
  3. 回退：`migrate documents 0006` 直接删两列，无数据依赖。

★ 本文件为**手写迁移**，不是 `makemigrations` 生成。
  原因：当前 `manage.py makemigrations` 会连带生成一批 RemoveField `search_vector`
  与 RemoveIndex（product_search_gin / method_search_gin / protocol_name_objective_trgm
  / reference_search_gin）——即模型状态与 DB 的历史漂移。提交即连根拔掉全文检索索引。
  详见 MEMORY.md「2026-10-28 P1 地雷（勿踩）」。
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('documents', '0006_sdsrevision_status'),
    ]

    operations = [
        migrations.AddField(
            model_name='sdsrevision',
            name='identity_conflict',
            field=models.BooleanField(
                default=False,
                help_text='CAS 与 SMILES/InChI 解析出的 PubChem CID 不一致；置 True 时禁止审批发布',
                verbose_name='标识符身份矛盾',
            ),
        ),
        migrations.AddField(
            model_name='sdsrevision',
            name='identity_conflict_detail',
            field=models.TextField(
                blank=True,
                default='',
                help_text='如 CAS 63-39-2 → CID 5957；smiles CCO → CID 702',
                verbose_name='身份矛盾详情',
            ),
        ),
    ]
